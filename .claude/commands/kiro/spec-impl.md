---
description: Execute spec tasks using TDD methodology
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, WebFetch, WebSearch, mcp__gopeak__lsp_diagnostics, mcp__gopeak__editor_run, mcp__gopeak__editor_stop, mcp__gopeak__runtime_status, mcp__gopeak__editor_debug_output, mcp__gopeak__dap_output, mcp__gopeak__script_create, mcp__gopeak__script_modify, mcp__gopeak__script_info, mcp__gopeak__scene_create, mcp__gopeak__scene_node_add, mcp__gopeak__scene_node_set, mcp__gopeak__scene_save, mcp__gopeak__signal_connect, mcp__gopeak__tool_groups
argument-hint: <feature-name> [task-numbers]
---

# 実装タスクエグゼキューター

<background_information>
- **ミッション**: 承認済みスペックに基づき、テスト駆動開発（TDD）手法を使用して実装タスクを実行する
- **成功基準**:
  - すべてのテストが実装コードの前に記述されている
  - コードがすべてのテストをパスし、リグレッションがない
  - タスクがtasks.mdで完了としてマークされている
  - 実装が設計と要件に整合している
</background_information>

<instructions>
## コアタスク
テスト駆動開発を使用して、機能 **$1** の実装タスクを実行する。

## 実行ステップ

### ステップ 1: コンテキストの読み込みとGoPoakの初期化

**必要なコンテキストをすべて読み込む**:
- `.kiro/specs/$1/spec.json`, `requirements.md`, `design.md`, `tasks.md`
- **`.kiro/steering/` ディレクトリ全体**（プロジェクトメモリとして）

**GoPoakの初期化**（ベストエフォート）:
1. ワークスペースルートから `project.godot` を検索してprojectPathを検出
2. 見つかった場合: `mcp__gopeak__tool_groups activate testing` でテストツールを有効化
3. `project.godot` が見つからないかGoPoakが利用できない場合: Bash専用モードを設定し **「GoPoak利用不可、Bash専用モードを使用」** を出力

**承認の検証**:
- spec.jsonでタスクが承認されていることを確認（未承認の場合は停止、「安全対策とフォールバック」を参照）

### ステップ 2: タスクの選択

**実行するタスクの決定**:
- `$2` が指定された場合: 以下のルールで指定されたタスク番号を実行:
  - `1` = メジャータスク1とそのすべてのサブタスク（例: 1.1, 1.2, ...）
  - `1.1` = サブタスク1.1のみ
  - `1,2,3` = メジャータスク1, 2, 3とそのすべてのサブタスク
  - `1.1,2.3` = 特定のサブタスクのみ
  - 完了済みタスク（`[x]`）はサイレントにスキップ
- それ以外: すべての保留タスク（tasks.mdの未チェック `- [ ]`）を実行

### ステップ 3: TDDによる実行

選択された各タスクについて、Kent BeckのTDDサイクルに従う:

1. **RED - 失敗するテストの記述**:
   - GdUnit4を使用して次の小さな機能のテストを記述（`extends GdUnitTestSuite`, `test_` プレフィックス）
   - **Layer 1**: テスト対象をRefCounted/Resourceとして直接`new()`で生成。SceneTree APIは使わない
   - **Layer 2**: テスト内で`auto_free()`+`add_child()`を使い、シグナル検証は`await assert_signal().is_emitted()`。`after_test()`でリーク防止を確実に行う
   - テストファイル作成には `mcp__gopeak__script_create` を優先。GoPoakが利用できない場合は `Write` ツールにフォールバック
   - Bashでテストを実行: `godot --headless --path <projectPath> -s addons/gdUnit4/bin/GdUnitCmdTool.gd`
   - テストは失敗するはず（コードがまだ存在しないため）

2. **GREEN - 最小限のコードの記述**:
   - テストをパスさせる最もシンプルなソリューションを実装
   - 新規GDScriptファイルには `mcp__gopeak__script_create`、編集には `mcp__gopeak__script_modify` を使用。`Write`/`Edit` ツールにフォールバック
   - シーン構築: `mcp__gopeak__scene_create`, `scene_node_add`, `scene_node_set`, `scene_save`。`.tscn` ファイル用に `Write` ツールにフォールバック
   - シグナル接続: `mcp__gopeak__signal_connect`。手動スクリプト編集にフォールバック
   - このテストをパスさせることだけに集中。オーバーエンジニアリングを避ける

3. **REFACTOR - クリーンアップ**:
   - コード構造と可読性を改善
   - 重複を除去
   - 適切な箇所にデザインパターンを適用
   - リファクタリング後もすべてのテストがパスすることを確認

4. **VERIFY - 品質の検証**:
   - すべてのテスト（新規・既存）がパス — Bashで実行
   - 既存機能にリグレッションがない
   - **LSP診断**（ベストエフォート）: `mcp__gopeak__lsp_diagnostics` を実行して静的エラーを確認。LSPが利用できない場合（エディタ未起動）、スキップして **「LSPチェックスキップ: エディタ未起動」** を出力
   - コードカバレッジが維持または改善されている

5. **Screenshotチェックポイント**（Layer 2タスクで `Screenshot checkpoint:` パターンのもの）:
   - `mcp__gopeak__editor_run` + `mcp__gopeak__editor_debug_output` + `mcp__gopeak__editor_stop` を優先使用
   - タイムアウト: 30秒。ランタイムがタイムアウトを超えるかエラーが発生した場合、クリーンアップのためすぐに `mcp__gopeak__editor_stop` を呼び出す
   - フォールバック: GoPoakが利用できない場合はBashで実行（`godot --path <projectPath>`）
   - 結果を目視確認し、結果を記録

6. **完了マーク**:
   - tasks.mdのチェックボックスを `- [ ]` から `- [x]` に更新

## 重要な制約
- **TDD必須**: テストは実装コードの前に記述すること
- **タスクスコープ**: 特定のタスクが要求するもののみを実装
- **テストカバレッジ**: すべての新規コードにテストが必要
- **リグレッションなし**: 既存のテストは引き続きパスすること
- **設計との整合性**: 実装はdesign.mdのスペックに従うこと
- **レイヤー認識**: テストタイプを選択する前に要件のTestability Layerを確認。L1/L2共にTDD必須（テスト先行）。L2テストはSceneTree依存（`add_child`/シグナル）だがGdUnit4ヘッドレスで実行可能
- **Screenshotチェックポイントの実行**: `Screenshot checkpoint:` パターンに一致するサブタスクは異なるフローを使用 — TDDをスキップし、代わりに: `mcp__gopeak__editor_run`（フォールバック: Bash）でアプリケーションを実行、`mcp__gopeak__editor_debug_output` で出力をキャプチャ、結果を目視確認、クリーンアップのため `mcp__gopeak__editor_stop` を呼び出す。タイムアウト: 30秒。検証がパスした場合は完了としてマーク。
- **ヒューマンレビューのスキップ**: `Human review:` パターンに一致するサブタスクはspec-implでは実行されない。タスク選択時に検出してスキップし、スキップされたタスクリストを出力に含める。これらのタスクの処理には `/kiro:scene-review` を使用する。
</instructions>

## ツールガイダンス

### 標準ツール
- **まず読み込み**: 実装前にすべてのコンテキストを読み込む
- **テストファースト**: コードの前にテストを記述
- ライブラリのドキュメントが必要な場合は **WebSearch/WebFetch** を使用
- テストとビルドコマンドの実行には **Bash** を使用

### GoPoakツール（ベストエフォート — すべてBash/Write/Editにフォールバック）

**GDScript開発**:
- `mcp__gopeak__script_create` — 新規GDScriptファイル作成（テスト・実装共通）
- `mcp__gopeak__script_modify` — 既存GDScriptの編集
- `mcp__gopeak__script_info` — スクリプトのメタ情報取得

**シーン構築**:
- `mcp__gopeak__scene_create` — 新規シーン作成
- `mcp__gopeak__scene_node_add` — ノード追加
- `mcp__gopeak__scene_node_set` — ノードプロパティ設定
- `mcp__gopeak__scene_save` — シーン保存
- `mcp__gopeak__signal_connect` — シグナル接続

**テスト検証**:
- `mcp__gopeak__lsp_diagnostics` — 静的解析（エディタ起動時のみ）
- `mcp__gopeak__editor_run` — ランタイム実行（Screenshotチェックポイント用）
- `mcp__gopeak__editor_debug_output` — デバッグ出力取得
- `mcp__gopeak__editor_stop` — ランタイム停止・クリーンアップ
- `mcp__gopeak__runtime_status` — ランタイム状態確認
- `mcp__gopeak__dap_output` — DAPデバッグ出力

## 出力の説明

spec.jsonで指定された言語で簡潔なサマリーを提供:

1. **実行されたタスク**: タスク番号とテスト結果
2. **Screenshotチェックポイント**: Layer 2のスクリーンショット検証タスクの結果（パス/失敗と詳細）
3. **スキップされたヒューマンレビュータスク**: スキップされたサブタスクのリスト（該当する場合）と `/kiro:scene-review` を実行するガイダンス
4. **ステータス**: tasks.mdで完了マークされたタスク、残りのタスク数

**フォーマット**: 簡潔（150語以下）

## 安全対策とフォールバック

### エラーシナリオ

**タスクが未承認またはスペックファイルが不足している場合**:
- **実行停止**: すべてのスペックファイルが存在し、タスクが承認されている必要がある
- **推奨アクション**: 「前のフェーズを完了してください: `/kiro:spec-requirements`, `/kiro:spec-design`, `/kiro:spec-tasks`」

**テスト失敗の場合**:
- **実装停止**: 続行前に失敗したテストを修正
- **アクション**: デバッグして修正し、再実行

### タスクの実行

**特定のタスクを実行**:
- `/kiro:spec-impl $1 1.1` - 単一タスク
- `/kiro:spec-impl $1 1,2,3` - 複数タスク

**すべての保留タスクを実行**:
- `/kiro:spec-impl $1` - すべての未チェックタスク
</output>
