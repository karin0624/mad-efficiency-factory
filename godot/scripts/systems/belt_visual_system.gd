class_name BeltVisualSystem
extends Node2D

## BeltVisualSystem — BeltGridの状態を読み取り、ベルト上アイテムの視覚表現を更新する
##
## BeltGridのアイテム位置と進行度に基づいて視覚表現を更新。
## `_process(delta)`で毎フレーム呼び出し（ティック間のアニメーション補間）。
## ベルト上アイテムはスプライトプールまたはMultiMeshInstance2Dで描画（tech.md方針）。
## Node2Dベース。

## タイルサイズ（ピクセル）
const TILE_SIZE: int = 32

## ベルトグリッドへの参照
var belt_grid: BeltGrid = null

## アイテム描画用スプライトプール
var _item_sprites: Array[Sprite2D] = []

## プール最大サイズ
const MAX_SPRITES: int = 2000


func _ready() -> void:
	# スプライトプールの初期化
	for i in range(MAX_SPRITES):
		var sprite := Sprite2D.new()
		sprite.visible = false
		sprite.modulate = Color.ORANGE  # デフォルトアイテム色
		add_child(sprite)
		_item_sprites.append(sprite)


## 毎フレーム呼び出し: BeltGridの状態を読み取り視覚を更新する
func _process(_delta: float) -> void:
	if belt_grid == null:
		return
	_update_visuals()


## BeltGridの状態に基づいてアイテムの視覚表現を更新する
## Req 9.1: ベルト上のアイテムをベルトの向き方向に視覚的に移動表示
## Req 9.2: バックプレッシャー発生時のアイテム停止状態を視覚的に表現
func update_visuals() -> void:
	_update_visuals()


func _update_visuals() -> void:
	var positions := belt_grid.get_all_positions()

	# 方向ベクトルのマッピング（N=0, E=1, S=2, W=3）
	var dir_offsets: Array[Vector2] = [
		Vector2(0.0, -1.0),   # N
		Vector2(1.0, 0.0),    # E
		Vector2(0.0, 1.0),    # S
		Vector2(-1.0, 0.0),   # W
	]

	var sprite_index := 0

	for pos: Vector2i in positions:
		var tile: BeltTileData = belt_grid.get_tile(pos)
		if tile == null or not tile.has_item():
			continue

		if sprite_index >= MAX_SPRITES:
			break

		var sprite := _item_sprites[sprite_index]
		sprite.visible = true

		# タイル中心座標（ピクセル）
		var tile_center := Vector2(
			pos.x * TILE_SIZE + TILE_SIZE / 2.0,
			pos.y * TILE_SIZE + TILE_SIZE / 2.0
		)

		# 進行度に基づいてアイテム位置を補間
		# progress=0.0: タイル入口、progress=1.0: タイル出口
		var dir_offset := dir_offsets[tile.direction]
		var item_offset := dir_offset * (tile.progress - 0.5) * TILE_SIZE

		sprite.position = tile_center + item_offset

		# バックプレッシャー状態の視覚表現（Req 9.2）
		# 進行度が1.0に達して停止中 = バックプレッシャー → 赤みがかった色
		if tile.progress >= 1.0:
			sprite.modulate = Color.RED
		else:
			sprite.modulate = Color.ORANGE

		sprite_index += 1

	# 使用されなかったスプライトを非表示
	for i in range(sprite_index, _item_sprites.size()):
		_item_sprites[i].visible = false
