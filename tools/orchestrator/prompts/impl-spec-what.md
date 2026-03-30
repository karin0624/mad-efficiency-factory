## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## Planファイル

promptで渡される `PLAN_FILE_ABSOLUTE_PATH` をRead toolで読み込んでください。
このパスはmain repoの絶対パスなので、worktree外からも読み込み可能です。

## ユーザーフィードバック

`USER_FEEDBACK` が空でない場合、そのフィードバック内容を最優先で対応すること。
指摘された問題点・改善要望を反映した上で、通常の手順を実行する。

## 実行手順

パイプラインの各フェーズは直列に実行してください。

### Phase 1: spec-init
- Skill tool: skill="kiro:spec-init", args="<plan内容から抽出した説明文>"
- 生成された .kiro/specs/ 配下のディレクトリを確認
- spec.json を読んで実際のfeature名を取得

### Phase 2: spec-requirements
- Skill tool: skill="kiro:spec-requirements", args="<feature-name> --plan PLAN_FILE_ABSOLUTE_PATH"
- PLAN_FILE_ABSOLUTE_PATH はpromptで渡された絶対パスに置換すること

## エラー処理
- いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
- 失敗フェーズ、エラー内容、再実行用のコマンドを含める

## フォールバック
Skill toolが使えない場合は .claude/commands/kiro/ の該当コマンドファイルを直接読んで手動実行

## 完了報告
以下を報告すること:
- 作成されたspec名（feature name）
- 完了したフェーズ一覧
- ブランチ名
