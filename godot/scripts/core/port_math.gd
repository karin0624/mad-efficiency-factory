class_name PortMath
extends RefCounted

## PortMath — ポートオフセット・方向の回転計算（純粋関数群）
##
## 機械の回転方向に応じたポートのワールド座標変換と方向変換を提供する。
## 純粋関数のみで構成し、状態を持たない。
## SceneTree/Node APIに依存しない完全独立クラス。
## 回転公式: N→そのまま、E→(size_y-1-y, x)、S→(size_x-1-x, size_y-1-y)、W→(y, size_x-1-x)
## direction_to_vector: N→(0,-1)、E→(1,0)、S→(0,1)、W→(-1,0)（Godot Y軸下向き）


## 相対オフセットを機械の回転方向に応じて回転する
## offset: 北基準の相対オフセット（base_cellからの差分）
## machine_size: 機械のフットプリントサイズ（Vector2i）
## direction: 機械の向き（Direction enum: N=0, E=1, S=2, W=3）
## Returns: 回転後のオフセット
static func rotate_offset(offset: Vector2i, machine_size: Vector2i, direction: int) -> Vector2i:
	match direction:
		Enums.Direction.N:
			return offset
		Enums.Direction.E:
			# E: (x,y) → (size_y-1-y, x)
			return Vector2i(machine_size.y - 1 - offset.y, offset.x)
		Enums.Direction.S:
			# S: (x,y) → (size_x-1-x, size_y-1-y)
			return Vector2i(machine_size.x - 1 - offset.x, machine_size.y - 1 - offset.y)
		Enums.Direction.W:
			# W: (x,y) → (y, size_x-1-x)
			return Vector2i(offset.y, machine_size.x - 1 - offset.x)
		_:
			return offset


## ポート方向を機械の回転方向に応じて回転する
## port_direction: 北基準のポート方向（Direction enum）
## machine_direction: 機械の向き（Direction enum）
## Returns: 回転後の方向
static func rotate_direction(port_direction: int, machine_direction: int) -> int:
	return (port_direction + machine_direction) % 4


## ポートの接続先ベルト位置を計算する
## port_world_pos: ポートのワールド座標
## port_world_dir: ポートのワールド方向
## Returns: 接続先のベルト位置（ポート位置 + 方向ベクトル）
static func get_connected_position(port_world_pos: Vector2i, port_world_dir: int) -> Vector2i:
	return port_world_pos + direction_to_vector(port_world_dir)


## 方向を単位ベクトルに変換する
## N→(0,-1)、E→(1,0)、S→(0,1)、W→(-1,0)（Godot Y軸下向き座標系）
static func direction_to_vector(direction: int) -> Vector2i:
	match direction:
		Enums.Direction.N:
			return Vector2i(0, -1)
		Enums.Direction.E:
			return Vector2i(1, 0)
		Enums.Direction.S:
			return Vector2i(0, 1)
		Enums.Direction.W:
			return Vector2i(-1, 0)
		_:
			return Vector2i(0, 0)
