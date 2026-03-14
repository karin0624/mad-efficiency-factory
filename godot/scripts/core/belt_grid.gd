class_name BeltGrid
extends RefCounted

## BeltGrid — 全ベルトタイルのデータストアと接続グラフを一元管理する
##
## Dictionary<Vector2i, BeltTileData>によるベルトタイル管理。
## ベルト間の接続関係（downstream）の計算と保持。
## タイルの追加/削除とアイテム操作の原子的実行。
## アイテム保存則の維持（追加/削除は1対1）。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## Vector2i → BeltTileData のマッピング
var _tiles: Dictionary = {}


## ベルトタイルを追加する
## Postconditions: BeltTileDataが作成され登録される
func add_tile(pos: Vector2i, direction: int) -> void:
	var tile := BeltTileData.new(direction)
	_tiles[pos] = tile


## ベルトタイルを削除する（保持アイテムは消失）
## Postconditions: BeltTileDataが削除される。保持アイテムは消失する
func remove_tile(pos: Vector2i) -> void:
	_tiles.erase(pos)


## 指定座標のBeltTileDataを取得する
## Postconditions: ベルトが存在すればBeltTileData、なければnull
func get_tile(pos: Vector2i) -> BeltTileData:
	return _tiles.get(pos, null)


## 指定座標がベルトタイルか判定する
func has_tile(pos: Vector2i) -> bool:
	return _tiles.has(pos)


## ベルトタイルにアイテムを設定する（空のタイルのみ）
## Preconditions: posにベルトが存在し、アイテムを保持していない
## Postconditions: 成功時true、タイルのitem_idとprogressが設定される
func set_item(pos: Vector2i, item_id: int) -> bool:
	var tile: BeltTileData = _tiles.get(pos, null)
	if tile == null:
		return false
	if tile.has_item():
		return false
	tile.set_item(item_id)
	return true


## ベルトタイルからアイテムを除去する
## Postconditions: タイルのitem_id=0, progress=0.0にリセット
func clear_item(pos: Vector2i) -> void:
	var tile: BeltTileData = _tiles.get(pos, null)
	if tile == null:
		return
	tile.clear_item()


## 全ベルトタイルの接続関係を再計算する
## Postconditions: 各タイルのdownstream_pos/has_downstreamが更新される
func rebuild_connections(grid: CoreGrid, _placement: PlacementSystem) -> void:
	## 方向ベクトルのマッピング（N=0, E=1, S=2, W=3）
	var dir_offsets: Array[Vector2i] = [
		Vector2i(0, -1),  # N
		Vector2i(1, 0),   # E
		Vector2i(0, 1),   # S
		Vector2i(-1, 0),  # W
	]

	for pos: Vector2i in _tiles:
		var tile: BeltTileData = _tiles[pos]
		var offset: Vector2i = dir_offsets[tile.direction]
		var downstream_pos := pos + offset

		# グリッド範囲チェック
		if not grid.is_in_bounds(downstream_pos):
			tile.clear_downstream()
			continue

		# 下流にベルトが存在するかチェック
		if has_tile(downstream_pos):
			tile.set_downstream(downstream_pos)
		else:
			tile.clear_downstream()


## 登録されたベルトタイル数を返す
func tile_count() -> int:
	return _tiles.size()


## アイテムを保持中のベルトタイル数を返す
func item_count() -> int:
	var count := 0
	for pos: Vector2i in _tiles:
		var tile: BeltTileData = _tiles[pos]
		if tile.has_item():
			count += 1
	return count


## 全ベルト座標を取得する
func get_all_positions() -> Array[Vector2i]:
	var positions: Array[Vector2i] = []
	for pos: Vector2i in _tiles:
		positions.append(pos)
	return positions
