extends GdUnitTestSuite

# Test: PortMath — ポートオフセットと方向の回転計算 (Req 1.3, 1.4)

## タスク1.1: ポートオフセットと方向の回転計算テスト


func test_rotate_offset_north_no_change() -> void:
	# 北向き（direction=0）は変化なし
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.N)
	assert_that(result).is_equal(Vector2i(1, 1))


func test_rotate_offset_east_2x2() -> void:
	# 東向き: (x,y) → (size_y-1-y, x)
	# offset=(1,1), size=(2,2): (2-1-1, 1) = (0, 1)
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.E)
	assert_that(result).is_equal(Vector2i(0, 1))


func test_rotate_offset_south_2x2() -> void:
	# 南向き: (x,y) → (size_x-1-x, size_y-1-y)
	# offset=(1,1), size=(2,2): (2-1-1, 2-1-1) = (0, 0)
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.S)
	assert_that(result).is_equal(Vector2i(0, 0))


func test_rotate_offset_west_2x2() -> void:
	# 西向き: (x,y) → (y, size_x-1-x)
	# offset=(1,1), size=(2,2): (1, 2-1-1) = (1, 0)
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.W)
	assert_that(result).is_equal(Vector2i(1, 0))


func test_rotate_offset_four_rotations_returns_original() -> void:
	# 4回同方向に回転すると元に戻ることを検証
	var original := Vector2i(1, 0)
	var size := Vector2i(2, 2)
	var result := original
	for _i in range(4):
		result = PortMath.rotate_offset(result, size, Enums.Direction.E)
	assert_that(result).is_equal(original)


func test_rotate_offset_miner_output_north() -> void:
	# 採掘機北向き: 出力ポートoffset=(1,1), 変化なし
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.N)
	assert_that(result).is_equal(Vector2i(1, 1))


func test_rotate_offset_miner_output_east() -> void:
	# 採掘機東向き: 出力ポートoffset=(1,1)がどうなるか
	# E: (size_y-1-y, x) = (2-1-1, 1) = (0, 1)
	var result := PortMath.rotate_offset(Vector2i(1, 1), Vector2i(2, 2), Enums.Direction.E)
	assert_that(result).is_equal(Vector2i(0, 1))


func test_rotate_direction_north_no_change() -> void:
	# 機械が北向きなら方向変化なし
	var result := PortMath.rotate_direction(Enums.Direction.S, Enums.Direction.N)
	assert_int(result).is_equal(Enums.Direction.S)


func test_rotate_direction_east() -> void:
	# 機械が東向き: ポート方向が1回時計回り
	var result := PortMath.rotate_direction(Enums.Direction.S, Enums.Direction.E)
	assert_int(result).is_equal(Enums.Direction.W)


func test_rotate_direction_south() -> void:
	# 機械が南向き: ポート方向が2回時計回り（180度回転）
	var result := PortMath.rotate_direction(Enums.Direction.S, Enums.Direction.S)
	assert_int(result).is_equal(Enums.Direction.N)


func test_rotate_direction_west() -> void:
	# 機械が西向き: ポート方向が3回時計回り
	var result := PortMath.rotate_direction(Enums.Direction.S, Enums.Direction.W)
	assert_int(result).is_equal(Enums.Direction.E)


func test_rotate_direction_four_rotations_identity() -> void:
	# ポート方向を4回E回転すると元に戻る
	var original := Enums.Direction.N
	var result := original
	for _i in range(4):
		result = PortMath.rotate_direction(result, Enums.Direction.E)
	assert_int(result).is_equal(original)


func test_direction_to_vector_north() -> void:
	# N → (0, -1)（Y軸下向き座標系）
	var result := PortMath.direction_to_vector(Enums.Direction.N)
	assert_that(result).is_equal(Vector2i(0, -1))


func test_direction_to_vector_east() -> void:
	# E → (1, 0)
	var result := PortMath.direction_to_vector(Enums.Direction.E)
	assert_that(result).is_equal(Vector2i(1, 0))


func test_direction_to_vector_south() -> void:
	# S → (0, 1)
	var result := PortMath.direction_to_vector(Enums.Direction.S)
	assert_that(result).is_equal(Vector2i(0, 1))


func test_direction_to_vector_west() -> void:
	# W → (-1, 0)
	var result := PortMath.direction_to_vector(Enums.Direction.W)
	assert_that(result).is_equal(Vector2i(-1, 0))


func test_get_connected_position_south() -> void:
	# ポート位置=(3,3), 方向=S → 接続先=(3,4)
	var result := PortMath.get_connected_position(Vector2i(3, 3), Enums.Direction.S)
	assert_that(result).is_equal(Vector2i(3, 4))


func test_get_connected_position_north() -> void:
	# ポート位置=(3,3), 方向=N → 接続先=(3,2)
	var result := PortMath.get_connected_position(Vector2i(3, 3), Enums.Direction.N)
	assert_that(result).is_equal(Vector2i(3, 2))


func test_get_connected_position_east() -> void:
	# ポート位置=(3,3), 方向=E → 接続先=(4,3)
	var result := PortMath.get_connected_position(Vector2i(3, 3), Enums.Direction.E)
	assert_that(result).is_equal(Vector2i(4, 3))


func test_get_connected_position_west() -> void:
	# ポート位置=(3,3), 方向=W → 接続先=(2,3)
	var result := PortMath.get_connected_position(Vector2i(3, 3), Enums.Direction.W)
	assert_that(result).is_equal(Vector2i(2, 3))
