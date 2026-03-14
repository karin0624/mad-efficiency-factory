class_name MachinePortTransfer
extends RefCounted

## MachinePortTransfer — 毎ティックの出力ポート→ベルト・ベルト→入力ポートのアイテム転送
##
## 出力ポート処理: バッファにアイテムがあり、接続先ベルトが空なら転送。
## 入力ポート処理: バッファが空で、接続先ベルトに到達済みアイテムがあれば引き込み。
## アイテム保存則: 転送は常にアトミック（1個除去 → 1個追加）。
## バックプレッシャー: 条件不成立時はスキップ（毎ティックのチェックで自然に実現）。
## SceneTree/Node APIに依存しない純粋なサービスクラス。


## 全出力ポートを処理する（Output → Belt）
## Preconditions: port_grid の接続が最新（rebuild_connections_if_dirty 済み）
## Returns: 転送されたアイテム数
func process_output_ports(port_grid: MachinePortGrid, belt_grid: BeltGrid) -> int:
	var transferred := 0
	var output_ports := port_grid.get_active_output_ports()

	for port: Dictionary in output_ports:
		# バッファが空ならスキップ
		if port["item_id"] == 0:
			continue

		# 接続先なしならスキップ
		if not port["has_connection"]:
			continue

		var belt_pos: Vector2i = port["connected_belt_pos"]
		var item_id: int = port["item_id"]

		# アトミック転送: ベルトに空きがある場合のみ
		if belt_grid.set_item(belt_pos, item_id):
			port["item_id"] = 0  # ポートバッファをクリア
			transferred += 1

	return transferred


## 全入力ポートを処理する（Belt → Input）
## Preconditions: port_grid の接続が最新（rebuild_connections_if_dirty 済み）
## Returns: 引き込まれたアイテム数
func process_input_ports(port_grid: MachinePortGrid, belt_grid: BeltGrid) -> int:
	var pulled := 0
	var input_ports := port_grid.get_active_input_ports()

	for port: Dictionary in input_ports:
		# バッファが満杯ならスキップ
		if port["item_id"] != 0:
			continue

		# 接続先なしならスキップ
		if not port["has_connection"]:
			continue

		var belt_pos: Vector2i = port["connected_belt_pos"]
		var belt_tile := belt_grid.get_tile(belt_pos)
		if belt_tile == null:
			continue

		# ベルトにアイテムがなければスキップ
		if not belt_tile.has_item():
			continue

		# 到達済み（progress >= 1.0）チェック
		if belt_tile.progress < 1.0:
			continue

		# アトミック引き込み: ベルトから除去 → ポートに追加
		var item_id: int = belt_tile.item_id
		belt_grid.clear_item(belt_pos)
		port["item_id"] = item_id
		pulled += 1

	return pulled
