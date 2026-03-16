extends GdUnitTestSuite

## PlacementSystem.can_place() のユニットテスト (Layer 1)
## 配置可否判定ロジックが正しく機能することを検証する
## 注: MVPエンティティは全て1x1。多セル検証にはテスト専用2x2エンティティ(ID=99)を使用。

const TEST_2X2_ID: int = 99  ## テスト専用の2x2エンティティID

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	# テスト専用の2x2エンティティを登録（境界・多セル検証用）
	_registry.register(EntityDefinition.new(TEST_2X2_ID, "TestLarge", Vector2i(2, 2)))
	_system = PlacementSystem.new(_grid, _registry)


func after_test() -> void:
	_system = null
	_registry = null
	_grid = null


func test_can_place_1x1_on_empty_cell_returns_true() -> void:
	# Belt(ID=3)は1x1
	var result := _system.can_place(3, Vector2i(0, 0))
	assert_bool(result).is_true()


func test_can_place_2x2_test_entity_on_empty_area_returns_true() -> void:
	# テスト専用2x2エンティティが空き領域に配置可能
	var result := _system.can_place(TEST_2X2_ID, Vector2i(0, 0))
	assert_bool(result).is_true()


func test_can_place_returns_false_on_occupied_cell() -> void:
	# Belt(ID=3)を(5,5)に配置済み
	_grid.occupy_rect(Vector2i(5, 5), Vector2i(1, 1), 999)
	var result := _system.can_place(3, Vector2i(5, 5))
	assert_bool(result).is_false()


func test_can_place_2x2_returns_false_when_partial_overlap() -> void:
	# (1,1)にベルトを配置して、(0,0)にテスト専用2x2を置こうとする
	_grid.occupy_rect(Vector2i(1, 1), Vector2i(1, 1), 999)
	var result := _system.can_place(TEST_2X2_ID, Vector2i(0, 0))
	assert_bool(result).is_false()


func test_can_place_2x2_test_entity_out_of_bounds_at_63_63_returns_false() -> void:
	# テスト専用2x2エンティティを(63,63)に置こうとすると範囲外
	var result := _system.can_place(TEST_2X2_ID, Vector2i(63, 63))
	assert_bool(result).is_false()


func test_can_place_2x2_test_entity_at_grid_edge_valid_returns_true() -> void:
	# テスト専用2x2が収まる最大位置(62, 62)
	var result := _system.can_place(TEST_2X2_ID, Vector2i(62, 62))
	assert_bool(result).is_true()


func test_can_place_1x1_at_corner_63_63_returns_true() -> void:
	# Req 2.4: 基準セル(63,63)への1x1エンティティ配置が空きの場合に許可される
	var result := _system.can_place(3, Vector2i(63, 63))
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
	var result := _system.can_place(9999, Vector2i(0, 0))
	assert_bool(result).is_false()


func test_can_place_is_query_only_no_side_effects() -> void:
	# can_place()はグリッド状態を変更しない（1x1エンティティで確認）
	_system.can_place(3, Vector2i(0, 0))
	assert_bool(_grid.is_occupied(Vector2i(0, 0))).is_false()
