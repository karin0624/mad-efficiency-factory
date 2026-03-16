extends GdUnitTestSuite

# Test: MachinePortSystemNode — ティック処理と配置/撤去イベントブリッジ (Req 6.1, 6.2, 6.3, 6.4)
# タスク5.1: MachinePortSystemNodeのコアロジック検証
# L1テスト: BeltTransportSystemと同様にon_entity_placed/on_entity_removedコールバックでテスト

var _catalog: MachinePortCatalog
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _transfer: MachinePortTransfer
var _sut: MachinePortSystemNode


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_port_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()
	_transfer = MachinePortTransfer.new()
	_sut = MachinePortSystemNode.new(_port_grid, _belt_grid, _transfer)


func after_test() -> void:
	_sut = null
	_transfer = null
	_port_grid = null
	_belt_grid = null
	_catalog = null


## entity_placedで機械が正しくポートグリッドに登録される（採掘機 type_id=1）
func test_entity_placed_registers_machine_ports() -> void:
	# 機械エンティティ（type_id=1 = Miner）
	_sut.on_entity_placed(1, Vector2i(2, 2), Enums.Direction.N, 1)
	var output_ports := _port_grid.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)


## entity_placedで機械が正しいworld座標でポートが生成される
func test_entity_placed_machine_port_world_position() -> void:
	_sut.on_entity_placed(1, Vector2i(2, 2), Enums.Direction.N, 1)
	var output_ports := _port_grid.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	# 採掘機(1x1)北向き: base(2,2) + offset(0,0) = (2,2), dir=S
	assert_that(port["world_position"]).is_equal(Vector2i(2, 2))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.S)


## entity_removedで機械が正しくポートグリッドから解除される
func test_entity_removed_unregisters_machine_ports() -> void:
	_sut.on_entity_placed(1, Vector2i(2, 2), Enums.Direction.N, 1)
	assert_int(_port_grid.get_active_output_ports().size()).is_equal(1)
	_sut.on_entity_removed(1, Vector2i(2, 2), 1)
	assert_int(_port_grid.get_active_output_ports().size()).is_equal(0)


## 非機械エンティティ（ベルト type_id=3）の配置でポート登録が行われない
func test_belt_entity_placed_does_not_register_ports() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)  # Belt
	assert_int(_port_grid.get_active_output_ports().size()).is_equal(0)
	assert_int(_port_grid.get_active_input_ports().size()).is_equal(0)


## 非機械エンティティ（ベルト）の配置でdirty flagがセットされる
func test_belt_entity_placed_sets_dirty_flag() -> void:
	_port_grid.rebuild_connections_if_dirty(_belt_grid)  # dirty=false
	assert_bool(_port_grid.is_dirty()).is_false()
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)  # Belt
	assert_bool(_port_grid.is_dirty()).is_true()


## 非機械エンティティ（ベルト）の撤去でdirty flagがセットされる
func test_belt_entity_removed_sets_dirty_flag() -> void:
	_port_grid.rebuild_connections_if_dirty(_belt_grid)  # dirty=false
	assert_bool(_port_grid.is_dirty()).is_false()
	_sut.on_entity_removed(1, Vector2i(5, 5), 3)  # Belt
	assert_bool(_port_grid.is_dirty()).is_true()


## tick_outputで出力ポートからベルトへ転送が行われる
func test_tick_output_transfers_from_output_port_to_belt() -> void:
	# 採掘機登録 + ベルト配置
	_sut.on_entity_placed(1, Vector2i(2, 2), Enums.Direction.N, 1)  # Miner
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# 出力ポートにアイテムをセット
	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	_sut.tick_output()

	# ポートがクリアされてベルトにアイテムが入る
	assert_int(output_ports[0]["item_id"]).is_equal(0)
	assert_int(_belt_grid.get_tile(Vector2i(2, 3)).item_id).is_equal(5)


## tick_inputでベルトから入力ポートへ引き込みが行われる
func test_tick_input_pulls_from_belt_to_input_port() -> void:
	# 精錬機登録 + ベルト配置（接続先 = (4,3), ベルト方向=N）
	_sut.on_entity_placed(2, Vector2i(4, 4), Enums.Direction.N, 2)  # Smelter
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_port_grid.rebuild_connections_if_dirty(_belt_grid)

	# ベルトにアイテム配置（到達済み）
	_belt_grid.set_item(Vector2i(4, 3), 3)
	_belt_grid.get_tile(Vector2i(4, 3)).progress = 1.0

	_sut.tick_input()

	# 入力ポートにアイテムが引き込まれた
	var input_ports := _port_grid.get_active_input_ports()
	assert_int(input_ports[0]["item_id"]).is_equal(3)
	assert_int(_belt_grid.get_tile(Vector2i(4, 3)).item_id).is_equal(0)


## tick_outputの前にrebuild_connectionsが実行される（dirty再構築）
func test_tick_output_rebuilds_connections_if_dirty() -> void:
	_sut.on_entity_placed(1, Vector2i(2, 2), Enums.Direction.N, 1)  # Miner → dirty=true
	# ベルト追加（dirty flagは既にtrueなので再構築が行われる）
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)

	# tick_outputが接続再構築を行い、転送が成功するはず
	var output_ports := _port_grid.get_active_output_ports()
	output_ports[0]["item_id"] = 5

	_sut.tick_output()

	# dirty flagがtrueのままでもrebuildが行われて転送される
	assert_int(output_ports[0]["item_id"]).is_equal(0)
	assert_int(_belt_grid.get_tile(Vector2i(2, 3)).item_id).is_equal(5)
