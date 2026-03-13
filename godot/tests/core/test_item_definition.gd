extends GdUnitTestSuite


var _sut: ItemDefinition

func before_test() -> void:
	_sut = ItemDefinition.new(1, "Iron Ore")

func after_test() -> void:
	_sut = null

# --- タスク 1.1: ItemDefinitionのユニットテスト ---

func test_instance_holds_id_and_display_name() -> void:
	# 正の整数IDと空でない表示名でインスタンスを生成し、各属性が正しく保持されることを検証する
	var def := ItemDefinition.new(42, "精錬鉄")
	assert_int(def.id).is_equal(42)
	assert_str(def.display_name).is_equal("精錬鉄")

func test_instance_with_id_one() -> void:
	# ID=1での正常生成を検証する
	assert_int(_sut.id).is_equal(1)
	assert_str(_sut.display_name).is_equal("Iron Ore")

func test_is_refcounted_no_scene_tree_needed() -> void:
	# RefCountedを継承しシーンツリーなしでインスタンス化できることを検証する
	var def := ItemDefinition.new(10, "テストアイテム")
	assert_object(def).is_instanceof(RefCounted)
	assert_int(def.id).is_equal(10)

func test_id_is_immutable_after_creation() -> void:
	# 生成後にIDが変更されないことを検証する（読み取り専用）
	var def := ItemDefinition.new(5, "テスト")
	var id_before := def.id
	# IDの読み取りを2回行い、値が変わらないことを確認
	assert_int(def.id).is_equal(id_before)
	assert_int(def.id).is_equal(5)

func test_display_name_is_immutable_after_creation() -> void:
	# 生成後に表示名が変更されないことを検証する（読み取り専用）
	var def := ItemDefinition.new(5, "テスト名")
	var name_before := def.display_name
	assert_str(def.display_name).is_equal(name_before)
	assert_str(def.display_name).is_equal("テスト名")
