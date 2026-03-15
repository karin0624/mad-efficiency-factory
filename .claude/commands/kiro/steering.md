---
description: Manage .kiro/steering/ as persistent project knowledge
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Kiro Steering 管理

<background_information>
**役割**: `.kiro/steering/` をプロジェクトの永続的メモリとして維持する。

**ミッション**:
- ブートストラップ: コードベースからコアSteeringを生成する（初回）
- 同期: Steeringとコードベースの整合性を保つ（メンテナンス）
- 保全: ユーザーのカスタマイズは神聖なものとして扱い、更新は追加的に行う

**成功基準**:
- Steeringがパターンと原則を捉え、網羅的なリストではないこと
- コードの乖離が検出・報告されること
- すべての `.kiro/steering/*.md` が等しく扱われること（コア + カスタム）
</background_information>

<instructions>
## シナリオ検出

`.kiro/steering/` の状態を確認する:

**ブートストラップモード**: 空 または コアファイル（product.md, tech.md, structure.md）が欠落している場合
**同期モード**: すべてのコアファイルが存在する場合

---

## ブートストラップフロー

1. `.kiro/settings/templates/steering/` からテンプレートを読み込む
2. コードベースを分析する（JIT）:
   - `Glob` でソースファイルを検索
   - `Read` で README, package.json 等を読み込む
   - `Grep` でパターンを検索
3. パターンを抽出する（リストではなくパターン）:
   - Product: 目的、価値、コア機能
   - Tech: フレームワーク、技術的判断、慣例
   - Structure: 構成、命名規則、インポート
4. Steeringファイルを生成する（テンプレートに従う）
5. `.kiro/settings/rules/steering-principles.md` から原則を読み込む
6. レビュー用にサマリーを提示する

**重点**: ファイルや依存関係のカタログではなく、判断を導くパターンに焦点を当てる。

---

## 同期フロー

1. 既存のSteeringをすべて読み込む（`.kiro/steering/*.md`）
   - `.kiro/decisions/` の既存ADRをスキャンし、関連する意思決定を把握
2. コードベースの変更を分析する（JIT）
3. 乖離を検出する:
   - **Steering → コード**: 欠落要素 → 警告
   - **コード → Steering**: 新しいパターン → 更新候補
   - **カスタムファイル**: 関連性をチェック
3.5. **ADR必要性の評価**:
   - ステップ3で検出された変更が既存のパターン・決定を**変更**する場合のみ評価
   - 新しいパターンの追加のみの場合はADR不要
   - `.kiro/settings/rules/decision-criteria.md` の基準に照らして判定
   - ADRが必要と判断した場合、Steering更新前に `/kiro:decision-create` の実行を提案
4. 更新を提案する（追加的に、ユーザーコンテンツを保全）
5. レポート: 更新内容、警告、推奨事項

**更新の哲学**: 置換ではなく追加。ユーザーのセクションを保全する。

---

## 粒度の原則

`.kiro/settings/rules/steering-principles.md` より:

> 「新しいコードが既存のパターンに従っている場合、Steeringを更新する必要はないはずである。」

網羅的なリストではなく、パターンと原則を文書化する。

**悪い例**: ディレクトリツリー内のすべてのファイルをリスト化する
**良い例**: 例を交えて構成パターンを説明する

</instructions>

## ツールガイダンス

- `Glob`: ソース/設定ファイルの検索
- `Read`: Steering、ドキュメント、設定の読み込み
- `Grep`: パターンの検索
- `Bash` (ls): 構造の分析

**JIT戦略**: 事前にではなく、必要になった時に取得する。

## 出力説明

チャットでのサマリーのみ（ファイルは直接更新される）。

### ブートストラップ:
```
✅ Steering 作成完了

## 生成されたファイル:
- product.md: [簡単な説明]
- tech.md: [主要な技術スタック]
- structure.md: [構成]

レビューしてソース・オブ・トゥルースとして承認してください。
```

### 同期:
```
✅ Steering 更新完了

## 変更内容:
- tech.md: React 18 → 19
- structure.md: APIパターンを追加

## コードの乖離:
- コンポーネントがインポート規則に従っていない

## ADR推奨:
- [変更名]: ADR推奨 (理由: [criteria match])

## 推奨事項:
- api-standards.md の作成を検討してください
```

## 使用例

### ブートストラップ
**入力**: 空のSteering、React TypeScriptプロジェクト
**出力**: パターンを含む3ファイル — 「フィーチャーファースト」「TypeScript strict」「React 19」

### 同期
**入力**: 既存のSteering、新しい `/api` ディレクトリ
**出力**: structure.md を更新、非準拠ファイルをフラグ、api-standards.md を提案

## 安全策とフォールバック

- **セキュリティ**: キー、パスワード、シークレットを絶対に含めないこと（原則を参照）
- **不確実な場合**: 両方の状態を報告し、ユーザーに確認する
- **保全**: 迷った場合は置換ではなく追加する

## 備考

- すべての `.kiro/steering/*.md` がプロジェクトメモリとして読み込まれる
- テンプレートと原則はカスタマイズのために外部化されている
- カタログではなくパターンに焦点を当てること
- 「ゴールデンルール」: パターンに従う新しいコードはSteering更新を必要としないはずである
- エージェント固有のツーリングディレクトリ（例: `.cursor/`, `.gemini/`, `.claude/`）のドキュメント化は避けること
- `.kiro/settings/` の内容はSteeringファイルに記載しないこと（設定はメタデータであり、プロジェクト知識ではない）
- `.kiro/specs/` と `.kiro/steering/` への軽い参照は許容される。他の `.kiro/` ディレクトリは避けること
