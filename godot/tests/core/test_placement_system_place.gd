extends GdUnitTestSuite

## PlacementSystem.place() のユニットテスト (Layer 1)
## エンティティ配置ロジックが正しく機能することを検証する

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_system = PlacementSystem.new(_grid, _registry)


func after_test() -> void:
	_system = null
	_registry = null
	_grid = null


func test_place_1x1_entity_succeeds_and_returns_positive_id() -> void:
	# Belt(ID=3)は1x1
	var entity_id := _system.place(3, Vector2i(5, 5), Enums.Direction.N)
	assert_int(entity_id).is_greater(0)


func test_place_1x1_entity_occupies_the_cell() -> void:
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	assert_bool(_grid.is_occupied(Vector2i(5, 5))).is_true()


func test_place_2x2_entity_occupies_all_four_cells() -> void:
	# Miner(ID=1)は2x2
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	# (0,0), (1,0), (0,1), (1,1)の4セルすべてが占有されること
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(1, 1))).is_true()


func test_place_records_placed_entity() -> void:
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	var entity := _system.get_placed_entity(entity_id)
	assert_object(entity).is_not_null()
	assert_int(entity.entity_id).is_equal(entity_id)
	assert_int(entity.entity_type_id).is_equal(1)
	assert_that(entity.base_cell).is_equal(Vector2i(0, 0))


func test_place_on_occupied_cell_returns_zero() -> void:
	# まず配置してから、同じ場所に再配置を試みる
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	var result := _system.place(3, Vector2i(5, 5), Enums.Direction.N)
	assert_int(result).is_equal(0)


func test_place_on_occupied_cell_does_not_change_grid() -> void:
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	# 既に占有されている(1,1)のセルに1x1を置こうとする
	var grid_entity_before := _grid.get_occupying_entity(Vector2i(1, 1))
	_system.place(3, Vector2i(1, 1), Enums.Direction.N)
	var grid_entity_after := _grid.get_occupying_entity(Vector2i(1, 1))
	# グリッド状態は変わらない
	assert_int(grid_entity_before).is_equal(grid_entity_after)


func test_place_out_of_bounds_returns_zero() -> void:
	# Req 2.4: 基準セル(63,63)に2x2エンティティは範囲外
	var result := _system.place(1, Vector2i(63, 63), Enums.Direction.N)
	assert_int(result).is_equal(0)


func test_place_out_of_bounds_does_not_modify_grid() -> void:
	_system.place(1, Vector2i(63, 63), Enums.Direction.N)
	# 64x64グリッドの範囲外への配置でグリッドに変化はない
	assert_bool(_grid.is_occupied(Vector2i(63, 63))).is_false()


func test_place_entity_ids_are_unique_and_increasing() -> void:
	var id1 := _system.place(3, Vector2i(0, 0), Enums.Direction.N)
	var id2 := _system.place(3, Vector2i(1, 0), Enums.Direction.N)
	var id3 := _system.place(3, Vector2i(2, 0), Enums.Direction.N)
	assert_int(id1).is_greater(0)
	assert_int(id2).is_greater(id1)
	assert_int(id3).is_greater(id2)


func test_place_invalid_entity_type_id_returns_zero() -> void:
	var result := _system.place(999, Vector2i(0, 0), Enums.Direction.N)
	assert_int(result).is_equal(0)


func test_place_returns_immediately_no_delay() -> void:
	# 配置は即座に完了する（戻り値が返ること）
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	# IDが正の整数であることで即座に完了したことを確認
	assert_int(entity_id).is_greater(0)


func test_place_failed_does_not_leave_partial_occupation() -> void:
	# 2x2エンティティで一部が占有済みの場合、部分的な占有が発生しないことを確認
	_grid.occupy_rect(Vector2i(1, 1), Vector2i(1, 1), 999)
	# (0,0)にMiner(2x2)を配置しようとする→(1,1)が占有済みで失敗
	var result := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	assert_int(result).is_equal(0)
	# (0,0), (1,0), (0,1)は未占有のまま
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_false()
