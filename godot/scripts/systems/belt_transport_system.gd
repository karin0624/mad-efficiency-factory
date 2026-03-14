class_name BeltTransportSystem
extends RefCounted

## BeltTransportSystem — ティックごとのベルト上アイテム搬送ロジックを実行する
##
## ティックごとにすべてのベルト上アイテムの進行度を更新。
## 末尾→先頭の処理順序でFIFOと飛び越え防止を保証。
## バックプレッシャーの連鎖的伝播と自動解除。
## 機械ポートからのアイテム受入と機械ポートへのアイテム引き渡し。
## 配置/撤去時の接続グラフ再構築（ダーティフラグ方式）。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## 1ティックあたりの進行度加算量（1タイル/秒 at 60tps = 1/60）
const SPEED_PER_TICK: float = 1.0 / 60.0

## Belt エンティティタイプID
const BELT_ENTITY_TYPE_ID: int = 3

## 依存コンポーネント
var _belt_grid: BeltGrid
var _grid: CoreGrid
var _placement: PlacementSystem

## ダーティフラグ（接続グラフ/処理順序の再構築が必要か）
var _dirty: bool = true

## 処理順序キャッシュ（末尾→先頭：下流→上流の順）
var _process_order: Array[Vector2i] = []


func _init(belt_grid: BeltGrid, grid: CoreGrid, placement: PlacementSystem) -> void:
	_belt_grid = belt_grid
	_grid = grid
	_placement = placement


## 1ティック分のベルト搬送処理を実行する
## Preconditions: belt_gridが初期化済み
## Postconditions:
##   - ダーティフラグがtrueの場合、接続とプロセス順序を再構築してからフラグをリセット
##   - 全アイテムの進行度がSPEED_PER_TICK分だけ加算される（ブロックされていない場合）
##   - progress >= 1.0のアイテムは下流に転送される（下流が受入可能な場合）
##   - アイテム保存則が維持される
func tick() -> void:
	# ダーティチェック
	if _dirty:
		_belt_grid.rebuild_connections(_grid, _placement)
		_rebuild_process_order()
		_dirty = false

	# 末尾→先頭の処理順序で各ベルトタイルを処理
	for pos: Vector2i in _process_order:
		var tile: BeltTileData = _belt_grid.get_tile(pos)
		if tile == null or not tile.has_item():
			continue

		# 進行度を加算
		tile.progress += SPEED_PER_TICK

		# progress >= 1.0 の場合、転送を試みる
		if tile.progress >= 1.0:
			if tile.has_downstream:
				var dst_tile: BeltTileData = _belt_grid.get_tile(tile.downstream_pos)
				if dst_tile != null and not dst_tile.has_item():
					# 転送実行: 元タイルをクリアし、先タイルに設定
					var item_id := tile.item_id
					_belt_grid.clear_item(pos)
					_belt_grid.set_item(tile.downstream_pos, item_id)
				else:
					# 転送先満杯 → 進行度を1.0にクランプ
					tile.progress = 1.0
			else:
				# 転送先なし → 進行度を1.0にクランプ
				tile.progress = 1.0


## エンティティ配置通知を受け取り、ベルトタイルを追加してダーティフラグを設定する
## Preconditions: entity_type_idがBelt(ID=3)であること
func on_entity_placed(entity_id: int, pos: Vector2i, direction: int, entity_type_id: int) -> void:
	if entity_type_id != BELT_ENTITY_TYPE_ID:
		return
	_belt_grid.add_tile(pos, direction)
	_dirty = true


## エンティティ撤去通知を受け取り、ベルトタイルを削除してダーティフラグを設定する
func on_entity_removed(entity_id: int, pos: Vector2i, entity_type_id: int) -> void:
	if entity_type_id != BELT_ENTITY_TYPE_ID:
		return
	_belt_grid.remove_tile(pos)
	_dirty = true


## 機械出力ポートからベルトへのアイテム受入
## Preconditions: posにベルトが存在する
## Postconditions: 成功時true（ベルトが空の場合のみ）、失敗時false
func receive_item_from_machine(pos: Vector2i, item_id: int) -> bool:
	return _belt_grid.set_item(pos, item_id)


## ベルト末端から機械入力ポートへのアイテム引き渡し
## Preconditions: posにベルトが存在する
## Postconditions: 成功時はアイテムIDを返しベルトをクリア、失敗時は0を返す
## 条件: アイテムが存在し、かつprogress >= 1.0（末端到達済み）の場合のみ引き渡す
func deliver_item_to_machine(pos: Vector2i) -> int:
	var tile: BeltTileData = _belt_grid.get_tile(pos)
	if tile == null:
		return 0
	if not tile.has_item():
		return 0
	if tile.progress < 1.0:
		return 0
	var item_id := tile.item_id
	_belt_grid.clear_item(pos)
	return item_id


## 処理順序キャッシュを再構築する（末尾→先頭：下流→上流の順）
## 深さベースソート：各ベルトの「下流からの距離」を計算し、距離が小さい順にソート
func _rebuild_process_order() -> void:
	_process_order.clear()
	var all_positions := _belt_grid.get_all_positions()

	if all_positions.is_empty():
		return

	# 各ベルトの下流からの距離（深さ）を計算
	var depth: Dictionary = {}

	# 初期化: 全タイルの深さを-1（未計算）
	for pos: Vector2i in all_positions:
		depth[pos] = -1

	# 深さを計算（BFS/反復アプローチ）
	# 末尾（下流なし）の深さ=0、上流に向かって増加
	var changed := true
	while changed:
		changed = false
		for pos: Vector2i in all_positions:
			var tile: BeltTileData = _belt_grid.get_tile(pos)
			var current_depth: int = depth[pos]

			if not tile.has_downstream:
				# 末尾タイル: 深さ = 0
				if current_depth != 0:
					depth[pos] = 0
					changed = true
			else:
				# 下流の深さ + 1
				var downstream_depth: int = depth.get(tile.downstream_pos, -1)
				if downstream_depth >= 0:
					var new_depth := downstream_depth + 1
					if current_depth != new_depth:
						depth[pos] = new_depth
						changed = true

	# 深さが計算できなかったタイル（孤立サイクルなど）には最大値を設定
	var max_depth := 0
	for pos: Vector2i in all_positions:
		if depth[pos] > max_depth:
			max_depth = depth[pos]

	for pos: Vector2i in all_positions:
		if depth[pos] < 0:
			depth[pos] = max_depth + 1

	# 深さでソート（小さい順 = 末尾から先頭）
	_process_order = all_positions.duplicate()
	_process_order.sort_custom(func(a: Vector2i, b: Vector2i) -> bool:
		return depth[a] < depth[b]
	)
