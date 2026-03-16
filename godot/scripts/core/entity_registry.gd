class_name EntityRegistry
extends RefCounted

## EntityRegistry — エンティティ定義の登録・検索を一元管理するカタログ
##
## ItemCatalogパターンに準拠。
## ID→EntityDefinitionのマッピングを管理し、同一IDの重複登録を拒否する。
## MVP初期データの静的ファクトリメソッドを提供する。

## ID → EntityDefinition のマッピング
var _definitions: Dictionary = {}


## エンティティ定義を登録する。
## Postconditions: 同一IDが未登録ならtrue、既に登録済みならfalseを返し既存を変更しない。
func register(definition: EntityDefinition) -> bool:
	if _definitions.has(definition.id):
		return false
	_definitions[definition.id] = definition
	return true


## IDからエンティティ定義を検索する。
## Postconditions: 有効なIDならEntityDefinitionを返す。無効なID（0含む）ならnullを返す。
func get_definition(entity_type_id: int) -> EntityDefinition:
	if entity_type_id <= 0:
		return null
	return _definitions.get(entity_type_id, null)


## 登録済みエンティティ定義の数を返す。
func size() -> int:
	return _definitions.size()


## MVPデフォルトデータ（Miner:2x2, Smelter:2x2, Belt:1x1, DeliveryBox:1x1）が登録済みのレジストリを生成する。
## Postconditions: ID=1(Miner), ID=2(Smelter), ID=3(Belt), ID=4(DeliveryBox)が登録されたEntityRegistryを返す。
static func create_default() -> EntityRegistry:
	var registry := EntityRegistry.new()
	registry.register(EntityDefinition.new(1, "Miner", Vector2i(2, 2)))
	registry.register(EntityDefinition.new(2, "Smelter", Vector2i(2, 2)))
	registry.register(EntityDefinition.new(3, "Belt", Vector2i(1, 1)))
	registry.register(EntityDefinition.new(4, "DeliveryBox", Vector2i(1, 1)))
	return registry
