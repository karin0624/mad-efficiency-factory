extends GdUnitTestSuite

# Test: BeltTransportSystem (Req 1.1, 1.3, 2.1, 2.2, 2.3, 7.1, 7.2, 7.3)

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


# =========================================================
# Task 4.1: アイテム進行の単体テスト
# =========================================================

func test_tick_advances_progress_by_speed_per_tick() -> void:
	# アイテムを持つベルトタイルを配置
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 0.0
	# ダーティフラグを設定して接続再計算をトリガー
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	# リセットしてアイテムを設定（on_entity_placedが空のタイルを追加するため）
	_belt_grid.set_item(Vector2i(5, 5), 1)

	_sut.tick()

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	var expected := BeltTransportSystem.SPEED_PER_TICK
	assert_float(tile.progress).is_between(expected - 0.0001, expected + 0.0001)


func test_tick_does_not_change_progress_on_empty_tile() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)

	_sut.tick()

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_float(tile.progress).is_equal(0.0)


func test_sixty_ticks_advances_progress_to_approximately_one() -> void:
	# 独立したシステムで1タイルのベルトテスト
	var grid2 := CoreGrid.new()
	var reg2 := EntityRegistry.create_default()
	var plac2 := PlacementSystem.new(grid2, reg2)
	var bg2 := BeltGrid.new()
	var sys2 := BeltTransportSystem.new(bg2, grid2, plac2)

	# ベルト配置（下流なし）
	sys2.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	bg2.set_item(Vector2i(5, 5), 1)

	# 60ティック処理
	for _i in range(60):
		sys2.tick()

	var tile := bg2.get_tile(Vector2i(5, 5))
	# 下流がないので1.0でクランプされて待機する
	assert_float(tile.progress).is_equal(1.0)


# =========================================================
# Task 4.2: アイテム転送の単体テスト
# =========================================================

func test_item_transfers_to_downstream_when_progress_reaches_one() -> void:
	# 2本の東向きベルトを接続
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	# 先頭ベルトにアイテムを配置、進行度を1.0手前に設定
	_belt_grid.set_item(Vector2i(5, 5), 42)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	# 1ティック処理で転送が発生するはず
	_sut.tick()

	# 元タイルは空
	var src_tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(src_tile.item_id).is_equal(0)
	assert_float(src_tile.progress).is_equal(0.0)

	# 先タイルにアイテムが転送された
	var dst_tile := _belt_grid.get_tile(Vector2i(6, 5))
	assert_int(dst_tile.item_id).is_equal(42)
	assert_float(dst_tile.progress).is_equal(0.0)


func test_item_transferred_exactly_once() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	_sut.tick()

	assert_int(_belt_grid.item_count()).is_equal(1)


func test_total_item_count_preserved_after_transfer() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	var before_count := _belt_grid.item_count()
	_sut.tick()
	var after_count := _belt_grid.item_count()

	assert_int(before_count).is_equal(1)
	assert_int(after_count).is_equal(1)


# =========================================================
# Task 4.3: 転送先なし・転送先満杯での待機テスト
# =========================================================

func test_item_waits_when_no_downstream() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5

	_sut.tick()

	# 転送先なし → progress = 1.0でクランプ、アイテムは保持
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_float(tile.progress).is_equal(1.0)
	assert_int(tile.item_id).is_equal(1)


func test_item_waits_when_downstream_is_full() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	# 両方にアイテムを配置
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0 - BeltTransportSystem.SPEED_PER_TICK * 0.5
	_belt_grid.set_item(Vector2i(6, 5), 2)

	_sut.tick()

	# 転送先満杯 → progress = 1.0でクランプ、アイテムは保持
	var src_tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_float(src_tile.progress).is_equal(1.0)
	assert_int(src_tile.item_id).is_equal(1)


func test_item_not_lost_while_waiting() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0

	# 複数ティック待機
	for _i in range(5):
		_sut.tick()

	# アイテムは消失しない
	assert_int(_belt_grid.item_count()).is_equal(1)
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(1)


# =========================================================
# Task 4.4で共通: BeltTransportSystem基本テスト
# =========================================================

func test_belt_transport_system_is_ref_counted() -> void:
	assert_object(_sut).is_instanceof(RefCounted)


func test_speed_per_tick_constant_is_correct() -> void:
	# 1秒/60tick = 1/60ティックあたりの進行度
	assert_float(BeltTransportSystem.SPEED_PER_TICK).is_between(0.0165, 0.0168)


func test_non_belt_entity_placement_is_ignored() -> void:
	# entity_type_id != 3 は無視される
	_sut.on_entity_placed(99, Vector2i(5, 5), Enums.Direction.E, 1)  # Minerは無視
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_false()


func test_non_belt_entity_removal_is_ignored() -> void:
	_belt_grid.add_tile(Vector2i(5, 5), Enums.Direction.E)
	# entity_type_id != 3 は無視される
	_sut.on_entity_removed(99, Vector2i(5, 5), 1)
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_true()
