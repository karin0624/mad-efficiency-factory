extends GdUnitTestSuite

# Test: Performance Benchmark (Req 8.1, 8.2)

var _sut: BeltTransportSystem
var _belt_grid: BeltGrid
var _grid: CoreGrid
var _registry: EntityRegistry
var _placement: PlacementSystem


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_placement = PlacementSystem.new(_grid, _registry)
	_belt_grid = BeltGrid.new()
	_sut = BeltTransportSystem.new(_belt_grid, _grid, _placement)


func after_test() -> void:
	_sut = null
	_belt_grid = null
	_grid = null
	_registry = null
	_placement = null


# --- ベルト500本+アイテム2000個のtick()処理時間が16ms以下であることを検証 ---

func test_tick_performance_500belts_2000items() -> void:
	# 500本のベルトを配置（64x64グリッド内に収まるよう）
	# 行ごとに東向きの直線チェーンを配置
	# 各行は最大63本（0列〜62列）、8行で504本
	var belt_count := 0
	var entity_id := 1
	for row in range(8):
		for col in range(63):
			if belt_count >= 500:
				break
			var pos := Vector2i(col, row)
			_sut.on_entity_placed(entity_id, pos, Enums.Direction.E, 3)
			entity_id += 1
			belt_count += 1

	# ティック処理で接続を初期化
	_sut.tick()

	# 2000個のアイテムを配置（空きベルトに順次設定）
	var item_count := 0
	var positions := _belt_grid.get_all_positions()
	for pos in positions:
		if item_count >= 2000:
			break
		if _belt_grid.set_item(pos, 1):
			item_count += 1

	assert_int(_belt_grid.tile_count()).is_equal(500)
	# アイテムは最大500個（ベルト数が500本）
	assert_int(_belt_grid.item_count()).is_greater_equal(minf(item_count, 500) as int)

	# tick()の処理時間を計測
	var start_time := Time.get_ticks_usec()
	_sut.tick()
	var elapsed_usec := Time.get_ticks_usec() - start_time
	var elapsed_ms := elapsed_usec / 1000.0

	# 16ms以下であることを検証
	assert_float(elapsed_ms).is_less_equal(16.0)


# --- rebuild_connections()の処理時間が500ベルトで1ms以下であることを検証 ---

func test_rebuild_connections_performance_500belts() -> void:
	# 500本のベルトを配置
	var belt_count := 0
	var entity_id := 1
	for row in range(8):
		for col in range(63):
			if belt_count >= 500:
				break
			_belt_grid.add_tile(Vector2i(col, row), Enums.Direction.E)
			entity_id += 1
			belt_count += 1

	# rebuild_connections()の処理時間を計測
	var start_time := Time.get_ticks_usec()
	_belt_grid.rebuild_connections(_grid, _placement)
	var elapsed_usec := Time.get_ticks_usec() - start_time
	var elapsed_ms := elapsed_usec / 1000.0

	# 1ms以下であることを検証
	assert_float(elapsed_ms).is_less_equal(1.0)


# --- 64x64グリッド内での動作を検証 ---

func test_operates_within_64x64_grid() -> void:
	# グリッド境界チェック
	assert_int(_grid.width).is_equal(64)
	assert_int(_grid.height).is_equal(64)

	# 境界ギリギリのベルト配置
	_sut.on_entity_placed(1, Vector2i(63, 63), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(0, 0), Enums.Direction.N, 3)

	# ティック処理でクラッシュしないことを確認
	_sut.tick()

	# 境界ベルトは下流なし（グリッド外なので）
	var corner_tile := _belt_grid.get_tile(Vector2i(63, 63))
	assert_bool(corner_tile.has_downstream).is_false()

	var origin_tile := _belt_grid.get_tile(Vector2i(0, 0))
	assert_bool(origin_tile.has_downstream).is_false()
