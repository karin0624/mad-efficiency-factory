extends GdUnitTestSuite

## TickEngineNode のL2テスト（SceneTree依存）
## GdUnit4のauto_free() + add_child()を使用してNodeをSceneTreeに追加し、
## シグナル発行を検証する。
##
## 注意: GdUnit4テストではラムダ関数でのシグナル接続が機能しないため、
## 名前付き関数を使用してシグナルを収集する。

# シグナル収集用変数
var _emitted_ticks: Array = []

func _on_tick_fired(tick: int) -> void:
	_emitted_ticks.append(tick)

func _create_node() -> TickEngineNode:
	var node: TickEngineNode = auto_free(TickEngineNode.new())
	add_child(node)
	return node

func before_test() -> void:
	_emitted_ticks.clear()

# --- タスク 3.1: シグナル発行テスト ---

func test_tick_fired_signal_emitted_on_tick() -> void:
	# ティック発火時にtick_firedシグナルが発行されることの検証
	var node := _create_node()
	node.tick_fired.connect(_on_tick_fired)
	# delta = 16667μs / 1_000_000 = 0.016667秒 → 1ティック発火
	node._physics_process(0.016667)
	assert_array(_emitted_ticks).has_size(1)
	assert_int(_emitted_ticks[0]).is_equal(1)  # 最初のティック番号は1

func test_no_signal_when_no_tick() -> void:
	# ティック非発火フレーム（蓄積時間がティック間隔未満）でシグナルが発行されないことの検証
	var node := _create_node()
	node.tick_fired.connect(_on_tick_fired)
	node._physics_process(0.005)  # 5000μs < 16667μs → ティック不発火
	assert_array(_emitted_ticks).is_empty()

func test_multiple_ticks_emitted_in_order() -> void:
	# 1フレーム内で複数ティック発火時にシグナルがtick昇順で発行されることの検証
	var node := _create_node()
	node.tick_fired.connect(_on_tick_fired)
	# 2ティック分のdelta（33334μs = 0.033334秒）
	node._physics_process(0.033334)
	assert_array(_emitted_ticks).has_size(2)
	# tick昇順であることを確認（tick_values[0] < tick_values[1]）
	assert_int(_emitted_ticks[0]).is_less(_emitted_ticks[1])
	# 連番であることを確認
	assert_int(_emitted_ticks[1]).is_equal(_emitted_ticks[0] + 1)

func test_delta_to_usec_conversion() -> void:
	# delta（float秒）→μs（int）変換の精度検証
	# int(0.016667 * 1_000_000) = 16667μs → 正確に1ティック発火
	var node := _create_node()
	node.tick_fired.connect(_on_tick_fired)
	node._physics_process(0.016667)  # 16667μs → 1ティック発火
	assert_array(_emitted_ticks).has_size(1)

func test_tick_value_matches_current_tick() -> void:
	# tick_firedシグナルで渡されるtick値がadvance後のcurrent_tickと一致することの検証
	var node := _create_node()
	node.tick_fired.connect(_on_tick_fired)
	node._physics_process(0.016667)  # 1ティック発火: 16667μs → current_tick = 1
	# シグナルが発行されていることを確認
	assert_array(_emitted_ticks).has_size(1)
	# emitted_tick (1) == current_tick (1)
	assert_int(_emitted_ticks[0]).is_equal(node.clock.current_tick)
