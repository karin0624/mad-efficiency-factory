extends GdUnitTestSuite

## L1テスト: GameStateDump の純粋ロジック検証


# --- null ガードテスト ---

func test_dump_tick_with_null_returns_empty() -> void:
	var dumper := GameStateDump.new()
	assert_str(dumper.dump_tick(null)).is_equal("")


func test_dump_belts_with_null_returns_empty() -> void:
	var dumper := GameStateDump.new()
	assert_str(dumper.dump_belts(null)).is_equal("")


func test_dump_placement_with_null_returns_empty() -> void:
	var dumper := GameStateDump.new()
	assert_str(dumper.dump_placement(null)).is_equal("")


func test_dump_ports_with_null_returns_empty() -> void:
	var dumper := GameStateDump.new()
	assert_str(dumper.dump_ports(null)).is_equal("")


func test_snapshot_with_all_null_does_not_crash() -> void:
	var dumper := GameStateDump.new()
	var result := dumper.snapshot(null, null, null, null)
	assert_str(result).contains("GAME STATE SNAPSHOT")


# --- 方向フォーマットテスト ---

func test_direction_format_n_e_s_w() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	grid.add_tile(Vector2i(0, 0), Enums.Direction.N)
	grid.add_tile(Vector2i(1, 0), Enums.Direction.E)
	grid.add_tile(Vector2i(2, 0), Enums.Direction.S)
	grid.add_tile(Vector2i(3, 0), Enums.Direction.W)

	var result := dumper.dump_belts(grid)
	assert_str(result).contains("dir=N")
	assert_str(result).contains("dir=E")
	assert_str(result).contains("dir=S")
	assert_str(result).contains("dir=W")


# --- アイテム名解決テスト ---

func test_item_name_with_catalog_shows_name() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	grid.add_tile(Vector2i(0, 0), Enums.Direction.N)
	grid.set_item(Vector2i(0, 0), 1)

	var catalog := ItemCatalog.create_default()
	var result := dumper.dump_belts(grid, catalog)
	assert_str(result).contains("鉄鉱石")


func test_item_name_without_catalog_shows_id() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	grid.add_tile(Vector2i(0, 0), Enums.Direction.N)
	grid.set_item(Vector2i(0, 0), 1)

	var result := dumper.dump_belts(grid, null)
	assert_str(result).contains("id:1")


func test_empty_tile_shows_none() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	grid.add_tile(Vector2i(0, 0), Enums.Direction.N)

	var result := dumper.dump_belts(grid)
	assert_str(result).contains("item=none")


# --- セクションヘッダーテスト ---

func test_output_contains_section_headers() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	var clock := TickClock.new()
	var core_grid := CoreGrid.new(64, 64)
	var registry := EntityRegistry.create_default()
	var system := PlacementSystem.new(core_grid, registry)
	var catalog := MachinePortCatalog.create_default()
	var port_grid := MachinePortGrid.new(catalog)

	var result := dumper.snapshot(grid, clock, system, port_grid)
	assert_str(result).contains("--- BELTS")
	assert_str(result).contains("--- MACHINES")
	assert_str(result).contains("--- PORTS")
	assert_str(result).contains("--- SUMMARY ---")
	assert_str(result).contains("--- TICK")


# --- サマリーモード閾値テスト ---

func test_summary_mode_when_exceeding_threshold() -> void:
	var dumper := GameStateDump.new(5)  # 閾値5
	var grid := BeltGrid.new()
	for i in range(10):
		grid.add_tile(Vector2i(i, 0), Enums.Direction.E)

	var result := dumper.dump_belts(grid)
	assert_str(result).contains("SUMMARY MODE")


func test_detail_mode_when_under_threshold() -> void:
	var dumper := GameStateDump.new(5)  # 閾値5
	var grid := BeltGrid.new()
	for i in range(3):
		grid.add_tile(Vector2i(i, 0), Enums.Direction.E)

	var result := dumper.dump_belts(grid)
	assert_str(result).not_contains("SUMMARY MODE")
	assert_str(result).contains("dir=E")


# --- 決定的順序テスト ---

func test_deterministic_output_order() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	# 逆順で追加
	grid.add_tile(Vector2i(5, 5), Enums.Direction.N)
	grid.add_tile(Vector2i(1, 1), Enums.Direction.E)
	grid.add_tile(Vector2i(3, 3), Enums.Direction.S)

	var result1 := dumper.dump_belts(grid)
	var result2 := dumper.dump_belts(grid)
	assert_str(result1).is_equal(result2)

	# (1,1) が (3,3) より先に来ること
	var idx1 := result1.find("(1,1)")
	var idx3 := result1.find("(3,3)")
	assert_bool(idx1 < idx3).is_true()


# --- snapshot デフォルト引数テスト ---

func test_snapshot_with_minimal_args() -> void:
	var dumper := GameStateDump.new()
	var grid := BeltGrid.new()
	var clock := TickClock.new()
	var core_grid := CoreGrid.new(64, 64)
	var registry := EntityRegistry.create_default()
	var system := PlacementSystem.new(core_grid, registry)
	var catalog := MachinePortCatalog.create_default()
	var port_grid := MachinePortGrid.new(catalog)

	# entity_registry と item_catalog を省略（デフォルトnull）
	var result := dumper.snapshot(grid, clock, system, port_grid)
	assert_str(result).contains("GAME STATE SNAPSHOT")
	assert_str(result).contains("tick=0")


# --- dump_tick テスト ---

func test_dump_tick_shows_current_state() -> void:
	var dumper := GameStateDump.new()
	var clock := TickClock.new()
	clock.advance(16667 * 5)  # 5 ticks

	var result := dumper.dump_tick(clock)
	assert_str(result).contains("tick=5")
	assert_str(result).contains("paused=false")


func test_dump_tick_shows_paused() -> void:
	var dumper := GameStateDump.new()
	var clock := TickClock.new()
	clock.pause()

	var result := dumper.dump_tick(clock)
	assert_str(result).contains("paused=true")


# --- dump_placement テスト ---

func test_dump_placement_shows_entity_name() -> void:
	var dumper := GameStateDump.new()
	var core_grid := CoreGrid.new(64, 64)
	var registry := EntityRegistry.create_default()
	var system := PlacementSystem.new(core_grid, registry)

	system.place(1, Vector2i(0, 0), Enums.Direction.N)  # Miner
	system.place(2, Vector2i(4, 0), Enums.Direction.E)  # Smelter

	var result := dumper.dump_placement(system, registry)
	assert_str(result).contains("Miner")
	assert_str(result).contains("Smelter")


func test_dump_placement_without_registry_shows_type_id() -> void:
	var dumper := GameStateDump.new()
	var core_grid := CoreGrid.new(64, 64)
	var registry := EntityRegistry.create_default()
	var system := PlacementSystem.new(core_grid, registry)

	system.place(1, Vector2i(0, 0), Enums.Direction.N)

	var result := dumper.dump_placement(system, null)
	assert_str(result).contains("type:1")
