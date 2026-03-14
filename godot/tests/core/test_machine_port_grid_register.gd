extends GdUnitTestSuite

# Test: MachinePortGrid — 機械登録・解除とポートインスタンス生成 (Req 1.1, 1.2, 1.3, 1.4, 6.3)

## タスク3.1: 機械登録・解除とポートインスタンス生成テスト

var _catalog: MachinePortCatalog
var _sut: MachinePortGrid


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_sut = MachinePortGrid.new(_catalog)


func after_test() -> void:
	_sut = null
	_catalog = null


# --- 機械登録時のポート生成テスト ---

func test_register_miner_creates_output_port_north() -> void:
	# 採掘機(ID=1)を北向きで (2,2) に配置
	# 出力ポート: base_cell(2,2) + offset(1,1) = world(3,3), dir=S
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	var output_ports := _sut.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)
	var port: Dictionary = output_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(3, 3))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.S)


func test_register_miner_output_world_position_east() -> void:
	# 採掘機を東向きで (2,2) に配置
	# 出力ポート北向き定義: offset=(1,1), dir=S
	# 東向き回転: rotate_offset((1,1), (2,2), E) = (2-1-1, 1) = (0, 1)
	# world_pos = (2,2) + (0,1) = (2,3)
	# rotate_direction(S, E) = (2+1)%4 = 3 = W
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.E)
	var output_ports := _sut.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)
	var port: Dictionary = output_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(2, 3))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.W)


func test_register_miner_output_world_position_south() -> void:
	# 採掘機を南向きで (2,2) に配置
	# 南向き回転: rotate_offset((1,1), (2,2), S) = (2-1-1, 2-1-1) = (0, 0)
	# world_pos = (2,2) + (0,0) = (2,2)
	# rotate_direction(S, S) = (2+2)%4 = 0 = N
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.S)
	var output_ports := _sut.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)
	var port: Dictionary = output_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(2, 2))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.N)


func test_register_miner_output_world_position_west() -> void:
	# 採掘機を西向きで (2,2) に配置
	# 西向き回転: rotate_offset((1,1), (2,2), W) = (1, 2-1-1) = (1, 0)
	# world_pos = (2,2) + (1,0) = (3,2)
	# rotate_direction(S, W) = (2+3)%4 = 1 = E
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.W)
	var output_ports := _sut.get_active_output_ports()
	assert_int(output_ports.size()).is_equal(1)
	var port: Dictionary = output_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(3, 2))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.E)


func test_register_smelter_creates_input_and_output_ports() -> void:
	# 精錬機(ID=2)を北向きで配置
	_sut.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	var input_ports := _sut.get_active_input_ports()
	var output_ports := _sut.get_active_output_ports()
	assert_int(input_ports.size()).is_equal(1)
	assert_int(output_ports.size()).is_equal(1)


func test_register_smelter_input_port_north() -> void:
	# 精錬機入力ポート: base_cell(4,4) + offset(0,0) = world(4,4), dir=N
	_sut.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	var input_ports := _sut.get_active_input_ports()
	var port: Dictionary = input_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(4, 4))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.N)


func test_register_delivery_box_creates_input_port() -> void:
	# 納品箱(ID=4)を北向きで配置: 1x1, 入力ポート offset=(0,0), dir=N
	_sut.register_machine(10, 4, Vector2i(6, 6), Enums.Direction.N)
	var input_ports := _sut.get_active_input_ports()
	assert_int(input_ports.size()).is_equal(1)
	var port: Dictionary = input_ports[0]
	assert_that(port["world_position"]).is_equal(Vector2i(6, 6))
	assert_int(port["world_direction"]).is_equal(Enums.Direction.N)


func test_port_buffer_initially_empty() -> void:
	# ポートバッファ初期状態は空（item_id=0）
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	var output_ports := _sut.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	assert_int(port["item_id"]).is_equal(0)


func test_port_has_no_connection_initially() -> void:
	# 初期状態では接続なし
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	var output_ports := _sut.get_active_output_ports()
	var port: Dictionary = output_ports[0]
	assert_bool(port["has_connection"]).is_false()


# --- 機械解除テスト ---

func test_unregister_machine_removes_ports() -> void:
	_sut.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	assert_int(_sut.get_active_output_ports().size()).is_equal(1)
	_sut.unregister_machine(1)
	assert_int(_sut.get_active_output_ports().size()).is_equal(0)


func test_unregister_smelter_removes_all_ports() -> void:
	_sut.register_machine(5, 2, Vector2i(4, 4), Enums.Direction.N)
	assert_int(_sut.get_active_input_ports().size()).is_equal(1)
	assert_int(_sut.get_active_output_ports().size()).is_equal(1)
	_sut.unregister_machine(5)
	assert_int(_sut.get_active_input_ports().size()).is_equal(0)
	assert_int(_sut.get_active_output_ports().size()).is_equal(0)


func test_unregister_nonexistent_machine_does_nothing() -> void:
	# 未登録エンティティの解除は無視
	_sut.unregister_machine(999)
	assert_int(_sut.get_active_output_ports().size()).is_equal(0)


func test_multiple_machines_ports_are_independent() -> void:
	# 複数機械を登録し、それぞれのポートが独立していることを確認
	_sut.register_machine(1, 1, Vector2i(0, 0), Enums.Direction.N)  # Miner
	_sut.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)  # Smelter
	assert_int(_sut.get_active_output_ports().size()).is_equal(2)
	assert_int(_sut.get_active_input_ports().size()).is_equal(1)
	_sut.unregister_machine(1)
	assert_int(_sut.get_active_output_ports().size()).is_equal(1)
	assert_int(_sut.get_active_input_ports().size()).is_equal(1)
