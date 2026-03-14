extends GdUnitTestSuite

# Test: BeltTileData (Req 1.1, 1.2, 1.3, 1.4)

var _sut: BeltTileData


func before_test() -> void:
	_sut = BeltTileData.new(Enums.Direction.E)


func after_test() -> void:
	_sut = null


# --- 初期値の検証 ---

func test_initial_direction_is_set() -> void:
	assert_int(_sut.direction).is_equal(Enums.Direction.E)


func test_initial_item_id_is_zero() -> void:
	assert_int(_sut.item_id).is_equal(0)


func test_initial_progress_is_zero() -> void:
	assert_float(_sut.progress).is_equal(0.0)


func test_initial_has_downstream_is_false() -> void:
	assert_bool(_sut.has_downstream).is_false()


func test_initial_downstream_pos_is_default() -> void:
	# downstream_pos is Vector2i, default value is Vector2i.ZERO when has_downstream is false
	assert_that(_sut.downstream_pos).is_equal(Vector2i.ZERO)


func test_direction_north() -> void:
	var tile := BeltTileData.new(Enums.Direction.N)
	assert_int(tile.direction).is_equal(Enums.Direction.N)


func test_direction_south() -> void:
	var tile := BeltTileData.new(Enums.Direction.S)
	assert_int(tile.direction).is_equal(Enums.Direction.S)


func test_direction_west() -> void:
	var tile := BeltTileData.new(Enums.Direction.W)
	assert_int(tile.direction).is_equal(Enums.Direction.W)


# --- アイテムの設定・クリア ---

func test_set_item_sets_item_id() -> void:
	_sut.set_item(5)
	assert_int(_sut.item_id).is_equal(5)


func test_set_item_resets_progress_to_zero() -> void:
	_sut.set_item(3)
	assert_float(_sut.progress).is_equal(0.0)


func test_clear_item_resets_item_id_to_zero() -> void:
	_sut.set_item(5)
	_sut.clear_item()
	assert_int(_sut.item_id).is_equal(0)


func test_clear_item_resets_progress_to_zero() -> void:
	_sut.set_item(5)
	_sut.progress = 0.7
	_sut.clear_item()
	assert_float(_sut.progress).is_equal(0.0)


func test_has_item_true_when_item_id_nonzero() -> void:
	_sut.set_item(1)
	assert_bool(_sut.has_item()).is_true()


func test_has_item_false_when_item_id_zero() -> void:
	assert_bool(_sut.has_item()).is_false()


# --- 進行度の範囲保持 ---

func test_progress_can_be_set_to_zero() -> void:
	_sut.set_item(1)
	_sut.progress = 0.0
	assert_float(_sut.progress).is_equal(0.0)


func test_progress_can_be_set_to_one() -> void:
	_sut.set_item(1)
	_sut.progress = 1.0
	assert_float(_sut.progress).is_equal(1.0)


func test_progress_can_be_set_to_midpoint() -> void:
	_sut.set_item(1)
	_sut.progress = 0.5
	assert_float(_sut.progress).is_between(0.49, 0.51)


# --- 下流接続情報の設定・取得 ---

func test_set_downstream_sets_has_downstream_true() -> void:
	_sut.set_downstream(Vector2i(5, 3))
	assert_bool(_sut.has_downstream).is_true()


func test_set_downstream_sets_position() -> void:
	_sut.set_downstream(Vector2i(5, 3))
	assert_that(_sut.downstream_pos).is_equal(Vector2i(5, 3))


func test_clear_downstream_sets_has_downstream_false() -> void:
	_sut.set_downstream(Vector2i(5, 3))
	_sut.clear_downstream()
	assert_bool(_sut.has_downstream).is_false()


func test_belt_tile_data_is_ref_counted() -> void:
	assert_object(_sut).is_instanceof(RefCounted)
