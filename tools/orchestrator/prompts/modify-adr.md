
## コアタスク

M1分析結果と実装後の変更差分に基づき、ADRを自動生成する。

## 入力パラメータ

promptから以下を受け取る:
- `FEATURE_NAME`: specフィーチャー名
- `CHANGE_DESCRIPTION`: 変更内容の自然言語記述
- `ADR_CATEGORY`: spec|architecture|governance
- `ADR_REASON`: ADR必要と判断された理由
- `DELTA_SUMMARY`: M1で生成された変更サマリー
- `M1_OUTPUT`: M1分析の全出力テキスト
- `SPEC_DIFF`: worktreeでのgit diff（実装結果の証拠）

## 実行手順

### 1. テンプレートと基準の読み込み

以下を読み込む:
- `.kiro/settings/templates/decisions/adr.md` — ADRテンプレート
- `.kiro/settings/rules/decision-criteria.md` — 判断基準（参考）

### 2. 既存ADRスキャン

- `.kiro/decisions/{ADR_CATEGORY}/` の既存ファイルをスキャンし、最大番号を取得
- 次のID = 最大番号 + 1（ファイルがない場合は0001）

### 3. ADR内容を自動生成

以下の情報源から各セクションを生成する:

- **Context**: `CHANGE_DESCRIPTION` と `ADR_REASON` から、この決定を促した状況を記述
- **Decision Drivers**: `M1_OUTPUT` から判断を左右した要因を3-5個抽出
- **Considered Options**: `M1_OUTPUT` と `DELTA_SUMMARY` から、検討した選択肢を推定（最低2つ）
- **Decision**: 何を決め、なぜそれを選んだかを能動態で記述
- **Consequences**:
  - Positive: `SPEC_DIFF` と `DELTA_SUMMARY` から肯定的な帰結を**証拠ベース**で推定
  - Negative (accepted trade-offs): 受け入れたトレードオフを記述
  - Constraints Created: この決定が生み出す制約を記述
- **Enforcement**: "N/A — レビューで確認" をデフォルトとする

フロントマター:
- `status: proposed`（ユーザーが `/kiro:decision-create review` で確認後に `accepted` へ遷移）
- `category`: `ADR_CATEGORY` の値
- `spec`: `ADR_CATEGORY` が `spec` の場合は `FEATURE_NAME` を設定
- `date`: 今日の日付

### 4. ADRファイル生成

- ファイルパス: `.kiro/decisions/{ADR_CATEGORY}/{NNNN}-{slug}.md`
  - `{NNNN}`: ゼロパディング4桁の連番
  - `{slug}`: タイトルを小文字化、スペースを `-` に置換、英数字とハイフンのみ保持
- テンプレートに従った形式で書き出す

## 出力形式

以下の形式で正確に出力すること:

```
ADR_CREATED
ADR_PATH: .kiro/decisions/{category}/{id}-{slug}.md
ADR_TITLE: {title}
```

**注意事項**:
- ADRの生成に失敗した場合は `ADR_CREATED` マーカーを出力しない
- 各フィールドは1行で出力し、改行しない
