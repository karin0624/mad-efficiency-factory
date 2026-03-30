
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## ユーザーフィードバック

`USER_FEEDBACK` が空でない場合、そのフィードバック内容を最優先で対応すること。
フィードバックで指摘された設計上の問題点を `design.md` に反映した上で、通常の手順を実行する。

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

#### REVISE → フィードバック反映（確信度に基づく確認）
1. Codexのフィードバック項目を分析し、各項目を分類:
   - **自動対応可能**: 明確な誤り、トレーサビリティギャップ、構造的問題 → 確認なしで自動適用
   - **人間判断が必要**: 主観的設計選択、複数の妥当な選択肢、要件解釈に依存する項目
2. 自動対応可能な項目を design.md に適用
3. 人間判断が必要な項目が残った場合:
   - `REVIEW_NEEDS_HUMAN` マーカーを出力
   - 各不確実項目の内容とその理由を報告
   - この時点で一時停止（パイプラインがユーザーに確認する）
4. 人間判断が不要な場合 → 従来通り再レビューを実行:
   - 再レビュー: Skill tool: skill="design-review", args="FEATURE_NAME"
   - 2回目の判定:
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
