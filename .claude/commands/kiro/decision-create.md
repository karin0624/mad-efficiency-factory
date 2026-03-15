---
description: Create or review Architecture Decision Records (ADR) interactively
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion
argument-hint: [new <context> | review [adr-path]]
---

# ADR（Architecture Decision Record）の作成・レビュー

<background_information>
- **ミッション**: 意思決定の根拠（なぜ）を永続化し、将来のAIが矛盾する決定をしないようにする。
- **成功基準**:
  - ADRが `.kiro/decisions/{category}/` に正しく配置される
  - YAMLフロントマターが正しくパースできる
  - 全セクション（Context, Decision Drivers, Considered Options, Decision, Consequences, Enforcement）が埋まる
  - 既存ADRとの整合性が確認される
</background_information>

<instructions>
## モード判定

`$ARGUMENTS` を解析する:

- `review` で始まる場合 → **レビューモード**（ステップ 1r へ）
- それ以外 → **新規作成モード**（ステップ 1 へ）
- 引数なしの場合、`.kiro/decisions/` 内の `status: proposed` なADRを検索し、あればレビューモードを提案

---

## 新規作成モード

### ステップ 1: コンテキスト読み込み

以下をすべて読み込む:
- `.kiro/settings/rules/decision-criteria.md` — ADR必要性の判断基準
- `.kiro/settings/templates/decisions/adr.md` — ADRテンプレート
- `.kiro/steering/` — プロジェクト全体のルールとコンテキスト
- `.kiro/decisions/` — 既存ADRスキャン（次ID決定 + 関連決定チェック）
- `$ARGUMENTS` があれば解析

### ステップ 2: カテゴリ選択 (AskUserQuestion)

AIが `$ARGUMENTS` を分析してカテゴリを推定する。

AskUserQuestion で確認:
- options: spec / architecture / governance
- spec の場合、追加でどのfeatureかを聞く（`.kiro/specs/` 一覧から選択肢生成）

### ステップ 3: 文脈と要因 (AskUserQuestion)

AIが変更内容から文脈と3-5個のdecision driversを生成する。

AskUserQuestion で確認:
- options: 「AI提案を採用」「修正して採用」
- 合わなければテキストで回答

### ステップ 4: 代替案 (AskUserQuestion)

AIが2-3個の代替案をpros/cons付きで提案する。

AskUserQuestion で確認:
- options: 各代替案 / 「代替案なし（この方法のみ）」

### ステップ 5: トレードオフ (AskUserQuestion)

AIがpositive/negative/constraintsを推定して提示する。

ユーザーが確認・修正。

### ステップ 6: 強制手段 (AskUserQuestion)

options:
- 「hook/lintで強制」
- 「steeringに追記」
- 「レビューで確認」
- 「強制不要」

### ステップ 7: ADRファイル生成

- カテゴリディレクトリ内の最大番号+1でID決定（初回は0001）
- ファイル名: `{NNNN}-{slugified-title}.md`
  - slugはタイトルを小文字化し、スペースを `-` に置換、英数字とハイフンのみ保持
- テンプレートに収集データを埋めて書き出し
- status: `accepted`（ユーザーが不確定な場合は `proposed`）

### ステップ 8: 出力サマリー

```
✅ ADR 作成完了

## 作成ファイル:
- {path}: {title}

## 決定の要約:
- {1行サマリー}

## 次のアクション:
- {提案}
```

---

## レビューモード

### ステップ 1r: 対象ADR特定

- パスが指定されていれば直接読み込み
- 未指定なら `.kiro/decisions/` 内の `status: proposed` なADRを一覧表示し選択（AskUserQuestion）
- `proposed` なADRがない場合は「レビュー対象のADRがありません」と報告して終了

### ステップ 2r: 内容レビュー (AskUserQuestion)

ADRの各セクションを表示し、修正要否を確認。

options:
- 「承認（accepted）」
- 「修正して承認」
- 「却下（deprecated）」

### ステップ 3r: ステータス更新

- **承認**: `status: proposed` → `status: accepted` + `date` を今日の日付に更新
- **修正**: ユーザーの修正を反映後に `accepted`
- **却下**: `status: deprecated` + 理由を Context に追記

</instructions>

## ツールガイダンス

- `Read`: テンプレート、基準、既存ADR、steeringの読み込み
- `Glob`: 既存ADRスキャン、spec一覧取得
- `Grep`: `status: proposed` なADRの検索
- `Write`: 新規ADRファイルの作成
- `Edit`: 既存ADRのステータス更新
- `AskUserQuestion`: 各ステップでのユーザー対話

## 安全策

- 既存ADRの**内容**は変更しない（ステータスフィールドのみ更新可）
- supersede時は旧ADRの `superseded_by` フィールドのみ更新し、内容は保全する
- セキュリティ関連の情報（キー、パスワード等）をADRに含めない
