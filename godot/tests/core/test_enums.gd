extends GdUnitTestSuite

# Test: Enums shared definitions (Req 9.1, 9.2, 9.3, 9.4, 11.4)

func test_terrain_type_empty_is_zero() -> void:
	assert_int(Enums.TerrainType.EMPTY).is_equal(0)

func test_terrain_type_ground_is_one() -> void:
	assert_int(Enums.TerrainType.GROUND).is_equal(1)

func test_resource_type_none_is_zero() -> void:
	assert_int(Enums.ResourceType.NONE).is_equal(0)

func test_resource_type_iron_ore_is_one() -> void:
	assert_int(Enums.ResourceType.IRON_ORE).is_equal(1)

func test_direction_n_is_zero() -> void:
	assert_int(Enums.Direction.N).is_equal(0)

func test_direction_e_is_one() -> void:
	assert_int(Enums.Direction.E).is_equal(1)

func test_direction_s_is_two() -> void:
	assert_int(Enums.Direction.S).is_equal(2)

func test_direction_w_is_three() -> void:
	assert_int(Enums.Direction.W).is_equal(3)

func test_enums_is_ref_counted() -> void:
	var e := Enums.new()
	assert_object(e).is_instanceof(RefCounted)
