
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `BRANCH_NAME` と `FEATURE_NAME` を使用する。

### Phase 6: コミット確認
1. git status で未コミットの変更を確認
2. 未コミットの変更がある場合:
   - git diff --name-only で変更ファイル一覧を取得
   - .kiro/specs/ 配下、ソースコード、テストファイルなど意図した変更のみをステージング
   - 変更内容に基づいた適切なコミットメッセージで git commit
3. すべてコミット済みの場合: このステップをスキップ

## 完了報告
以下を報告すること:
- コミットの有無と内容
