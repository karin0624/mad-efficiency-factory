class_name ItemCatalog
extends RefCounted


## ItemCatalog — アイテム定義の登録・検索を一元管理するカタログ
##
## SceneTree/Node APIに依存しない純粋なサービスクラス。
## Dictionaryを使用してID→ItemDefinitionのマッピングを管理し、
## 同一IDの重複登録を拒否し、存在しないIDでの検索はnullを返す。

## ID → ItemDefinition のマッピング
var _items: Dictionary = {}


## アイテム定義を登録する。
## Postconditions: 同一IDが未登録ならtrue、既に登録済みならfalseを返し既存を変更しない。
func register(definition: ItemDefinition) -> bool:
	if _items.has(definition.id):
		return false
	_items[definition.id] = definition
	return true


## IDからアイテム定義を検索する。
## Postconditions: 有効なIDならItemDefinitionを返す。無効なID（0含む）ならnullを返す。
func get_by_id(id: int) -> ItemDefinition:
	if id <= 0:
		return null
	return _items.get(id, null)


## 登録済みアイテム定義の数を返す。
func size() -> int:
	return _items.size()


## MVP初期データ（鉄鉱石・精錬鉄）が登録済みのカタログを生成する。
## Postconditions: ID=1(鉄鉱石)、ID=2(精錬鉄)が登録されたItemCatalogを返す。
static func create_default() -> ItemCatalog:
	var catalog := ItemCatalog.new()
	catalog.register(ItemDefinition.new(1, "鉄鉱石"))
	catalog.register(ItemDefinition.new(2, "精錬鉄"))
	return catalog
