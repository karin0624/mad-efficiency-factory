extends GdUnitTestSuite

# Test: MachinePortGrid — ポート接続解決とdirty再構築 (Req 2.1, 2.2, 2.3, 2.4, 6.1, 6.2, 6.4)
# タスク3.3: ポート接続解決とdirty再構築テスト

var _catalog: MachinePortCatalog
var _grid: MachinePortGrid
var _belt_grid: BeltGrid


func before_test() -> void:
	_catalog = MachinePortCatalog.create_default()
	_grid = MachinePortGrid.new(_catalog)
	_belt_grid = BeltGrid.new()


func after_test() -> void:
	_grid = null
	_catalog = null
	_belt_grid = null


## 出力ポート: 隣接にベルトが存在する場合に接続が成立する
## 採掘機(1x1)北向き: 出力ポートworld_pos=(2,2), world_dir=S
## 接続先belt_pos = (2,2) + (0,1) = (2,3)
func test_output_port_connects_when_adjacent_belt_exists() -> void:
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	# 出力ポートは(2,2)、方向S → 接続先=(2,3)
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_output_ports()
	var port: Dictionary = ports[0]
	assert_bool(port["has_connection"]).is_true()
	assert_that(port["connected_belt_pos"]).is_equal(Vector2i(2, 3))


## 出力ポート: 隣接にベルトが存在しない場合に接続が不成立
func test_output_port_no_connection_when_no_belt() -> void:
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	# ベルトを追加しない
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_output_ports()
	var port: Dictionary = ports[0]
	assert_bool(port["has_connection"]).is_false()


## 入力ポート: 隣接ベルトが存在し方向互換の場合に接続が成立する
## 精錬機北向き: 入力ポートworld_pos=(4,4), world_dir=N
## 接続先belt_pos = (4,4) + (0,-1) = (4,3)
## ベルト方向=N で方向互換
func test_input_port_connects_when_adjacent_belt_direction_compatible() -> void:
	_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	# 入力ポートは(4,4)、方向N → 接続先=(4,3)
	# ベルト方向=N (入力ポートと同方向)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.N)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_input_ports()
	var port: Dictionary = ports[0]
	assert_bool(port["has_connection"]).is_true()
	assert_that(port["connected_belt_pos"]).is_equal(Vector2i(4, 3))


## 入力ポート: 隣接にベルトが存在しない場合に接続が不成立
func test_input_port_no_connection_when_no_belt() -> void:
	_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_input_ports()
	var port: Dictionary = ports[0]
	assert_bool(port["has_connection"]).is_false()


## 入力ポート: 方向が互換でない場合に接続が不成立（ベルト方向=S、ポート方向=N）
func test_input_port_no_connection_when_direction_incompatible() -> void:
	_grid.register_machine(2, 2, Vector2i(4, 4), Enums.Direction.N)
	# 入力ポート方向=N、接続先=(4,3)にベルト方向=S (方向不一致)
	_belt_grid.add_tile(Vector2i(4, 3), Enums.Direction.S)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_input_ports()
	var port: Dictionary = ports[0]
	assert_bool(port["has_connection"]).is_false()


## dirty flagが機械登録でセットされ、再構築後にクリアされる
func test_dirty_flag_set_on_register_cleared_on_rebuild() -> void:
	assert_bool(_grid.is_dirty()).is_false()
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	assert_bool(_grid.is_dirty()).is_true()
	_grid.rebuild_connections_if_dirty(_belt_grid)
	assert_bool(_grid.is_dirty()).is_false()


## dirty flagが機械解除でセットされる
func test_dirty_flag_set_on_unregister() -> void:
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	assert_bool(_grid.is_dirty()).is_false()
	_grid.unregister_machine(1)
	assert_bool(_grid.is_dirty()).is_true()


## mark_dirty()でdirty flagがセットされる
func test_mark_dirty_sets_flag() -> void:
	_grid.rebuild_connections_if_dirty(_belt_grid)
	assert_bool(_grid.is_dirty()).is_false()
	_grid.mark_dirty()
	assert_bool(_grid.is_dirty()).is_true()


## 配置/撤去が発生していない場合に接続関係が変化しない
func test_connections_unchanged_without_placement() -> void:
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports_before := _grid.get_active_output_ports()
	var has_connection_before: bool = ports_before[0]["has_connection"]
	# dirty flagなしで再度rebuild → 状態変化なし
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports_after := _grid.get_active_output_ports()
	assert_bool(ports_after[0]["has_connection"]).is_equal(has_connection_before)


## 接続なしから接続ありに変化する（ベルト追加後に再構築）
func test_connection_updates_after_belt_added() -> void:
	_grid.register_machine(1, 1, Vector2i(2, 2), Enums.Direction.N)
	# 最初はベルトなし → 接続なし
	_grid.rebuild_connections_if_dirty(_belt_grid)
	var ports := _grid.get_active_output_ports()
	assert_bool(ports[0]["has_connection"]).is_false()

	# ベルト追加後にmark_dirty→rebuild
	_belt_grid.add_tile(Vector2i(2, 3), Enums.Direction.S)
	_grid.mark_dirty()
	_grid.rebuild_connections_if_dirty(_belt_grid)
	ports = _grid.get_active_output_ports()
	assert_bool(ports[0]["has_connection"]).is_true()
