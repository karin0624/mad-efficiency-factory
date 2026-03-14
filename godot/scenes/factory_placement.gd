extends Node2D

## FactoryPlacement — PlacementSystemをゲームシーンに統合するルートノード
##
## PlacementSystem、CoreGrid、EntityRegistry、GhostPreviewNode、PlacementInputNodeを接続する。
## BeltTransportSystem、BeltVisualSystem、TickEngineNodeを統合し、ベルト搬送を実現する。

const CELL_SIZE: int = 64  # グリッドセルのピクセルサイズ

var _grid: CoreGrid
var _registry: EntityRegistry
var _system: PlacementSystem
var _ghost: GhostPreviewNode
var _input_handler: PlacementInputNode

## ベルト搬送関連
var _tick_engine: TickEngineNode
var _belt_grid: BeltGrid
var _belt_transport: BeltTransportSystem
var _belt_visual: BeltVisualSystem

func _ready() -> void:
	# Core Logicの初期化
	_grid = CoreGrid.new()
	_registry = EntityRegistry.create_default()
	_system = PlacementSystem.new(_grid, _registry)

	# TickEngineNodeの初期化
	_tick_engine = TickEngineNode.new()
	add_child(_tick_engine)

	# BeltGrid / BeltTransportSystem / BeltVisualSystem の初期化
	_belt_grid = BeltGrid.new()
	_belt_transport = BeltTransportSystem.new(_belt_grid, _grid, _system)

	_belt_visual = BeltVisualSystem.new()
	_belt_visual.belt_grid = _belt_grid
	add_child(_belt_visual)

	# TickEngineのtick_firedシグナルをBeltTransportSystem.tick()に接続
	_tick_engine.tick_fired.connect(_on_tick_fired)

	# Presentationノードの初期化
	_ghost = GhostPreviewNode.new()
	_ghost.placement_system = _system
	add_child(_ghost)

	_input_handler = PlacementInputNode.new()
	_input_handler.placement_system = _system
	_input_handler.ghost_preview = _ghost
	add_child(_input_handler)

	# PlacementInputNodeの配置・撤去シグナルをBeltTransportSystemに接続
	_input_handler.entity_placed.connect(_belt_transport.on_entity_placed)
	_input_handler.entity_removed.connect(_belt_transport.on_entity_removed)

	# Belt(ID=3)をデフォルト選択
	_input_handler.select_entity(3)

	print("FactoryPlacement ready: grid=64x64, entities=", _registry.size())


## TickEngine tick_fired ハンドラ（tick引数を無視してBeltTransportSystem.tick()を呼ぶ）
func _on_tick_fired(_tick: int) -> void:
	_belt_transport.tick()


## 入力イベント処理（エンティティ切替・デバッグ用アイテム投入）
func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed:
		return

	match key_event.keycode:
		# エンティティ切替
		KEY_1:
			_input_handler.select_entity(1)  # Miner
		KEY_2:
			_input_handler.select_entity(2)  # Smelter
		KEY_3:
			_input_handler.select_entity(3)  # Belt
		KEY_4:
			_input_handler.select_entity(4)  # DeliveryBox
		# デバッグ用: Tキーでマウス位置のベルトに鉄鉱石(ID=1)を投入
		KEY_T:
			_debug_inject_item()


## デバッグ用: マウスカーソル位置のベルトにアイテムを投入する
func _debug_inject_item() -> void:
	var mouse_pos := get_viewport().get_mouse_position()
	var cell := Vector2i(
		floori(mouse_pos.x) / CELL_SIZE,
		floori(mouse_pos.y) / CELL_SIZE
	)
	var success := _belt_grid.set_item(cell, 1)  # 鉄鉱石(ID=1)
	if success:
		print("Debug: injected iron ore at ", cell)
	else:
		print("Debug: no empty belt at ", cell)
