class_name MachinePortCatalog
extends RefCounted

## MachinePortCatalog — MachinePortConfigのカタログ管理
##
## machine_type_id → MachinePortConfig のマッピングを管理する。
## 非機械エンティティ（Belt等）は登録しない。
## create_default() で MVP 機械のポート構成を一括登録する。
## SceneTree/Node APIに依存しない純粋なサービスクラス。

## {int: MachinePortConfig} のマッピング
var _configs: Dictionary = {}


## ポート構成を登録する
func register(config: MachinePortConfig) -> void:
	_configs[config.machine_type_id] = config


## machine_type_id からポート構成を取得する
## Returns: 登録済みならMachinePortConfig、未登録ならnull
func get_config(machine_type_id: int) -> MachinePortConfig:
	return _configs.get(machine_type_id, null)


## machine_type_id が登録されているかチェックする
func has_config(machine_type_id: int) -> bool:
	return _configs.has(machine_type_id)


## MVP3機械（採掘機・精錬機・納品箱）のポート構成が登録済みのカタログを生成する
## Miner(ID=1): 1x1, 出力ポート offset=(0,0) dir=S  (ADR 0001: 2x2→1x1)
## Smelter(ID=2): 1x1, 入力ポート offset=(0,0) dir=N, 出力ポート offset=(0,0) dir=S  (ADR 0001: 2x2→1x1)
## DeliveryBox(ID=4): 1x1, 入力ポート offset=(0,0) dir=N
static func create_default() -> MachinePortCatalog:
	var catalog := MachinePortCatalog.new()

	# Miner (ID=1): 1x1, 出力ポート1つ
	var miner_config := MachinePortConfig.new()
	miner_config.machine_type_id = 1
	miner_config.machine_size = Vector2i(1, 1)
	miner_config.input_ports = []
	miner_config.output_ports = [
		{"local_offset": Vector2i(0, 0), "local_direction": Enums.Direction.S}
	]
	catalog.register(miner_config)

	# Smelter (ID=2): 1x1, 入力ポート1つ・出力ポート1つ
	var smelter_config := MachinePortConfig.new()
	smelter_config.machine_type_id = 2
	smelter_config.machine_size = Vector2i(1, 1)
	smelter_config.input_ports = [
		{"local_offset": Vector2i(0, 0), "local_direction": Enums.Direction.N}
	]
	smelter_config.output_ports = [
		{"local_offset": Vector2i(0, 0), "local_direction": Enums.Direction.S}
	]
	catalog.register(smelter_config)

	# DeliveryBox (ID=4): 1x1, 入力ポート1つ
	var delivery_config := MachinePortConfig.new()
	delivery_config.machine_type_id = 4
	delivery_config.machine_size = Vector2i(1, 1)
	delivery_config.input_ports = [
		{"local_offset": Vector2i(0, 0), "local_direction": Enums.Direction.N}
	]
	delivery_config.output_ports = []
	catalog.register(delivery_config)

	return catalog
