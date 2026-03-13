extends GdUnitTestSuite

# Test: TilemapInitializer (Req 10.1-10.7, 11.3)

var _sut: TilemapInitializer


func before_test() -> void:
	_sut = TilemapInitializer.new()


func after_test() -> void:
	_sut = null


func test_create_grid_returns_64x64() -> void:
	var grid := _sut.create_grid(12345)
	assert_int(grid.width).is_equal(64)
	assert_int(grid.height).is_equal(64)


func test_all_terrain_is_ground() -> void:
	var grid := _sut.create_grid(12345)
	for y in range(64):
		for x in range(64):
			var terrain := grid.get_terrain(Vector2i(x, y))
			if terrain != Enums.TerrainType.GROUND:
				fail("Cell (%d, %d) terrain is %d, expected GROUND(%d)" % [x, y, terrain, Enums.TerrainType.GROUND])
				return


func test_iron_ore_exists() -> void:
	var grid := _sut.create_grid(12345)
	var iron_count: int = 0
	for y in range(64):
		for x in range(64):
			if grid.get_resource(Vector2i(x, y)) == Enums.ResourceType.IRON_ORE:
				iron_count += 1
	# 5 patches of 3x3 to 5x5 = minimum 45 cells, maximum 125 cells
	assert_int(iron_count).is_greater(0)


func test_deterministic_same_seed() -> void:
	var grid1 := _sut.create_grid(42)
	var grid2 := _sut.create_grid(42)
	# Compare all resource values
	for y in range(64):
		for x in range(64):
			var pos := Vector2i(x, y)
			if grid1.get_resource(pos) != grid2.get_resource(pos):
				fail("Cell (%d, %d) differs between same-seed grids" % [x, y])
				return


func test_different_seed_produces_different_result() -> void:
	var grid1 := _sut.create_grid(1)
	var grid2 := _sut.create_grid(999)
	var differs := false
	for y in range(64):
		for x in range(64):
			var pos := Vector2i(x, y)
			if grid1.get_resource(pos) != grid2.get_resource(pos):
				differs = true
				break
		if differs:
			break
	assert_bool(differs).is_true()


func test_tilemap_initializer_is_ref_counted() -> void:
	assert_object(_sut).is_instanceof(RefCounted)
