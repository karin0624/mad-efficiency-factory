extends GdUnitTestSuite

# Test: MachinePortTransfer — 出力ポートからベルトへの転送 (Req 3.1, 3.2, 3.3, 3.4, 5.2, 7.1, 7.3)

## タスク4.1: 出力ポートからベルトへの転送テスト

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _sut: MachinePortTransfer


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_sut = MachinePortTransfer.new()

	# 採掘機(ID=1, 1x1)を (2,2) 北向きで配置: 出力ポート world_pos=(2,2), dir=S
	# 接続先ベルト = (2,3)
	_port_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)


func after_test() -> void:
	_sut = null
	_port_grid = null
	_belt_grid = null
	_catalog = null


# --- 出力転送テスト ---

func test_output_transfer_succeeds_when_belt_empty() -> void:
	# 出力ポートにアイテムあり・接続先ベルト空 → 転送成功
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1  # 鉄鉱石をセット
	var transferred := _sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(transferred).is_equal(1)


func test_output_transfer_clears_port_buffer() -> void:
	# 転送成功時にポートバッファがクリアされる
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1
	_sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(port["item_id"]).is_equal(0)


func test_output_transfer_adds_item_to_belt() -> void:
	# 転送成功時にベルトにアイテムが追加される
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 5
	_sut.process_output_ports(_port_grid, _belt_grid)
	var belt_tile := _belt_grid.get_tile(Vector2i(2, 3))
	assert_int(belt_tile.item_id).is_equal(5)


func test_output_transfer_skipped_when_belt_full() -> void:
	# 出力ポートにアイテムあり・接続先ベルト満杯 → 転送スキップ
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1
	_belt_grid.set_item(Vector2i(2, 3), 99)  # ベルト満杯
	var transferred := _sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(transferred).is_equal(0)


func test_output_port_buffer_maintained_when_belt_full() -> void:
	# ベルト満杯時にポートバッファが維持される
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1
	_belt_grid.set_item(Vector2i(2, 3), 99)
	_sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(port["item_id"]).is_equal(1)


func test_output_transfer_skipped_when_no_connection() -> void:
	# 出力ポートにアイテムあり・接続先なし → 転送スキップ
	var catalog2 := MachinePortCatalog.create_default()
	var port_grid2 := MachinePortGrid.new(catalog2)
	var belt_grid2 := BeltGrid.new()
	# ベルトなしで登録
	port_grid2.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	port_grid2.rebuild_connections_if_dirty(belt_grid2)
	var output_ports := port_grid2.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 1
	var transferred := _sut.process_output_ports(port_grid2, belt_grid2)
	assert_int(transferred).is_equal(0)
	assert_int(port["item_id"]).is_equal(1)


func test_output_transfer_when_port_empty_does_nothing() -> void:
	# 出力ポートが空の場合は何もしない（転送0件）
	var transferred := _sut.process_output_ports(_port_grid, _belt_grid)
	assert_int(transferred).is_equal(0)


func test_item_count_conserved_on_transfer() -> void:
	# 転送前後のアイテム総数が保存される（出力ポート-1、ベルト+1）
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	port["item_id"] = 3
	var belt_items_before := _belt_grid.item_count()
	_sut.process_output_ports(_port_grid, _belt_grid)
	var belt_items_after := _belt_grid.item_count()
	assert_int(port["item_id"]).is_equal(0)  # ポート空
	assert_int(belt_items_after).is_equal(belt_items_before + 1)
