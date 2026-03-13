class_name TickEngineNode
extends Node

## TickEngineNode — Godotフレームループとティックエンジンのブリッジ
##
## _physics_process(delta)でGodotエンジンからdeltaTimeを受け取り、
## TickClockに転送し、ティック発火をシグナルで通知する。
## ティック非発火フレームではシグナルを発行しない。

## ティックが発火するたびに発行されるシグナル
## tick: 発火時のcurrent_tick値
signal tick_fired(tick: int)

## 内部TickClockインスタンスへの参照（外部からアクセス可能）
var clock: TickClock


func _ready() -> void:
	clock = TickClock.new()


func _physics_process(delta: float) -> void:
	# delta（float秒）→μs（int）変換: int(delta * 1_000_000)
	var delta_usec: int = int(delta * 1_000_000)
	var ticks_fired: int = clock.advance(delta_usec)

	# 発火数分だけtick_firedシグナルをtick昇順で発行
	# ticks_firedが0の場合はシグナルを発行しない
	if ticks_fired > 0:
		# advance()後のcurrent_tickから逆算してtick昇順でシグナル発行
		var start_tick: int = clock.current_tick - ticks_fired + 1
		for i in range(ticks_fired):
			tick_fired.emit(start_tick + i)
