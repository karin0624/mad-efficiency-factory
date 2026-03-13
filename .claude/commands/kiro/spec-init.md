---
description: Initialize a new specification with detailed project description
allowed-tools: Bash, Read, Write, Glob
argument-hint: <project-description>
---

# Spec 初期化

<background_information>
- **ミッション**: Spec駆動開発の最初のフェーズを初期化し、新しいSpecのディレクトリ構造とメタデータを作成する
- **成功基準**:
  - プロジェクトの説明から適切なフィーチャー名を生成する
  - 競合のないユニークなSpec構造を作成する
  - 次のフェーズ（要件生成）への明確なパスを提示する
</background_information>

<instructions>
## コアタスク
プロジェクトの説明（$ARGUMENTS）からユニークなフィーチャー名を生成し、Spec構造を初期化する。

## 実行ステップ
1. **一意性チェック**: `.kiro/specs/` で名前の競合がないか確認する（必要に応じて数字サフィックスを付加）
2. **ディレクトリ作成**: `.kiro/specs/[feature-name]/`
3. **テンプレートを使用してファイルを初期化**:
   - `.kiro/settings/templates/specs/init.json` を読み込む
   - `.kiro/settings/templates/specs/requirements-init.md` を読み込む
   - プレースホルダーを置換:
     - `{{FEATURE_NAME}}` → 生成されたフィーチャー名
     - `{{TIMESTAMP}}` → 現在のISO 8601タイムスタンプ
     - `{{PROJECT_DESCRIPTION}}` → $ARGUMENTS
   - `spec.json` と `requirements.md` をSpecディレクトリに書き込む

## 重要な制約
- このステージでは要件/設計/タスクを生成しないこと
- ステージごとの開発原則に従うこと
- 厳密なフェーズ分離を維持すること
- このフェーズでは初期化のみを実行すること
</instructions>

## ツールガイダンス
- **Glob** を使用して既存のSpecディレクトリを確認し、名前の一意性を検証する
- **Read** を使用してテンプレート `init.json` と `requirements-init.md` を取得する
- **Write** を使用してプレースホルダー置換後に spec.json と requirements.md を作成する
- ファイル書き込み操作の前にバリデーションを実行すること

## 出力説明
`spec.json` で指定された言語で、以下の構造で出力する:

1. **生成されたフィーチャー名**: `feature-name` 形式で、1〜2文の根拠を付記
2. **プロジェクト概要**: 簡潔な要約（1文）
3. **作成されたファイル**: フルパスの箇条書きリスト
4. **次のステップ**: `/kiro:spec-requirements <feature-name>` を示すコマンドブロック
5. **備考**: 初期化のみが実行された理由の説明（フェーズ分離について2〜3文）

**フォーマット要件**:
- Markdownの見出し（##, ###）を使用する
- コマンドはコードブロックで囲む
- 出力全体を簡潔に保つ（250語以内）
- `spec.json.language` に従った明確でプロフェッショナルな言語を使用する

## 安全策とフォールバック
- **フィーチャー名が曖昧な場合**: フィーチャー名の生成が不明確な場合、2〜3の選択肢を提示してユーザーに選択を求める
- **テンプレートが見つからない場合**: テンプレートファイルが `.kiro/settings/templates/specs/` に存在しない場合、具体的なファイルパスを示してエラーを報告し、リポジトリのセットアップを確認するよう提案する
- **ディレクトリの競合**: フィーチャー名が既に存在する場合、数字サフィックスを付加し（例: `feature-name-2`）、自動的な競合解決をユーザーに通知する
- **書き込み失敗**: 具体的なパスを示してエラーを報告し、パーミッションまたはディスク容量の確認を提案する
