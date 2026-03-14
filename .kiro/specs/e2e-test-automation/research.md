# Research & Design Decisions

## Summary
- **Feature**: `e2e-test-automation`
- **Discovery Scope**: Extension
- **Key Findings**:
  - 変更対象は全てMarkdown/JSONドキュメントファイル（20ファイル）であり、GDScriptコードの変更は不要
  - 既存のLayer 3参照箇所は`.kiro/steering/`、`.kiro/settings/`、`.claude/commands/`、`.kiro/specs/`に分散しており、一貫した置換戦略が必要
  - 新ライブラリ・外部依存の追加は不要。既存のGdUnit4/SceneRunner/xvfb-run環境をそのまま活用

## Research Log

### 既存Layer 3参照の分布調査
- **Context**: 変更漏れを防ぐため、現在のLayer 3参照箇所を網羅的に調査
- **Sources Consulted**: `grep -r "Layer 3"` によるコードベース検索
- **Findings**:
  - `steering/tech.md`: 1箇所（L3ヒューマンレビュー定義）
  - `steering/testing.md`: L3の定義が暗黙的（テスト層の選択基準テーブル）
  - `settings/templates/specs/`: requirements.md(1箇所), design.md(1箇所)
  - `specs/`: tick-engine(2箇所), conveyor-belt(2箇所), entity-placement(1箇所), tilemap-core(1箇所)
  - `commands/`: spec-tasks, spec-impl, spec-requirements, scene-review, plan, implement
- **Implications**: 変更対象が明確で、カテゴリ別（A:定義、B:パイプライン、C:既存spec、D:インフラ）に整理して順次更新する戦略が有効

### L3/L4振り分け基準の設計
- **Context**: 既存specのLayer 3項目をL3(E2E)とL4(Human Review)のどちらに移行するかの基準が必要
- **Findings**:
  - L3に移行可能: 色・位置・FPS・応答時間・動きの連続性などスクショ/メトリクスで客観的に判定可能な項目
  - L4に留まる: 「気持ちいい」「直感的」など主観的で再現困難な項目
  - tick-engine: 性能メトリクス→L3 E2E、conveyor-belt: 視覚品質→L3 E2E、entity-placement: 完了済み→L4、tilemap-core: →L4
- **Implications**: 振り分け基準をtesting.mdに明記し、今後のspec作成時にも適用可能にする

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 一括テキスト置換 | 全ファイルを一括検索・置換で更新 | 高速・単純 | コンテキストに応じた差異を見落とす可能性 | 不採用: 各ファイルで置換内容が微妙に異なる |
| カテゴリ別順次更新 | A(定義)→B(パイプライン)→C(既存spec)→D(インフラ)の順で更新 | 依存関係を尊重、レビュー容易 | やや時間がかかる | 採用: planの構成に合致 |

## Design Decisions

### Decision: カテゴリ別順次更新戦略の採用
- **Context**: 20ファイルの一貫した更新が必要だが、各ファイルの変更内容は微妙に異なる
- **Alternatives Considered**:
  1. 一括sed置換 — 単純だがコンテキスト依存の差異を見落とすリスク
  2. カテゴリ別順次更新 — planの構成に従い4カテゴリに分けて更新
- **Selected Approach**: カテゴリ別順次更新
- **Rationale**: planが既にA〜Dのカテゴリに整理されており、依存関係（定義→パイプライン→既存spec→インフラ）を尊重できる
- **Trade-offs**: 実装タスクが多くなるが、各タスクが小さく検証しやすい
- **Follow-up**: 最終検証でLayer 3がE2E以外で残っていないことをgrepで確認

### Decision: E2Eテストパターンのsteering文書化
- **Context**: L3 E2E層を新設するにあたり、実装パターンの標準化が必要
- **Selected Approach**: testing.mdにE2Eテストパターン節・フィルムストリップパターン・スクショ戦略テーブルを追加
- **Rationale**: steeringドキュメントは全specで共有される基盤知識であり、ここに標準パターンを記載することで一貫性を確保
- **Trade-offs**: testing.mdの分量が増えるが、spec-implが参照する重要なガイダンスとなる

## Risks & Mitigations
- 変更漏れによるレイヤー参照の不整合 — 最終検証ステップ（grep検証）で検出・修正
- 既存specの移行時に意味が変わるリスク — 各specのコンテキストを確認し、L3/L4の振り分け基準に基づいて判断
- E2Eテストパターンの記述が過度に具体的になるリスク — steeringには方針のみ記載し、具体的な実装はspec-implフローに委ねる
