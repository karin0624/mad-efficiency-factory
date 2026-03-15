
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `FEATURE_NAME` を使用する。

### Phase 5.5: validate-impl
- Skill tool: skill="kiro:validate-impl", args="FEATURE_NAME"

## 判定結果の処理
- **GO** または **CONDITIONAL GO** の場合:
  - spec.jsonの `phase` を `"validated"` に更新
  - 「VALIDATION_PASSED」と報告
- **NO-GO** の場合:
  - spec.jsonの `phase` は `"impl-completed"` のまま維持
  - 「VALIDATION_FAILED」と詳細な問題リストを報告

## エラー処理
- 失敗した場合、バリデーション結果と詳細を報告
- 再実行用のコマンドを含める

## フォールバック
Skill toolが使えない場合は .claude/commands/kiro/validate-impl.md を直接読んで手動実行

## 完了報告
以下を報告すること:
- 判定結果（GO / CONDITIONAL GO / NO-GO）
- バリデーションサマリー（issues, coverage, traceability）
- 設計ドリフトの検出・パッチ結果
- NO-GOの場合: 修正が必要な具体的な問題リスト
