extends GdUnitTestSuite

# Test: MachinePortConfig / MachinePortCatalog — ポート構成データの登録・取得 (Req 1.1, 1.2, 1.5)

## タスク2.1: ポート構成データの登録・取得テスト
## MVP3機械: Miner(ID=1, 2x2), Smelter(ID=2, 2x2), DeliveryBox(ID=4, 1x1)
## Belt(ID=3)はポート構成を持たない非機械エンティティ


func test_create_default_returns_catalog() -> void:
	var catalog := MachinePortCatalog.create_default()
	assert_object(catalog).is_not_null()
	assert_object(catalog).is_instanceof(MachinePortCatalog)


func test_miner_has_config() -> void:
	var catalog := MachinePortCatalog.create_default()
	assert_bool(catalog.has_config(1)).is_true()


func test_smelter_has_config() -> void:
	var catalog := MachinePortCatalog.create_default()
	assert_bool(catalog.has_config(2)).is_true()


func test_delivery_box_has_config() -> void:
	var catalog := MachinePortCatalog.create_default()
	assert_bool(catalog.has_config(4)).is_true()


func test_belt_has_no_config() -> void:
	var catalog := MachinePortCatalog.create_default()
	assert_bool(catalog.has_config(3)).is_false()


func test_unregistered_type_returns_null() -> void:
	var catalog := MachinePortCatalog.create_default()
	var result := catalog.get_config(99)
	assert_object(result).is_null()


func test_miner_config_has_no_input_ports() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(1)
	assert_int(config.input_ports.size()).is_equal(0)


func test_miner_config_has_one_output_port() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(1)
	assert_int(config.output_ports.size()).is_equal(1)


func test_miner_output_port_offset() -> void:
	# 採掘機出力ポート: offset=(1,1), dir=S
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(1)
	var port: Dictionary = config.output_ports[0]
	assert_that(port["local_offset"]).is_equal(Vector2i(1, 1))


func test_miner_output_port_direction() -> void:
	# 採掘機出力ポート方向: S
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(1)
	var port: Dictionary = config.output_ports[0]
	assert_int(port["local_direction"]).is_equal(Enums.Direction.S)


func test_miner_machine_size() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(1)
	assert_that(config.machine_size).is_equal(Vector2i(2, 2))


func test_smelter_config_has_one_input_port() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	assert_int(config.input_ports.size()).is_equal(1)


func test_smelter_config_has_one_output_port() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	assert_int(config.output_ports.size()).is_equal(1)


func test_smelter_input_port_offset() -> void:
	# 精錬機入力ポート: offset=(0,0), dir=N
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	var port: Dictionary = config.input_ports[0]
	assert_that(port["local_offset"]).is_equal(Vector2i(0, 0))


func test_smelter_input_port_direction() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	var port: Dictionary = config.input_ports[0]
	assert_int(port["local_direction"]).is_equal(Enums.Direction.N)


func test_smelter_output_port_offset() -> void:
	# 精錬機出力ポート: offset=(1,1), dir=S
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	var port: Dictionary = config.output_ports[0]
	assert_that(port["local_offset"]).is_equal(Vector2i(1, 1))


func test_smelter_output_port_direction() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(2)
	var port: Dictionary = config.output_ports[0]
	assert_int(port["local_direction"]).is_equal(Enums.Direction.S)


func test_delivery_box_has_one_input_port() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(4)
	assert_int(config.input_ports.size()).is_equal(1)


func test_delivery_box_has_no_output_ports() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(4)
	assert_int(config.output_ports.size()).is_equal(0)


func test_delivery_box_input_port_offset() -> void:
	# 納品箱入力ポート: offset=(0,0), dir=N
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(4)
	var port: Dictionary = config.input_ports[0]
	assert_that(port["local_offset"]).is_equal(Vector2i(0, 0))


func test_delivery_box_machine_size() -> void:
	var catalog := MachinePortCatalog.create_default()
	var config := catalog.get_config(4)
	assert_that(config.machine_size).is_equal(Vector2i(1, 1))


func test_register_custom_config() -> void:
	var catalog := MachinePortCatalog.new()
	var config := MachinePortConfig.new()
	config.machine_type_id = 10
	config.input_ports = []
	config.output_ports = []
	config.machine_size = Vector2i(1, 1)
	catalog.register(config)
	assert_bool(catalog.has_config(10)).is_true()
	assert_object(catalog.get_config(10)).is_equal(config)
