# Nyamu MCP リファレンス

## アーキテクチャ

2サーバー構成:
```
Claude Code ←(stdio)→ mcp-server.js (Node.js) ←(HTTP)→ Unity HTTPサーバー (C#)
```

- Unity公式relay (`relay_win.exe`) とは別物
- `.mcp.json` のサーバー名: `nyamu`
- transport: stdio（nyamu.bat が node mcp-server.js を起動）

## 提供MCPツール（18ツール）

権威ソース: `unity/Library/PackageCache/dev.polyblank.nyamu@8255b643caa0/Node/mcp-server.js` の `capabilities.tools`

| カテゴリ | ツール名 |
|---------|---------|
| アセット | `assets_refresh` |
| コンパイル | `scripts_compile`, `scripts_compile_status` |
| シェーダー | `shaders_compile_single`, `shaders_compile_all`, `shaders_compile_regex`, `shaders_compile_status` |
| テスト | `tests_run_single`, `tests_run_all`, `tests_run_regex`, `tests_run_status`, `tests_run_cancel` |
| エディタ | `editor_status` |
| ログ | `editor_log_path`, `editor_log_head`, `editor_log_tail`, `editor_log_grep` |
| メニュー | `menu_items_execute` |

**注意**: `editor_exit_play_mode` はハンドラに存在するが `capabilities.tools` に未登録。MCP経由では使用不可。
**注意**: Play Mode開始ツールは存在しない。`menu_items_execute` で代替可能。

## 操作パターン

- **ファイル操作**: `Write`/`Edit`で直接操作 → `assets_refresh` でUnityに反映
- **テスト実行**: `tests_run_all`/`tests_run_single` → `tests_run_status` でポーリング（非同期）
- **コンパイル確認**: `scripts_compile` → `scripts_compile_status` でポーリング
- **エラー診断**: `editor_log_tail`/`editor_log_grep` でログ確認
- **ファイル新規/削除/移動**: `assets_refresh` が必要。既存ファイル編集のみなら `scripts_compile` で十分

## エラーハンドリング

- HTTP `-32603`（request failed）はコンパイル中に正常発生 → 3-5秒待ってリトライ
- `assets_refresh` 後にHTTPサーバーが一時的に再起動する場合あり

## WSL ↔ Windows パス変換

`/mnt/c/` → `C:\`

## 存在しないツール（使用禁止）

以下はNyamu未提供。呼び出してはならない:
- `Unity_ManageScript`, `manage_components`, `manage_prefabs`, `Unity_ManageGameObject`
- `screenshot-game-view`, `screenshot-scene-view`, `Unity_ManageScene`
- `Unity_ReadConsole`, `Unity_ManageEditor`

ファイル操作はClaude Codeの `Write`/`Edit` で行い、`assets_refresh` で反映する。
シーン構築はC#スクリプト（EditorScript）で自動化する。
