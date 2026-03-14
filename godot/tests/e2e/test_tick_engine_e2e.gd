extends GdUnitTestSuite

## E2E Tests for Tick Engine — Task 4.1 (High-load FPS), Task 4.2 (Pause/Resume Response)
## Requirements: 8.1, 8.2, 4.1, 4.4

const BELT_TYPE_ID := 3
const TARGET_BELT_COUNT := 500
const TARGET_ITEM_COUNT := 2000


func _setup_high_load(scene_root: Node) -> Dictionary:
	var belt_transport: BeltTransportSystem = scene_root._belt_transport
	var belt_grid: BeltGrid = scene_root._belt_grid

	# Place 500 belts in rows (8 rows × 63 cols max)
	var belt_count := 0
	var entity_id := 1000
	for row in range(8):
		for col in range(63):
			if belt_count >= TARGET_BELT_COUNT:
				break
			belt_transport.on_entity_placed(
				entity_id, Vector2i(col, row), Enums.Direction.E, BELT_TYPE_ID
			)
			entity_id += 1
			belt_count += 1

	# Initialize connections via first tick
	belt_transport.tick()

	# Place items on all available belts
	var item_count := 0
	for pos in belt_grid.get_all_positions():
		if item_count >= TARGET_ITEM_COUNT:
			break
		if belt_grid.set_item(pos, 1):
			item_count += 1

	var result := {"belts": belt_grid.tile_count(), "items": belt_grid.item_count()}
	print("[E2E] Setup: belts=%d items=%d" % [result.belts, result.items])
	return result


func _save_screenshot(scene_root: Node, filename: String) -> void:
	DirAccess.make_dir_recursive_absolute("res://test_screenshots")
	var viewport := scene_root.get_viewport()
	if viewport and viewport.get_texture():
		var img := viewport.get_texture().get_image()
		if img:
			img.save_png("res://test_screenshots/%s" % filename)
			print("[E2E] Screenshot: test_screenshots/%s" % filename)


# --- Task 4.1: High-load FPS measurement ---

func test_e2e_high_load_fps() -> void:
	var runner := scene_runner("res://scenes/factory_placement.tscn")
	await runner.simulate_frames(2)

	var scene_root := runner.scene()
	var counts := _setup_high_load(scene_root)

	assert_int(counts.belts).is_equal(TARGET_BELT_COUNT)

	# Measure effective FPS over 120 simulated frames
	var frame_count := 120
	var start_usec := Time.get_ticks_usec()
	await runner.simulate_frames(frame_count)
	var elapsed_usec := Time.get_ticks_usec() - start_usec
	var elapsed_sec := elapsed_usec / 1_000_000.0
	var effective_fps := frame_count / elapsed_sec

	print("[E2E 4.1] Frames=%d Elapsed=%.3fs EffectiveFPS=%.1f" % [frame_count, elapsed_sec, effective_fps])
	print("[E2E 4.1] RESULT: %s (FPS >= 30)" % ["PASS" if effective_fps >= 30.0 else "FAIL"])

	await runner.simulate_frames(1)
	_save_screenshot(scene_root, "high_load_fps.png")

	assert_float(effective_fps).is_greater_equal(30.0)


# --- Task 4.2: Pause/Resume response time ---

func test_e2e_pause_resume_response_time() -> void:
	var runner := scene_runner("res://scenes/factory_placement.tscn")
	await runner.simulate_frames(2)

	var scene_root := runner.scene()
	_setup_high_load(scene_root)

	var tick_engine: TickEngineNode = scene_root._tick_engine
	var clock: TickClock = tick_engine.clock

	var max_pause_ms := 0.0
	var max_resume_ms := 0.0

	# 10 continuous pause/resume cycles
	for i in range(10):
		# Measure pause() response time
		var t0 := Time.get_ticks_usec()
		clock.pause()
		var pause_usec := Time.get_ticks_usec() - t0
		var pause_ms := pause_usec / 1000.0

		await runner.simulate_frames(3)

		# Measure resume() response time
		t0 = Time.get_ticks_usec()
		clock.resume()
		var resume_usec := Time.get_ticks_usec() - t0
		var resume_ms := resume_usec / 1000.0

		await runner.simulate_frames(3)

		max_pause_ms = maxf(max_pause_ms, pause_ms)
		max_resume_ms = maxf(max_resume_ms, resume_ms)

		print("[E2E 4.2] Cycle %d: pause=%.3fms resume=%.3fms" % [i + 1, pause_ms, resume_ms])

	print("[E2E 4.2] Max: pause=%.3fms resume=%.3fms" % [max_pause_ms, max_resume_ms])
	print("[E2E 4.2] RESULT: %s (< 100ms)" % [
		"PASS" if max_pause_ms < 100.0 and max_resume_ms < 100.0 else "FAIL"
	])

	await runner.simulate_frames(1)
	_save_screenshot(scene_root, "pause_resume_response.png")

	assert_float(max_pause_ms).is_less(100.0)
	assert_float(max_resume_ms).is_less(100.0)
