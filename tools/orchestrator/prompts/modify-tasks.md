
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## コアタスク

変更影響分析レポートに基づき、既存 tasks.md にデルタタスクを適用する。

## 入力パラメータ

promptから以下を受け取る:
- `WORKTREE_PATH`: worktreeの絶対パス
- `FEATURE_NAME`: 既存spec名
- `CHANGE_IMPACT_REPORT`: Agent M1の出力（ANALYSIS_DONE以降のテキスト）
- `CASCADE_DEPTH`: カスケード深度

## 実行手順

### 0. ルール読み込み

以下のルールファイルを読み込み、タスク生成の基盤とする:
- `.kiro/settings/rules/tasks-generation.md` — タスク分解原則、テンプレート、TDD順序
- `.kiro/settings/rules/tasks-parallel-analysis.md` — 並列タスク `(P)` マーカーの判定基準

### 1. 既存タスクの把握

`{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/tasks.md` を読み込み:
- 全タスクの番号・状態（`[x]` / `[ ]`）・Requirements マーカーを把握
- 最終タスク番号を特定（新規タスクの開始番号に使用）

### 2. 更新済みSpecの読み込み

- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/requirements.md` — M2による更新済み
- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/design.md` — M2による更新済み

### 3. Change Impact Reportのパース

`CHANGE_IMPACT_REPORT` から以下を抽出:
- `CHANGE_TYPE`: additive / modifying / removal / mixed
- `AFFECTED_REQUIREMENTS`: 影響要件ID一覧
- `AFFECTED_TASKS`: 影響タスクID一覧
- `DELTA_SUMMARY`: 変更の構造化記述

### 4. 変更タイプに応じたタスク更新

#### `additive`（新規追加）

1. 既存タスクは**一切変更しない**
2. 既存最終タスク番号の次から新規タスクグループを追加
3. 新規要件に対するタスクを生成:
   - L1テスト → L1実装 → L2テスト → L2実装 → ... のTDD順序
   - `_Requirements: X.X_` マーカーを付与
   - 並列実行可能なタスクには `(P)` マーカーを付与

#### `modifying`（既存変更）

1. `AFFECTED_TASKS` で特定された影響タスクを処理:
   - 新しい要件を満たさないタスクの `[x]` を `[ ]` にリセット
   - タスク記述を新しい要件に合わせて更新
2. 必要に応じて新規サブタスクを追加（既存タスク番号の末尾に）
3. 影響を受けないタスクは**一切変更しない**

#### `removal`（削除）

1. 既存の完了済みタスク `[x]` は**そのまま保持**（削除しない）
2. 末尾に新規の**撤去タスク**を `[ ]` として追加:
   - 削除対象コードの除去
   - 関連テストの更新・削除
   - 依存コードの修正（参照の除去、フォールバック処理等）
3. 撤去タスクには `_Requirements: removed X.X_` マーカーを付与

**removal の設計根拠**: 要件の削除は「作業がない」のではなく「削除という作業がある」。既存の完了済みタスクを削除してしまうと、撤去作業を実行する `[ ]` タスクが存在しなくなり、Agent Bが何も実行せず、Agent B2の検証対象からも消える。

#### `mixed`（複合）

上記のルールを組み合わせて適用:
1. まず `modifying` のルールで影響タスクを更新
2. 次に `additive` のルールで新規タスクを追加
3. 最後に `removal` のルールで撤去タスクを追加

### 5. タスク品質チェック

生成・更新したタスクが以下を満たすか確認:
- 各タスクに `_Requirements: X.X_` マーカーがある
- TDD順序（テスト先行）が守られている
- 並列可能タスクに `(P)` マーカーが付いている
- 最大2レベルのネスト（X.Y まで、X.Y.Z は不可）
- タスク記述がユーザー視点（「プレイヤーとして...」等）

### 6. spec.json の更新

```json
{
  "approvals": {
    "tasks": { "generated": true, "approved": true }
  }
}
```

## 重要な設計原則

- **リナンバリングしない**: 完了済みタスクとの整合性を壊さないため、番号にギャップがあっても許容する
- **変更履歴を残さない**: tasks.md にコメントやメタマーカーを残さない。変更履歴は git + spec.json `modifications` が担う
- `[x]`/`[ ]` チェックボックスはタスクの本来の状態管理機構。reworkでの `[ ]` リセットはこの機構の正当な使用

## 出力形式

```
DELTA_TASKS_DONE
TASKS_ADDED: N
TASKS_RESET: N
TASKS_UNCHANGED: N
REMOVAL_TASKS_ADDED: N
```
