
## コアタスク

変更記述を受け取り、プロジェクト内の全specを走査して、影響を受けるspecの特定・依存順序の決定・伝播マップの生成を行う。

## 入力パラメータ

promptから以下を受け取る:
- `CHANGE_DESCRIPTION`: 変更内容の自然言語記述

## 実行手順

### 1. 全Specの走査

`.kiro/specs/` 配下の全ディレクトリを列挙し、各specについて以下を読み込む:
- `spec.json` — phase, feature名
- `requirements.md` — 要件一覧
- `design.md` — 設計概要（存在する場合）

**注意**: `phase` が `initialized` のspecは走査対象から除外する（要件未生成のため分析不可）。

### 2. 変更との関連性評価

各specについて、変更記述との関連性を以下の基準で評価する:

1. **直接的な関連**: 変更記述がspecの要件・設計に直接言及している
2. **機能的な依存**: 変更によりspecの入出力インターフェースが影響を受ける
3. **ドメイン的な関連**: 同じドメイン概念を扱っており、変更の波及が予想される

各specに信頼度を付与:
- `high`: 変更記述が明確にspecの機能に言及している
- `medium`: 機能的な依存関係がある
- `low`: ドメイン的な関連のみ（通常は対象外）

**信頼度が `low` のspecは対象から除外する。**

### 3. 依存順序の決定

対象specが複数ある場合、以下の基準で実行順序を決定する:

1. **上流spec優先**: 他のspecのインターフェースに影響を与えるspecを先に処理
2. **依存関係グラフ**: spec間のデータフロー・インターフェース依存を分析
3. **独立spec**: 相互に独立しているspecは同一順位

### 4. 伝播マップの生成

各対象specについて、以下の情報を構造化して記述:
- **change**: 振る舞いレベルの変更記述（何がどう変わるか）
- **downstream_impact**: 下流specへの影響（あれば）
- **depends_on**: 依存する上流spec（あれば）

### 5. 特殊ケースの判定

- **対象specなし**: 変更記述がどのspecにも該当しない場合 → `MP0_NO_MATCH` を出力
- **新規spec推奨**: 変更が既存specのスコープ外で、新規featureとして実装すべき場合 → `MP0_NEW_SPEC_RECOMMENDED` を出力

## 出力形式

### 通常ケース

```
MP0_DONE
TARGET_SPECS: spec2 (high), spec1 (medium)
EXECUTION_ORDER: spec2, spec1
PROPAGATION_MAP_START
## spec2 (confidence: high)
- change: <振る舞いレベルの変更記述>
- downstream_impact: spec1のインターフェース変更
- depends_on: none (upstream)

## spec1 (confidence: medium)
- change: <振る舞いレベルの変更記述>
- downstream_impact: none
- depends_on: spec2
PROPAGATION_MAP_END
```

### 対象specなし

```
MP0_NO_MATCH
REASON: <対象specが見つからない理由>
RECOMMENDATION: /plan で新規featureとして実装することを推奨
```

### 新規spec推奨

```
MP0_NEW_SPEC_RECOMMENDED
REASON: <新規specを推奨する理由>
SUGGESTED_FEATURE: <推奨するfeature名>
```

**注意事項**:
- `TARGET_SPECS` は信頼度の高い順に列挙
- `EXECUTION_ORDER` は依存関係に基づく実行順（上流 → 下流）
- 伝播マップ内の各エントリは `##` ヘッダーで区切る
- 各フィールドは1行で出力し、改行しない（伝播マップ内のリスト項目を除く）
