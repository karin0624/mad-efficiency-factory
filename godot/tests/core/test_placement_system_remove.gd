extends GdUnitTestSuite

## PlacementSystem.remove() のユニットテスト (Layer 1)
## エンティティ撤去ロジックが正しく機能することを検証する

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


func test_remove_1x1_entity_returns_true() -> void:
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	var result := _system.remove(Vector2i(5, 5))
	assert_bool(result).is_true()


func test_remove_1x1_entity_frees_the_cell() -> void:
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	_system.remove(Vector2i(5, 5))
	assert_bool(_grid.is_occupied(Vector2i(5, 5))).is_false()


func test_remove_2x2_entity_by_origin_cell() -> void:
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	var result := _system.remove(Vector2i(0, 0))
	assert_bool(result).is_true()


func test_remove_2x2_entity_frees_all_four_cells() -> void:
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	_system.remove(Vector2i(0, 0))
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 1))).is_false()


func test_remove_2x2_entity_by_non_origin_cell() -> void:
	# Req 4.2: 2x2エンティティのいずれか1セル指定で全体を撤去
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	# (1,1)（右下）を指定して撤去
	var result := _system.remove(Vector2i(1, 1))
	assert_bool(result).is_true()
	# 全4セルが解放される
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 1))).is_false()


func test_remove_2x2_entity_by_top_right_cell() -> void:
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	# (1,0)（右上）を指定して撤去
	var result := _system.remove(Vector2i(1, 0))
	assert_bool(result).is_true()
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_false()


func test_remove_deletes_placed_entity_record() -> void:
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	_system.remove(Vector2i(0, 0))
	var entity := _system.get_placed_entity(entity_id)
	assert_object(entity).is_null()


func test_remove_empty_cell_returns_false() -> void:
	# Req 4.4: 指定されたセルにエンティティが存在しない場合は無視
	var result := _system.remove(Vector2i(10, 10))
	assert_bool(result).is_false()


func test_remove_empty_cell_does_not_change_grid() -> void:
	# 空セルへの撤去でグリッド状態は変わらない
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	_system.remove(Vector2i(10, 10))
	# (5,5)はまだ占有されている
	assert_bool(_grid.is_occupied(Vector2i(5, 5))).is_true()


func test_place_remove_replace_cycle_succeeds() -> void:
	# Req: 配置→撤去→同位置への再配置が成功すること
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	_system.remove(Vector2i(5, 5))
	var second_id := _system.place(3, Vector2i(5, 5), Enums.Direction.N)
	assert_int(second_id).is_greater(0)
	assert_bool(_grid.is_occupied(Vector2i(5, 5))).is_true()


func test_remove_immediately_completes() -> void:
	# Req 4.6: 撤去操作は即座に完了する
	_system.place(1, Vector2i(0, 0), Enums.Direction.N)
	var result := _system.remove(Vector2i(0, 0))
	# 即座に完了: boolが返ること
	assert_bool(result).is_true()


func test_remove_entity_can_always_be_removed() -> void:
	# Req 4.5: 配置済みエンティティはいつでも撤去可能
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	assert_int(entity_id).is_greater(0)
	var result := _system.remove(Vector2i(0, 0))
	assert_bool(result).is_true()
