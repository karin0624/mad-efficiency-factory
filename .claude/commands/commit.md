---
description: Commit only the files Claude modified in this session
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*)
argument-hint: [commit-message]
---

# セッション変更コミット

<background_information>
- **ミッション**: このセッションでClaudeが変更したファイルだけを、適切なコミットメッセージで選択的にコミットする
- **成功基準**: Claudeの変更のみがコミットされ、ユーザーの既存ステージングや未コミット変更に影響しないこと
</background_information>

<instructions>

## ステップ 1: セッション変更ファイルの特定

この会話の履歴を振り返り、自分（Claude）が変更したファイルの完全なリストを構築する。

対象となるツール呼び出し:
- **Edit** ツール: `file_path` パラメータのファイル
- **Write** ツール: `file_path` パラメータのファイル
- **Bash** ツール: ファイルを作成・移動・削除したコマンド（`mv`, `cp`, `rm`, `touch` 等）

このリストを「セッションファイル一覧」とする。

## ステップ 2: git状態との突合

以下を並列実行:
- `git status -u`
- `git branch --show-current`
- `git log --oneline -5`

セッションファイル一覧と `git status` の出力を突合し、以下のカテゴリに分類:
- **コミット対象**: 未コミットの変更がある（modified, new file, deleted）セッションファイル
- **スキップ**: 変更がない（既にコミット済み、または変更を元に戻した）セッションファイル

## ステップ 3: 早期終了判定

コミット対象ファイルが0件の場合:
- 「セッション中の変更はすべてコミット済みです」と報告して終了

## ステップ 4: ステージングとコミット

### 4a. ファイルのステージング
コミット対象ファイルを `git add` する（新規ファイル・削除ファイル対応のため）:
```
git add <file1> <file2> ...
```

### 4b. コミットメッセージの決定
- `$ARGUMENTS` が指定されている場合: それをコミットメッセージとして使用
- 指定がない場合: `git diff --cached -- <session-files>` の内容から自動生成
  - conventional commit形式のprefixを選択: `feat:`, `fix:`, `chore:`, `test:`, `docs:`, `refactor:`
  - 簡潔な英語の要約（`git log` のスタイルに合わせる）

### 4c. コミット実行
**重要**: `--only` フラグを使い、セッションファイルだけをコミットする。これにより既存のステージング状態は保持される。

```bash
git commit --only -m "$(cat <<'EOF'
<prefix>: <message>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)" -- <file1> <file2> ...
```

## ステップ 5: 結果報告

以下を簡潔に報告:
- コミットハッシュとメッセージ
- コミットされたファイル一覧
- スキップしたセッションファイル（あれば）

## 重要な制約

- **セッションファイルのみ**: `git status` に表示される変更でも、Claudeが触っていないファイルは絶対にステージング・コミットしない
- **既存ステージ保持**: `git reset HEAD` は使わない。`git commit --only` で他のステージを無傷に保つ
- **最小出力**: ツール呼び出しと結果報告のみ。余計な説明やテキストは出力しない

</instructions>
