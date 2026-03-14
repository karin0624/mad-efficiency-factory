extends GdUnitTestSuite

# Test: Machine Port I/O (Req 4.1, 4.2, 4.3, 4.4)
# Note: 機械ポートの詳細な接続解決は別機能のスコープ。
# 本テストではインターフェースベースの基本的な受け渡しを検証する。

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


# --- 機械出力ポートから隣接する空ベルトへアイテムが転送されることを検証 ---

func test_machine_output_to_empty_belt() -> void:
	# ベルト配置
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)

	# 機械出力ポートからベルトへの転送（インターフェース呼び出し）
	var result := _sut.receive_item_from_machine(Vector2i(5, 5), 10)
	assert_bool(result).is_true()

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(10)


func test_machine_output_to_full_belt_fails() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 1)  # ベルト満杯

	# 満杯のベルトへの転送は拒否される
	var result := _sut.receive_item_from_machine(Vector2i(5, 5), 10)
	assert_bool(result).is_false()

	# 元のアイテムは変更されない
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(1)


# --- ベルト末端から機械入力ポートへアイテムが引き渡されることを検証 ---

func test_belt_delivers_to_machine_input_when_at_end() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 42)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0

	# 機械入力ポートへの引き渡し（ベルトが受入可能な入力ポートに接続）
	var item_id := _sut.deliver_item_to_machine(Vector2i(5, 5))
	assert_int(item_id).is_equal(42)

	# ベルトからアイテムが除去された
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(0)


func test_deliver_returns_zero_when_no_item() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	# アイテムなし

	var item_id := _sut.deliver_item_to_machine(Vector2i(5, 5))
	assert_int(item_id).is_equal(0)


func test_deliver_returns_zero_when_progress_not_full() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 42)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 0.5  # まだ進行中

	# 進行度が1.0未満なら引き渡し不可
	var item_id := _sut.deliver_item_to_machine(Vector2i(5, 5))
	assert_int(item_id).is_equal(0)

	# アイテムはベルト上に保持
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(42)


# --- 機械入力ポート満杯時にバックプレッシャーが適用されることを検証 ---

func test_backpressure_when_machine_input_full() -> void:
	# ベルト末端でアイテムが待機（機械が受け入れない場合）
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 1)
	_belt_grid.get_tile(Vector2i(5, 5)).progress = 1.0

	# receive_item_from_machineを呼ばない（機械が受け入れない）
	# ティック処理でアイテムは保持されたまま
	for _i in range(10):
		_sut.tick()

	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.item_id).is_equal(1)
	assert_float(tile.progress).is_equal(1.0)


# --- 隣接ベルト満杯時に機械出力ポートからの転送が行われないことを検証 ---

func test_machine_output_blocked_when_belt_full() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 99)  # ベルト満杯

	# 転送できない
	var result := _sut.receive_item_from_machine(Vector2i(5, 5), 1)
	assert_bool(result).is_false()

	# アイテム総数変化なし
	assert_int(_belt_grid.item_count()).is_equal(1)
