class_name MachinePortSystemNode
extends RefCounted

## MachinePortSystemNode — ティック・配置イベントのコアロジックへのブリッジ
##
## TickEngineNodeのtick_firedシグナルを受信し、
##   接続再構築 → 出力転送 → 入力転送 を呼び出す。
## PlacementSystemのentity_placed/entity_removedシグナルを受信し、
##   機械タイプならポートグリッドに登録/解除するブリッジ。
## ベルトの配置/撤去時にもポートグリッドのdirty flagをセットする。
##
## NOTE: 本クラスはRefCountedとして実装し、Nodeに依存しない。
## 実際のシーンへの統合はMachinePortSystemNode.tscnでラッパーNodeが担う。
## (BeltTransportSystemと同様のパターン)
##
## Belt(type_id=3)はポート登録対象外の非機械エンティティ

## Belt エンティティタイプID
const BELT_ENTITY_TYPE_ID: int = 3

## 依存コンポーネント
var _port_grid: MachinePortGrid
var _belt_grid: BeltGrid
var _transfer: MachinePortTransfer


func _init(port_grid: MachinePortGrid, belt_grid: BeltGrid, transfer: MachinePortTransfer) -> void:
	_port_grid = port_grid
	_belt_grid = belt_grid
	_transfer = transfer


## 出力転送ティック処理（接続再構築 + 出力ポート → ベルト）
## TickEngineNodeの高優先度tick_firedで呼び出される
func tick_output() -> void:
	_port_grid.rebuild_connections_if_dirty(_belt_grid)
	_transfer.process_output_ports(_port_grid, _belt_grid)


## 入力転送ティック処理（ベルト → 入力ポート）
## TickEngineNodeの低優先度tick_firedで呼び出される
func tick_input() -> void:
	_transfer.process_input_ports(_port_grid, _belt_grid)


## エンティティ配置通知を受け取り、機械なら登録・ベルトならdirtyをセット
func on_entity_placed(entity_id: int, base_cell: Vector2i, direction: int, entity_type_id: int) -> void:
	if entity_type_id == BELT_ENTITY_TYPE_ID:
		# ベルト配置: ポート接続関係を再評価するためdirty
		_port_grid.mark_dirty()
		return

	# 機械エンティティ: ポートグリッドに登録
	_port_grid.register_machine(entity_id, entity_type_id, base_cell, direction)


## エンティティ撤去通知を受け取り、機械なら解除・ベルトならdirtyをセット
func on_entity_removed(entity_id: int, _base_cell: Vector2i, entity_type_id: int) -> void:
	if entity_type_id == BELT_ENTITY_TYPE_ID:
		# ベルト撤去: ポート接続関係を再評価するためdirty
		_port_grid.mark_dirty()
		return

	# 機械エンティティ: ポートグリッドから解除
	_port_grid.unregister_machine(entity_id)
