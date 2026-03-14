extends GdUnitTestSuite

# Test: Placement/Removal Integration (Req 5.1, 5.2, 5.3, 5.4)

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


# --- ベルト配置通知でBeltGridにタイルが追加されることを検証 ---

func test_on_entity_placed_adds_belt_tile() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_true()


func test_on_entity_placed_sets_correct_direction() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.N, 3)
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_int(tile.direction).is_equal(Enums.Direction.N)


# --- ベルト撤去通知でBeltGridからタイルが削除されることを検証 ---

func test_on_entity_removed_removes_belt_tile() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_removed(1, Vector2i(5, 5), 3)
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_false()


# --- 撤去時にベルト上のアイテムが消失することを検証 ---

func test_on_entity_removed_loses_belt_item() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_belt_grid.set_item(Vector2i(5, 5), 99)
	assert_int(_belt_grid.item_count()).is_equal(1)

	_sut.on_entity_removed(1, Vector2i(5, 5), 3)
	assert_int(_belt_grid.item_count()).is_equal(0)


# --- ベルト以外のエンティティの通知が無視されることを検証 ---

func test_non_belt_entity_placement_ignored() -> void:
	# entity_type_id=1 (Miner) → 無視
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 1)
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_false()


func test_non_belt_entity_removal_ignored() -> void:
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)  # Belt配置
	# entity_type_id=2 (Smelter) の撤去通知 → 無視
	_sut.on_entity_removed(1, Vector2i(5, 5), 2)
	assert_bool(_belt_grid.has_tile(Vector2i(5, 5))).is_true()


# --- 配置/撤去後にダーティフラグが設定されることを検証（接続再計算の確認） ---

func test_placement_triggers_connection_rebuild() -> void:
	# 2本ベルト配置
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)

	# ティック処理で接続が再計算される（ダーティフラグがリセットされる）
	_sut.tick()

	# (5,5)が(6,5)に接続されていることを確認
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_true()
	assert_that(tile.downstream_pos).is_equal(Vector2i(6, 5))


func test_removal_triggers_connection_rebuild() -> void:
	# 2本ベルト配置
	_sut.on_entity_placed(1, Vector2i(5, 5), Enums.Direction.E, 3)
	_sut.on_entity_placed(2, Vector2i(6, 5), Enums.Direction.E, 3)
	_sut.tick()  # 初期接続

	# (6,5)を撤去
	_sut.on_entity_removed(2, Vector2i(6, 5), 3)
	_sut.tick()  # 接続再計算

	# (5,5)の下流接続が解除されていること
	var tile := _belt_grid.get_tile(Vector2i(5, 5))
	assert_bool(tile.has_downstream).is_false()
