extends GdUnitTestSuite

# Test: CoreGrid (Req 1-8, 11.1)

var _sut: CoreGrid


func before_test() -> void:
	_sut = CoreGrid.new()


func after_test() -> void:
	_sut = null


# --- 3.1: Grid generation and dimensions (Req 1.1, 1.2, 1.3, 1.4) ---

func test_grid_width_is_64() -> void:
	assert_int(_sut.width).is_equal(64)


func test_grid_height_is_64() -> void:
	assert_int(_sut.height).is_equal(64)


func test_initial_terrain_is_empty() -> void:
	# Spot check several cells
	assert_int(_sut.get_terrain(Vector2i(0, 0))).is_equal(Enums.TerrainType.EMPTY)
	assert_int(_sut.get_terrain(Vector2i(32, 32))).is_equal(Enums.TerrainType.EMPTY)
	assert_int(_sut.get_terrain(Vector2i(63, 63))).is_equal(Enums.TerrainType.EMPTY)


func test_initial_resource_is_none() -> void:
	assert_int(_sut.get_resource(Vector2i(0, 0))).is_equal(Enums.ResourceType.NONE)
	assert_int(_sut.get_resource(Vector2i(32, 32))).is_equal(Enums.ResourceType.NONE)
	assert_int(_sut.get_resource(Vector2i(63, 63))).is_equal(Enums.ResourceType.NONE)


# --- 3.2: Bounds checking (Req 2.1, 2.2, 2.3) ---

func test_is_in_bounds_valid_origin() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(0, 0))).is_true()


func test_is_in_bounds_valid_max() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(63, 63))).is_true()


func test_is_in_bounds_valid_middle() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(32, 32))).is_true()


func test_is_in_bounds_negative_x() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(-1, 0))).is_false()


func test_is_in_bounds_negative_y() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(0, -1))).is_false()


func test_is_in_bounds_x_too_large() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(64, 0))).is_false()


func test_is_in_bounds_y_too_large() -> void:
	assert_bool(_sut.is_in_bounds(Vector2i(0, 64))).is_false()


func test_out_of_bounds_get_terrain_does_not_crash() -> void:
	# Should return default value, not crash
	var result := _sut.get_terrain(Vector2i(-1, -1))
	assert_int(result).is_equal(Enums.TerrainType.EMPTY)


func test_out_of_bounds_set_terrain_does_not_crash() -> void:
	# Should silently ignore, not crash
	_sut.set_terrain(Vector2i(100, 100), Enums.TerrainType.GROUND)
	# If we get here without crashing, the test passes


func test_out_of_bounds_get_resource_does_not_crash() -> void:
	var result := _sut.get_resource(Vector2i(-1, -1))
	assert_int(result).is_equal(Enums.ResourceType.NONE)


# --- 3.3: Terrain and resource read/write (Req 3.1-3.3, 4.1-4.3) ---

func test_set_get_terrain_roundtrip() -> void:
	_sut.set_terrain(Vector2i(5, 5), Enums.TerrainType.GROUND)
	assert_int(_sut.get_terrain(Vector2i(5, 5))).is_equal(Enums.TerrainType.GROUND)


func test_set_get_resource_roundtrip() -> void:
	_sut.set_resource(Vector2i(10, 10), Enums.ResourceType.IRON_ORE)
	assert_int(_sut.get_resource(Vector2i(10, 10))).is_equal(Enums.ResourceType.IRON_ORE)


func test_terrain_write_independent_cells() -> void:
	_sut.set_terrain(Vector2i(0, 0), Enums.TerrainType.GROUND)
	_sut.set_terrain(Vector2i(1, 0), Enums.TerrainType.EMPTY)
	assert_int(_sut.get_terrain(Vector2i(0, 0))).is_equal(Enums.TerrainType.GROUND)
	assert_int(_sut.get_terrain(Vector2i(1, 0))).is_equal(Enums.TerrainType.EMPTY)


func test_resource_write_independent_cells() -> void:
	_sut.set_resource(Vector2i(0, 0), Enums.ResourceType.IRON_ORE)
	_sut.set_resource(Vector2i(1, 0), Enums.ResourceType.NONE)
	assert_int(_sut.get_resource(Vector2i(0, 0))).is_equal(Enums.ResourceType.IRON_ORE)
	assert_int(_sut.get_resource(Vector2i(1, 0))).is_equal(Enums.ResourceType.NONE)


# --- 3.4: Single cell occupy (Req 5.1, 5.2, 5.3, 5.4, 5.5) ---

func test_occupy_unoccupied_cell_succeeds() -> void:
	var result := _sut.occupy(Vector2i(5, 5), 1)
	assert_bool(result).is_true()


func test_is_occupied_after_occupy() -> void:
	_sut.occupy(Vector2i(5, 5), 1)
	assert_bool(_sut.is_occupied(Vector2i(5, 5))).is_true()


func test_get_occupying_entity_returns_correct_id() -> void:
	_sut.occupy(Vector2i(5, 5), 42)
	assert_int(_sut.get_occupying_entity(Vector2i(5, 5))).is_equal(42)


func test_double_occupy_rejected() -> void:
	_sut.occupy(Vector2i(5, 5), 1)
	var result := _sut.occupy(Vector2i(5, 5), 2)
	assert_bool(result).is_false()
	# Original occupier remains
	assert_int(_sut.get_occupying_entity(Vector2i(5, 5))).is_equal(1)


func test_vacate_clears_occupation() -> void:
	_sut.occupy(Vector2i(5, 5), 1)
	_sut.vacate(Vector2i(5, 5))
	assert_bool(_sut.is_occupied(Vector2i(5, 5))).is_false()


func test_unoccupied_cell_is_not_occupied() -> void:
	assert_bool(_sut.is_occupied(Vector2i(5, 5))).is_false()


func test_get_occupying_entity_unoccupied_returns_zero() -> void:
	assert_int(_sut.get_occupying_entity(Vector2i(5, 5))).is_equal(0)


# --- 3.5: Rect occupy (Req 6.1, 6.2, 6.3, 6.4) ---

func test_occupy_rect_all_unoccupied_succeeds() -> void:
	var result := _sut.occupy_rect(Vector2i(0, 0), Vector2i(2, 2), 1)
	assert_bool(result).is_true()
	assert_bool(_sut.is_occupied(Vector2i(0, 0))).is_true()
	assert_bool(_sut.is_occupied(Vector2i(1, 0))).is_true()
	assert_bool(_sut.is_occupied(Vector2i(0, 1))).is_true()
	assert_bool(_sut.is_occupied(Vector2i(1, 1))).is_true()


func test_occupy_rect_atomic_rejection() -> void:
	# Occupy one cell within the target rect
	_sut.occupy(Vector2i(1, 1), 99)
	# Try to occupy_rect that overlaps
	var result := _sut.occupy_rect(Vector2i(0, 0), Vector2i(2, 2), 1)
	assert_bool(result).is_false()
	# No cells should have been changed
	assert_bool(_sut.is_occupied(Vector2i(0, 0))).is_false()
	assert_bool(_sut.is_occupied(Vector2i(1, 0))).is_false()
	assert_bool(_sut.is_occupied(Vector2i(0, 1))).is_false()
	# Original occupier untouched
	assert_int(_sut.get_occupying_entity(Vector2i(1, 1))).is_equal(99)


func test_occupy_rect_out_of_bounds_rejected() -> void:
	var result := _sut.occupy_rect(Vector2i(63, 63), Vector2i(2, 2), 1)
	assert_bool(result).is_false()
	# Cell at (63,63) should remain unoccupied
	assert_bool(_sut.is_occupied(Vector2i(63, 63))).is_false()


func test_vacate_rect_clears_all() -> void:
	_sut.occupy_rect(Vector2i(2, 2), Vector2i(2, 2), 1)
	_sut.vacate_rect(Vector2i(2, 2), Vector2i(2, 2))
	assert_bool(_sut.is_occupied(Vector2i(2, 2))).is_false()
	assert_bool(_sut.is_occupied(Vector2i(3, 2))).is_false()
	assert_bool(_sut.is_occupied(Vector2i(2, 3))).is_false()
	assert_bool(_sut.is_occupied(Vector2i(3, 3))).is_false()


# --- 3.6: Adjacent cells query (Req 7.1, 7.2) ---

func test_get_adjacent_interior_returns_four() -> void:
	var adj := _sut.get_adjacent(Vector2i(5, 5))
	assert_int(adj.size()).is_equal(4)
	assert_array(adj).contains([
		Vector2i(5, 4), Vector2i(5, 6),
		Vector2i(4, 5), Vector2i(6, 5)
	])


func test_get_adjacent_corner_returns_two() -> void:
	var adj := _sut.get_adjacent(Vector2i(0, 0))
	assert_int(adj.size()).is_equal(2)
	assert_array(adj).contains([Vector2i(1, 0), Vector2i(0, 1)])


func test_get_adjacent_edge_returns_three() -> void:
	var adj := _sut.get_adjacent(Vector2i(0, 5))
	assert_int(adj.size()).is_equal(3)
	assert_array(adj).contains([Vector2i(0, 4), Vector2i(0, 6), Vector2i(1, 5)])


# --- 3.7: Cell data snapshot (Req 8.1, 8.2) ---

func test_get_cell_returns_grid_cell_data() -> void:
	var cell := _sut.get_cell(Vector2i(0, 0))
	assert_object(cell).is_instanceof(GridCellData)


func test_get_cell_contains_correct_values() -> void:
	_sut.set_terrain(Vector2i(3, 3), Enums.TerrainType.GROUND)
	_sut.set_resource(Vector2i(3, 3), Enums.ResourceType.IRON_ORE)
	_sut.occupy(Vector2i(3, 3), 7)
	var cell := _sut.get_cell(Vector2i(3, 3))
	assert_int(cell.terrain).is_equal(Enums.TerrainType.GROUND)
	assert_int(cell.resource).is_equal(Enums.ResourceType.IRON_ORE)
	assert_int(cell.occupying_entity).is_equal(7)


func test_get_cell_snapshot_independence() -> void:
	_sut.set_terrain(Vector2i(3, 3), Enums.TerrainType.GROUND)
	var cell := _sut.get_cell(Vector2i(3, 3))
	# Modify the snapshot
	cell.terrain = Enums.TerrainType.EMPTY
	# CoreGrid should still have GROUND
	assert_int(_sut.get_terrain(Vector2i(3, 3))).is_equal(Enums.TerrainType.GROUND)


# --- SceneTree independence (Req 11.1) ---

func test_core_grid_is_ref_counted() -> void:
	assert_object(_sut).is_instanceof(RefCounted)
