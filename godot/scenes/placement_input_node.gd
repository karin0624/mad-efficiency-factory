class_name PlacementInputNode
extends Node2D

## PlacementInputNode — プレイヤー入力をPlacementSystemのメソッド呼び出しに変換するノード
##
## マウス位置からグリッドセル座標への変換を行う。
## 配置・撤去・回転の入力を処理し、PlacementSystemに委譲する。
## 配置・撤去の結果に応じてゴーストプレビューを更新する。
##
## Presentation層: 薄いアダプター。ロジックはPlacementSystemに委譲。

const CELL_SIZE: int = 64  # グリッドセルのピクセルサイズ

## 依存コンポーネント（外部から注入）
var placement_system: PlacementSystem = null
var ghost_preview: GhostPreviewNode = null

## 現在の状態
var _selected_entity_type_id: int = 0   ## 0 = 選択なし
var _current_direction: int = Enums.Direction.N
var _current_cell: Vector2i = Vector2i(-1, -1)


## エンティティ種別を選択する。
func select_entity(entity_type_id: int) -> void:
	_selected_entity_type_id = entity_type_id
	if placement_system == null or ghost_preview == null:
		return

	if entity_type_id <= 0:
		ghost_preview.set_entity_type(0, Vector2i(1, 1))
		return

	var def := placement_system._registry.get_definition(entity_type_id)
	if def != null:
		ghost_preview.set_entity_type(entity_type_id, def.footprint)


## 入力イベント処理
func _input(event: InputEvent) -> void:
	if placement_system == null:
		return

	# マウス移動: ゴースト位置を更新
	if event is InputEventMouseMotion:
		var cell := _pixel_to_cell(event.position)
		if cell != _current_cell:
			_current_cell = cell
			if ghost_preview != null:
				ghost_preview.update_target_cell(cell)

	# 左クリック: 配置
	elif event is InputEventMouseButton:
		var mouse_event := event as InputEventMouseButton
		if mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_LEFT:
			if _selected_entity_type_id > 0:
				_handle_place()

		# 右クリック: 撤去
		elif mouse_event.pressed and mouse_event.button_index == MOUSE_BUTTON_RIGHT:
			_handle_remove()

	# Rキー: 回転
	elif event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and key_event.keycode == KEY_R:
			_handle_rotate()


## 配置操作
func _handle_place() -> void:
	if _current_cell.x < 0 or _current_cell.y < 0:
		return
	var entity_id := placement_system.place(
		_selected_entity_type_id,
		_current_cell,
		_current_direction
	)
	if entity_id > 0:
		# 配置成功: ゴーストプレビューを更新
		if ghost_preview != null:
			ghost_preview.update_target_cell(_current_cell)


## 撤去操作
func _handle_remove() -> void:
	if _current_cell.x < 0 or _current_cell.y < 0:
		return
	placement_system.remove(_current_cell)
	if ghost_preview != null:
		ghost_preview.update_target_cell(_current_cell)


## 回転操作
func _handle_rotate() -> void:
	_current_direction = PlacementSystem.rotate_cw(_current_direction)
	# ゴーストプレビューを再描画（同じセルで有効性を再チェック）
	if ghost_preview != null and _current_cell.x >= 0:
		ghost_preview.update_target_cell(_current_cell)


## ピクセル座標をグリッドセル座標に変換する。
func _pixel_to_cell(pixel_pos: Vector2) -> Vector2i:
	return Vector2i(
		floori(pixel_pos.x) / CELL_SIZE,
		floori(pixel_pos.y) / CELL_SIZE
	)
