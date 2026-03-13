extends GdUnitTestSuite


var _catalog: ItemCatalog

func before_test() -> void:
	_catalog = ItemCatalog.new()

func after_test() -> void:
	_catalog = null

# --- タスク 3.1: ItemCatalogのユニットテスト（登録・検索） ---

func test_register_adds_definition_to_catalog() -> void:
	# 新しいアイテム定義を登録し、カタログに追加されることを検証する
	var def := ItemDefinition.new(1, "鉄鉱石")
	var result := _catalog.register(def)
	assert_bool(result).is_true()
	assert_int(_catalog.size()).is_equal(1)

func test_register_returns_false_for_duplicate_id() -> void:
	# 同一IDのアイテム定義を重複登録しようとした場合、登録が拒否されることを検証する
	var def1 := ItemDefinition.new(1, "鉄鉱石")
	var def2 := ItemDefinition.new(1, "別の鉄鉱石")
	_catalog.register(def1)
	var result := _catalog.register(def2)
	assert_bool(result).is_false()

func test_duplicate_register_does_not_change_existing() -> void:
	# 重複登録の試行後、既存の登録が変更されていないことを検証する
	var def1 := ItemDefinition.new(1, "鉄鉱石")
	var def2 := ItemDefinition.new(1, "変更後の名前")
	_catalog.register(def1)
	_catalog.register(def2)
	var found := _catalog.get_by_id(1)
	assert_str(found.display_name).is_equal("鉄鉱石")

func test_get_by_id_returns_definition_for_valid_id() -> void:
	# 有効なIDで検索し、対応するアイテム定義が返されることを検証する
	var def := ItemDefinition.new(5, "精錬鉄")
	_catalog.register(def)
	var found := _catalog.get_by_id(5)
	assert_object(found).is_not_null()
	assert_int(found.id).is_equal(5)
	assert_str(found.display_name).is_equal("精錬鉄")

func test_get_by_id_returns_null_for_nonexistent_id() -> void:
	# 存在しないIDで検索した場合、nullが返されることを検証する
	var found := _catalog.get_by_id(999)
	assert_object(found).is_null()

func test_get_by_id_returns_null_for_id_zero() -> void:
	# ID=0で検索した場合、nullが返されることを検証する
	var found := _catalog.get_by_id(0)
	assert_object(found).is_null()

func test_new_registration_does_not_affect_existing() -> void:
	# 新しいアイテム定義の追加登録後、既存のアイテム定義が変更されていないことを検証する
	var def1 := ItemDefinition.new(1, "鉄鉱石")
	var def2 := ItemDefinition.new(2, "精錬鉄")
	_catalog.register(def1)
	_catalog.register(def2)
	var found1 := _catalog.get_by_id(1)
	assert_int(found1.id).is_equal(1)
	assert_str(found1.display_name).is_equal("鉄鉱石")

func test_is_refcounted_no_scene_tree_needed() -> void:
	# RefCountedを継承しシーンツリーなしでインスタンス化できることを検証する
	assert_object(_catalog).is_instanceof(RefCounted)
	assert_int(_catalog.size()).is_equal(0)

# --- タスク 3.3: MVP初期データのユニットテスト ---

func test_default_catalog_has_iron_ore_id_one() -> void:
	# デフォルトカタログ生成で鉄鉱石（ID=1）が登録されていることを検証する
	var default_catalog := ItemCatalog.create_default()
	var found := default_catalog.get_by_id(1)
	assert_object(found).is_not_null()

func test_default_catalog_has_refined_iron_id_two() -> void:
	# デフォルトカタログ生成で精錬鉄（ID=2）が登録されていることを検証する
	var default_catalog := ItemCatalog.create_default()
	var found := default_catalog.get_by_id(2)
	assert_object(found).is_not_null()

func test_default_catalog_iron_ore_by_id() -> void:
	# ID=1で検索し鉄鉱石のアイテム定義が返されることを検証する
	var default_catalog := ItemCatalog.create_default()
	var found := default_catalog.get_by_id(1)
	assert_int(found.id).is_equal(1)
	assert_str(found.display_name).is_not_empty()

func test_default_catalog_refined_iron_by_id() -> void:
	# ID=2で検索し精錬鉄のアイテム定義が返されることを検証する
	var default_catalog := ItemCatalog.create_default()
	var found := default_catalog.get_by_id(2)
	assert_int(found.id).is_equal(2)
	assert_str(found.display_name).is_not_empty()

func test_default_catalog_has_two_items() -> void:
	# デフォルトカタログに2件のアイテム定義が登録されていることを検証する
	var default_catalog := ItemCatalog.create_default()
	assert_int(default_catalog.size()).is_equal(2)
