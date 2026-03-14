extends GdUnitTestSuite

## PlacedEntity のユニットテスト (Layer 1)
## 配置済みエンティティの状態を保持する値オブジェクトが正しく機能することを検証する


func test_placed_entity_stores_all_fields_for_2x2() -> void:
	# Arrange & Act
	var entity := PlacedEntity.new(1, 1, Vector2i(5, 5), Enums.Direction.N, Vector2i(2, 2))
	# Assert
	assert_int(entity.entity_id).is_equal(1)
	assert_int(entity.entity_type_id).is_equal(1)
	assert_that(entity.base_cell).is_equal(Vector2i(5, 5))
	assert_int(entity.direction).is_equal(Enums.Direction.N)
	assert_that(entity.footprint).is_equal(Vector2i(2, 2))


func test_placed_entity_stores_all_fields_for_1x1() -> void:
	var entity := PlacedEntity.new(42, 3, Vector2i(10, 20), Enums.Direction.E, Vector2i(1, 1))
	assert_int(entity.entity_id).is_equal(42)
	assert_int(entity.entity_type_id).is_equal(3)
	assert_that(entity.base_cell).is_equal(Vector2i(10, 20))
	assert_int(entity.direction).is_equal(Enums.Direction.E)
	assert_that(entity.footprint).is_equal(Vector2i(1, 1))


func test_placed_entity_direction_north() -> void:
	var entity := PlacedEntity.new(1, 1, Vector2i(0, 0), Enums.Direction.N, Vector2i(2, 2))
	assert_int(entity.direction).is_equal(0)  # N=0


func test_placed_entity_direction_east() -> void:
	var entity := PlacedEntity.new(1, 1, Vector2i(0, 0), Enums.Direction.E, Vector2i(2, 2))
	assert_int(entity.direction).is_equal(1)  # E=1


func test_placed_entity_direction_south() -> void:
	var entity := PlacedEntity.new(1, 1, Vector2i(0, 0), Enums.Direction.S, Vector2i(2, 2))
	assert_int(entity.direction).is_equal(2)  # S=2


func test_placed_entity_direction_west() -> void:
	var entity := PlacedEntity.new(1, 1, Vector2i(0, 0), Enums.Direction.W, Vector2i(2, 2))
	assert_int(entity.direction).is_equal(3)  # W=3
