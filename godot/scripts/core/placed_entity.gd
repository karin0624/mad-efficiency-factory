class_name PlacedEntity
extends RefCounted

## PlacedEntity — 配置済みエンティティの状態を保持する値オブジェクト
##
## 配置済みエンティティのメタデータ（entity_id, entity_type_id, 基準セル, 方向, フットプリント）を保持する。
## entity_idはPlacementSystemが採番する。
## SceneTree/Node APIに依存しない純粋な値オブジェクト。

var entity_id: int            ## 配置済みエンティティの一意ID
var entity_type_id: int       ## EntityDefinitionのID
var base_cell: Vector2i       ## 基準セル（フットプリントの左上）
var direction: int            ## Enums.Direction（N=0, E=1, S=2, W=3）
var footprint: Vector2i       ## フットプリントサイズ（EntityDefinitionから取得）


func _init(
	p_entity_id: int,
	p_entity_type_id: int,
	p_base_cell: Vector2i,
	p_direction: int,
	p_footprint: Vector2i
) -> void:
	entity_id = p_entity_id
	entity_type_id = p_entity_type_id
	base_cell = p_base_cell
	direction = p_direction
	footprint = p_footprint
