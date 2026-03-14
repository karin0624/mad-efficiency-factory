class_name BeltTileData
extends RefCounted

## BeltTileData — ベルトタイル1つの状態を保持する値オブジェクト
##
## 方向（Enums.Direction）、保持アイテムのアイテム種別ID（0=なし）、
## 進行度（0.0〜1.0）、下流接続情報を保持する。
## RefCountedベース、SceneTree非依存の純粋な値オブジェクト。

## 搬送方向（Enums.Direction: N=0, E=1, S=2, W=3）
var direction: int

## 保持中のアイテム種別ID（0=空、正整数=アイテム保持中）
var item_id: int = 0

## アイテムの進行度（0.0=タイル入口、1.0=タイル出口）
var progress: float = 0.0

## 下流ベルトの座標（has_downstreamがtrueの時のみ有効）
var downstream_pos: Vector2i = Vector2i.ZERO

## 下流接続の有無
var has_downstream: bool = false


func _init(p_direction: int) -> void:
	direction = p_direction


## アイテムを設定する（進行度は0.0にリセット）
func set_item(p_item_id: int) -> void:
	item_id = p_item_id
	progress = 0.0


## アイテムをクリアする（item_id=0, progress=0.0にリセット）
func clear_item() -> void:
	item_id = 0
	progress = 0.0


## アイテムを保持しているかどうかを返す
func has_item() -> bool:
	return item_id > 0


## 下流接続を設定する
func set_downstream(pos: Vector2i) -> void:
	downstream_pos = pos
	has_downstream = true


## 下流接続をクリアする
func clear_downstream() -> void:
	has_downstream = false
