---
description: Commit and push the files Claude modified in this session
allowed-tools: Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*)
argument-hint: [commit-message]
---

# セッション変更コミット＆プッシュ

<background_information>
- **ミッション**: このセッションでClaudeが変更したファイルだけを、適切なコミットメッセージでコミットし、リモートにプッシュする
- **成功基準**: Claudeの変更のみがコミット＆プッシュされ、ユーザーの既存ステージングや未コミット変更に影響しないこと
</background_information>

<instructions>

## ステップ 1: セッション変更ファイルの特定

この会話の履歴を振り返り、自分（Claude）が変更したファイルの完全なリストを構築する。

対象となるツール呼び出し:
- **Edit** ツール: `file_path` パラメータのファイル
- **Write** ツール: `file_path` パラメータのファイル
- **Bash** ツール: ファイルを作成・移動・削除したコマンド（`mv`, `cp`, `rm`, `touch` 等）

このリストを「セッションファイル一覧」とする。

## ステップ 2: git状態との突合と早期終了判定

`git status -u` を実行し、セッションファイル一覧と突合する。

- **コミット対象**: 未コミットの変更がある（modified, new file, deleted）セッションファイル
- **スキップ**: 変更がない（既にコミット済み、または変更を元に戻した）セッションファイル

**コミット対象ファイルが0件の場合**: 「セッション中の変更はすべてコミット済みです」と報告して**終了**。

## ステップ 3: コミットメッセージの生成

会話コンテキストからコミットメッセージを生成する。

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

## ステップ 4: コミット＆プッシュの実行

`git branch --show-current` でブランチ名を取得し、以下を順次実行する。

### 4a. ステージング＆コミット
```bash
git add <file1> <file2> ...
git commit --only -m "$(cat <<'EOF'
{COMMIT_MESSAGE}

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)" -- <file1> <file2> ...
```

- `--only` フラグで既存のステージング状態を保持する
- リスト外のファイルは絶対にステージング・コミットしない
- `--force` 禁止

### 4b. プッシュ
```bash
git push origin {BRANCH_NAME}
```
- リモートブランチが存在しない場合: `git push -u origin {BRANCH_NAME}`

## ステップ 5: 結果報告

以下を簡潔に報告:
- コミットハッシュとメッセージ
- コミットされたファイル一覧
- スキップしたファイル（あれば）
- プッシュの成否

</instructions>
