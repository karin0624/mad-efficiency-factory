# Unity MCP 機能リファレンス

> ソース: com.unity.ai.assistant@2.0 公式ドキュメント + コミュニティ実装調査
> 注意: 2.0.0-pre.1（プレリリース版）のため、ツール名やAPIは今後変更の可能性がある

## 1. アーキテクチャ概要

Unity MCPは、Model Context Protocol (MCP) を通じて、AI エージェント（Claude Code, Cursor, Windsurf, Claude Desktop等）とUnity Editorを接続するシステム。

**通信方式:**
- IPCブリッジ: Windows は Named Pipes、macOS/Linux は Unix Socket
- リレーバイナリが `~/.unity/relay/` に自動インストールされMCPサーバーとして動作
- 設定画面: Edit > Project Settings > AI > Unity MCP

**セキュリティ:**
- Gateway接続: 自動承認
- Direct接続: ユーザーの手動承認が必要

**カスタムツール拡張:**
- `[McpTool]` アトリビュートを付与した `public static` メソッド
- `IUnityMcpTool` / `IUnityMcpTool<T>` インターフェースの実装
- ランタイム API による登録
- エディタ起動時に TypeCache スキャンで自動検出・登録

---

## 2. ビルトインツール一覧

### 2.1 シーン管理

| ツール | アクション | 説明 |
|---|---|---|
| `Unity_ManageScene` | create | 新規シーンアセットを作成 |
| | open | シーンをエディタで開く（Additive対応） |
| | save | 現在のシーンを保存（Save As対応） |
| | unload | Additiveシーンをアンロード |
| | set_active | アクティブシーンを設定 |
| | get_data / get_info | ルートオブジェクト一覧、シーンメタデータ取得 |
| | list_opened | 現在開いているシーン一覧 |
| | delete | シーンを削除しBuild Settingsから除去 |

### 2.2 GameObject管理

| ツール | アクション | 説明 |
|---|---|---|
| `Unity_ManageGameObject` | create | 新規GameObject作成（Empty/Primitive） |
| | destroy / delete | GameObjectを削除 |
| | duplicate | GameObjectを複製（リネーム・リペアレント可能） |
| | find | Name/Tag/Type による検索 |
| | modify / update | Transform, Name, Tag, Layer, Active/Static状態の更新 |
| | set_parent / reparent | 親子関係の変更 |

### 2.3 コンポーネント管理

| ツール | アクション | 説明 |
|---|---|---|
| `manage_components` | add | コンポーネントを追加（例: Rigidbody） |
| | destroy | コンポーネントを削除 |
| | get | コンポーネントの詳細情報を取得 |
| | modify / update | フィールド・プロパティ・オブジェクト参照を設定 |
| | list_all | 利用可能なコンポーネント型の一覧 |

### 2.4 アセット管理

| ツール | アクション | 説明 |
|---|---|---|
| `Unity_ManageAsset` | import | 再インポート（プロパティ設定付き） |
| | create | 新規アセット作成（マテリアル、PhysicsMaterial、ScriptableObject、フォルダ） |
| | modify | 既存アセットのプロパティ変更 |
| | delete | アセットを削除 |
| | duplicate / copy | アセットを複製 |
| | move / rename | 移動・リネーム |
| | search / find | フィルタ付き検索（例: `t:Texture`）、ページネーション対応 |
| | get_info / get_data | メタデータ取得 |
| | create_folder | フォルダ作成（ネストパス対応） |
| | refresh | AssetDatabase の強制リフレッシュ |

### 2.5 Prefab操作

| ツール | アクション | 説明 |
|---|---|---|
| `manage_prefabs` | instantiate | Prefabをアクティブシーンに生成 |
| | create | シーンオブジェクトからPrefabを作成 |
| | open | Prefab Modeを開く |
| | close | Prefab Modeを閉じる |
| | save | Prefab Modeの変更を保存 |

### 2.6 スクリプト管理・C#コード実行

| ツール | 説明 |
|---|---|
| `Unity_ManageScript` | C#スクリプトファイルの作成・更新・削除 |
| `script-execute` | C#コードスニペットを動的にコンパイルして実行 |
| `script-read` | `.cs` ファイルの内容を読み取り |
| `validate_script` | スクリプトの構文・名前空間の検証 |
| `recompile_scripts` | 全スクリプトの再コンパイル強制実行 |
| `find_in_file` | プロジェクトファイル内のコンテンツ検索 |

### 2.7 テスト実行

| ツール | 説明 |
|---|---|
| `run_tests` | Unity Test Runner を使用してテストを実行 |

- EditMode テストと PlayMode テストの両方に対応
- オプションのフィルタ指定が可能（特定テストのみ実行）
- テスト結果のレポートを返却（pass/fail の詳細）
- 失敗時はスタックトレースを含む詳細情報を提供

### 2.8 コンソールログ

| ツール | 説明 |
|---|---|
| `Unity_ReadConsole` | Unity Console のログを取得（ページネーション対応） |
| `send_console_log` | Unity Console にログメッセージを送信 |

### 2.9 エディタ制御

| ツール | アクション | 説明 |
|---|---|---|
| `Unity_ManageEditor` | play / pause / stop | Play Mode の制御 |
| | get_state | 再生/一時停止/編集モード状態の取得 |
| | get_project_root | プロジェクトルートのパス取得 |
| | get_windows | 開いているエディタウィンドウ一覧 |
| | get_selection / set_selection | 現在の選択オブジェクト取得・設定 |
| | add_tag / remove_tag / get_tags | Tag管理 |
| | add_layer / remove_layer / get_layers | Layer管理 |

### 2.10 マテリアル・シェーダー

| ツール | 説明 |
|---|---|
| `manage_material` | マテリアル作成・プロパティ変更・適用 |
| `manage_shader` | シェーダー編集・一覧取得 |
| `manage_texture` | テクスチャアセット管理 |

### 2.11 スクリーンショット

| ツール | 説明 |
|---|---|
| `screenshot-camera` | カメラからスクリーンショットを撮影 |
| `screenshot-game-view` | Game View のスクリーンショット |
| `screenshot-scene-view` | Scene View のスクリーンショット |

### 2.12 その他

| ツール | 説明 |
|---|---|
| `manage_animation` | アニメーションアセット・コントローラーの管理 |
| `manage_camera` | カメラ設定（Cinemachine対応） |
| `manage_ui` | Unity UI 要素・レイアウトの調整 |
| `manage_vfx` | Visual Effects コンポーネント管理 |
| `manage_probuilder` | ProBuilder メッシュ編集 |
| `manage_scriptable_object` | ScriptableObject の管理 |
| `package-list / add / remove / search` | Package Manager 操作 |
| `batch_execute` | 複数操作の一括実行（ロールバック対応） |
| `execute_menu_item` | エディタメニュー項目をプログラムから実行 |
| `reflection-method-find` | C# メソッド検索（public/private問わず） |
| `reflection-method-call` | 見つけたメソッドを実行 |

---

## 3. 制限事項・注意点

- `com.unity.ai.assistant@2.0` は **2.0.0-pre.1**（プレリリース版）
- 対応 Unity バージョン: Unity 6.0.60f1 または Unity 6.3 (6000.3) 以降
- 公式パッケージのビルトインツールは上記カテゴリの一部。コミュニティ実装 (CoplayDev/unity-mcp, CoderGamester/mcp-unity, IvanMurzak/Unity-MCP) で提供されるツールも含む
- カスタムツールは `[McpTool]` アトリビュートで独自に追加可能
- オーディオ関連のツールは提供されていない
