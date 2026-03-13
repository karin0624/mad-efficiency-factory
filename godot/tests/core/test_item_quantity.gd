extends GdUnitTestSuite


var _sut: ItemQuantity

func before_test() -> void:
	_sut = ItemQuantity.new()

func after_test() -> void:
	_sut = null

# --- タスク 2.1: ItemQuantityのユニットテスト ---

func test_default_initial_value_is_zero() -> void:
	# デフォルト値（初期値0、上限999）でインスタンスを生成し、初期状態が正しいことを検証する
	assert_int(_sut.current).is_equal(0)
	assert_int(_sut.max_value).is_equal(999)

func test_custom_initial_value_and_max() -> void:
	# カスタム初期値と上限値でインスタンスを生成し、各属性が正しく保持されることを検証する
	var q := ItemQuantity.new(50, 200)
	assert_int(q.current).is_equal(50)
	assert_int(q.max_value).is_equal(200)

func test_add_increases_quantity() -> void:
	# 加算で数量が正しく増加することを検証する
	_sut.add(10)
	assert_int(_sut.current).is_equal(10)

func test_add_clamps_at_max_value() -> void:
	# 加算の結果が上限値を超える場合、上限値にクランプされることを検証する
	var q := ItemQuantity.new(990, 999)
	q.add(20)
	assert_int(q.current).is_equal(999)

func test_add_exactly_to_max() -> void:
	# 加算で上限値ちょうどになる場合の検証
	var q := ItemQuantity.new(0, 100)
	q.add(100)
	assert_int(q.current).is_equal(100)

func test_sub_decreases_quantity() -> void:
	# 減算で数量が正しく減少することを検証する
	var q := ItemQuantity.new(50)
	q.sub(20)
	assert_int(q.current).is_equal(30)

func test_sub_clamps_at_zero() -> void:
	# 減算の結果が0を下回る場合、0にクランプされることを検証する
	var q := ItemQuantity.new(5)
	q.sub(10)
	assert_int(q.current).is_equal(0)

func test_sub_exactly_to_zero() -> void:
	# 減算でちょうど0になる場合の検証
	var q := ItemQuantity.new(10)
	q.sub(10)
	assert_int(q.current).is_equal(0)

func test_is_refcounted_no_scene_tree_needed() -> void:
	# RefCountedを継承しシーンツリーなしでインスタンス化できることを検証する
	assert_object(_sut).is_instanceof(RefCounted)
	assert_int(_sut.current).is_equal(0)
