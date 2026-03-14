extends GdUnitTestSuite

# Test: Processing Order Cache and FIFO (Req 6.1, 6.2, 6.3)

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


# --- 直線5本ベルトチェーンで末尾→先頭の処理順序を検証 ---

func test_five_belt_chain_items_travel_forward() -> void:
	# 5本直線チェーン: (1,1)→(2,1)→(3,1)→(4,1)→(5,1)
	for x in range(1, 6):
		_sut.on_entity_placed(x, Vector2i(x, 1), Enums.Direction.E, 3)

	# (1,1)にアイテムを配置して60ティック進行させる
	_belt_grid.set_item(Vector2i(1, 1), 42)

	# 5ベルトを通過するのに最大5秒（300ティック）かかる
	# 各ベルトで60ティック、5本で300ティック
	var max_ticks := 350
	for _i in range(max_ticks):
		_sut.tick()
		# アイテムが末端(5,1)を超えたら（転送先なし）停止する

	# 最終的にアイテムは(5,1)にあるはず（下流がないので）
	var end_tile := _belt_grid.get_tile(Vector2i(5, 1))
	assert_int(end_tile.item_id).is_equal(42)
	assert_float(end_tile.progress).is_equal(1.0)

	# (1,1)〜(4,1)は空
	for x in range(1, 5):
		var tile := _belt_grid.get_tile(Vector2i(x, 1))
		assert_int(tile.item_id).is_equal(0)


# --- アイテムが占有中の中間ベルトをスキップしないことを検証（飛び越え防止） ---

func test_item_does_not_skip_occupied_belt() -> void:
	# 3本直線: (1,1)→(2,1)→(3,1)
	_sut.on_entity_placed(1, Vector2i(1, 1), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(2, 1), Enums.Direction.E, 3)
	_sut.on_entity_placed(3, Vector2i(3, 1), Enums.Direction.E, 3)

	# (2,1)にアイテムを配置（中間ベルト満杯）
	_belt_grid.set_item(Vector2i(2, 1), 99)

	# (1,1)にアイテムを配置
	_belt_grid.set_item(Vector2i(1, 1), 1)
	_belt_grid.get_tile(Vector2i(1, 1)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	_sut.tick()

	# (1,1)のアイテムは(2,1)が満杯なので移動できない
	var tile1 := _belt_grid.get_tile(Vector2i(1, 1))
	assert_int(tile1.item_id).is_equal(1)
	assert_float(tile1.progress).is_equal(1.0)

	# (2,1)のアイテムはそのまま（(3,1)はまだ空だが、(2,1)は進行中）
	var tile2 := _belt_grid.get_tile(Vector2i(2, 1))
	assert_int(tile2.item_id).is_equal(99)


# --- FIFO: ベルトチェーンに投入した順序でアイテムが出力されることを検証 ---

func test_fifo_order_maintained() -> void:
	# 4本直線: (1,1)→(2,1)→(3,1)→(4,1)
	for x in range(1, 5):
		_sut.on_entity_placed(x, Vector2i(x, 1), Enums.Direction.E, 3)

	# (1,1)にアイテム1を配置
	_belt_grid.set_item(Vector2i(1, 1), 1)
	# 60ティック後にアイテム1は(2,1)に移動
	for _i in range(60):
		_sut.tick()

	# (2,1)にアイテム1があることを確認
	var tile2 := _belt_grid.get_tile(Vector2i(2, 1))
	assert_int(tile2.item_id).is_equal(1)

	# (1,1)にアイテム2を配置
	_belt_grid.set_item(Vector2i(1, 1), 2)

	# さらに60ティック
	for _i in range(60):
		_sut.tick()

	# アイテム1は(3,1)に、アイテム2は(2,1)に
	var tile3 := _belt_grid.get_tile(Vector2i(3, 1))
	assert_int(tile3.item_id).is_equal(1)  # 先に投入したアイテム1が先行

	var tile2b := _belt_grid.get_tile(Vector2i(2, 1))
	assert_int(tile2b.item_id).is_equal(2)  # 後に投入したアイテム2が後続


# --- L字配置での処理順序テスト ---

func test_l_shape_items_transport_correctly() -> void:
	# L字: (1,1)→(2,1)→(2,2)→(2,3)  (東→東→南→南)
	_sut.on_entity_placed(1, Vector2i(1, 1), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(2, 1), Enums.Direction.S, 3)
	_sut.on_entity_placed(3, Vector2i(2, 2), Enums.Direction.S, 3)
	_sut.on_entity_placed(4, Vector2i(2, 3), Enums.Direction.S, 3)

	_belt_grid.set_item(Vector2i(1, 1), 7)

	# 4ベルト通過 = 240ティック以上
	for _i in range(280):
		_sut.tick()

	# アイテムは末端(2,3)にあるはず
	var end_tile := _belt_grid.get_tile(Vector2i(2, 3))
	assert_int(end_tile.item_id).is_equal(7)
	assert_float(end_tile.progress).is_equal(1.0)


# --- 独立した複数ベルトチェーンがすべて処理されることを検証 ---

func test_independent_chains_all_processed() -> void:
	# チェーン1: (1,1)→(2,1)
	_sut.on_entity_placed(1, Vector2i(1, 1), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(2, 1), Enums.Direction.E, 3)

	# チェーン2: (10,10)→(11,10)
	_sut.on_entity_placed(3, Vector2i(10, 10), Enums.Direction.E, 3)
	_sut.on_entity_placed(4, Vector2i(11, 10), Enums.Direction.E, 3)

	# 両チェーンにアイテムを配置
	_belt_grid.set_item(Vector2i(1, 1), 1)
	_belt_grid.get_tile(Vector2i(1, 1)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5
	_belt_grid.set_item(Vector2i(10, 10), 2)
	_belt_grid.get_tile(Vector2i(10, 10)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	_sut.tick()

	# 両チェーンのアイテムが転送されること
	assert_int(_belt_grid.get_tile(Vector2i(1, 1)).item_id).is_equal(0)
	assert_int(_belt_grid.get_tile(Vector2i(2, 1)).item_id).is_equal(1)
	assert_int(_belt_grid.get_tile(Vector2i(10, 10)).item_id).is_equal(0)
	assert_int(_belt_grid.get_tile(Vector2i(11, 10)).item_id).is_equal(2)
