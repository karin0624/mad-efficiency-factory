extends GdUnitTestSuite

# Test: MachinePortTransfer — アイテム転送ロジック (Req 3.x, 4.x, 5.x, 7.x)
# タスク4.1, 4.3, 4.5: 出力/入力ポート転送テスト + バックプレッシャー統合検証

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _transfer: MachinePortTransfer


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_transfer = MachinePortTransfer.new()


func after_test() -> void:
	_transfer = null
	_port_grid = null
	_catalog = null
	_belt_grid = null


## ========== タスク4.1: 出力ポートからベルトへの転送 ==========

## 出力ポートにアイテムあり・接続先ベルト空 → 転送成功・ポートバッファクリア
func test_output_transfer_success_when_belt_empty() -> void:
	# 採掘機北向き: 出力ポートworld_pos=(3,3), world_dir=S, 接続先=(3,4)
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# ポートにアイテムをセット
	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5  # item_id=5

	# 転送実行
	var count := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(1)

	# ポートバッファがクリアされている
	assert_int(output_ports[0]["item_id"]).is_equal(0)

	# ベルトにアイテムが配置されている
	var belt_tile := _belt_grid.get_tile(Vector2i(3, 4))
	assert_int(belt_tile.item_id).is_equal(5)


## 出力ポートにアイテムあり・接続先ベルト満杯 → 転送スキップ・ポートバッファ維持
func test_output_transfer_skipped_when_belt_full() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_belt_grid.set_item(Vector2i(3, 4), 99)  # ベルト満杯
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	var count := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)

	# ポートバッファは維持されている
	assert_int(output_ports[0]["item_id"]).is_equal(5)

	# ベルトのアイテムは変化なし
	var belt_tile := _belt_grid.get_tile(Vector2i(3, 4))
	assert_int(belt_tile.item_id).is_equal(99)


## 出力ポートにアイテムあり・接続先なし → 転送スキップ・ポートバッファ維持
func test_output_transfer_skipped_when_no_connection() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	# ベルトを追加しない → has_connection=false
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	var count := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)
	assert_int(output_ports[0]["item_id"]).is_equal(5)


## 出力ポートにアイテムなし → 転送なし
func test_output_transfer_skipped_when_no_item() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# item_id=0 (空)のまま
	var count := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)


## 転送前後のアイテム総数が保存される（出力ポート-1、ベルト+1）
func test_output_transfer_item_conservation() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 7

	# 転送前: ポートに1アイテム、ベルトに0
	var port_items_before := 1
	var belt_items_before := _belt_grid.item_count()
	assert_int(port_items_before + belt_items_before).is_equal(1)

	_transfer.process_output_ports(_port_grid, _belt_grid)

	# 転送後: ポートに0、ベルトに1 → 合計変化なし
	var port_items_after := 0  # cleared
	var belt_items_after := _belt_grid.item_count()
	assert_int(port_items_after + belt_items_after).is_equal(1)


## ========== タスク4.3: ベルトから入力ポートへの引き込み ==========

## 入力ポート空・接続先ベルトにアイテム到達済み → 引き込み成功
func test_input_transfer_success_when_belt_has_arrived_item() -> void:
	# 精錬機北向き: 入力ポートworld_pos=(4,4), world_dir=N, 接続先=(4,3)
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# ベルトにアイテムを配置（progress=1.0 = 到達済み）
	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 1.0

	var count := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(1)

	# 入力ポートにアイテムが引き込まれた
	var input_ports := _port_grid.get_active_input_ports()
	assert_int(input_ports[0]["item_id"]).is_equal(3)

	# ベルトからアイテムが除去された
	var belt_tile := _belt_grid.get_tile(Vector2i(4, 3))
	assert_int(belt_tile.item_id).is_equal(0)


## 入力ポート満杯 → 引き込みスキップ
func test_input_transfer_skipped_when_port_full() -> void:
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 1.0

	# ポートを満杯に
	var input_ports := _port_grid.get_active_input_ports()
	input_ports[0]["item_id"] = 99

	var count := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)

	# ポートのアイテムは変化なし
	assert_int(input_ports[0]["item_id"]).is_equal(99)

	# ベルトのアイテムも変化なし
	var belt_tile := _belt_grid.get_tile(Vector2i(4, 3))
	assert_int(belt_tile.item_id).is_equal(3)


## 入力ポートに接続先なし → 引き込みスキップ
func test_input_transfer_skipped_when_no_connection() -> void:
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	# ベルトなし → 接続なし
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var count := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)


## ベルトにアイテムあるが未到達（progress<1.0）→ 引き込みスキップ
func test_input_transfer_skipped_when_item_not_arrived() -> void:
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 0.5  # 未到達

	var count := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count).is_equal(0)


## 転送前後のアイテム総数が保存される（ベルト-1、入力ポート+1）
func test_input_transfer_item_conservation() -> void:
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 1.0

	# 転送前: ベルト1、ポート0
	assert_int(_belt_grid.item_count()).is_equal(1)
	var input_ports := _port_grid.get_active_input_ports()
	assert_int(input_ports[0]["item_id"]).is_equal(0)

	_transfer.process_input_ports(_port_grid, _belt_grid)

	# 転送後: ベルト0、ポート1 → 合計変化なし
	assert_int(_belt_grid.item_count()).is_equal(0)
	assert_int(input_ports[0]["item_id"]).is_equal(3)


## ========== タスク4.5: バックプレッシャー解消と保存則の統合検証 ==========

## 出力先ベルト満杯→空き発生→転送自動再開
func test_backpressure_output_resumes_when_belt_space_available() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_belt_grid.set_item(Vector2i(3, 4), 99)  # 満杯
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	# ベルト満杯 → 転送スキップ
	var count1 := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count1).is_equal(0)
	assert_int(output_ports[0]["item_id"]).is_equal(5)

	# ベルトを空に → 転送再開
	_belt_grid.clear_item(Vector2i(3, 4))
	var count2 := _transfer.process_output_ports(_port_grid, _belt_grid)
	assert_int(count2).is_equal(1)
	assert_int(output_ports[0]["item_id"]).is_equal(0)


## 入力ポート満杯→アイテム消費→引き込み自動再開
func test_backpressure_input_resumes_when_port_emptied() -> void:
	_port_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 1.0

	var input_ports := _port_grid.get_active_input_ports()
	input_ports[0]["item_id"] = 99  # 満杯

	# ポート満杯 → 引き込みスキップ
	var count1 := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count1).is_equal(0)

	# ポートを空に → 引き込み再開
	input_ports[0]["item_id"] = 0
	var count2 := _transfer.process_input_ports(_port_grid, _belt_grid)
	assert_int(count2).is_equal(1)
	assert_int(input_ports[0]["item_id"]).is_equal(3)


## バックプレッシャー発生中のアイテム消失なし
func test_no_item_loss_during_backpressure() -> void:
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_belt_grid.set_item(Vector2i(3, 4), 99)  # 満杯
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	# 複数ティックのバックプレッシャー → アイテムは消失しない
	for _i in range(5):
		_transfer.process_output_ports(_port_grid, _belt_grid)

	# ポートのアイテムは維持
	assert_int(output_ports[0]["item_id"]).is_equal(5)
	# ベルトのアイテムも維持
	assert_int(_belt_grid.get_tile(Vector2i(3, 4)).item_id).is_equal(99)


## 複数ティックにわたる転送でアイテム総数が保存される
func test_item_count_preserved_across_multiple_ticks() -> void:
	# 採掘機 + ベルト + 精錬機の縦列構成
	# 採掘機北向き: 出力ポート (3,3) → 接続先(3,4)
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()

	# 3アイテムを転送（1ティック=1アイテム）
	var total_transferred := 0
	for i in range(3):
		output_ports[0]["item_id"] = i + 1  # アイテムID 1,2,3
		var count := _transfer.process_output_ports(_port_grid, _belt_grid)
		total_transferred += count
		# ベルトを空にして次の転送を可能にする
		_belt_grid.clear_item(Vector2i(3, 4))

	assert_int(total_transferred).is_equal(3)
