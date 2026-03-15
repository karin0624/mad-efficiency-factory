extends GdUnitTestSuite

## L2テスト: SceneTreeDump のNode依存テスト


func test_dump_simple_hierarchy() -> void:
	var root: Node2D = auto_free(Node2D.new())
	root.name = "Root"
	var child := Node2D.new()
	child.name = "Child"
	root.add_child(child)
	child.owner = root

	var result := SceneTreeDump.dump(root)
	assert_str(result).contains("=== SCENE TREE (root: Root) ===")
	assert_str(result).contains("Root (Node2D)")
	assert_str(result).contains("Child (Node2D)")


func test_dump_shows_position() -> void:
	var root: Node2D = auto_free(Node2D.new())
	root.name = "Root"
	root.position = Vector2(128, 64)

	var result := SceneTreeDump.dump(root)
	assert_str(result).contains("pos=(128,64)")


func test_dump_shows_visibility() -> void:
	var root: Node2D = auto_free(Node2D.new())
	root.name = "Root"
	root.visible = false

	var result := SceneTreeDump.dump(root)
	assert_str(result).contains("visible=false")


func test_dump_max_depth_control() -> void:
	# 3段階の階層を作成
	var root: Node2D = auto_free(Node2D.new())
	root.name = "Level0"
	var level1 := Node2D.new()
	level1.name = "Level1"
	root.add_child(level1)
	level1.owner = root
	var level2 := Node2D.new()
	level2.name = "Level2"
	level1.add_child(level2)
	level2.owner = root

	# max_depth=0: rootのみ
	var result0 := SceneTreeDump.dump(root, 0)
	assert_str(result0).contains("Level0")
	assert_str(result0).not_contains("Level1")

	# max_depth=1: root + level1
	var result1 := SceneTreeDump.dump(root, 1)
	assert_str(result1).contains("Level1")
	assert_str(result1).not_contains("Level2")

	# max_depth=2: 全部
	var result2 := SceneTreeDump.dump(root, 2)
	assert_str(result2).contains("Level2")


func test_dump_null_returns_empty() -> void:
	var result := SceneTreeDump.dump(null)
	assert_str(result).is_equal("")


func test_dump_label_shows_text() -> void:
	var root: Control = auto_free(Control.new())
	root.name = "Root"
	var label := Label.new()
	label.name = "MyLabel"
	label.text = "Hello World"
	root.add_child(label)
	label.owner = root

	var result := SceneTreeDump.dump(root)
	assert_str(result).contains("text=\"Hello World\"")
