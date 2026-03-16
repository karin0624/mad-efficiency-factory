extends GdUnitTestSuite

## GhostPreviewNode のL2テスト
## ゴーストプレビューノードの状態変化を検証する
## 注: 範囲外検証にはテスト専用2x2エンティティ(ID=99)を使用。

const TEST_2X2_ID: int = 99

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem
var _ghost: GhostPreviewNode


func before_test() -> void:
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_registry.register(EntityDefinition.new(TEST_2X2_ID, "TestLarge", Vector2i(2, 2)))
	_system = PlacementSystem.new(_grid, _registry)
	_ghost = auto_free(GhostPreviewNode.new())
	_ghost.placement_system = _system
	add_child(_ghost)


func after_test() -> void:
	_system = null
	_registry = null
	_grid = null
	# _ghost は auto_free() で自動解放


func test_ghost_hidden_when_no_entity_selected() -> void:
	# デフォルト状態（entity_type_id=0）はゴーストを非表示
	_ghost.set_entity_type(0, Vector2i(1, 1))
	assert_bool(_ghost.visible).is_false()


func test_ghost_visible_when_entity_selected() -> void:
	_ghost.set_entity_type(3, Vector2i(1, 1))  # Belt(1x1)
	assert_bool(_ghost.visible).is_true()


func test_ghost_valid_when_cell_is_empty() -> void:
	_ghost.set_entity_type(3, Vector2i(1, 1))
	_ghost.update_target_cell(Vector2i(0, 0))
	# 空セルは配置可能 → _is_valid = true
	assert_bool(_ghost._is_valid).is_true()


func test_ghost_invalid_when_cell_is_occupied() -> void:
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	_ghost.set_entity_type(3, Vector2i(1, 1))
	_ghost.update_target_cell(Vector2i(5, 5))
	# 占有済みセルは配置不可 → _is_valid = false
	assert_bool(_ghost._is_valid).is_false()


func test_ghost_invalid_when_out_of_bounds() -> void:
	# テスト専用2x2エンティティ: (63,63)に配置すると範囲外
	_ghost.set_entity_type(TEST_2X2_ID, Vector2i(2, 2))
	_ghost.update_target_cell(Vector2i(63, 63))
	# 範囲外は配置不可 → _is_valid = false
	assert_bool(_ghost._is_valid).is_false()


func test_ghost_updates_validity_on_cell_change() -> void:
	_system.place(3, Vector2i(5, 5), Enums.Direction.N)
	_ghost.set_entity_type(3, Vector2i(1, 1))
	# 有効セルに更新
	_ghost.update_target_cell(Vector2i(0, 0))
	assert_bool(_ghost._is_valid).is_true()
	# 占有セルに更新
	_ghost.update_target_cell(Vector2i(5, 5))
	assert_bool(_ghost._is_valid).is_false()
