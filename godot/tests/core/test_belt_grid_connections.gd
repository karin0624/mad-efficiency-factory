extends GdUnitTestSuite

# Test: BeltGrid.rebuild_connections (Req 2.4, 2.6, 5.1, 5.2, 5.3)

var _belt_grid: BeltGrid
var _grid: CoreGrid
var _registry: EntityRegistry
var _placement: PlacementSystem


func before_test() -> void:
	_belt_grid = BeltGrid.new()
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_placement = PlacementSystem.new(_grid, _registry)


func after_test() -> void:
	_belt_grid = null
	_grid = null
	_registry = null
	_placement = null


# --- 東向きベルトの接続検証 ---

func test_east_belt_connects_to_east_neighbor() -> void:
	# 東向きベルトを(5,5)に配置、東隣の(6,5)にもベルトを配置
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(6, 5), Enums.Direction.E)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_true()
	assert_that(tile.downstream_pos).is_equal(Vector2i(6, 5))


func test_east_belt_no_downstream_when_no_east_neighbor() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_false()


# --- 4方向の接続パターン ---

func test_north_belt_connects_to_north_neighbor() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(5, 4), Enums.Direction.N)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_true()
	assert_that(tile.downstream_pos).is_equal(Vector2i(5, 4))


func test_south_belt_connects_to_south_neighbor() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.S)
	_belt_grid.add_tile(Vector2i(5, 6), Enums.Direction.S)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_true()
	assert_that(tile.downstream_pos).is_equal(Vector2i(5, 6))


func test_west_belt_connects_to_west_neighbor() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.W)
	_belt_grid.add_tile(Vector2i(4, 5), Enums.Direction.W)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_true()
	assert_that(tile.downstream_pos).is_equal(Vector2i(4, 5))


# --- 向きと合致しない方向への接続が発生しないことを検証 ---

func test_east_belt_does_not_connect_to_north_neighbor() -> void:
	# 東向きベルト(5,5)と北隣(5,4)にベルト→接続されないこと
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(5, 4), Enums.Direction.N)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_false()


func test_east_belt_does_not_connect_to_south_neighbor() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(5, 6), Enums.Direction.S)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_false()


# --- L字配置での接続検証（東→南への方向転換） ---

func test_l_shape_east_to_south_connection() -> void:
	# 東向き(5,5)→東隣(6,5)は南向き → 東向き→南向きのL字
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(6, 5), Enums.Direction.S)
	_belt_grid.rebuild_connections(_grid, _placement)

	# 東向きベルト(5,5)は東の(6,5)に接続される（下流の方向は関係ない）
	var tile_e := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile_e.has_downstream).is_true()
	assert_that(tile_e.downstream_pos).is_equal(Vector2i(6, 5))

	# 南向きベルト(6,5)は南の(6,6)に接続がないのでhas_downstream=false
	var tile_s := _belt_grid.get_tile(Vector2i(6, 5))
	assert_bool(tile_s.has_downstream).is_false()


# --- グリッド範囲外への接続が発生しないことを検証 ---

func test_east_belt_at_grid_edge_has_no_downstream() -> void:
	# グリッド右端(63,5)に東向きベルト → 範囲外なのでdownstreamなし
	_belt_grid.add_tile(Vector2i(63, 5), Enums.Direction.E)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(63, 5))
	assert_bool(tile.has_downstream).is_false()


func test_north_belt_at_grid_edge_has_no_downstream() -> void:
	# グリッド上端(5,0)に北向きベルト → 範囲外なのでdownstreamなし
	_belt_grid.add_tile(Vector2i(5, 0), Enums.Direction.N)
	_belt_grid.rebuild_connections(_grid, _placement)

	var tile := _belt_grid.get_tile(Vector2i(5, 0))
	assert_bool(tile.has_downstream).is_false()


# --- 複数ベルトの一括再計算 ---

func test_rebuild_updates_all_tiles() -> void:
	# 3本直線チェーン
	_belt_grid.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(2, 1), Enums.Direction.E)
	_belt_grid.add_tile(Vector2i(3, 1), Enums.Direction.E)
	_belt_grid.rebuild_connections(_grid, _placement)

	var t1 := _belt_grid.get_tile(Vector2i(1, 1))
	var t2 := _belt_grid.get_tile(Vector2i(2, 1))
	var t3 := _belt_grid.get_tile(Vector2i(3, 1))

	assert_bool(t1.has_downstream).is_true()
	assert_that(t1.downstream_pos).is_equal(Vector2i(2, 1))
	assert_bool(t2.has_downstream).is_true()
	assert_that(t2.downstream_pos).is_equal(Vector2i(3, 1))
	# 末尾は下流なし
	assert_bool(t3.has_downstream).is_false()
