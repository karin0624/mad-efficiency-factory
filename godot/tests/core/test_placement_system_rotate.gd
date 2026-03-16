extends GdUnitTestSuite

## PlacementSystem.rotate_cw() のユニットテスト (Layer 1)
## 回転ロジックが正しく機能することを検証する
## 注: 多セル回転検証にはテスト専用2x2エンティティ(ID=99)を使用。

const TEST_2X2_ID: int = 99

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_registry.register(EntityDefinition.new(TEST_2X2_ID, "TestLarge", Vector2i(2, 2)))
	_system = PlacementSystem.new(_grid, _registry)


func after_test() -> void:
	_system = null
	_registry = null
	_grid = null


func test_rotate_cw_north_to_east() -> void:
	var result := PlacementSystem.rotate_cw(Enums.Direction.N)
	assert_int(result).is_equal(Enums.Direction.E)


func test_rotate_cw_east_to_south() -> void:
	var result := PlacementSystem.rotate_cw(Enums.Direction.E)
	assert_int(result).is_equal(Enums.Direction.S)


func test_rotate_cw_south_to_west() -> void:
	var result := PlacementSystem.rotate_cw(Enums.Direction.S)
	assert_int(result).is_equal(Enums.Direction.W)


func test_rotate_cw_west_to_north() -> void:
	# Req 3.1: 北→東→南→西→北の順でサイクル
	var result := PlacementSystem.rotate_cw(Enums.Direction.W)
	assert_int(result).is_equal(Enums.Direction.N)


func test_rotate_cw_full_cycle_returns_to_north() -> void:
	var dir := Enums.Direction.N
	dir = PlacementSystem.rotate_cw(dir)
	dir = PlacementSystem.rotate_cw(dir)
	dir = PlacementSystem.rotate_cw(dir)
	dir = PlacementSystem.rotate_cw(dir)
	assert_int(dir).is_equal(Enums.Direction.N)


func test_place_north_direction_is_stored_in_entity() -> void:
	# Req 3.3: 配置時に回転方向がPlacedEntityに保持される
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.N)
	var entity := _system.get_placed_entity(entity_id)
	assert_int(entity.direction).is_equal(Enums.Direction.N)


func test_place_east_direction_is_stored_in_entity() -> void:
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.E)
	var entity := _system.get_placed_entity(entity_id)
	assert_int(entity.direction).is_equal(Enums.Direction.E)


func test_place_south_direction_is_stored_in_entity() -> void:
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.S)
	var entity := _system.get_placed_entity(entity_id)
	assert_int(entity.direction).is_equal(Enums.Direction.S)


func test_place_west_direction_is_stored_in_entity() -> void:
	var entity_id := _system.place(1, Vector2i(0, 0), Enums.Direction.W)
	var entity := _system.get_placed_entity(entity_id)
	assert_int(entity.direction).is_equal(Enums.Direction.W)


func test_rotation_does_not_change_occupied_cells_for_2x2() -> void:
	# Req 3.4: 正方形フットプリントは回転で占有領域が変化しない（テスト専用2x2で検証）
	# 北向きで配置
	var id_north := _system.place(TEST_2X2_ID, Vector2i(0, 0), Enums.Direction.N)
	assert_int(id_north).is_greater(0)
	_system.remove(Vector2i(0, 0))

	# 東向きで配置 - 同じ4セルを占有する
	var id_east := _system.place(TEST_2X2_ID, Vector2i(0, 0), Enums.Direction.E)
	assert_int(id_east).is_greater(0)
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_true()
	assert_bool(_grid.is_occupied(Vector2i(1, 1))).is_true()
