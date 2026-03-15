class_name GridCellData
extends RefCounted

var terrain: int    # Enums.TerrainType
var resource: int   # Enums.ResourceType
var occupying_entity: int  # Entity ID (0 = unoccupied)


func _init(
	p_terrain: int = Enums.TerrainType.EMPTY,
	p_resource: int = Enums.ResourceType.NONE,
	p_occupying_entity: int = 0,
) -> void:
	terrain = p_terrain
	resource = p_resource
	occupying_entity = p_occupying_entity
