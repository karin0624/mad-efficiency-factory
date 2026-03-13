# Requirements Document

## Introduction
ゲーム内で流通するアイテムの種別を一意に識別し、その定義情報を一元管理する仕組み（Item Registry）を提供する。ベルト輸送・機械加工・納品カウントなど、すべてのアイテム関連システムが共通のアイテム定義を参照できるようにし、散在するハードコードや不整合を防ぐ。MVPでは鉄鉱石（ID=1）と精錬鉄（ID=2）の2種を初期定義として提供する。

## Requirements

### Requirement 1: アイテム定義の構造
**Objective:** アイテムを扱うゲームプレイシステムとして、各アイテム種別が一意な整数IDと表示名を持つことで、システム間でアイテムを一貫して識別・参照できるようにしたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The ItemDefinition shall 一意な正の整数IDと表示名（空でない文字列）を保持する
2. The ItemDefinition shall ID=0を予約値（アイテムなし）として扱い、有効なアイテム定義に割り当てない
3. When アイテム定義が生成される, the ItemDefinition shall IDと表示名を不変の属性として保持する

### Requirement 2: アイテムカタログへの登録
**Objective:** アイテムを扱うゲームプレイシステムとして、アイテム定義をカタログに登録し一元管理することで、すべてのシステムが同じ定義を参照できるようにしたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 新しいアイテム定義が登録される, the ItemCatalog shall そのアイテム定義をカタログに追加する
2. If 既に同一IDのアイテム定義が登録されている場合, the ItemCatalog shall 登録を拒否し、既存の登録を変更しない
3. When 新しいアイテム定義が追加登録される, the ItemCatalog shall 既存のアイテム定義の振る舞いを変更しない

### Requirement 3: IDによるアイテム検索
**Objective:** アイテムを扱うゲームプレイシステムとして、IDを指定してアイテム定義を検索・取得することで、必要なアイテム情報に素早くアクセスしたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. When 有効なIDで検索される, the ItemCatalog shall 対応するアイテム定義を返す
2. If 存在しないIDで検索された場合, the ItemCatalog shall nullに相当する結果を返す（クラッシュしない）
3. If ID=0で検索された場合, the ItemCatalog shall nullに相当する結果を返す

### Requirement 4: 数量値の管理
**Objective:** アイテムを扱うゲームプレイシステムとして、アイテムの数量を安全に増減できることで、数量が常に有効範囲内に収まり不正な状態を防ぎたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The ItemQuantity shall 0以上かつ上限値以下の有効範囲内の値を保持する
2. When 数量に正の値が加算される, the ItemQuantity shall 結果が上限値を超えない範囲で数量を増加する
3. When 数量から正の値が減算される, the ItemQuantity shall 結果が0を下回らない範囲で数量を減少する
4. If 加算の結果が上限値を超える場合, the ItemQuantity shall 上限値にクランプする（エラーを発生させない）
5. If 減算の結果が0を下回る場合, the ItemQuantity shall 0にクランプする（エラーを発生させない）

### Requirement 5: MVP初期データ
**Objective:** アイテムを扱うゲームプレイシステムとして、MVP段階で必要な最小限のアイテム定義が事前に用意されていることで、ベルト輸送や加工の開発をすぐに開始できるようにしたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The ItemCatalog shall 鉄鉱石（ID=1）のアイテム定義を初期状態で保持する
2. The ItemCatalog shall 精錬鉄（ID=2）のアイテム定義を初期状態で保持する
3. When ID=1で検索される, the ItemCatalog shall 鉄鉱石のアイテム定義を返す
4. When ID=2で検索される, the ItemCatalog shall 精錬鉄のアイテム定義を返す

### Requirement 6: シーン非依存性
**Objective:** アイテムを扱うゲームプレイシステムとして、アイテムカタログがシーン状態や視覚コンテキストに依存しないことで、ユニットテストや他システムからの利用が容易になるようにしたい
**Testability:** Layer 1 (Fully Testable)

#### Acceptance Criteria
1. The ItemCatalog shall シーンツリーへの参照なしにインスタンス化できる
2. The ItemCatalog shall シーン状態や視覚コンテキストなしで全機能（登録・検索・数量操作）を提供する
3. The ItemDefinition shall シーンノードに依存しない純粋なデータ構造として動作する
