class_name ItemDefinition
extends RefCounted


## ItemDefinition — アイテム種別の定義情報を保持する値オブジェクト
##
## SceneTree/Node APIに依存しない純粋なデータ構造として実装。
## 一意な正の整数IDと空でない表示名を不変の属性として保持する。
## ID=0は予約値（アイテムなし）として扱い、有効なアイテム定義に割り当てない。

## アイテム種別の一意な正の整数ID（ID=0は予約値）
var id: int

## アイテムの表示名（空でない文字列）
var display_name: String


## アイテム定義を生成する。
## Preconditions: p_id > 0, p_display_name is not empty
func _init(p_id: int, p_display_name: String) -> void:
	assert(p_id > 0, "ItemDefinition: id must be a positive integer (got %d)" % p_id)
	assert(p_display_name != "", "ItemDefinition: display_name must not be empty")
	id = p_id
	display_name = p_display_name
