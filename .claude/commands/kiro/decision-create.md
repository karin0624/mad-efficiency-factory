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
- **インタラクションパターン**: Proposal-First — まず完全なドラフトを生成し、その後ユーザーのフィードバックで改善する（事前に順番に質問しない）
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
- `.kiro/decisions/` — 既存ADRスキャン（次ID決定 + 関連決定チェック + 矛盾分析）
- `$ARGUMENTS` があれば解析し、カテゴリを推定する（spec / architecture / governance）
  - カテゴリが明確に推定できない場合のみ AskUserQuestion で確認する
  - spec カテゴリの場合は `.kiro/specs/` から対象featureも推定する

### ステップ 2: 完全なドラフトADR生成

`$ARGUMENTS`、コードベースの状況、steering コンテキスト、既存ADRを総合し、**AIが以下のすべてを自律的に生成する**:

- **Context**: 引数・コード変更・steeringから決定が必要になった状況を推定・記述
- **Decision Drivers**: 3-5個の判断要因を特定（プロジェクト固有の文脈を反映）
- **Considered Options**: 2-3個の代替案をpros/cons付きで構成（コードベースとsteering文脈から実現可能な選択肢を推定）
- **Decision**: 最も合理的な選択肢を推薦し、根拠を能動態で記述（「〜を採用する」）
- **Consequences**: positive / negative (accepted trade-offs) / constraints created を推定
- **Enforcement**: 決定内容に最も適した強制手段をAIが具体的に提案する（固定選択肢から選ばせるのではなく、決定の性質に応じた手段を推薦。例: lint ruleの具体的な設定、steeringへの追記内容、hook scriptの概要など）

ファイル生成ルール:
- カテゴリディレクトリ内の最大番号+1でID決定（初回は0001）
- ファイル名: `{NNNN}-{slugified-title}.md`
  - slugはタイトルを小文字化し、スペースを `-` に置換、英数字とハイフンのみ保持
- テンプレートに生成データを埋めて `status: proposed` で書き出す
- 既存ADRとのsupersede関係がある場合は `supersedes` フィールドを設定する

### ステップ 3: ドラフト提示 + 的確なレビュー質問 (AskUserQuestion × 1回)

生成したドラフト全体を提示した上で、AIが**最も不確実な2-3点について的確な質問**を投げかける。

質問の設計原則:
- **具体的**: 「この提案でOKですか？」ではなく「Decision DriversにXを含めましたが、Yの観点も考慮すべきですか？」
- **判断を助ける**: 「Option AをBより優先した理由はZですが、チームの経験と合致していますか？」
- **不確実性に焦点**: AIが自信のない部分だけを聞く（自明な部分は聞かない）

AskUserQuestion:
- question: ドラフトの要約 + 不確実な2-3点の質問（具体的に記述）
- options:
  - 「承認（このまま accepted にする）」
  - 「proposed のまま保留する」
  - 「修正指示をテキストで回答」（←ユーザーがテキスト入力で修正点を指示）

### ステップ 4: フィードバック反映 + 最終確認

- **承認の場合**: `status: accepted` に更新 → ステップ 5 へ
- **保留の場合**: `status: proposed` のまま → ステップ 5 へ
- **修正指示の場合**:
  - ユーザーのフィードバックに基づきドラフトを修正する
  - 修正箇所のdiffを簡潔に提示する
  - 大幅な変更（新しい代替案の追加、Decision自体の変更）があれば再度 AskUserQuestion で確認する
  - 軽微な修正（文言調整、Drivers/Consequences の追加・削除）は直接反映し、ステップ 5 へ

### ステップ 5: ファイル確定 + サマリー出力

- 既存ADRとのsupersede関係があれば旧ADRの `superseded_by` フィールドを更新する（内容は変更しない）
- サマリー出力:

```
✅ ADR 作成完了

## 作成ファイル:
- {path}: {title}

## 決定の要約:
- {1行サマリー}

## 既存ADRとの関係:
- {関連/矛盾/supersede があれば記載、なければ「なし」}

## 次のアクション:
- {enforcement に基づく具体的な次のステップ}
```

---

## レビューモード

### ステップ 1r: 対象ADR特定

- パスが指定されていれば直接読み込み
- 未指定なら `.kiro/decisions/` 内の `status: proposed` なADRを一覧表示し選択（AskUserQuestion）
- `proposed` なADRがない場合は「レビュー対象のADRがありません」と報告して終了

### ステップ 2r: 整合性チェック + 内容レビュー (AskUserQuestion)

まず既存ADRとの整合性チェック結果を提示する:
- 関連する既存ADRとの整合性（矛盾がないか）
- supersede すべき既存ADRがないか
- 不足しているセクションや不明瞭な記述がないか

その上でADRの内容を表示し、AIが発見した懸念点や改善提案を具体的に提示する。

AskUserQuestion:
- question: 整合性チェック結果 + ADR内容の要約 + 具体的な改善提案（あれば）
- options:
  - 「承認（accepted）」
  - 「却下（deprecated）」
  - 「修正指示をテキストで回答」

### ステップ 3r: ステータス更新

- **承認**: `status: proposed` → `status: accepted` + `date` を今日の日付に更新
- **修正**: ユーザーの修正指示を反映 → 修正箇所のdiffを提示 → 大幅な変更なら再度確認、軽微なら `accepted` に更新
- **却下**: `status: deprecated` + 理由を Context に追記

</instructions>

## ツールガイダンス

- `Read`: テンプレート、基準、既存ADR、steeringの読み込み
- `Glob`: 既存ADRスキャン、spec一覧取得
- `Grep`: `status: proposed` なADRの検索
- `Write`: 新規ADRファイルの作成（ステップ 2 でドラフト書き出し）
- `Edit`: 既存ADRのステータス更新、フィードバック反映
- `AskUserQuestion`: ステップ 3 でのレビュー質問（新規作成モードでは原則1回のみ）

## 安全策

- 既存ADRの**内容**は変更しない（ステータスフィールドと `superseded_by` フィールドのみ更新可）
- supersede時は旧ADRの `superseded_by` フィールドのみ更新し、内容は保全する
- セキュリティ関連の情報（キー、パスワード等）をADRに含めない
