---
description: Commit and push the files Claude modified in this session
allowed-tools: Agent, Bash(git status:*), Bash(git branch:*)
argument-hint: [commit-message]
---

# セッション変更コミット＆プッシュ

<background_information>
- **ミッション**: このセッションでClaudeが変更したファイルだけを、適切なコミットメッセージでコミットし、リモートにプッシュする
- **成功基準**: Claudeの変更のみがコミット＆プッシュされ、ユーザーの既存ステージングや未コミット変更に影響しないこと
- **コスト最適化**: メインセッションはファイル特定のみ行い、git操作はsonnetサブエージェントに委譲する
</background_information>

<instructions>

## ステップ 1: セッション変更ファイルの特定（メインセッションで実行）

この会話の履歴を振り返り、自分（Claude）が変更したファイルの完全なリストを構築する。

対象となるツール呼び出し:
- **Edit** ツール: `file_path` パラメータのファイル
- **Write** ツール: `file_path` パラメータのファイル
- **Bash** ツール: ファイルを作成・移動・削除したコマンド（`mv`, `cp`, `rm`, `touch` 等）

このリストを「セッションファイル一覧」とする。

## ステップ 2: コミットメッセージの生成（メインセッションで実行）

`.agents/skills/contextual-commit/SKILL.md` のフォーマットに従い、**メインセッションの会話コンテキストから**コミットメッセージを生成する。

コミットメッセージ引数（`{$ARGUMENTS}`）が指定されている場合はそれをsubject lineとして使用する。

### Subject line
Conventional Commit形式（`feat(scope):`, `fix(scope):`, `chore:` 等）

### Body（action lines）
セッション中の会話から以下を抽出してbodyに記載（該当するものだけ。1-3行が目安）:
- `intent(scope):` — ユーザーが何を達成したかったか（ユーザーの言葉で）
- `decision(scope):` — 代替案がある中で選んだアプローチと理由
- `rejected(scope):` — 検討して却下した案と理由（最重要。次回の再提案を防ぐ）
- `constraint(scope):` — 実装を形作った制約・制限
- `learned(scope):` — 実装中に発見した非自明な知見

### ルール
- 会話コンテキストがあるchangeのみaction linesを書く
- trivialなコミット（typo修正等）にはaction lines不要
- scopeはプロジェクト内で一貫させる

生成したコミットメッセージ全文を「COMMIT_MESSAGE」とする。

## ステップ 3: 現在のブランチ確認（メインセッションで実行）

`git branch --show-current` でブランチ名を取得する。

## ステップ 4: サブエージェントに委譲

セッションファイル一覧、ブランチ名、**生成済みコミットメッセージ**をsonnetサブエージェントに渡す。

```
Agent(
  description: "commit-push",
  model: "sonnet",
  prompt: """
  以下のファイルをコミットし、リモートにプッシュしてください。

  ## セッション変更ファイル一覧
  {SESSION_FILES_LIST}

  ## 現在のブランチ
  {BRANCH_NAME}

  ## コミットメッセージ（確定済み・変更しないこと）
  {COMMIT_MESSAGE}

  ## 実行手順

  ### 1. git状態との突合
  以下を並列実行:
  - `git status -u`
  - `git log --oneline -5`

  セッションファイル一覧と `git status` の出力を突合し、以下のカテゴリに分類:
  - **コミット対象**: 未コミットの変更がある（modified, new file, deleted）セッションファイル
  - **スキップ**: 変更がない（既にコミット済み、または変更を元に戻した）セッションファイル

  ### 2. 早期終了判定
  コミット対象ファイルが0件の場合:
  - 「セッション中の変更はすべてコミット済みです」と報告して終了

  ### 3. ステージングとコミット

  #### 3a. ファイルのステージング
  コミット対象ファイルを `git add` する:
  ```
  git add <file1> <file2> ...
  ```

  #### 3b. コミット実行
  **重要**: `--only` フラグを使い、セッションファイルだけをコミットする。これにより既存のステージング状態は保持される。
  **重要**: コミットメッセージは上記の確定済みメッセージをそのまま使う。改変しないこと。

  ```bash
  git commit --only -m "$(cat <<'EOF'
  {COMMIT_MESSAGE}

  Co-Authored-By: Claude <noreply@anthropic.com>
  EOF
  )" -- <file1> <file2> ...
  ```

  ### 4. プッシュ
  コミット成功後、リモートにプッシュ:
  ```bash
  git push origin {BRANCH_NAME}
  ```
  - プッシュが失敗した場合: エラー内容を報告（コミット自体は保持される）
  - リモートブランチが存在しない場合: `git push -u origin {BRANCH_NAME}` を使用

  ### 5. 結果報告
  以下を簡潔に報告:
  - コミットハッシュとメッセージ
  - コミットされたファイル一覧
  - スキップしたセッションファイル（あれば）
  - プッシュの成否

  ## 重要な制約
  - **セッションファイルのみ**: `git status` に表示される変更でも、リストにないファイルは絶対にステージング・コミットしない
  - **既存ステージ保持**: `git reset HEAD` は使わない。`git commit --only` で他のステージを無傷に保つ
  - **コミットメッセージ固定**: 渡されたコミットメッセージを改変しない。Co-Authored-Byの追記のみ許可
  - **最小出力**: ツール呼び出しと結果報告のみ。余計な説明やテキストは出力しない
  - **force push禁止**: `--force` は絶対に使わない
  """
)
```

## ステップ 5: 結果の伝達

サブエージェントの報告をそのままユーザーに伝える。余計な装飾は不要。

</instructions>
