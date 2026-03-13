class_name TickClock
extends RefCounted

## TickClock — 固定レートティック発火の純粋ロジッククラス
##
## SceneTree/Node APIに依存しない純粋なロジックとして実装。
## deltaTime（μs整数）を受け取り、固定間隔(60tps = 16667μs)でティックを発火し、
## ティックカウントを管理する。

## ティック間隔: 1/60秒 = 16667μs
const TICK_INTERVAL_USEC: int = 16667

## 1フレームあたりの最大ティック発火数（スパイラルオブデス防止）
const MAX_TICKS_PER_FRAME: int = 5

## 現在のティックカウント（単調増加、初期値0）
var current_tick: int = 0

## 一時停止状態
var is_paused: bool = false

## 蓄積時間（μs単位）
var _accumulator_usec: int = 0


## 蓄積時間にdelta_usecを加算し、発火したティック数を返す。
## Preconditions: delta_usec >= 0
## Postconditions:
##   - 戻り値は0以上MAX_TICKS_PER_FRAME以下
##   - current_tickは戻り値の分だけ増加
##   - is_paused == trueの場合、戻り値は常に0
func advance(delta_usec: int) -> int:
	assert(delta_usec >= 0, "delta_usec must be non-negative")

	if is_paused:
		return 0

	_accumulator_usec += delta_usec

	var ticks_fired: int = 0
	while _accumulator_usec >= TICK_INTERVAL_USEC and ticks_fired < MAX_TICKS_PER_FRAME:
		_accumulator_usec -= TICK_INTERVAL_USEC
		current_tick += 1
		ticks_fired += 1

	# キャッチアップ上限到達時は蓄積時間を0にリセットして超過分を完全破棄
	if ticks_fired >= MAX_TICKS_PER_FRAME:
		_accumulator_usec = 0

	return ticks_fired


## シミュレーションを一時停止する。
## Postconditions: is_paused == true
func pause() -> void:
	is_paused = true


## シミュレーションを再開する。
## Postconditions: is_paused == false, accumulator == 0
func resume() -> void:
	is_paused = false
	_accumulator_usec = 0


## 全状態を初期値にリセットする。
## Postconditions: current_tick == 0, accumulator == 0, is_paused == false
func reset() -> void:
	current_tick = 0
	_accumulator_usec = 0
	is_paused = false
