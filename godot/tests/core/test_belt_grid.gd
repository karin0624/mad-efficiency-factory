extends GdUnitTestSuite

# Test: BeltGrid (Req 1.2, 5.4, 7.1, 7.2, 7.3)

var _sut: BeltGrid


func before_test() -> void:
	_sut = BeltGrid.new()


func after_test() -> void:
	_sut = null


# --- タイルの追加・削除・取得・存在チェック ---

func test_add_tile_then_has_tile_true() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	assert_bool(_sut.has_tile(Vector2i(5, 5))).is_true()


func test_has_tile_false_for_empty_grid() -> void:
	assert_bool(_sut.has_tile(Vector2i(5, 5))).is_false()


func test_get_tile_returns_belt_tile_data() -> void:
	_sut.add_tile(Vector2i(3, 3), Enums.Direction.N)
	var tile := _sut.get_tile(Vector2i(3, 3))
	assert_object(tile).is_instanceof(BeltTileData)


func test_get_tile_returns_correct_direction() -> void:
	_sut.add_tile(Vector2i(3, 3), Enums.Direction.S)
	var tile := _sut.get_tile(Vector2i(3, 3))
	assert_int(tile.direction).is_equal(Enums.Direction.S)


func test_get_tile_returns_null_for_missing_tile() -> void:
	var tile := _sut.get_tile(Vector2i(10, 10))
	assert_object(tile).is_null()


func test_remove_tile_then_has_tile_false() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.remove_tile(Vector2i(5, 5))
	assert_bool(_sut.has_tile(Vector2i(5, 5))).is_false()


func test_remove_nonexistent_tile_does_not_crash() -> void:
	# Should not crash
	_sut.remove_tile(Vector2i(99, 99))


# --- アイテムの設定・クリア ---

func test_set_item_on_empty_tile_returns_true() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	var result := _sut.set_item(Vector2i(5, 5), 1)
	assert_bool(result).is_true()


func test_set_item_sets_item_id_on_tile() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 42)
	var tile := _sut.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(42)


func test_set_item_on_occupied_tile_returns_false() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 1)
	var result := _sut.set_item(Vector2i(5, 5), 2)
	assert_bool(result).is_false()


func test_set_item_on_occupied_tile_does_not_overwrite() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 1)
	_sut.set_item(Vector2i(5, 5), 2)
	var tile := _sut.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(1)


func test_set_item_on_nonexistent_tile_returns_false() -> void:
	var result := _sut.set_item(Vector2i(99, 99), 1)
	assert_bool(result).is_false()


func test_clear_item_removes_item_from_tile() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 1)
	_sut.clear_item(Vector2i(5, 5))
	var tile := _sut.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(0)


func test_clear_item_resets_progress() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 1)
	_sut.get_tile(Vector2i(5, 5)).progress = 0.8
	_sut.clear_item(Vector2i(5, 5))
	var tile := _sut.get_tile(Vector2i(5, 5))
	assert_float(tile.progress).is_equal(0.0)


# --- カウントのクエリ ---

func test_tile_count_zero_initially() -> void:
	assert_int(_sut.tile_count()).is_equal(0)


func test_tile_count_increments_on_add() -> void:
	_sut.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_sut.add_tile(Vector2i(2, 2), Enums.Direction.N)
	assert_int(_sut.tile_count()).is_equal(2)


func test_tile_count_decrements_on_remove() -> void:
	_sut.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_sut.add_tile(Vector2i(2, 2), Enums.Direction.N)
	_sut.remove_tile(Vector2i(1, 1))
	assert_int(_sut.tile_count()).is_equal(1)


func test_item_count_zero_initially() -> void:
	assert_int(_sut.item_count()).is_equal(0)


func test_item_count_increments_when_item_set() -> void:
	_sut.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_sut.set_item(Vector2i(1, 1), 1)
	assert_int(_sut.item_count()).is_equal(1)


func test_item_count_decrements_when_item_cleared() -> void:
	_sut.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_sut.set_item(Vector2i(1, 1), 1)
	_sut.clear_item(Vector2i(1, 1))
	assert_int(_sut.item_count()).is_equal(0)


# --- 全ベルト座標の取得 ---

func test_get_all_positions_empty_grid() -> void:
	var positions := _sut.get_all_positions()
	assert_array(positions).has_size(0)


func test_get_all_positions_returns_added_tiles() -> void:
	_sut.add_tile(Vector2i(1, 1), Enums.Direction.E)
	_sut.add_tile(Vector2i(2, 2), Enums.Direction.N)
	var positions := _sut.get_all_positions()
	assert_array(positions).has_size(2)
	assert_array(positions).contains([Vector2i(1, 1), Vector2i(2, 2)])


# --- タイル削除時のアイテム消失 ---

func test_remove_tile_with_item_loses_item() -> void:
	_sut.add_tile(Vector2i(5, 5), Enums.Direction.E)
	_sut.set_item(Vector2i(5, 5), 1)
	assert_int(_sut.item_count()).is_equal(1)
	_sut.remove_tile(Vector2i(5, 5))
	assert_int(_sut.item_count()).is_equal(0)


func test_belt_grid_is_ref_counted() -> void:
	assert_object(_sut).is_instanceof(RefCounted)
