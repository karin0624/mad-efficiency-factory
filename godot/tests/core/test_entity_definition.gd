extends GdUnitTestSuite

## EntityDefinition のユニットテスト (Layer 1)
## エンティティ種別の値オブジェクトが正しく機能することを検証する


func test_valid_entity_definition_stores_all_fields() -> void:
	# Arrange & Act
	var def := EntityDefinition.new(1, "Miner", Vector2i(2, 2))
	# Assert
	assert_int(def.id).is_equal(1)
	assert_str(def.display_name).is_equal("Miner")
	assert_that(def.footprint).is_equal(Vector2i(2, 2))


func test_valid_1x1_entity_definition() -> void:
	var def := EntityDefinition.new(3, "Belt", Vector2i(1, 1))
	assert_int(def.id).is_equal(3)
	assert_str(def.display_name).is_equal("Belt")
	assert_that(def.footprint).is_equal(Vector2i(1, 1))


func test_id_zero_is_rejected() -> void:
	# ID=0は予約値として拒否される
	var def := EntityDefinition.new(0, "Invalid", Vector2i(1, 1))
	assert_bool(def.is_valid()).is_false()


func test_empty_display_name_is_rejected() -> void:
	var def := EntityDefinition.new(1, "", Vector2i(1, 1))
	assert_bool(def.is_valid()).is_false()


func test_footprint_width_zero_is_rejected() -> void:
	var def := EntityDefinition.new(1, "Test", Vector2i(0, 1))
	assert_bool(def.is_valid()).is_false()


func test_footprint_height_zero_is_rejected() -> void:
	var def := EntityDefinition.new(1, "Test", Vector2i(1, 0))
	assert_bool(def.is_valid()).is_false()


func test_footprint_negative_is_rejected() -> void:
	var def := EntityDefinition.new(1, "Test", Vector2i(-1, -1))
	assert_bool(def.is_valid()).is_false()


func test_valid_entity_definition_is_valid() -> void:
	var def := EntityDefinition.new(2, "Smelter", Vector2i(2, 2))
	assert_bool(def.is_valid()).is_true()
