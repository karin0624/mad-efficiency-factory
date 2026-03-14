class_name EntityDefinition
extends RefCounted

## EntityDefinition — エンティティ種別の定義情報を保持する不変の値オブジェクト
##
## エンティティ種別のID、表示名、フットプリントサイズを保持する。
## SceneTree/Node APIに依存しない純粋な値オブジェクト。
## 生成後は不変（イミュータブル）として扱う。

var id: int              ## エンティティ種別の一意ID（正の整数、0は予約）
var display_name: String ## 表示名
var footprint: Vector2i  ## フットプリントサイズ（例: Vector2i(2, 2)）


func _init(p_id: int, p_display_name: String, p_footprint: Vector2i) -> void:
	id = p_id
	display_name = p_display_name
	footprint = p_footprint


## 定義が有効かどうかを検証する。
## Preconditions: id > 0, display_name != "", footprint.x > 0, footprint.y > 0
func is_valid() -> bool:
	if id <= 0:
		return false
	if display_name.is_empty():
		return false
	if footprint.x <= 0 or footprint.y <= 0:
		return false
	return true
