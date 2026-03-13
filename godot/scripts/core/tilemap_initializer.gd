class_name TilemapInitializer
extends RefCounted

const PATCH_COUNT: int = 5
const PATCH_MIN_SIZE: int = 3
const PATCH_MAX_SIZE: int = 5


func create_grid(seed_value: int) -> CoreGrid:
	var grid := CoreGrid.new()

	# Set all terrain to GROUND
	for y in range(grid.height):
		for x in range(grid.width):
			grid.set_terrain(Vector2i(x, y), Enums.TerrainType.GROUND)

	# Place iron ore patches using seeded RNG
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value

	for _i in range(PATCH_COUNT):
		var patch_w: int = rng.randi_range(PATCH_MIN_SIZE, PATCH_MAX_SIZE)
		var patch_h: int = rng.randi_range(PATCH_MIN_SIZE, PATCH_MAX_SIZE)
		# Ensure patch stays within grid bounds
		var px: int = rng.randi_range(0, grid.width - patch_w)
		var py: int = rng.randi_range(0, grid.height - patch_h)

		for dy in range(patch_h):
			for dx in range(patch_w):
				grid.set_resource(Vector2i(px + dx, py + dy), Enums.ResourceType.IRON_ORE)

	return grid
