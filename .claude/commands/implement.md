---
description: Execute cc-sdd pipeline from a plan file in an isolated worktree.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
argument-hint: <plan-file-or-name>
---

# 実装: Plan → cc-sdd 自動実行

<background_information>
- **ミッション**: planファイルから隔離されたworktreeでcc-sddパイプライン全体（spec-init → requirements → design → tasks → spec-impl → validate-impl）を実行する
- **成功基準**:
  - planファイルが解決・検証済みであること
  - フィーチャーブランチ上にworktreeが作成されていること
  - spec生成（Agent A1/A2/A3）と実装（Agent B）が隔離されたサブエージェントで完了していること
  - 実装バリデーション（Agent B2）がGO/CONDITIONAL GOであること
  - 変更がコミットされていること（Agent C）
  - L4 Human Reviewタスクがない場合: プッシュされ、PRが作成されていること（Agent D）
  - L4 Human Reviewタスクがある場合: scene-reviewが実行され、worktreeが保持されていること
  - メインセッションのコンテキストが最小限に保たれていること（オーケストレーターのみ）
</background_information>

<instructions>
## コアタスク
plan **$ARGUMENTS** に対してcc-sddパイプライン全体を隔離されたworktreeで実行する。
引数が未指定の場合、現在の会話コンテキスト内で作成されたplanファイルを自動的に使用する。

## 実行ステップ

### ステップ 0: プリフライトチェック

1. GitHub CLIの確認: `which gh` および `gh auth status`
   - 利用不可または未認証の場合: 報告して停止
2. ベースブランチの検出:
   - 試行: `git symbolic-ref refs/remotes/origin/HEAD` → ブランチ名を抽出（例: `origin/master` → `master`）
   - フォールバック: `git remote show origin | grep 'HEAD branch'`
   - 両方失敗した場合: ユーザーに確認して停止
3. 現在のブランチが検出されたベースブランチと一致することを確認
   - 別のブランチにいる場合: ユーザーに警告して停止
4. `git fetch origin` でリモートと同期
5. ローカルとリモートの差分を確認:
   - `git rev-list HEAD..origin/<base-branch> --count` でリモートの未取得コミット数（behind）を取得
   - `git rev-list origin/<base-branch>..HEAD --count` でローカルの未プッシュコミット数（ahead）を取得
   - **両方 0** の場合: そのまま続行
   - **behind > 0（リモートが先行）** の場合: AskUserQuestion toolで確認
     - question: 「リモートに {N} 件の新しいコミットがあります。どうしますか？」
     - options: 「pullして続行」（`git pull origin <base-branch>` を実行）/ 「そのまま続行」（何もせず続行）
     - ユーザーの選択に応じて実行
   - **ahead > 0（ローカルが先行）** の場合: AskUserQuestion toolで確認
     - question: 「ローカルに {N} 件の未プッシュコミットがあります。どうしますか？」
     - options: 「pushして続行」（`git push origin <base-branch>` を実行）/ 「そのまま続行」（何もせず続行）
     - ユーザーの選択に応じて実行
   - **両方 > 0（分岐）** の場合: 「ローカルが {ahead} 件先行、リモートが {behind} 件先行しており、ブランチが分岐しています。手動で解決してください。」と報告して停止

### ステップ 1: planファイルの解決

`$ARGUMENTS` をplanファイルの**絶対パス**に解決する:

#### 引数が空の場合
`$ARGUMENTS` が空文字列または未指定の場合、以下の優先順位で解決する:
1. **コンテキスト内のplanファイル**: 現在の会話で `/plan` コマンドなどにより作成・言及されたplanファイルがある場合、そのファイルを使用する（会話履歴から直近のplanファイルパスを特定）
2. **フォールバック**: コンテキスト内にplanファイルが見つからない場合、`docs/plans/` 内の利用可能なplanを一覧表示して停止

#### 引数がある場合
- `/` を含むか `.md` で終わる場合: そのまま使用（ワークスペースルートからの相対パス）
- それ以外: `docs/plans/<identifier>.md` に解決
- 見つからない場合: Glob `docs/plans/*<identifier>*` で検索
  - 候補が2〜4件の場合: AskUserQuestion toolで選択肢として提示（各候補をoptionとして表示）
  - 候補が5件以上の場合: 一覧を表示して停止（ユーザーに選択を依頼）
- それでも見つからない場合: `docs/plans/` 内の利用可能なplanを一覧表示して停止
- **絶対パスに変換**: `PLAN_FILE_ABSOLUTE_PATH="$(pwd)/<resolved-relative-path>"`
- ブランチ名用にplan名を抽出（拡張子なしのファイル名）
  - ブランチ名用にサニタイズ: 小文字化、スペースや特殊文字をハイフンに置換

**重要**: ここではパスの解決のみ行う。planの内容は読まない（トークン節約）。絶対パスをAgent A1に渡す。

### ステップ 2: 再開検出 + worktree作成

1. フィーチャーブランチ名を生成: `feat/<sanitized-plan-name>`
2. ブランチ/worktreeが既に存在するか確認:
   - `.claude/worktrees/feat/<sanitized-plan-name>` にworktreeが存在する場合:
     a. `<worktree-path>/.kiro/specs/*/spec.json` を読んで既存specを検索
     b. `spec.json.phase` と `approvals.design` で再開ポイントを判定:
        - `validated` → Agent A1, A2, A3, B, B2をスキップ → Agent C（commit）から開始
        - `impl-completed` → Agent A1, A2, A3, Bをスキップ → Agent B2（validate-impl）から開始
        - `tasks-generated` + `approvals.tasks.approved: true` → Agent A1, A2, A3をスキップ、Agent Bから開始
        - `tasks-generated`（未承認） → Agent A3を再開（tasks承認から）
        - `design-generated` + `approvals.design.codex_reviewed: true` → Agent A3から開始（tasks生成から）
        - `design-generated` + `approvals.design.codex_reviewed: false` → Agent A2から開始（design-reviewから — spec-designはスキップ）
        - `requirements-generated` → Agent A2から開始（design生成 + review）
        - `initialized` → Agent A1をPhase 2から起動
     c. `spec.json.feature_name` からフィーチャー名を抽出
     d. 既存のworktreeを使用し、適切なAgentにスキップ
   - ブランチは存在するがworktreeがない場合: 既存ブランチ用にworktreeを作成
   - どちらも存在しない場合: 新しいブランチ + worktreeを作成
3. worktreeを作成（必要な場合）:
   ```
   git worktree add -b feat/<sanitized-plan-name> .claude/worktrees/feat/<sanitized-plan-name> origin/<base-branch>
   ```
   - ブランチが既に存在する場合（再開時）: `git worktree add .claude/worktrees/feat/<sanitized-plan-name> feat/<sanitized-plan-name>`
   - ブランチ名が無関係の作業と競合する場合: サフィックスを付加（例: `feat/<plan-name>-2`）
4. 以降のすべてのAgentのためにworktreeの絶対パスとブランチ名を保持

### ステップ 3: Agent A1 — WHAT（init + requirements）

Agent A1を起動してworktree内でPhase 1-2を処理する。planファイルの絶対パスとworktreeパスを渡す。`isolation: "worktree"` は使用しない — worktreeは既に作成済み。

後のフェーズからの再開（ステップ2で検出）の場合、Agent A1をスキップして適切なAgentから開始する。

```
Agent(
  description: "spec-what <plan-name>",
  model: "opus",
  prompt: """
  以下のplanファイルを読み込み、cc-sddパイプラインのWHATフェーズ（init + requirements）を実行してください。
  パイプラインの各フェーズは直列に実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Planファイル（絶対パス — main repoから読み込み可能）
  {PLAN_FILE_ABSOLUTE_PATH}
  このファイルをRead toolで読み込んでください。

  ## 実行手順

  ### Phase 1: spec-init
  - Skill tool: skill="kiro:spec-init", args="<plan内容から抽出した説明文>"
  - 生成された .kiro/specs/ 配下のディレクトリを確認
  - spec.json を読んで実際のfeature名を取得

  ### Phase 2: spec-requirements
  - Skill tool: skill="kiro:spec-requirements", args="<feature-name> --plan {PLAN_FILE_ABSOLUTE_PATH}"

  ## エラー処理
  - いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
  - 失敗フェーズ、エラー内容、再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/ の該当コマンドファイルを直接読んで手動実行

  ## 完了報告
  - 作成されたspec名（feature name）
  - 完了したフェーズ一覧
  - ブランチ名
  """
)
```

**Agent A1の結果から抽出する情報**: worktreeパス、ブランチ名、フィーチャー名。

### ステップ 3.5: Agent A2 — HOW + レビュー（design + design-review）

Agent A2を起動してworktree内でPhase 3 + Codex設計レビューを処理する。フィーチャー名とworktreeパスを渡す。

再開時の特殊ケース:
- `requirements-generated` → design生成 + review の両方を実行
- `design-generated` + `codex_reviewed: false` → design-reviewのみ実行（spec-designはスキップ）

```
Agent(
  description: "spec-how <feature-name>",
  model: "opus",
  prompt: """
  以下のfeatureのHOWフェーズ（design生成 + Codex設計レビュー）を実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Feature
  {FEATURE_NAME}

  ## 再開モード
  {RESUME_MODE}
  - "full": Phase 3（design生成）から開始
  - "review-only": design-reviewのみ実行（design.mdは生成済み）

  ## 実行手順

  ### Phase 3: spec-design（再開モードが "full" の場合のみ）
  - Skill tool: skill="kiro:spec-design", args="{FEATURE_NAME} -y"

  ### Phase 3.5: design-review（常に実行）
  - Skill tool: skill="design-review", args="{FEATURE_NAME}"
  - Codex出力の先頭行 `STATUS:` をパース

  ### Phase 3.5の判定処理
  判定に基づくアクション:

  #### APPROVE → 完了
  - 何もしない、次のAgentに進む

  #### REVISE → フィードバック反映 + 1回だけ再レビュー（max 2パス）
  1. design-review Skillが自動的にdesign.mdを更新する
  2. 再レビューを実行: Skill tool: skill="design-review", args="{FEATURE_NAME}"
  3. 2回目の判定:
     - APPROVE → 完了
     - REVISE → 修正は適用済み + 警告付きで完了（これ以上レビューしない）
     - REJECT → 停止、手動介入を報告

  #### REJECT → 停止
  - エラー報告して停止: 手動介入が必要である旨を表示
  - 停止理由とCodexのフィードバック全文を含める

  ## エラー処理
  - design生成が失敗した場合、そのフェーズで停止し詳細を報告
  - design-reviewが失敗した場合（Codex未インストール等）、警告を表示しつつ完了として扱う（レビューはベストエフォート）
  - REJECTは常に停止

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/ の該当コマンドファイルを直接読んで手動実行

  ## 完了報告
  - design生成の完了有無
  - Codexレビュー判定（APPROVE / REVISE / REJECT）
  - レビューパス数（1 or 2）
  - REJECTの場合: 停止理由
  """
)
```

**Agent A2の結果による分岐**:
- **完了（APPROVE or REVISE後の完了）** → Agent A3に進む
- **REJECT** → パイプラインを停止し、Codexフィードバックとworktreeパスを報告

### ステップ 3.75: Agent A3 — 実行計画（tasks + 承認）

Agent A3を起動してworktree内でPhase 4-4.5を処理する。フィーチャー名とworktreeパスを渡す。

```
Agent(
  description: "spec-tasks <feature-name>",
  model: "sonnet",
  prompt: """
  以下のfeatureの実行計画フェーズ（tasks生成 + 承認）を実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 4: spec-tasks
  - Skill tool: skill="kiro:spec-tasks", args="{FEATURE_NAME} -y"

  ### Phase 4.5: タスク承認 + メタデータ記録
  **Phase 4 (spec-tasks) が正常完了した直後に必ず実行すること。**
  spec.jsonを直接編集して以下を設定:
    - `approvals.tasks.approved: true`

  ## エラー処理
  - いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
  - 失敗フェーズ、エラー内容、再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/ の該当コマンドファイルを直接読んで手動実行

  ## 完了報告
  - tasks生成の完了有無
  - タスク承認の完了有無
  """
)
```

**Agent A3の結果から確認**: tasks生成・承認が完了していること。

### ステップ 4: Agent B — 実装

Agent Bを起動して同じworktree内でPhase 5を実行する。新しいエージェント（再開ではない）で、フィーチャー名とworktreeパスのみを渡す。

```
Agent(
  description: "impl <feature-name>",
  model: "sonnet",
  prompt: """
  以下のfeatureのspec-implを実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 5: spec-impl
  - Skill tool: skill="kiro:spec-impl", args="{FEATURE_NAME}"

  ## エラー処理
  - 失敗した場合、失敗タスク番号と詳細を報告
  - 再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/spec-impl.md を直接読んで手動実行

  ## 完了報告
  - 完了したタスク数 / 全タスク数
  - スキップされたHuman Reviewタスク一覧（あれば）
  - 未コミットの変更があるかどうか
  """
)
```

### ステップ 4.5: Agent B2 — validate-impl

Agent B完了後にバリデーションを実行する。新しいエージェント（Opus）で、フィーチャー名とworktreeパスのみを渡す。

```
Agent(
  description: "validate-impl <feature-name>",
  model: "opus",
  prompt: """
  以下のfeatureの実装バリデーションを実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 5.5: validate-impl
  - Skill tool: skill="kiro:validate-impl", args="{FEATURE_NAME}"
  - バリデーション完了後、spec.jsonの `phase` を `"validated"` に更新

  ## 判定結果の処理
  - GO または CONDITIONAL GO の場合:
    - spec.jsonの `phase` を `"validated"` に更新
    - 「VALIDATION_PASSED」と報告
  - NO-GO の場合:
    - spec.jsonの `phase` は `"impl-completed"` のまま維持
    - 「VALIDATION_FAILED」と詳細な問題リストを報告

  ## エラー処理
  - 失敗した場合、バリデーション結果と詳細を報告
  - 再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/validate-impl.md を直接読んで手動実行

  ## 完了報告
  - 判定結果（GO / CONDITIONAL GO / NO-GO）
  - バリデーションサマリー（issues, coverage, traceability）
  - 設計ドリフトの検出・パッチ結果
  - NO-GOの場合: 修正が必要な具体的な問題リスト
  """
)
```

**Agent B2の結果による分岐**:
- **VALIDATION_PASSED（GO / CONDITIONAL GO）** → Agent C（commit）に進む
- **VALIDATION_FAILED（NO-GO）** → パイプラインを停止し、以下を出力:
  - バリデーション結果のサマリー
  - worktreeパス（保持中）
  - 次のステップの案内:
    - worktreeで直接修正 → `/implement {plan}` で再開（`impl-completed` フェーズから再開検出される）

### ステップ 5: Agent C — コミット

Agent Cを起動して同じworktree内でPhase 6（コミットのみ）を実行する。

```
Agent(
  description: "commit <feature-name>",
  model: "sonnet",
  prompt: """
  以下のworktreeブランチで、未コミットの変更を確認し、コミットしてください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## ブランチ
  {BRANCH_NAME}

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 6: コミット確認
  1. git status で未コミットの変更を確認
  2. 未コミットの変更がある場合:
     - git diff --name-only で変更ファイル一覧を取得
     - .kiro/specs/ 配下、ソースコード、テストファイルなど意図した変更のみをステージング
     - 変更内容に基づいた適切なコミットメッセージで git commit
  3. すべてコミット済みの場合: このステップをスキップ

  ## 完了報告
  - コミットの有無と内容
  """
)
```

### ステップ 5.5: L4 Human Review 分岐判定

Agent C完了後、worktree内の `tasks.md` を確認してL4 Human Reviewタスクの有無を判定する:
1. `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/tasks.md` を読み込む
2. 未チェックのL4 Human Reviewサブタスク（パターン: `- [ ] X.Y Human review:`）を検索
3. 結果に応じて次のステップを分岐:
   - **L4 Human Reviewタスクあり** → ステップ 6A へ
   - **L4 Human Reviewタスクなし** → ステップ 6B へ

### ステップ 6A: scene-review（L4 Human Reviewタスクがある場合）

L4 Human Reviewタスクが存在する場合、PR作成の前にscene-reviewを実行する。

1. Skill toolで scene-review を起動:
   - `Skill(skill="kiro:scene-review", args="{FEATURE_NAME}")`
   - **注意**: scene-reviewはインタラクティブ（AskUserQuestionでユーザーの合格/不合格判断を収集する）
2. scene-review完了後の分岐:
   - **不合格の項目がある場合**: worktreeを保持し、修正→再実行の案内をして停止（ステップ 7A へ）
   - **全項目合格の場合**: ステップ 6B に進む（Push + PR + クリーンアップ）

### ステップ 6B: Agent D — Push + PR + クリーンアップ

ステップ 5.5 でL4 Human Reviewタスクがなかった場合、またはステップ 6A で全項目合格の場合にAgent Dを起動してPush・PR作成を行う。

```
Agent(
  description: "push-pr <feature-name>",
  model: "sonnet",
  prompt: """
  以下のworktreeブランチで、Push・PR作成を行ってください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## ブランチ
  {BRANCH_NAME}

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 7: Push + PR作成
  1. gh pr list --head {BRANCH_NAME} で既存PRを確認
     - 既にPRが存在する場合: PR URLを報告してスキップ
  2. git push -u origin {BRANCH_NAME}
  3. gh pr create でPRを作成:
     - title: {FEATURE_NAME} に基づいた簡潔なタイトル
     - body: specのrequirements.mdの内容をサマリとして含める
     - base: {BASE_BRANCH}

  ## 完了報告
  - PR URL
  """
)
```

Agent DがPR作成に成功した場合、worktreeを削除する:
1. `git worktree remove {WORKTREE_PATH}` を実行
   - 未コミットの変更がある場合（Agent Dが失敗した場合など）: `--force` は使わず、警告を表示してスキップ
2. worktree削除後、空になった親ディレクトリも整理: `rmdir --ignore-fail-on-non-empty .claude/worktrees/feat/`
3. ブランチはPRに紐付いているため削除しない

**注意**: Agent Dが失敗した場合はworktreeを保持し、手動リカバリ用にパスを報告する。

### ステップ 7A: 最終出力（scene-reviewで不合格あり）

scene-reviewで不合格項目がある場合の出力:
- ブランチ名
- 作成されたspec名
- タスク完了状況
- バリデーション結果（GO / CONDITIONAL GO）
- scene-reviewの結果（合格/不合格の項目）
- worktreeパス（保持中）
- 次のステップの案内:
  - **通常**: worktreeで直接修正 → `/kiro:scene-review` で再レビュー
  - **specに問題がある場合**（tasks/design/requirementsの誤り）: 該当フェーズから再生成（例: `/kiro:spec-design` → `/kiro:spec-tasks` → `/kiro:spec-impl`）

### ステップ 7B: 最終出力（PR作成完了）

scene-reviewが全項目合格だった場合、またはL4 Human Reviewタスクがなかった場合の出力:
- ブランチ名
- 作成されたspec名
- タスク完了状況
- バリデーション結果（GO / CONDITIONAL GO）
- PR URL
- worktreeが削除済みであること（または失敗時は保持パス）

## 重要な設計判断

1. **常にworktreeで隔離**: planのサイズに関わらず、すべての呼び出しでworktreeを使用する。メインセッションは最小限に保つ。
2. **トークン最適化のためのサブエージェント分割**: spec生成（A1/A2/A3）と実装（B）は別々のエージェントを使用し、コンテキストの持ち越しを避ける。A1(WHAT)→A2(HOW+レビュー)→A3(実行計画)の3分割により、各エージェントが必要なファイルだけを読み直す。
3. **steeringの自動読み込み**: 各specコマンドは自動的に `.kiro/steering/` を読み込む。Agentプロンプトにsteeringを渡す必要はない。
4. **フィーチャー名はspec.jsonから取得**: spec-init後、常にspec.jsonから実際のフィーチャー名を読む（plan名と異なる場合がある）。
5. **フェーズベースの再開**: 既存specは `spec.json.phase` で検出され、パイプラインの途中から決定論的に再開できる。
6. **`-y` による自動承認**: planが承認済みソースとして機能するため、承認ゲートはスキップされる。タスクはPhase 4.5で自動承認される。
7. **`--plan` フラグでplan内容を渡す**: requirements.mdを汚染せずにコンテキスト対応のrequirements生成を行うため、spec-requirementsに渡される。
8. **planファイルの絶対パス**: planファイルは絶対パスに解決され、worktreeコンテキストからもアクセス可能にする。
9. **cwd強制**: 各Agentは `cd` + `git rev-parse --show-toplevel` の検証で開始し、worktreeの隔離を保証する。
</instructions>

## ツールガイド
- **Bash**: プリフライトチェック、git操作、worktree管理
- **Read**: 再開検出時のspec.json確認
- **Glob**: planファイルの解決
- **Agent**: サブエージェントA1、A2、A3、B、B2、C（、D）を順次起動（`isolation: "worktree"` は使用しない — worktreeは事前作成済み）
- **Skill**: scene-reviewの起動（Human Reviewタスクがある場合）
- **AskUserQuestion**: ユーザー確認が必要で選択肢形式にできる場合（pull/push確認、plan候補選択など）

## 出力内容
以下を含む簡潔な最終サマリ:
1. ブランチ名
2. spec名と完了状況
3. Human Reviewなし: PR URL + worktree削除済み
4. Human Reviewあり: scene-review結果 + worktreeパス（保持中）+ 次のステップ案内

## 安全性とフォールバック
- **引数なし + コンテキストにplanなし**: `docs/plans/` 内の利用可能なplanをフルパスで一覧表示
- **引数ありでplanが見つからない場合**: `docs/plans/` 内の利用可能なplanをフルパスで一覧表示
- **gitコンフリクト**: 強制プッシュはしない。コンフリクトを報告し手動解決を依頼
- **Agent A1/A2/A3/B/B2失敗**: どのAgentが失敗したか報告し、手動リカバリのためにworktreeを保持
- **Agent A2 REJECT**: Codex設計レビューがREJECTを返した場合、パイプラインを停止しCodexフィードバックとworktreeパスを報告
- **Agent B2 NO-GO**: パイプラインを停止し、バリデーション結果とworktreeパスを報告。修正後 `/implement` で再開（`impl-completed` フェーズから再開）
- **Agent C失敗**: worktreeを保持し、パスを報告（手動コミット後にリカバリ可能）
- **Agent D失敗**: worktreeを保持し、パスを報告（手動でPR作成後に `git worktree remove` で削除可能）
- **Agent D成功**: worktreeを自動削除（ブランチはPR用に保持）
- **Human Reviewあり**: worktreeを保持（scene-review後の追加修正に備える）
</output>
