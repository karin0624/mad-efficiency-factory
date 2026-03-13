extends GdUnitTestSuite

var _clock: TickClock

func before_test() -> void:
	_clock = TickClock.new()

func after_test() -> void:
	_clock = null

# --- タスク 1.1: 固定レート発火テスト ---

func test_one_tick_fires_at_exact_interval() -> void:
	# ティック間隔（16667μs）ちょうどの入力で1ティック発火
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(1)

func test_two_ticks_fire_at_double_interval() -> void:
	# ティック間隔の2倍（33334μs）の入力で2ティック発火
	var ticks := _clock.advance(33334)
	assert_int(ticks).is_equal(2)

func test_no_tick_below_interval() -> void:
	# ティック間隔未満（10000μs）の入力でティックが発火しない
	var ticks := _clock.advance(10000)
	assert_int(ticks).is_equal(0)

func test_fractional_carryover() -> void:
	# 端数繰り越しの検証: 20000μs入力で1ティック発火し、残りの蓄積時間が3333μsであること
	var ticks := _clock.advance(20000)
	assert_int(ticks).is_equal(1)
	# 次のadvanceで3333μs分追加: 3333 + 13334 = 16667 でちょうど1ティック
	var ticks2 := _clock.advance(13334)
	assert_int(ticks2).is_equal(1)

func test_accumulation_across_frames() -> void:
	# 連続フレームでの蓄積と発火: 10000μs × 2回で1ティック発火し、残り3333μs
	var ticks1 := _clock.advance(10000)
	assert_int(ticks1).is_equal(0)
	var ticks2 := _clock.advance(10000)
	assert_int(ticks2).is_equal(1)
	# 残り3333μsを確認: 次の13334μsで1ティック
	var ticks3 := _clock.advance(13334)
	assert_int(ticks3).is_equal(1)

func test_initial_tick_count_is_zero() -> void:
	# 初期ティックカウントが0であることの検証
	assert_int(_clock.current_tick).is_equal(0)

# --- タスク 1.3: ティックカウント管理テスト ---

func test_tick_count_increases_by_ticks_fired() -> void:
	# advance()呼び出しごとにcurrent_tickが発火数分だけ正確に増加
	_clock.advance(16667)
	assert_int(_clock.current_tick).is_equal(1)
	_clock.advance(33334)
	assert_int(_clock.current_tick).is_equal(3)

func test_tick_count_monotonically_increases() -> void:
	# 単調増加の検証: 複数回のadvance()で減少しないこと
	var prev_tick := _clock.current_tick
	for i in range(10):
		_clock.advance(8000)
		assert_int(_clock.current_tick).is_greater_equal(prev_tick)
		prev_tick = _clock.current_tick

func test_tick_count_readable() -> void:
	# current_tickが外部から読み取り可能であることの検証
	_clock.advance(16667)
	var tick := _clock.current_tick
	assert_int(tick).is_equal(1)

# --- タスク 1.4: キャッチアップ制限テスト ---

func test_catchup_limit_five_ticks() -> void:
	# 100000μs（100ms、6ティック相当）入力で5ティックのみ発火することの検証
	var ticks := _clock.advance(100000)
	assert_int(ticks).is_equal(5)

func test_catchup_resets_accumulator() -> void:
	# キャッチアップ上限到達後に蓄積時間が0にリセットされることの検証
	_clock.advance(100000)
	# 蓄積時間が0にリセットされていれば、次のadvanceでは少量のdeltaでティック不発
	var ticks := _clock.advance(10000)
	assert_int(ticks).is_equal(0)

func test_catchup_limit_applies_to_large_input() -> void:
	# 200000μs（200ms、12ティック相当）でも5ティック上限が適用されることの検証
	var ticks := _clock.advance(200000)
	assert_int(ticks).is_equal(5)

func test_normal_firing_resumes_after_catchup() -> void:
	# 上限到達直後の次フレームで正常にティック発火が再開することの検証
	_clock.advance(100000)  # キャッチアップ上限到達
	var ticks := _clock.advance(16667)  # 次フレームで1ティック
	assert_int(ticks).is_equal(1)

# --- タスク 2.1: 一時停止・再開テスト ---

func test_no_tick_after_pause() -> void:
	# pause()後のadvance()で0ティック発火し、ティックカウントが変更されないこと
	_clock.pause()
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(0)
	assert_int(_clock.current_tick).is_equal(0)

func test_large_delta_during_pause() -> void:
	# 一時停止中に大量のdelta_usec（例: 1000000μs）を与えてもティックが発火しないこと
	_clock.pause()
	var ticks := _clock.advance(1000000)
	assert_int(ticks).is_equal(0)

func test_resume_resets_accumulator() -> void:
	# resume()後に蓄積時間が0にリセットされることの検証
	_clock.pause()
	_clock.advance(16667)  # 一時停止中は蓄積しない
	_clock.resume()
	# resume後の最初のadvanceでは蓄積時間0から始まるため、小さなdeltaではティック不発
	var ticks := _clock.advance(10000)
	assert_int(ticks).is_equal(0)

func test_normal_firing_after_resume() -> void:
	# resume()後の最初のadvance()で正常にティック発火が再開することの検証
	_clock.pause()
	_clock.advance(1000000)
	_clock.resume()
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(1)

func test_no_catchup_after_resume() -> void:
	# resume()後に大量のキャッチアップが発生しないことの検証（蓄積時間リセットにより保証）
	_clock.pause()
	_clock.advance(1000000)  # 一時停止中の大量時間
	_clock.resume()
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(1)  # 通常の1ティックのみ

func test_pause_is_idempotent() -> void:
	# pause()の冪等性
	_clock.pause()
	_clock.pause()  # 2回目のpauseは安全
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(0)

func test_resume_is_idempotent() -> void:
	# resume()の冪等性: 既にrunning中のresume()呼び出しが安全に処理されること
	_clock.resume()  # 既にrunning状態でresume
	var ticks := _clock.advance(16667)
	assert_int(ticks).is_equal(1)

# --- タスク 2.3: 決定性テスト ---

func test_determinism_same_sequence() -> void:
	# 同一のdelta_usecシーケンスを2回実行し、ティック発火パターンとcurrent_tickが完全一致
	var sequence := [16667, 8000, 25000, 16667, 100000]
	var clock1 := TickClock.new()
	var clock2 := TickClock.new()
	var results1 := []
	var results2 := []
	for d in sequence:
		results1.append(clock1.advance(d))
		results2.append(clock2.advance(d))
	assert_array(results1).is_equal(results2)
	assert_int(clock1.current_tick).is_equal(clock2.current_tick)

func test_no_float_accumulation_error() -> void:
	# 整数演算による累積誤差なしの検証: 16667μs × 60回で正確に60ティック発火
	var total_ticks := 0
	for i in range(60):
		total_ticks += _clock.advance(16667)
	assert_int(total_ticks).is_equal(60)

func test_determinism_with_pause_resume() -> void:
	# pause/resume を含むシーケンスでの再現性検証
	var clock1 := TickClock.new()
	var clock2 := TickClock.new()
	# clock1のシーケンス
	clock1.advance(16667)
	clock1.pause()
	clock1.advance(50000)
	clock1.resume()
	clock1.advance(16667)
	# clock2のシーケンス（同じ）
	clock2.advance(16667)
	clock2.pause()
	clock2.advance(50000)
	clock2.resume()
	clock2.advance(16667)
	assert_int(clock1.current_tick).is_equal(clock2.current_tick)

# --- タスク 2.4: フレームレート非依存性テスト ---

func test_120fps_fires_60_ticks_per_second() -> void:
	# 120fps相当のdeltaシーケンス（8334μs × 120回）で60ティック発火することの検証
	# 1/120s = 8333.33μs → int()で切り捨て → 端数を考慮して8334μs（切り上げ相当）を使用
	# 8334μs × 120 = 1000080μs → 60ティック発火
	var total_ticks := 0
	for i in range(120):
		total_ticks += _clock.advance(8334)
	assert_int(total_ticks).is_equal(60)

func test_60fps_fires_60_ticks_per_second() -> void:
	# 60fps相当のdeltaシーケンス（16667μs × 60回）で60ティック発火することの検証
	var total_ticks := 0
	for i in range(60):
		total_ticks += _clock.advance(16667)
	assert_int(total_ticks).is_equal(60)

func test_30fps_fires_60_ticks_per_second() -> void:
	# 30fps相当のdeltaシーケンス（33334μs × 30回）で60ティック発火することの検証
	# 1/30s = 33333.33μs → int()で切り捨て → 端数を考慮して33334μsを使用
	# 33334μs × 30 = 1000020μs → 60ティック発火
	var total_ticks := 0
	for i in range(30):
		total_ticks += _clock.advance(33334)
	assert_int(total_ticks).is_equal(60)

func test_same_ticks_for_same_realtime_different_fps() -> void:
	# 異なるフレームレートで同一の実時間に対して同一のティック数が発火することの比較検証
	# 各フレームレートで1秒分のdeltaを合算した場合に同一ティック数が発火することを検証
	var clock_120 := TickClock.new()
	var clock_60 := TickClock.new()
	var clock_30 := TickClock.new()
	var ticks_120 := 0
	var ticks_60 := 0
	var ticks_30 := 0
	for i in range(120):
		ticks_120 += clock_120.advance(8334)
	for i in range(60):
		ticks_60 += clock_60.advance(16667)
	for i in range(30):
		ticks_30 += clock_30.advance(33334)
	# 全て同じティック数（60）であること
	assert_int(ticks_120).is_equal(60)
	assert_int(ticks_60).is_equal(60)
	assert_int(ticks_30).is_equal(60)
