class_name MachinePortGrid
extends RefCounted

## MachinePortGrid — アクティブポートのランタイム状態と接続関係の管理
##
## 配置済み機械のポートインスタンス（ワールド座標・方向・バッファ）を管理する。
## dirty-flag による遅延接続再構築（配置/撤去時にフラグセット、次ティックで再構築）。
## ポートバッファは1アイテム最大（item_id: int, 0=空）。
## 機械撤去時はポートを即座に削除し、バッファ内アイテムは消失。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## ActivePort の port_type 定数
const PORT_TYPE_INPUT: int = 0
const PORT_TYPE_OUTPUT: int = 1

## カタログ参照
var _catalog: MachinePortCatalog

## ポートインスタンスの配列 (Array of Dictionary/ActivePort)
## port: {entity_id, port_type, world_position, world_direction, item_id, connected_belt_pos, has_connection}
var _ports: Array = []

## entity_id → ポートインデックスの配列マッピング
var _entity_port_indices: Dictionary = {}  # {int: Array[int]}

## ポートのワールド位置 → ポートインデックス（高速参照用）
var _position_to_port_index: Dictionary = {}  # {Vector2i: int}

## dirty flag（接続再構築が必要か）
var _dirty: bool = false


func _init(catalog: MachinePortCatalog) -> void:
	_catalog = catalog


## --- 機械の登録/解除 ---

## 機械を登録し、ポートインスタンスを生成する
## entity_id: 配置済みエンティティの一意ID
## machine_type_id: 機械タイプID（MachinePortCatalogに登録済みであること）
## base_cell: 機械のベースセル座標
## direction: 機械の向き（Direction enum）
func register_machine(entity_id: int, machine_type_id: int,
		base_cell: Vector2i, direction: int) -> void:
	var config := _catalog.get_config(machine_type_id)
	if config == null:
		push_warning("MachinePortGrid: unknown machine_type_id=%d" % machine_type_id)
		return

	# 重複登録時は既存を上書き（警告ログ）
	if _entity_port_indices.has(entity_id):
		push_warning("MachinePortGrid: duplicate entity_id=%d, overwriting" % entity_id)
		unregister_machine(entity_id)

	var port_indices: Array = []

	# 入力ポートの生成
	for port_def: Dictionary in config.input_ports:
		var rotated_offset := PortMath.rotate_offset(
			port_def["local_offset"], config.machine_size, direction)
		var rotated_dir := PortMath.rotate_direction(
			port_def["local_direction"], direction)
		var world_pos := base_cell + rotated_offset
		var port_index := _ports.size()
		_ports.append({
			"entity_id": entity_id,
			"port_type": PORT_TYPE_INPUT,
			"world_position": world_pos,
			"world_direction": rotated_dir,
			"item_id": 0,
			"connected_belt_pos": Vector2i(-1, -1),
			"has_connection": false,
		})
		port_indices.append(port_index)
		_position_to_port_index[world_pos] = port_index

	# 出力ポートの生成
	for port_def: Dictionary in config.output_ports:
		var rotated_offset := PortMath.rotate_offset(
			port_def["local_offset"], config.machine_size, direction)
		var rotated_dir := PortMath.rotate_direction(
			port_def["local_direction"], direction)
		var world_pos := base_cell + rotated_offset
		var port_index := _ports.size()
		_ports.append({
			"entity_id": entity_id,
			"port_type": PORT_TYPE_OUTPUT,
			"world_position": world_pos,
			"world_direction": rotated_dir,
			"item_id": 0,
			"connected_belt_pos": Vector2i(-1, -1),
			"has_connection": false,
		})
		port_indices.append(port_index)
		_position_to_port_index[world_pos] = port_index

	_entity_port_indices[entity_id] = port_indices
	_dirty = true


## 機械を解除し、ポートインスタンスを削除する（バッファ内アイテムは消失）
func unregister_machine(entity_id: int) -> void:
	if not _entity_port_indices.has(entity_id):
		return

	var indices: Array = _entity_port_indices[entity_id]
	var indices_to_remove := {}
	for idx: int in indices:
		indices_to_remove[idx] = true

	# ポジションインデックスから削除
	for idx: int in indices:
		var port: Dictionary = _ports[idx]
		_position_to_port_index.erase(port["world_position"])

	_entity_port_indices.erase(entity_id)

	# _ports配列から削除し、インデックスを再構築
	var new_ports: Array = []
	var old_to_new_index: Dictionary = {}  # {old_idx: new_idx}
	for i in range(_ports.size()):
		if not indices_to_remove.has(i):
			old_to_new_index[i] = new_ports.size()
			new_ports.append(_ports[i])

	_ports = new_ports

	# entity_port_indices の全インデックスを更新
	for eid: int in _entity_port_indices:
		var old_indices: Array = _entity_port_indices[eid]
		var new_indices: Array = []
		for old_idx: int in old_indices:
			if old_to_new_index.has(old_idx):
				new_indices.append(old_to_new_index[old_idx])
		_entity_port_indices[eid] = new_indices

	# position_to_port_index の全インデックスを更新
	for pos: Vector2i in _position_to_port_index:
		var old_idx: int = _position_to_port_index[pos]
		if old_to_new_index.has(old_idx):
			_position_to_port_index[pos] = old_to_new_index[old_idx]

	_dirty = true


## --- 接続管理 ---

## dirty flag をセットする
func mark_dirty() -> void:
	_dirty = true


## dirty なら接続関係を再構築する
## belt_grid: ベルトの存在確認に使用
func rebuild_connections_if_dirty(belt_grid: BeltGrid) -> void:
	if not _dirty:
		return
	_rebuild_connections(belt_grid)
	_dirty = false


## 全ポートの接続関係を再構築する
func _rebuild_connections(belt_grid: BeltGrid) -> void:
	for port: Dictionary in _ports:
		var belt_pos := PortMath.get_connected_position(
			port["world_position"], port["world_direction"])

		if belt_grid.has_tile(belt_pos):
			if port["port_type"] == PORT_TYPE_INPUT:
				# 入力ポート: ベルト存在 + 方向互換チェック
				# ベルトのdownstreamがポート方向を向いているか確認
				var belt_tile := belt_grid.get_tile(belt_pos)
				if belt_tile != null and belt_tile.direction == port["world_direction"]:
					port["connected_belt_pos"] = belt_pos
					port["has_connection"] = true
				else:
					port["connected_belt_pos"] = Vector2i(-1, -1)
					port["has_connection"] = false
			else:
				# 出力ポート: ベルト存在のみチェック
				port["connected_belt_pos"] = belt_pos
				port["has_connection"] = true
		else:
			port["connected_belt_pos"] = Vector2i(-1, -1)
			port["has_connection"] = false


## --- ポート状態アクセス ---

## アクティブな出力ポート一覧を取得する
func get_active_output_ports() -> Array:
	var result: Array = []
	for port: Dictionary in _ports:
		if port["port_type"] == PORT_TYPE_OUTPUT:
			result.append(port)
	return result


## アクティブな入力ポート一覧を取得する
func get_active_input_ports() -> Array:
	var result: Array = []
	for port: Dictionary in _ports:
		if port["port_type"] == PORT_TYPE_INPUT:
			result.append(port)
	return result


## ポートのバッファアイテムを取得する（0=空）
## port_index: _ports配列のインデックス
func get_port_item(port_index: int) -> int:
	if port_index < 0 or port_index >= _ports.size():
		return 0
	return _ports[port_index]["item_id"]


## ポートのバッファにアイテムをセットする
func set_port_item(port_index: int, item_id: int) -> void:
	if port_index < 0 or port_index >= _ports.size():
		return
	_ports[port_index]["item_id"] = item_id


## ポートのバッファをクリアする
func clear_port_item(port_index: int) -> void:
	if port_index < 0 or port_index >= _ports.size():
		return
	_ports[port_index]["item_id"] = 0


## ポートのインデックスを取得する（Arrayへの参照からインデックスを計算）
## port: get_active_output_ports()/get_active_input_ports()で取得したDictionary
func get_port_index(port: Dictionary) -> int:
	for i in range(_ports.size()):
		if _ports[i] == port:
			return i
	return -1


## dirty flag の状態を返す（テスト用）
func is_dirty() -> bool:
	return _dirty
