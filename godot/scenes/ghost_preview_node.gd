class_name GhostPreviewNode
extends Node2D

## GhostPreviewNode — 配置予定位置にゴースト（半透明）プレビューを描画するノード
##
## PlacementSystem.can_place()の結果に応じて緑色/赤色を切り替える。
## マウス移動に追従してゴースト位置を更新する。
## 選択中エンティティがない場合はゴーストを非表示にする。
##
## Presentation層: 薄いアダプター。ロジックはPlacementSystemに委譲。

const CELL_SIZE: int = 64  # グリッドセルのピクセルサイズ

## カラー定数
const COLOR_VALID := Color(0.0, 1.0, 0.0, 0.5)    # 緑半透明: 配置可能
const COLOR_INVALID := Color(1.0, 0.0, 0.0, 0.5)   # 赤半透明: 配置不可

## 依存コンポーネント（外部から注入）
var placement_system: PlacementSystem = null

## 現在の状態
var _current_entity_type_id: int = 0   ## 0 = 選択なし
var _current_cell: Vector2i = Vector2i(-1, -1)
var _current_footprint: Vector2i = Vector2i(1, 1)
var _is_valid: bool = false


## 選択中エンティティ種別を設定する。0を渡すとゴーストを非表示にする。
func set_entity_type(entity_type_id: int, footprint: Vector2i) -> void:
	_current_entity_type_id = entity_type_id
	_current_footprint = footprint
	visible = entity_type_id > 0
	queue_redraw()


## 対象セルを更新してゴーストを再描画する。
func update_target_cell(cell: Vector2i) -> void:
	_current_cell = cell
	_update_validity()
	queue_redraw()


## 有効/無効状態を更新する（PlacementSystem.can_place()を使用）。
func _update_validity() -> void:
	if placement_system == null or _current_entity_type_id <= 0:
		_is_valid = false
		return
	_is_valid = placement_system.can_place(_current_entity_type_id, _current_cell)


## ゴーストを描画する。
func _draw() -> void:
	if _current_entity_type_id <= 0:
		return

	var color := COLOR_VALID if _is_valid else COLOR_INVALID
	var pixel_pos := Vector2(_current_cell.x * CELL_SIZE, _current_cell.y * CELL_SIZE)
	var pixel_size := Vector2(_current_footprint.x * CELL_SIZE, _current_footprint.y * CELL_SIZE)

	draw_rect(Rect2(pixel_pos, pixel_size), color)
