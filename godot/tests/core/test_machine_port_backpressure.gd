extends GdUnitTestSuite

# Test: MachinePortTransfer — バックプレッシャー解消と保存則の統合検証
# (Req 5.3, 5.4, 5.5, 7.1, 7.2, 7.3, 7.4)

## タスク4.5: バックプレッシャー解消と保存則の統合テスト

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _sut: MachinePortTransfer


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_sut = MachinePortTransfer.new()


func after_test() -> void:
	_sut = null
	_port_grid = null
	_belt_grid = null
	_catalog = null


# --- 出力ポートバックプレッシャーテスト ---

func test_output_backpressure_resumes_when_belt_space_available() -> void:
	# 出力先ベルト満杯→空き発生→転送自動再開
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1
	_belt_grid.set_item(Vector2i(3, 4), 99)  # ベルト満杯

	# 転送スキップ（バックプレッシャー）
	var result1 := _sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(result1).is_equal(0)
	assert_int(port["item_id"]).is_equal(1)  # ポートにアイテムが残る

	# ベルトを空に → 転送自動再開
	_belt_grid.clear_item(Vector2i(3, 4))
	var result2 := _sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(result2).is_equal(1)
	assert_int(port["item_id"]).is_equal(0)  # ポートが空に


func test_output_backpressure_no_item_loss() -> void:
	# バックプレッシャー発生中のアイテム消失なし
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 5
	_belt_grid.set_item(Vector2i(3, 4), 99)  # ベルト満杯

	# 複数ティックにわたる転送試行でもアイテムが消失しない
	for _i in range(5):
		_sut.process_output_ports(_port_grid, _belt_grid)

	assert_int(port["item_id"]).is_equal(5)  # アイテムが保持されている


# --- 入力ポートバックプレッシャーテスト ---

func test_input_backpressure_resumes_when_port_consumed() -> void:
	# 入力ポート満杯→アイテム消費→引き込み自動再開
	_port_grid.register_machine(1, 2, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(2, 1), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var input_ports := _port_grid.get_active_input_ports()
	var port: Dictionary = input_ports[0]
	port["item_id"] = 99  # ポート満杯

	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(1)
	belt_tile.progress = 1.0

	# 引き込みスキップ（ポート満杯）
	var result1 := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(result1).is_equal(0)
	assert_int(belt_tile.item_id).is_equal(1)  # ベルトにアイテムが残る

	# ポートを空に → 引き込み自動再開
	port["item_id"] = 0
	var result2 := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(result2).is_equal(1)
	assert_int(port["item_id"]).is_equal(1)  # ポートにアイテムが入った


func test_input_backpressure_no_item_loss() -> void:
	# バックプレッシャー中のアイテム消失なし
	_port_grid.register_machine(1, 2, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(2, 1), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var input_ports := _port_grid.get_active_input_ports()
	var port: Dictionary = input_ports[0]
	port["item_id"] = 99  # ポート満杯

	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(3)
	belt_tile.progress = 1.0

	# 複数ティックにわたる引き込み試行でもアイテムが消失しない
	for _i in range(5):
		_sut.process_input_ports(_port_grid, _belt_grid)

	assert_int(belt_tile.item_id).is_equal(3)  # ベルトにアイテムが残る


# --- 複数ティックにわたる出力→入力の連続転送テスト ---

func test_multi_tick_output_to_input_item_conservation() -> void:
	# 複数ティックにわたる出力→入力の連続転送でアイテム総数が保存される
	# セットアップ: 採掘機(出力) → ベルト(消費専用) → 各ティックで消費
	# Miner@(0,0): 出力ポート world_pos=(1,1), dir=S → 接続先=(1,2)

	_port_grid.register_machine(1, 1, Vector2i(0, 0), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(1, 2), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	var out_port: Dictionary = output_ports[0]

	# アイテムを5回投入・転送・ベルトをクリアのサイクルで総数保存を確認
	var total_items_in := 0
	var total_items_out := 0

	for _i in range(5):
		out_port["item_id"] = 1
		total_items_in += 1
		var transferred := _sut.process_output_ports(_port_grid, _belt_grid)
		total_items_out += transferred
		# ベルトをクリアして次のティックに備える（保存則の検証）
		_belt_grid.clear_item(Vector2i(1, 2))

	# 全5回の転送が成功し、アイテム総数が保存されている
	assert_int(total_items_out).is_equal(total_items_in)


func test_no_item_duplication_on_transfer() -> void:
	# いかなる状態でもアイテムの消失・重複が発生しないことを検証
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(3, 4), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1

	# 1回目の転送
	_sut.process_output_ports(_port_grid, _belt_grid)

	# ポート空、ベルトにアイテム1個
	assert_int(port["item_id"]).is_equal(0)
	assert_int(_belt_grid.item_count()).is_equal(1)

	# 2回目の転送（ポート空なので何もしない）
	_sut.process_output_ports(_port_grid, _belt_grid)

	# 重複なし: ベルトはまだ1個
	assert_int(_belt_grid.item_count()).is_equal(1)
