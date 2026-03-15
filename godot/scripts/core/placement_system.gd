class_name PlacementSystem
extends RefCounted

## PlacementSystem — 配置・撤去・回転のビジネスロジックを統合する中核システム
##
## エンティティの配置（フットプリント検証 → CoreGrid占有 → PlacedEntity記録）、
## エンティティの撤去（entity_id特定 → CoreGrid解放 → PlacedEntity削除）、
## 配置可否の問い合わせ（ゴーストプレビュー用）、
## 回転方向の管理（選択中エンティティの方向切り替え）を行う。
##
## PlacementSystemを経由しないCoreGrid直接操作を許容しない設計。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## 内部カウンタとストレージ
var _next_entity_id: int = 1
var _entities: Dictionary = {}  # entity_id -> PlacedEntity

## 依存コンポーネント
var _grid: CoreGrid
var _registry: EntityRegistry


func _init(grid: CoreGrid, registry: EntityRegistry) -> void:
	_grid = grid
	_registry = registry


## エンティティを配置する。
## Preconditions: entity_type_id はEntityRegistryに登録済み
## Postconditions:
##   成功時: entity_id (正の整数) を返す。CoreGridの該当セルが占有される。PlacedEntityが記録される。
##   失敗時: 0 を返す。CoreGridの状態は変更されない。
## 失敗条件: フットプリント内にグリッド範囲外または占有済みセルが存在する、またはentity_type_idが未登録
func place(entity_type_id: int, base_cell: Vector2i, direction: int) -> int:
	var def := _registry.get_definition(entity_type_id)
	if def == null:
		return 0

	var entity_id := _next_entity_id
	var success := _grid.occupy_rect(base_cell, def.footprint, entity_id)
	if not success:
		return 0

	_next_entity_id += 1
	var entity := PlacedEntity.new(entity_id, entity_type_id, base_cell, direction, def.footprint)
	_entities[entity_id] = entity
	return entity_id


## セル座標を指定して配置済みエンティティを撤去する。
## Postconditions:
##   エンティティ存在時: true。CoreGridの該当セルが解放される。PlacedEntityが削除される。
##   エンティティなし時: false。CoreGridの状態は変更されない。
func remove(cell: Vector2i) -> bool:
	var entity_id := _grid.get_occupying_entity(cell)
	if entity_id == 0:
		return false

	var entity: PlacedEntity = _entities.get(entity_id, null)
	if entity == null:
		return false

	_grid.vacate_rect(entity.base_cell, entity.footprint)
	_entities.erase(entity_id)
	return true


## 配置可否を判定するクエリメソッド（副作用なし）。
## Postconditions: フットプリント全体が空きかつグリッド範囲内ならtrue、それ以外false
func can_place(entity_type_id: int, base_cell: Vector2i) -> bool:
	var def := _registry.get_definition(entity_type_id)
	if def == null:
		return false

	for y in range(base_cell.y, base_cell.y + def.footprint.y):
		for x in range(base_cell.x, base_cell.x + def.footprint.x):
			var pos := Vector2i(x, y)
			if not _grid.is_in_bounds(pos):
				return false
			if _grid.is_occupied(pos):
				return false
	return true


## entity_idから配置済みエンティティを取得する。
## Postconditions: 有効IDならPlacedEntity、無効ならnull
func get_placed_entity(entity_id: int) -> PlacedEntity:
	return _entities.get(entity_id, null)


## セル座標から配置済みエンティティを取得する。
## Postconditions: 占有セルならPlacedEntity、未占有ならnull
func get_entity_at(cell: Vector2i) -> PlacedEntity:
	var entity_id := _grid.get_occupying_entity(cell)
	if entity_id == 0:
		return null
	return _entities.get(entity_id, null)


## 全配置済みエンティティを取得する。
## Postconditions: PlacedEntityの配列を返す（読み取り専用）
func get_all_entities() -> Array:
	return _entities.values()


## 時計回りに回転方向を切り替える（N→E→S→W→N）。
## Postconditions: (direction + 1) % 4 を返す
static func rotate_cw(direction: int) -> int:
	return (direction + 1) % 4
