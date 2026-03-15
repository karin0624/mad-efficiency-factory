class_name ItemQuantity
extends RefCounted


## ItemQuantity — アイテム数量の安全な増減と範囲クランプ
##
## SceneTree/Node APIに依存しない純粋なロジッククラス。
## 数量値を0以上かつ上限値以下の有効範囲内に保持する。
## 加算・減算の結果が範囲外になった場合はクランプする（エラーを発生させない）。

## 数量値の上限デフォルト値
const DEFAULT_MAX: int = 999

## 現在の数量値（0 <= current <= max_value）
var current: int

## 上限値
var max_value: int


## アイテム数量を生成する。
## Preconditions: p_max_value > 0, 0 <= initial_value <= p_max_value
func _init(initial_value: int = 0, p_max_value: int = DEFAULT_MAX) -> void:
	assert(p_max_value > 0, "ItemQuantity: max_value must be positive (got %d)" % p_max_value)
	assert(initial_value >= 0, "ItemQuantity: initial_value must be non-negative (got %d)" % initial_value)
	assert(initial_value <= p_max_value,
		"ItemQuantity: initial_value (%d) must not exceed max_value (%d)"
		% [initial_value, p_max_value])
	current = initial_value
	max_value = p_max_value


## amountを加算し、上限を超えた場合はクランプする。
## Preconditions: amount >= 0
## Postconditions: current = min(current + amount, max_value)
func add(amount: int) -> void:
	assert(amount >= 0, "ItemQuantity.add: amount must be non-negative (got %d)" % amount)
	current = mini(current + amount, max_value)


## amountを減算し、0を下回った場合はクランプする。
## Preconditions: amount >= 0
## Postconditions: current = max(current - amount, 0)
func sub(amount: int) -> void:
	assert(amount >= 0, "ItemQuantity.sub: amount must be non-negative (got %d)" % amount)
	current = maxi(current - amount, 0)
