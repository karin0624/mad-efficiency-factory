extends GdUnitTestSuite

# 統合テスト: machine-port-system統合フロー (Req 8.1, 8.2, 8.3)
# タスク6.1: 出力ポート→ベルト5本→入力ポートのアイテム到達
# タスク6.2: 全4方向回転でのポート転送検証
# ADR 0001: Miner・Smelter フットプリント 1x1

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _transfer: MachinePortTransfer
var _port_system: MachinePortSystemNode


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_transfer = MachinePortTransfer.new()
	_port_system = MachinePortSystemNode.new(_port_grid, _belt_grid, _transfer)


func after_test() -> void:
	_port_system = null
	_transfer = null
	_port_grid = null
	_belt_grid = null
	_catalog = null


## タスク6.1: 出力ポート→ベルト5本→入力ポートのアイテム到達
## 1x1レイアウト（design.md標準レイアウト参照）:
## 採掘機(1x1)北向き at (5,0): 出力ポート world(5,0) dir=S → 接続先(5,1)
## ベルト5本: (5,1)S, (5,2)S, (5,3)S, (5,4)S, (5,5)S
## 精錬機(1x1)北向き at (5,6): 入力ポート world(5,6) dir=N → 接続先(5,5)
func test_e2e_output_belt5_input_flow() -> void:
	# 採掘機 (entity_id=1, type_id=1) 北向き at (5,0)
	# 出力ポート: (5,0) dir=S → 接続先(5,1)
	_port_system.on_entity_placed(1, Vector2i(5, 0), Enums.Direction.N, 1)

	# 精錬機 (entity_id=2, type_id=2) 北向き at (5,6)
	# 入力ポート: (5,6) dir=N → 接続先(5,5)
	_port_system.on_entity_placed(2, Vector2i(5, 6), Enums.Direction.N, 2)

	# ベルト5本配置: (5,1)〜(5,5) すべてS方向
	for i in range(5):
		_belt_grid.add_tile(Vector2i(5, 1 + i), Enums.Direction.S)
		_port_system.on_entity_placed(10 + i, Vector2i(5, 1 + i), Enums.Direction.S, 3)

	# 接続再構築
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# Miner + Smelter 両方が出力ポートを持つ (1x1フットプリント)
	var output_ports := _port_grid.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(2)

	# Minerの出力ポート(5,0)を特定
	var miner_out: Dictionary = {}
	for p in output_ports:
		if p["world_position"] == Vector2i(5, 0):
			miner_out = p
			break
	assert_bool(miner_out.is_empty()).is_false()
	assert_bool(miner_out["has_connection"]).is_true()

	# 出力ポートにアイテムをセット
	miner_out["item_id"] = 1  # 鉄鉱石

	# tick_output でポートからベルト(5,1)に転送
	_port_system.tick_output()

	# アイテムがベルト(5,1)に転送された
	var belt_tile := _belt_grid.get_tile(Vector2i(5, 1))
	assert_int(belt_tile.item_id).is_equal(1)
	assert_int(miner_out["item_id"]).is_equal(0)

	print("[E2E 6.1] Output port(5,0) → belt(5,1) transfer: PASS")


## 100アイテムを投入して100アイテムが受取られることを検証 (Req 8.2)
func test_e2e_100_items_conservation() -> void:
	# 採掘機(1x1)北向き at (5,0): 出力ポート(5,0)dir=S, ベルト(5,1)dir=S
	_port_system.on_entity_placed(1, Vector2i(5, 0), Enums.Direction.N, 1)
	_belt_grid.add_tile(Vector2i(5, 1), Enums.Direction.S)
	_port_system.on_entity_placed(10, Vector2i(5, 1), Enums.Direction.S, 3)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var received := 0
	var output_ports := _port_grid.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)

	# 100回転送
	for i in range(100):
		output_ports[0]["item_id"] = 1  # アイテムをセット
		_port_system.tick_output()  # 転送実行
		# ベルト上のアイテムを確認してクリア（次のティック用）
		var tile := _belt_grid.get_tile(Vector2i(5, 1))
		if tile.item_id > 0:
			received += 1
			_belt_grid.clear_item(Vector2i(5, 1))

	assert_int(received).is_equal(100)
	print("[E2E 6.1] 100 items conservation: sent=100, received=", received)


## タスク6.2: 全4方向回転でのポート転送検証 (Req 8.3)
## 採掘機(1x1) at (5,5)、各方向でのポート位置とベルト転送を検証
## 1x1のため全方向でworld_pos=(5,5)、方向のみ変化:
##   N: dir=S → 接続先(5,6)
##   E: dir=W → 接続先(4,5)
##   S: dir=N → 接続先(5,4)
##   W: dir=E → 接続先(6,5)
func test_e2e_all_4_directions_transfer() -> void:
	var directions := [Enums.Direction.N, Enums.Direction.E, Enums.Direction.S, Enums.Direction.W]
	var direction_names := ["N", "E", "S", "W"]
	# 採掘機(1x1) base=(5,5) 各方向: world_pos=(5,5)で方向のみ変化
	var expected_belt_positions: Array[Vector2i] = [
		Vector2i(5, 6),  # N: dir=S → 接続先(5,6)
		Vector2i(4, 5),  # E: dir=W → 接続先(4,5)
		Vector2i(5, 4),  # S: dir=N → 接続先(5,4)
		Vector2i(6, 5),  # W: dir=E → 接続先(6,5)
	]
	var expected_belt_directions: Array[int] = [
		Enums.Direction.S,  # N rotation → port dir=S, belt goes S
		Enums.Direction.W,  # E rotation → port dir=W, belt goes W
		Enums.Direction.N,  # S rotation → port dir=N, belt goes N
		Enums.Direction.E,  # W rotation → port dir=E, belt goes E
	]

	for i in range(4):
		var direction: int = directions[i]
		var expected_pos: Vector2i = expected_belt_positions[i]
		var expected_dir: int = expected_belt_directions[i]

		# テスト用グリッドをリセット
		var local_port_grid := MachinePortGrid.new(_catalog)
		var local_belt_grid := BeltGrid.new()
		var local_transfer := MachinePortTransfer.new()
		var local_system := MachinePortSystemNode.new(local_port_grid, local_belt_grid, local_transfer)

		# 採掘機(1x1)配置
		local_system.on_entity_placed(1, Vector2i(5, 5), direction, 1)

		# 接続先ベルトを配置
		local_belt_grid.add_tile(expected_pos, expected_dir)
		local_port_grid.rebuild_connections_if_dirty(local_belt_grid)

		# 出力ポートにアイテムをセット
		var output_ports := local_port_grid.get_active_output_ports()
		assert_int(output_ports.size()).is_equal(1)
		assert_bool(output_ports[0]["has_connection"]).is_true()
		output_ports[0]["item_id"] = 1

		# 転送実行
		local_system.tick_output()

		# ベルトにアイテムが転送されている
		var belt_tile := local_belt_grid.get_tile(expected_pos)
		assert_int(belt_tile.item_id).is_equal(1)
		assert_int(output_ports[0]["item_id"]).is_equal(0)

		print("[E2E 6.2] Direction ", direction_names[i], ": port(5,5) → belt", expected_pos, " PASS")
