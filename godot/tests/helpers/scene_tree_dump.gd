class_name SceneTreeDump
extends RefCounted

## SceneTreeDump — シーンツリー構造をテキストダンプするテスト専用ユーティリティ
##
## Node引数が必要なためcore/には置けない。テスト専用。
## ファイル保存にはGameStateDump.save()を使用。


## シーンツリーをテキストダンプする
## root: ダンプ対象のルートノード
## max_depth: 再帰の最大深さ（デフォルト6）
static func dump(root: Node, max_depth: int = 6) -> String:
	if root == null:
		return ""

	var lines: Array[String] = []
	lines.append("=== SCENE TREE (root: %s) ===" % root.name)
	_dump_node(root, 0, max_depth, lines)
	return "\n".join(lines)


static func _dump_node(node: Node, depth: int, max_depth: int, lines: Array[String]) -> void:
	if depth > max_depth:
		return

	var indent := "  ".repeat(depth)
	var info := "%s%s (%s)" % [indent, node.name, node.get_class()]

	# Node2D/Control: position を表示
	if node is Node2D:
		info += " pos=(%d,%d)" % [int(node.position.x), int(node.position.y)]
	elif node is Control:
		info += " pos=(%d,%d)" % [int(node.position.x), int(node.position.y)]

	# CanvasItem: visible を表示
	if node is CanvasItem:
		info += " visible=%s" % str(node.visible)

	# Label: text を表示
	if node is Label:
		var text: String = node.text
		if text.length() > 30:
			text = text.substr(0, 27) + "..."
		info += " text=\"%s\"" % text

	lines.append(info)

	for child in node.get_children():
		_dump_node(child, depth + 1, max_depth, lines)
