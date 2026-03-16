extends GdUnitTestSuite

## PlacementSystem.can_place() のユニットテスト (Layer 1)
## 配置可否判定ロジックが正しく機能することを検証する

## 汎用テスト用2x2エンティティのID
const TEST_2X2_ID := 99

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_registry.register(EntityDefinition.new(TEST_2X2_ID, "TestMachine2x2", Vector2i(2, 2)))
	_system = PlacementSystem.new(_grid, _registry)


func after_test() -> void:
	_system = null
	_registry = null
	_grid = null


func test_can_place_1x1_on_empty_cell_returns_true() -> void:
	# Belt(ID=3)は1x1
	var result := _system.can_place(3, Vector2i(0, 0))
	assert_bool(result).is_true()


func test_can_place_2x2_on_empty_area_returns_true() -> void:
	# 汎用テスト用2x2エンティティ
	var result := _system.can_place(TEST_2X2_ID, Vector2i(0, 0))
	assert_bool(result).is_true()


func test_can_place_returns_false_on_occupied_cell() -> void:
	# Belt(ID=3)を(5,5)に配置済み
	_grid.occupy_rect(Vector2i(5, 5), Vector2i(1, 1), 999)
	var result := _system.can_place(3, Vector2i(5, 5))
	assert_bool(result).is_false()


func test_can_place_2x2_returns_false_when_partial_overlap() -> void:
	# (1,1)にベルトを配置して、(0,0)に汎用2x2を置こうとする
	_grid.occupy_rect(Vector2i(1, 1), Vector2i(1, 1), 999)
	var result := _system.can_place(TEST_2X2_ID, Vector2i(0, 0))
	assert_bool(result).is_false()


func test_can_place_out_of_bounds_returns_false() -> void:
	# グリッドは64x64、基準セル(63,63)に汎用2x2エンティティを置こうとする → 範囲外
	var result := _system.can_place(TEST_2X2_ID, Vector2i(63, 63))
	assert_bool(result).is_false()


func test_can_place_at_grid_edge_valid_2x2_returns_true() -> void:
	# 2x2が収まる最大位置 (62, 62)
	var result := _system.can_place(TEST_2X2_ID, Vector2i(62, 62))
	assert_bool(result).is_true()


func test_can_place_1x1_at_origin_returns_true() -> void:
	# Req 2.5: 基準セル(0,0)に1x1エンティティ、空きの場合
	var result := _system.can_place(3, Vector2i(0, 0))
	assert_bool(result).is_true()


func test_can_place_out_of_bounds_negative_returns_false() -> void:
	var result := _system.can_place(3, Vector2i(-1, -1))
	assert_bool(result).is_false()


func test_can_place_invalid_entity_type_id_returns_false() -> void:
	# 未登録のエンティティIDは配置不可
	var result := _system.can_place(999, Vector2i(0, 0))
	assert_bool(result).is_false()


func test_can_place_is_query_only_no_side_effects() -> void:
	# can_place()はグリッド状態を変更しない（汎用2x2でチェック）
	_system.can_place(TEST_2X2_ID, Vector2i(0, 0))
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 0))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(0, 1))).is_false()
	assert_bool(_grid.is_occupied(Vector2i(1, 1))).is_false()
