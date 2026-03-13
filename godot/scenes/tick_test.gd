extends Node

## tick_firedシグナルの動作確認用スクリプト
## TickEngineNodeを追加してtick_firedシグナルをprint出力する

var _tick_engine: TickEngineNode
var _tick_count: int = 0

func _ready() -> void:
	_tick_engine = TickEngineNode.new()
	add_child(_tick_engine)
	_tick_engine.tick_fired.connect(_on_tick_fired)
	print("TickEngineNode initialized. Waiting for tick_fired signals...")

func _on_tick_fired(tick: int) -> void:
	_tick_count += 1
	print("tick_fired: tick=", tick, " (fired count: ", _tick_count, ")")
	if _tick_count >= 5:
		print("SUCCESS: tick_fired signal received ", _tick_count, " times. Test passed!")
		get_tree().quit()
