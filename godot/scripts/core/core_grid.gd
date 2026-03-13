class_name CoreGrid
extends RefCounted

# --- Constants ---
const GRID_WIDTH: int = 64
const GRID_HEIGHT: int = 64
const GRID_SIZE: int = GRID_WIDTH * GRID_HEIGHT  # 4096

# --- Properties ---
var width: int:
	get: return _width
var height: int:
	get: return _height

# --- Internal Storage ---
var _width: int = GRID_WIDTH
var _height: int = GRID_HEIGHT
var _terrain: PackedInt32Array  # size: 4096, zero-initialized (EMPTY=0)
var _resource: PackedInt32Array  # size: 4096, zero-initialized (NONE=0)
var _occupancy: Dictionary = {}  # Vector2i -> int (entity_id)


func _init() -> void:
	_terrain = PackedInt32Array()
	_terrain.resize(GRID_SIZE)
	_resource = PackedInt32Array()
	_resource.resize(GRID_SIZE)


# --- Index calculation ---
func _index(pos: Vector2i) -> int:
	return pos.y * _width + pos.x


# --- Query Methods ---

func is_in_bounds(pos: Vector2i) -> bool:
	return pos.x >= 0 and pos.x < _width and pos.y >= 0 and pos.y < _height


func get_terrain(pos: Vector2i) -> int:
	if not is_in_bounds(pos):
		return Enums.TerrainType.EMPTY
	return _terrain[_index(pos)]


func get_resource(pos: Vector2i) -> int:
	if not is_in_bounds(pos):
		return Enums.ResourceType.NONE
	return _resource[_index(pos)]


func is_occupied(pos: Vector2i) -> bool:
	return _occupancy.has(pos)


func get_occupying_entity(pos: Vector2i) -> int:
	if _occupancy.has(pos):
		return _occupancy[pos]
	return 0


func get_cell(pos: Vector2i) -> GridCellData:
	return GridCellData.new(
		get_terrain(pos),
		get_resource(pos),
		get_occupying_entity(pos)
	)


func get_adjacent(pos: Vector2i) -> Array[Vector2i]:
	var result: Array[Vector2i] = []
	var candidates: Array[Vector2i] = [
		Vector2i(pos.x, pos.y - 1),  # North
		Vector2i(pos.x, pos.y + 1),  # South
		Vector2i(pos.x - 1, pos.y),  # West
		Vector2i(pos.x + 1, pos.y),  # East
	]
	for c in candidates:
		if is_in_bounds(c):
			result.append(c)
	return result


# --- Mutation Methods ---

func set_terrain(pos: Vector2i, terrain: int) -> void:
	if not is_in_bounds(pos):
		return
	_terrain[_index(pos)] = terrain


func set_resource(pos: Vector2i, resource: int) -> void:
	if not is_in_bounds(pos):
		return
	_resource[_index(pos)] = resource


func occupy(pos: Vector2i, entity_id: int) -> bool:
	if not is_in_bounds(pos):
		return false
	if _occupancy.has(pos):
		return false
	_occupancy[pos] = entity_id
	return true


func occupy_rect(origin: Vector2i, size: Vector2i, entity_id: int) -> bool:
	# Pass 1: Validate all cells
	for y in range(origin.y, origin.y + size.y):
		for x in range(origin.x, origin.x + size.x):
			var pos := Vector2i(x, y)
			if not is_in_bounds(pos):
				return false
			if _occupancy.has(pos):
				return false
	# Pass 2: Commit all cells
	for y in range(origin.y, origin.y + size.y):
		for x in range(origin.x, origin.x + size.x):
			_occupancy[Vector2i(x, y)] = entity_id
	return true


func vacate(pos: Vector2i) -> void:
	_occupancy.erase(pos)


func vacate_rect(origin: Vector2i, size: Vector2i) -> void:
	for y in range(origin.y, origin.y + size.y):
		for x in range(origin.x, origin.x + size.x):
			_occupancy.erase(Vector2i(x, y))
