extends GdUnitTestSuite

# Test: MachinePortTransfer — ベルトから入力ポートへの引き込み (Req 4.1, 4.2, 4.3, 4.4, 5.1, 7.2, 7.3)

## タスク4.3: ベルトから入力ポートへの引き込みテスト

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _sut: MachinePortTransfer


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_sut = MachinePortTransfer.new()

	# 精錬機(ID=2)を (2,2) 北向きで配置
	# 入力ポート: world_pos=(2,2), dir=N → 接続先=(2,1)
	_port_grid.register_machine(1, 2, Vector2i(2, 2), Enums.Direction.N)
	# ベルトを接続先 (2,1) に配置（方向=N で方向互換）
	_belt_grid.add_tile(Vector2i(2, 1), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)


func after_test() -> void:
	_sut = null
	_port_grid = null
	_belt_grid = null
	_catalog = null


# --- 引き込みテスト ---

func test_input_pull_succeeds_when_belt_has_deliverable_item() -> void:
	# 入力ポート空・ベルトにアイテム到達済み → 引き込み成功
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(1)
	belt_tile.progress = 1.0  # 到達済み

	var pulled := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(pulled).is_equal(1)


func test_input_pull_removes_item_from_belt() -> void:
	# 引き込み後にベルトのアイテムが除去される
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(1)
	belt_tile.progress = 1.0

	_sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(belt_tile.item_id).is_equal(0)


func test_input_pull_sets_port_buffer() -> void:
	# 引き込み後にポートバッファにアイテムがセットされる
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(7)
	belt_tile.progress = 1.0

	_sut.process_input_ports(_port_grid, _belt_grid)
	var input_ports := _port_grid.get_active_input_ports()
	assert_int(input_ports[0]["item_id"]).is_equal(7)


func test_input_pull_skipped_when_port_full() -> void:
	# 入力ポート満杯 → 引き込みスキップ
	var input_ports := _port_grid.get_active_input_ports()
	input_ports[0]["item_id"] = 99  # ポート満杯

	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(1)
	belt_tile.progress = 1.0

	var pulled := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(pulled).is_equal(0)
	assert_int(belt_tile.item_id).is_equal(1)  # ベルトにアイテムが残る


func test_input_pull_skipped_when_no_connection() -> void:
	# 入力ポートに接続先なし → 引き込みスキップ
	var catalog2 := MachinePortCatalog.create_default()
	var port_grid2 := MachinePortGrid.new(catalog2)
	var belt_grid2 := BeltGrid.new()
	port_grid2.register_machine(1, 2, Vector2i(2, 2), Enums.Direction.N)
	port_grid2.rebuild_connections_if_dirty(belt_grid2)  # ベルトなし → 接続なし
	var input_ports := port_grid2.get_active_input_ports()
	assert_bool(input_ports[0]["has_connection"]).is_false()

	var pulled := _sut.process_input_ports(port_grid2, belt_grid2)
	assert_int(pulled).is_equal(0)


func test_input_pull_skipped_when_belt_item_not_delivered() -> void:
	# ベルトアイテムが未到達（progress < 1.0）→ 引き込みスキップ
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(1)
	belt_tile.progress = 0.5  # まだ進行中

	var pulled := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(pulled).is_equal(0)
	assert_int(belt_tile.item_id).is_equal(1)  # ベルトにアイテムが残る


func test_input_pull_skipped_when_belt_empty() -> void:
	# ベルトにアイテムなし → 引き込みスキップ
	var pulled := _sut.process_input_ports(_port_grid, _belt_grid)
	assert_int(pulled).is_equal(0)


func test_item_count_conserved_on_input_pull() -> void:
	# 転送前後のアイテム総数が保存される（ベルト-1、入力ポート+1）
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 1))
	belt_tile.set_item(3)
	belt_tile.progress = 1.0

	var belt_items_before := _belt_grid.item_count()
	_sut.process_input_ports(_port_grid, _belt_grid)
	var belt_items_after := _belt_grid.item_count()

	assert_int(belt_items_after).is_equal(belt_items_before - 1)
	var input_ports := _port_grid.get_active_input_ports()
	assert_int(input_ports[0]["item_id"]).is_equal(3)
