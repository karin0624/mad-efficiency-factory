
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## コアタスク

Change Impact Reportに基づき、カスケード深度に応じてspec成果物（requirements.md, design.md, spec.json）を更新する。

## 入力パラメータ

promptから以下を受け取る:
- `WORKTREE_PATH`: worktreeの絶対パス
- `FEATURE_NAME`: 既存spec名
- `CHANGE_IMPACT_REPORT`: Agent M1の出力（ANALYSIS_DONE以降のテキスト）
- `CASCADE_DEPTH`: カスケード深度（`requirements-only` / `requirements+design` / `requirements+design+tasks` / `full`）

## 実行手順

### 1. 現在のSpec読み込み

以下のファイルをすべて読み込む:
- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/spec.json`
- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/requirements.md`
- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/design.md`
- `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/tasks.md`

### 2. Change Impact Reportのパース

`CHANGE_IMPACT_REPORT` から以下を抽出:
- `CLASSIFICATION`: major / minor
- `CHANGE_TYPE`: additive / modifying / removal / mixed
- `AFFECTED_REQUIREMENTS`: 影響要件ID一覧
- `AFFECTED_DESIGN_SECTIONS`: 影響設計セクション一覧
- `DELTA_SUMMARY`: 変更の構造化記述

### 3. requirements.md のデルタ適用（全深度共通）

**原則: requirements.md は常に「現在の真の要求」だけを記述する。変更履歴やマーカーは一切残さない。**

変更タイプに応じた処理:

| 変更タイプ | 処理 |
|-----------|------|
| `additive` | 既存要件をそのまま保持。次の連番IDで新要件を末尾に追加 |
| `modifying` | 該当要件のObjective/受入基準を新しい記述で上書き。IDは保持。マーカーなし |
| `removal` | 要件セクションをそのまま削除。**リナンバリングしない**（番号のギャップはgit historyで追跡可能） |
| `mixed` | 上記を組み合わせて適用 |

新要件を追加する場合は、既存requirements.mdのEARS形式・スタイルに合わせること。

### 4. design.md の再生成（`requirements+design` 以上の場合のみ）

**原則: design.md は自己完結した宣言的仕様である。「このシステムはこうあるべき」という記述のみを含む。他ドキュメントとの差異、変更前の状態、変更経緯・理由への言及は一切含めない。読み手がこのファイルだけで仕様の全体像を理解できること。**

CLASSIFICATIONに応じた処理:

#### minor変更の場合
- design.md をEdit toolで直接修正（該当セクションのみ）
- 影響範囲が限定的なため、全体再生成は不要
- **design-review はスキップ**（変更規模がレビュー不要なため）

#### major変更の場合
1. 既存の `/kiro:spec-design` をSkill tool経由で呼び出し（マージモード）:
   ```
   Skill(skill="kiro:spec-design", args="{FEATURE_NAME} -y")
   ```
   - マージモード: 既存design.mdを参照として使用し、再生成
   - Implementation Changelogも保持・活用

2. design-review ゲートの実行:
   - まず spec.json の `approvals.design.codex_reviewed` と `approvals.design.codex_status` をリセット:
     ```json
     {
       "approvals": {
         "design": {
           "codex_reviewed": false,
           "codex_status": null
         }
       }
     }
     ```
   - `/design-review` をSkill tool経由で呼び出し:
     ```
     Skill(skill="design-review", args="{FEATURE_NAME}")
     ```
   - 結果に応じた分岐:
     - **APPROVE** → 次のステップ（M3タスク生成）に進む
     - **REVISE** → design.md修正後、再レビュー（最大2パス）
     - **REJECT** → パイプラインを停止し、フィードバックとworktreeパスを報告

### 5. spec.json の更新

カスケード深度に応じて `phase` をリセット:

| CASCADE_DEPTH | phase リセット先 |
|--------------|-----------------|
| `requirements-only` | `requirements-generated` |
| `requirements+design` | `design-generated` |
| `requirements+design+tasks` | `design-generated` |
| `full` | `design-generated` |

下流のapprovalをリセット（カスケード深度に応じて）:
- `requirements+design` 以上: `approvals.design.approved` をリセット不要（再生成時にspec-designが更新）
- `requirements+design+tasks` 以上: `approvals.tasks` をリセット（M3が再設定）

`modifications` 配列に新エントリを追加:
```json
{
  "id": <既存modificationsの最大id + 1、なければ 1>,
  "date": "<現在日時のISO 8601形式>",
  "description": "<DELTA_SUMMARYの要約（1行）>",
  "classification": "<CLASSIFICATION>",
  "change_type": "<CHANGE_TYPE>",
  "cascade_depth": "<CASCADE_DEPTH>",
  "affected_requirements": [<AFFECTED_REQUIREMENTSの数値配列>],
  "modify_phase": "spec-cascaded",
  "branch": "modify/<FEATURE_NAME>"
}
```

`modifications` 配列が存在しない場合は新規作成する。

### 6. CASCADE_DEPTH が `requirements-only` の場合

requirements.md の更新と spec.json の更新のみ行い、design.md と tasks.md は変更しない。
`modify_phase` を `spec-cascaded` に設定して完了を報告。

## 出力形式

```
CASCADE_DONE
REQUIREMENTS_UPDATED: true|false
DESIGN_UPDATED: true|false
DESIGN_REVIEW: APPROVE|REVISE|REJECT|SKIPPED
PHASE_RESET_TO: <リセット先のphase>
```

design-reviewがREJECTの場合:
```
CASCADE_FAILED
REASON: design-review REJECT
FEEDBACK: <Codexからのフィードバック要約>
WORKTREE_PATH: <worktreeパス>
```
