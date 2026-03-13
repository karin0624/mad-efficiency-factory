extends GdUnitTestSuite

# Test: GridCellData snapshot class (Req 8.1, 8.2, 11.2)

func test_grid_cell_data_is_ref_counted() -> void:
	var cell := GridCellData.new(Enums.TerrainType.GROUND, Enums.ResourceType.IRON_ORE, 42)
	assert_object(cell).is_instanceof(RefCounted)

func test_grid_cell_data_stores_terrain() -> void:
	var cell := GridCellData.new(Enums.TerrainType.GROUND, Enums.ResourceType.NONE, 0)
	assert_int(cell.terrain).is_equal(Enums.TerrainType.GROUND)

func test_grid_cell_data_stores_resource() -> void:
	var cell := GridCellData.new(Enums.TerrainType.EMPTY, Enums.ResourceType.IRON_ORE, 0)
	assert_int(cell.resource).is_equal(Enums.ResourceType.IRON_ORE)

func test_grid_cell_data_stores_occupying_entity() -> void:
	var cell := GridCellData.new(Enums.TerrainType.EMPTY, Enums.ResourceType.NONE, 99)
	assert_int(cell.occupying_entity).is_equal(99)

func test_grid_cell_data_default_unoccupied() -> void:
	var cell := GridCellData.new(Enums.TerrainType.EMPTY, Enums.ResourceType.NONE, 0)
	assert_int(cell.occupying_entity).is_equal(0)
