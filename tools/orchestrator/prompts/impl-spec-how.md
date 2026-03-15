
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `FEATURE_NAME` と `RESUME_MODE` を使用する。

### Phase 3: spec-design（RESUME_MODE が "full" の場合のみ）
- Skill tool: skill="kiro:spec-design", args="FEATURE_NAME -y"

### Phase 3.5: design-review（常に実行）
- Skill tool: skill="design-review", args="FEATURE_NAME"
- Codex出力の先頭行 `STATUS:` をパース

### Phase 3.5の判定処理

#### APPROVE → 完了
- 何もしない、次のAgentに進む

#### REVISE → フィードバック反映 + 1回だけ再レビュー（max 2パス）
1. design-review Skillが自動的にdesign.mdを更新する
2. 再レビューを実行: Skill tool: skill="design-review", args="FEATURE_NAME"
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
以下を報告すること:
- design生成の完了有無
- Codexレビュー判定（APPROVE / REVISE / REJECT）
- レビューパス数（1 or 2）
- REJECTの場合: 停止理由
