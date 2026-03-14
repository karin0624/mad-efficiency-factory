extends GdUnitTestSuite

# Test: Backpressure (Req 3.1, 3.2, 3.3, 3.4)

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


# --- 出力先満杯でベルト末端アイテムが停止することを検証 ---

func test_belt_end_item_stops_when_downstream_full() -> void:
	# 2本直線: (5,5)→(6,5)
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	# 両方にアイテム設定（(6,5)が満杯）
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5
	_belt_grid.set_item(Vector2i(6, 5), 2)

	_sut.tick()

	# (5,5)は転送できず停止（progress=1.0）
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_float(tile.progress).is_equal(1.0)
	assert_int(tile.item_id).is_equal(1)


# --- 末端停止時に後続アイテムも連鎖的に停止することを検証（圧力の逆伝播） ---

func test_backpressure_propagates_upstream() -> void:
	# 3本直線: (5,5)→(6,5)→(7,5)
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(3, Vector2i(7, 5), Enums.Direction.E, 3)

	# 全タイルにアイテムを配置（満杯状態）
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.set_item(Vector2i(6, 5), 2)
	_belt_grid.set_item(Vector2i(7, 5), 3)

	# 全て進行度1.0手前に設定
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5
	_belt_grid.get_tile(Vector2i(6, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5
	_belt_grid.get_tile(Vector2i(7, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	_sut.tick()

	# (7,5)は下流なし → 停止
	var t3 := _belt_grid.get_tile(Vector2i(7, 5))
	assert_float(t3.progress).is_equal(1.0)
	assert_int(t3.item_id).is_equal(3)

	# (6,5)は(7,5)が満杯 → 停止
	var t2 := _belt_grid.get_tile(Vector2i(6, 5))
	assert_float(t2.progress).is_equal(1.0)
	assert_int(t2.item_id).is_equal(2)

	# (5,5)は(6,5)が満杯 → 停止
	var t1 := _belt_grid.get_tile(Vector2i(5, 5))
	assert_float(t1.progress).is_equal(1.0)
	assert_int(t1.item_id).is_equal(1)


# --- 出力先に空きが生じた時点で停止アイテムが自動再開することを検証 ---

func test_item_resumes_when_downstream_space_becomes_available() -> void:
	# 2本直線: (5,5)→(6,5)
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	# 両方にアイテム設定（待機状態）
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0
	_belt_grid.set_item(Vector2i(6, 5), 2)
	_belt_grid.get_tile(Vector2i(6, 5)).progress = 1.0

	# (6,5)のアイテムを手動でクリア（下流に空きが生じた状態をシミュレート）
	_belt_grid.clear_item(Vector2i(6, 5))

	_sut.tick()

	# (5,5)のアイテムが(6,5)に転送された
	var src_tile := _belt_grid.get_tile(Vector2i(5, 5))
	var dst_tile := _belt_grid.get_tile(Vector2i(6, 5))
	assert_int(src_tile.item_id).is_equal(0)
	assert_int(dst_tile.item_id).is_equal(1)


# --- バックプレッシャー中もアイテム保存則が維持されることを検証 ---

func test_item_conservation_during_backpressure() -> void:
	# 3本直線: 全満杯でバックプレッシャー
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(3, Vector2i(7, 5), Enums.Direction.E, 3)

	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.set_item(Vector2i(6, 5), 2)
	_belt_grid.set_item(Vector2i(7, 5), 3)

	# 全タイル待機状態
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0
	_belt_grid.get_tile(Vector2i(6, 5)).progress = 1.0
	_belt_grid.get_tile(Vector2i(7, 5)).progress = 1.0

	var before_count := _belt_grid.item_count()

	# 複数ティック処理
	for _i in range(10):
		_sut.tick()

	var after_count := _belt_grid.item_count()

	# アイテム総数が保存されている
	assert_int(before_count).is_equal(3)
	assert_int(after_count).is_equal(3)
