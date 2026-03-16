extends GdUnitTestSuite

## EntityRegistry のユニットテスト (Layer 1)
## エンティティ定義のカタログが正しく機能することを検証する


func test_register_and_retrieve_entity_definition() -> void:
	# Arrange
	var registry := EntityRegistry.new()
	var def := EntityDefinition.new(1, "Miner", Vector2i(2, 2))
	# Act
	var registered := registry.register(def)
	var retrieved := registry.get_definition(1)
	# Assert
	assert_bool(registered).is_true()
	assert_object(retrieved).is_not_null()
	assert_int(retrieved.id).is_equal(1)
	assert_str(retrieved.display_name).is_equal("Miner")
	assert_that(retrieved.footprint).is_equal(Vector2i(2, 2))


func test_duplicate_registration_is_rejected() -> void:
	var registry := EntityRegistry.new()
	var def1 := EntityDefinition.new(1, "Miner", Vector2i(2, 2))
	var def2 := EntityDefinition.new(1, "Duplicate", Vector2i(1, 1))
	# Act
	var first := registry.register(def1)
	var second := registry.register(def2)
	# Assert
	assert_bool(first).is_true()
	assert_bool(second).is_false()
	# 元の定義が維持されていること
	assert_str(registry.get_definition(1).display_name).is_equal("Miner")


func test_get_definition_unknown_id_returns_null() -> void:
	var registry := EntityRegistry.new()
	var result := registry.get_definition(999)
	assert_object(result).is_null()


func test_get_definition_id_zero_returns_null() -> void:
	var registry := EntityRegistry.new()
	var result := registry.get_definition(0)
	assert_object(result).is_null()


func test_size_reflects_registered_count() -> void:
	var registry := EntityRegistry.new()
	assert_int(registry.size()).is_equal(0)
	registry.register(EntityDefinition.new(1, "Miner", Vector2i(2, 2)))
	assert_int(registry.size()).is_equal(1)
	registry.register(EntityDefinition.new(2, "Smelter", Vector2i(2, 2)))
	assert_int(registry.size()).is_equal(2)


func test_create_default_has_four_entity_types() -> void:
	var registry := EntityRegistry.create_default()
	assert_int(registry.size()).is_equal(4)


func test_create_default_miner_is_1x1() -> void:
	var registry := EntityRegistry.create_default()
	# MinerはID=1
	var miner := registry.get_definition(1)
	assert_object(miner).is_not_null()
	assert_str(miner.display_name).is_equal("Miner")
	assert_that(miner.footprint).is_equal(Vector2i(1, 1))


func test_create_default_smelter_is_1x1() -> void:
	var registry := EntityRegistry.create_default()
	# SmelterはID=2
	var smelter := registry.get_definition(2)
	assert_object(smelter).is_not_null()
	assert_str(smelter.display_name).is_equal("Smelter")
	assert_that(smelter.footprint).is_equal(Vector2i(1, 1))


func test_create_default_belt_is_1x1() -> void:
	var registry := EntityRegistry.create_default()
	# BeltはID=3
	var belt := registry.get_definition(3)
	assert_object(belt).is_not_null()
	assert_str(belt.display_name).is_equal("Belt")
	assert_that(belt.footprint).is_equal(Vector2i(1, 1))


func test_create_default_delivery_box_is_1x1() -> void:
	var registry := EntityRegistry.create_default()
	# DeliveryBoxはID=4
	var delivery_box := registry.get_definition(4)
	assert_object(delivery_box).is_not_null()
	assert_str(delivery_box.display_name).is_equal("DeliveryBox")
	assert_that(delivery_box.footprint).is_equal(Vector2i(1, 1))
