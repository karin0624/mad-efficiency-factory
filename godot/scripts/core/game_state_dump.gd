class_name GameStateDump
extends RefCounted

## GameStateDump — ゲーム状態を構造化テキストに変換するユーティリティ
##
## 各サブシステム（BeltGrid, TickClock, PlacementSystem, MachinePortGrid）の
## 状態を人間可読かつLLM効率的なテキストフォーマットに変換する。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## 方向の文字列表現
const DIR_NAMES: Array[String] = ["N", "E", "S", "W"]

## 詳細表示の最大アイテム数（超過時はサマリーモード）
var _max_detail_items: int = 20


func _init(max_detail: int = 20) -> void:
	_max_detail_items = max_detail


## 全サブシステムの状態をスナップショットとして出力する
## entity_registry と item_catalog はオプショナル（null時はID表示/空セクション）
func snapshot(
	belt_grid: BeltGrid,
	tick_clock: TickClock,
	placement: PlacementSystem,
	port_grid: MachinePortGrid,
	entity_registry: EntityRegistry = null,
	item_catalog: ItemCatalog = null,
) -> String:
	var parts: Array[String] = []

	var tick_str := "N/A"
	var paused_str := "N/A"
	if tick_clock != null:
		tick_str = str(tick_clock.current_tick)
		paused_str = str(tick_clock.is_paused)

	parts.append("=== GAME STATE SNAPSHOT (tick=%s, paused=%s) ===" % [tick_str, paused_str])
	parts.append("")
	parts.append(dump_tick(tick_clock))
	parts.append(dump_belts(belt_grid, item_catalog))
	parts.append(dump_placement(placement, entity_registry))
	parts.append(dump_ports(port_grid, item_catalog))
	parts.append(dump_summary(belt_grid, port_grid, placement))

	return "\n".join(parts)


## TickClock の状態をダンプする
func dump_tick(clock: TickClock) -> String:
	if clock == null:
		return ""
	return "--- TICK (tick=%d, paused=%s) ---" % [clock.current_tick, str(clock.is_paused)]


## BeltGrid の状態をダンプする
func dump_belts(grid: BeltGrid, catalog: ItemCatalog = null) -> String:
	if grid == null:
		return ""

	var tile_ct := grid.tile_count()
	var item_ct := grid.item_count()
	var header := "--- BELTS (%d tiles, %d items) ---" % [tile_ct, item_ct]

	if tile_ct == 0:
		return header + "\n  (empty)"

	if tile_ct > _max_detail_items:
		return header + "\n  [SUMMARY MODE: tile_count=%d, item_count=%d]" % [tile_ct, item_ct]

	# 詳細モード: positionでソート
	var positions := grid.get_all_positions()
	positions.sort()

	var lines: Array[String] = [header]
	for pos: Vector2i in positions:
		var tile := grid.get_tile(pos)
		if tile == null:
			continue
		var dir_name := _dir_to_str(tile.direction)
		var item_name := _resolve_item_name(tile.item_id, catalog)
		var downstream_str := "none"
		if tile.has_downstream:
			downstream_str = str(tile.downstream_pos)
		lines.append("  (%d,%d) dir=%s item=%s progress=%.1f downstream=%s" % [
			pos.x, pos.y, dir_name, item_name, tile.progress, downstream_str
		])

	return "\n".join(lines)


## PlacementSystem の状態をダンプする
func dump_placement(system: PlacementSystem, registry: EntityRegistry = null) -> String:
	if system == null:
		return ""

	var entities := system.get_all_entities()
	var header := "--- MACHINES (%d entities) ---" % entities.size()

	if entities.is_empty():
		return header + "\n  (empty)"

	# entity_id でソート
	var sorted_entities := entities.duplicate()
	sorted_entities.sort_custom(func(a: PlacedEntity, b: PlacedEntity) -> bool:
		return a.entity_id < b.entity_id
	)

	if sorted_entities.size() > _max_detail_items:
		return header + "\n  [SUMMARY MODE: entity_count=%d]" % sorted_entities.size()

	var lines: Array[String] = [header]
	for entity: PlacedEntity in sorted_entities:
		var name := _resolve_entity_name(entity.entity_type_id, registry)
		var dir_name := _dir_to_str(entity.direction)
		lines.append("  #%d %s at (%d,%d) dir=%s footprint=%dx%d" % [
			entity.entity_id, name, entity.base_cell.x, entity.base_cell.y,
			dir_name, entity.footprint.x, entity.footprint.y
		])

	return "\n".join(lines)


## MachinePortGrid の状態をダンプする
## 注: dump_ports実行前にrebuild_connections_if_dirty()を呼び出してstale回避
func dump_ports(grid: MachinePortGrid, catalog: ItemCatalog = null) -> String:
	if grid == null:
		return ""

	var outputs := grid.get_active_output_ports()
	var inputs := grid.get_active_input_ports()
	var all_ports: Array = []
	for p: Dictionary in outputs:
		all_ports.append(p)
	for p: Dictionary in inputs:
		all_ports.append(p)

	var connected_count := 0
	for p: Dictionary in all_ports:
		if p["has_connection"]:
			connected_count += 1

	var header := "--- PORTS (%d active, %d connected) ---" % [all_ports.size(), connected_count]

	if all_ports.is_empty():
		return header + "\n  (empty)"

	if all_ports.size() > _max_detail_items:
		return header + "\n  [SUMMARY MODE: port_count=%d, connected=%d]" % [
			all_ports.size(), connected_count
		]

	# entity_id → port_type の順でソート
	all_ports.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a["entity_id"] != b["entity_id"]:
			return a["entity_id"] < b["entity_id"]
		return a["port_type"] < b["port_type"]
	)

	var lines: Array[String] = [header]
	var idx := 1
	for port: Dictionary in all_ports:
		var type_str := "OUTPUT" if port["port_type"] == MachinePortGrid.PORT_TYPE_OUTPUT else "INPUT"
		var pos: Vector2i = port["world_position"]
		var dir_name := _dir_to_str(port["world_direction"])
		var item_name := _resolve_item_name(port["item_id"], catalog)
		var belt_pos: Vector2i = port["connected_belt_pos"]
		var belt_str := str(belt_pos) if port["has_connection"] else "none"
		var conn_str := str(port["has_connection"])
		lines.append("  #%d %s at (%d,%d) dir=%s item=%s belt=%s connected=%s" % [
			idx, type_str, pos.x, pos.y, dir_name, item_name, belt_str, conn_str
		])
		idx += 1

	return "\n".join(lines)


## サマリー情報を出力する（コンソール表示用）
func dump_summary(
	belt_grid: BeltGrid,
	port_grid: MachinePortGrid,
	placement: PlacementSystem,
) -> String:
	var parts: Array[String] = ["--- SUMMARY ---"]

	if belt_grid != null:
		parts.append("  belts=%d items=%d" % [belt_grid.tile_count(), belt_grid.item_count()])

	if placement != null:
		parts.append("  entities=%d" % placement.get_all_entities().size())

	if port_grid != null:
		var total := port_grid.get_active_output_ports().size() + port_grid.get_active_input_ports().size()
		parts.append("  ports=%d" % total)

	return "\n".join(parts)


## ファイルに保存する（ベストエフォート、失敗してもテストを落とさない）
static func save(content: String, filename: String) -> void:
	var dir_path := "res://test_snapshots"
	if not DirAccess.dir_exists_absolute(dir_path):
		DirAccess.make_dir_recursive_absolute(dir_path)

	var path := "%s/%s" % [dir_path, filename]
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(content)
		file.close()
		print("[Snapshot] Saved: test_snapshots/%s" % filename)
	else:
		print("[Snapshot] WARNING: Failed to save %s" % path)


## --- 内部ヘルパー ---

func _dir_to_str(direction: int) -> String:
	if direction >= 0 and direction < DIR_NAMES.size():
		return DIR_NAMES[direction]
	return "?"


func _resolve_item_name(item_id: int, catalog: ItemCatalog) -> String:
	if item_id <= 0:
		return "none"
	if catalog == null:
		return "id:%d" % item_id
	var def := catalog.get_by_id(item_id)
	if def != null:
		return def.display_name
	return "id:%d" % item_id


func _resolve_entity_name(entity_type_id: int, registry: EntityRegistry) -> String:
	if registry == null:
		return "type:%d" % entity_type_id
	var def := registry.get_definition(entity_type_id)
	if def != null:
		return def.display_name
	return "type:%d" % entity_type_id
