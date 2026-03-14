class_name BeltVisualSystem
extends Node2D

## BeltVisualSystem — BeltGridの状態を読み取り、ベルトタイルとアイテムの視覚表現を描画する
##
## BeltGridのタイル配置とアイテム位置・進行度に基づいて視覚表現を更新。
## `_process(delta)`で毎フレーム`queue_redraw()`を呼び、`_draw()`で描画。
## ベルトタイルは背景矩形+方向矢印、アイテムは色付き円で描画。
## Node2Dベース。

## タイルサイズ（ピクセル）— GhostPreviewNode / PlacementInputNode と同じ64px
const TILE_SIZE: int = 64

## ベルトタイルの背景色
const BELT_BG_COLOR := Color(0.55, 0.60, 0.70, 0.85)

## ベルトタイルの境界線色
const BELT_BORDER_COLOR := Color(0.35, 0.40, 0.50, 1.0)

## 方向矢印の色
const ARROW_COLOR := Color(0.90, 0.90, 0.95, 0.9)

## アイテム通常色
const ITEM_COLOR := Color.ORANGE

## アイテムバックプレッシャー色（progress >= 1.0 で停止中）
const ITEM_BLOCKED_COLOR := Color.RED

## アイテム描画の半径（ピクセル）
const ITEM_RADIUS: float = 10.0

## ベルトグリッドへの参照
var belt_grid: BeltGrid = null


## 毎フレーム呼び出し: 再描画をリクエストする
func _process(_delta: float) -> void:
	if belt_grid == null:
		return
	queue_redraw()


## 公開API: テストやコードからの明示的な視覚更新
## Req 9.1: ベルト上のアイテムをベルトの向き方向に視覚的に移動表示
## Req 9.2: バックプレッシャー発生時のアイテム停止状態を視覚的に表現
func update_visuals() -> void:
	queue_redraw()


## ベルトタイルとアイテムを描画する
func _draw() -> void:
	if belt_grid == null:
		return

	var positions := belt_grid.get_all_positions()

	# 方向ベクトルのマッピング（N=0, E=1, S=2, W=3）
	var dir_offsets: Array[Vector2] = [
		Vector2(0.0, -1.0),   # N
		Vector2(1.0, 0.0),    # E
		Vector2(0.0, 1.0),    # S
		Vector2(-1.0, 0.0),   # W
	]

	# パス1: ベルトタイル背景・境界線・方向矢印
	for pos: Vector2i in positions:
		var tile: BeltTileData = belt_grid.get_tile(pos)
		if tile == null:
			continue

		var pixel_pos := Vector2(pos.x * TILE_SIZE, pos.y * TILE_SIZE)
		var tile_rect := Rect2(pixel_pos, Vector2(TILE_SIZE, TILE_SIZE))

		draw_rect(tile_rect, BELT_BG_COLOR)
		draw_rect(tile_rect, BELT_BORDER_COLOR, false, 1.5)

		var center := pixel_pos + Vector2(TILE_SIZE / 2.0, TILE_SIZE / 2.0)
		_draw_direction_arrow(center, tile.direction)

	# パス2: アイテム（ベルト境界線の上に描画）
	for pos: Vector2i in positions:
		var tile: BeltTileData = belt_grid.get_tile(pos)
		if tile == null:
			continue
		if not tile.has_item():
			continue

		var pixel_pos := Vector2(pos.x * TILE_SIZE, pos.y * TILE_SIZE)
		var center := pixel_pos + Vector2(TILE_SIZE / 2.0, TILE_SIZE / 2.0)
		var dir_offset := dir_offsets[tile.direction]
		var item_offset := dir_offset * (tile.progress - 0.5) * TILE_SIZE
		var item_pos := center + item_offset

		var color := ITEM_BLOCKED_COLOR if tile.progress >= 1.0 else ITEM_COLOR
		draw_circle(item_pos, ITEM_RADIUS, color)
		draw_arc(item_pos, ITEM_RADIUS, 0.0, TAU, 16, Color.BLACK, 1.5)


## 方向矢印を描画する（三角形ポリゴン）
func _draw_direction_arrow(center: Vector2, direction: int) -> void:
	var arrow_size: float = TILE_SIZE * 0.25
	var points: PackedVector2Array

	match direction:
		Enums.Direction.N:
			# 上向き三角形
			points = PackedVector2Array([
				center + Vector2(0, -arrow_size),
				center + Vector2(-arrow_size * 0.7, arrow_size * 0.5),
				center + Vector2(arrow_size * 0.7, arrow_size * 0.5),
			])
		Enums.Direction.E:
			# 右向き三角形
			points = PackedVector2Array([
				center + Vector2(arrow_size, 0),
				center + Vector2(-arrow_size * 0.5, -arrow_size * 0.7),
				center + Vector2(-arrow_size * 0.5, arrow_size * 0.7),
			])
		Enums.Direction.S:
			# 下向き三角形
			points = PackedVector2Array([
				center + Vector2(0, arrow_size),
				center + Vector2(-arrow_size * 0.7, -arrow_size * 0.5),
				center + Vector2(arrow_size * 0.7, -arrow_size * 0.5),
			])
		Enums.Direction.W:
			# 左向き三角形
			points = PackedVector2Array([
				center + Vector2(-arrow_size, 0),
				center + Vector2(arrow_size * 0.5, -arrow_size * 0.7),
				center + Vector2(arrow_size * 0.5, arrow_size * 0.7),
			])

	if points.size() == 3:
		draw_colored_polygon(points, ARROW_COLOR)
