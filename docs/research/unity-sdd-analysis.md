# Unity × 仕様駆動開発（AI駆動）適用可能性分析

## 前提: Unity MCPで可能になったこと

Unity MCP (`com.unity.ai.assistant@2.0`) により、AIエージェントがUnityエディタに対して以下を直接実行できるようになった。

| 能力 | 具体的ツール |
|---|---|
| シーン・GameObject操作 | `manage_scene`, `manage_gameobject`, `manage_components` |
| スクリプト生成・編集 | `manage_script`, `script-execute` (動的C#実行) |
| テスト実行・結果取得 | `run_tests` (EditMode/PlayMode両対応) |
| コンソールログ読み取り | `read_console` |
| Play/Pause/Stop制御 | `manage_editor` |
| スクリーンショット取得 | `screenshot-game-view`, `screenshot-scene-view` |
| アセット管理 | `manage_asset`, `manage_prefabs` |
| マテリアル/シェーダー | `manage_material`, `manage_shader` |
| アニメーション | `manage_animation` |
| UI | `manage_ui` |
| パッケージ管理 | `package-list`, `package-add`, `package-remove` |

特に重要なのは **`run_tests`と`script-execute`の存在** で、これが仕様→テスト→検証ループを成立させる基盤になる。

---

## 1. 適用可能な領域（仕様→テスト→AI生成が機能する）

### 1.1 ゲームロジック / ビジネスロジック

**適用度: 非常に高い**

ダメージ計算、インベントリ管理、スキルシステム、経済システムなど、**純粋なC#ロジック** は仕様駆動開発の最適な対象。

```yaml
# spec/combat/damage-calculation.yaml
feature: ダメージ計算
rules:
  - 基本ダメージ = 攻撃力 - 防御力 (最低1)
  - クリティカル時: ダメージ × 1.5
  - 属性有利時: ダメージ × 1.2
  - 属性不利時: ダメージ × 0.8
test_cases:
  - input: { atk: 100, def: 30, critical: false }
    expected: 70
  - input: { atk: 10, def: 50, critical: false }
    expected: 1  # 最低保証
```

→ NUnit/EditModeテストに直接変換可能。`run_tests`で検証可能。

### 1.2 ステートマシン / ゲーム進行

**適用度: 高い**

プレイヤーの状態遷移、ゲームフロー、クエスト進行などは状態と遷移条件を仕様として定義すればテスト可能。

```yaml
feature: プレイヤー状態遷移
states: [Idle, Run, Jump, Fall, Attack]
transitions:
  - from: Idle, input: MoveInput, to: Run
  - from: Idle, input: JumpInput, to: Jump, condition: IsGrounded
  - from: Jump, auto: velocity.y < 0, to: Fall
  - from: Any, input: AttackInput, to: Attack, condition: "state != Attack"
invalid_transitions:
  - from: Fall, input: JumpInput  # 空中ジャンプ不可
```

### 1.3 データスキーマ / ScriptableObject定義

**適用度: 高い**

アイテムデータ、敵パラメータ、スキルテーブルなどのデータ構造は仕様から直接生成でき、バリデーションテストも自動生成できる。

```yaml
schema: WeaponData (ScriptableObject)
fields:
  - name: weaponName, type: string, required: true
  - name: baseDamage, type: int, range: [1, 9999]
  - name: attackSpeed, type: float, range: [0.1, 5.0]
  - name: weaponType, type: enum(Sword, Axe, Bow, Staff)
  - name: rarity, type: enum(Common, Rare, Epic, Legendary)
constraints:
  - "Legendary武器のbaseDamageは100以上"
```

### 1.4 API / ネットワーク通信レイヤー

**適用度: 高い**

サーバーとのリクエスト/レスポンス契約、シリアライズ形式は仕様定義→テスト生成の典型的な対象。

---

## 2. 部分的に適用可能な領域（工夫が必要）

### 2.1 物理挙動 / キャラクター制御

**適用度: 中程度**

**問題点:**
- Unityの物理エンジン(PhysX)は非決定的な要素があり、フレームレート依存の挙動がある
- PlayModeテストは時間経過を伴うため実行が遅い
- 「ジャンプの高さが3m」は検証できるが、「ジャンプが気持ちいい」は検証できない

**対策:**

```yaml
feature: プレイヤージャンプ
testable_specs:  # 検証可能な仕様
  - "ジャンプ力12を加えた時、最高到達点が2.8〜3.2mの範囲"
  - "接地判定がtrueの時のみジャンプ可能"
  - "ジャンプ中に再ジャンプ不可"
non_testable_specs:  # 検証不可能な仕様（人間レビュー必要）
  - "ジャンプの弧が自然に見えること"
  - "着地時の減速が心地よいこと"
verification: PlayMode + screenshot + human_review
```

`screenshot-game-view` でスクリーンショットを取得し、マルチモーダルAIで補助的に判断するハイブリッドアプローチが可能だが、信頼性は限定的。

### 2.2 UI/UXレイアウト

**適用度: 中程度**

**問題点:**
- UIの「見た目」や「操作感」はテストで検証しにくい
- RectTransformの座標検証はできるが、「使いやすいか」は検証できない
- 異なる解像度・アスペクト比での表示崩れの網羅的検証が困難

**対策:**

```yaml
feature: HPバー
testable_specs:
  - "HPバーは画面左上に配置(anchor: upper-left)"
  - "HP 50/100の時、バーの fillAmount が 0.5"
  - "HP 0の時、GameOverイベントが発行される"
  - "ダメージ時にバーが赤く点滅（DOTween Sequence完了を検証）"
non_testable_specs:
  - "バーのデザインが世界観に合っていること"
review_method: screenshot + human_review
```

UIのロジック部分(fillAmount, イベント発行)はEditModeテストで検証可能。レイアウトの妥当性は `script-execute` でRectTransformの値を取得して検証する方法もある。

### 2.3 AI / 敵行動パターン

**適用度: 中程度**

**問題点:**
- 確率的な挙動（「30%の確率で回避」）はテストの期待値が一意に定まらない
- NavMeshを使った経路探索の結果は環境に強く依存
- 「賢く見える敵AI」は主観的

**対策:**
- 統計的テスト: 1000回実行して確率が許容範囲内か検証
- 行動ツリーの構造テスト: 条件→行動の選択ロジックを単体テスト
- シナリオテスト: 「プレイヤーがHP20%以下の時、敵は攻撃頻度を上げる」→ 状態を設定して行動を検証

---

## 3. 適用が困難な領域（根本的な課題がある）

### 3.1 ビジュアル・アートディレクション

**問題点:**
- 「キャラクターの見た目」「エフェクトの派手さ」「ライティングの雰囲気」は仕様として形式化できない
- シェーダーパラメータの数値は指定できるが、その結果の見た目の良し悪しはテストできない
- 根本的に、審美的判断はテストに変換不可能

**対策案:**
1. リファレンス画像ベースの仕様: 参考画像を仕様に含め、スクリーンショット→マルチモーダルAI比較
2. パラメータ境界の仕様化: 「ブルームの強度は0.5〜1.5の範囲」のように数値制約だけ定義
3. スタイルガイド文書: AIリーダブルなスタイルガイドを作成し、生成時の参照資料とする（ただしテスト不可）

**現実的結論:** この領域は仕様駆動ではなく、人間のアートディレクター判断 + AIの作業補助が適切。

### 3.2 レベルデザイン / 空間設計

**問題点:**
- 「面白いレベル」は主観的で形式化できない
- 空間的なフロー、難易度曲線、探索の楽しさはテスト化が極めて困難
- オブジェクト配置は可能でも、その配置が「良いか」は判断できない

**対策案:**
1. 制約ベースの仕様: テスト可能な制約だけを定義
   ```yaml
   constraints:
     - "スタートからゴールまでNavMeshで到達可能"
     - "全ての敵配置ポイントがプレイヤーの視線上に1つ以上存在"
     - "プラットフォーム間の距離がジャンプ到達距離以下"
   ```
2. プレイテスト自動化: `manage_editor`でPlay開始→`script-execute`で自動操作→`read_console`で結果収集

### 3.3 サウンド / BGM / 効果音

**問題点:**
- Unity MCPにはオーディオ関連のツールが提供されていない
- 音の「印象」「タイミングの心地よさ」は形式化不可能
- AudioSource/AudioMixerのパラメータ設定は可能だが、結果の検証手段がない

**対策案:**
- ロジック面のみテスト化: 「攻撃ヒット時にSE再生メソッドが呼ばれる」「BGMがシーン遷移で切り替わる」
- AudioSourceのパラメータ（volume, pitch, spatialBlend）の範囲検証

### 3.4 「ゲームフィール」/ ゲーム体験の質

**問題点:**
- 「操作が気持ちいい」「テンポが良い」「達成感がある」は形式化不可能
- これがゲーム開発の本質的な価値であり、最も重要な部分
- 仕様駆動で最もカバーできない領域が、最も重要な領域であるというジレンマ

**対策案:**
- ゲームフィールは仕様駆動の**外**に置く設計判断として明示的に扱う
- 仕様駆動で「正しく動く骨格」を高速に構築し、人間が「面白くする」調整に集中する、という分業

---

## 4. Unity特有の構造的課題

### 4.1 MonoBehaviour / コンポーネント指向とテスタビリティ

**問題:**
MonoBehaviourは`new`でインスタンス化できず、Unityのライフサイクル（`Awake`, `Start`, `Update`）に依存するため、純粋な単体テストが書きにくい。

**対策:**
```
仕様 → テスト生成時のルール:
  1. ロジックはPure C#クラス(POCO)に分離
  2. MonoBehaviourはPOCOへの薄いアダプタとして実装
  3. POCOに対してEditModeテスト、MonoBehaviourに対してPlayModeテスト
```

仕様にこのアーキテクチャパターンを含めることで、AIが自動的にテスタブルなコードを生成するよう誘導できる。

### 4.2 シリアライズフィールド / Inspectorの値

**問題:**
Unityの多くの設定はInspectorでシリアライズされた値として保持される。これはコードではなく `.scene` や `.prefab` ファイル（YAML形式）に含まれるため、テストでの検証が特殊。

**対策:**
- `script-execute`でランタイムにGetComponentしてフィールド値を検証
- Prefabのバリデーションテスト: 「PlayerPrefabにはRigidbodyが必ず付いている」等
- Unity MCPの`manage_components` → `get`で設定値を取得・検証

### 4.3 アセットパイプラインの非決定性

**問題:**
テクスチャのインポート設定、モデルのインポート、アセットバンドルビルドなどは、仕様化はできても結果の自動検証が難しい。

**対策:**
- インポート設定の仕様化と、設定値の一致確認テスト
- ビルドパイプラインの出力（サイズ、含まれるアセット一覧）の検証

---

## 5. 推奨アーキテクチャ: 3層仕様モデル

Unity仕様駆動開発を実践するなら、仕様を3層に分けて管理することを推奨する。

```
┌─────────────────────────────────────────────┐
│  Layer 1: Fully Testable Specs              │
│  (テスト完全自動化可能)                        │
│                                              │
│  - ゲームロジック / 計算                       │
│  - ステートマシン / 状態遷移                    │
│  - データスキーマ / バリデーション               │
│  - イベントシステム / メッセージング             │
│                                              │
│  → YAML/JSON仕様 → NUnitテスト自動生成         │
│  → run_tests で自動検証                       │
├─────────────────────────────────────────────┤
│  Layer 2: Partially Testable Specs           │
│  (制約・数値のみテスト可能)                     │
│                                              │
│  - 物理挙動（範囲で検証）                       │
│  - UI配置（座標・anchor検証）                   │
│  - AI行動（統計的検証）                         │
│  - パフォーマンス（FPS, メモリ閾値）             │
│                                              │
│  → YAML仕様(testable + non_testable分離)      │
│  → PlayModeテスト + screenshot + 人間レビュー   │
├─────────────────────────────────────────────┤
│  Layer 3: Non-Testable Specs                 │
│  (人間の判断が必要)                            │
│                                              │
│  - ビジュアル品質 / アートディレクション          │
│  - ゲームフィール / 操作感                      │
│  - レベルデザインの面白さ                       │
│  - サウンドの印象                              │
│                                              │
│  → リファレンス資料 + スタイルガイド             │
│  → AIは作業補助、人間が判断                     │
└─────────────────────────────────────────────┘
```

---

## 6. 具体的なワークフロー

```
仕様(YAML/JSON)
    │
    ├──→ タスク生成（AIが実装タスクを分解）
    │
    ├──→ テスト生成（Layer1: 完全自動, Layer2: 制約テスト）
    │         │
    │         ▼
    │    Unity TestRunner (EditMode/PlayMode)
    │
    ├──→ コード生成（AIがC#スクリプトを生成）
    │         │
    │         ▼
    │    Unity MCP: manage_script → recompile → run_tests
    │         │
    │         ├── テスト通過 → 次のタスクへ
    │         └── テスト失敗 → read_console → AIが修正 → 再テスト
    │
    └──→ シーン構築（AIがMCPでGameObject/Prefab配置）
              │
              ▼
         screenshot → Layer2/3の人間レビュー
```

Unity MCPの `run_tests` → `read_console` → `manage_script` のループにより、Layer 1の仕様については完全自動のTDDサイクルがAIだけで回せるのが最大のポイント。

---

## 7. まとめ

| 観点 | 評価 |
|---|---|
| 仕様→テスト→検証ループ | Layer1（純粋ロジック）では完全に機能する。Unity MCPの`run_tests`が決定的 |
| AIによるコード生成の制御 | テスト可能な仕様があれば高精度。MonoBehaviour分離パターンの仕様化が鍵 |
| 最大の障壁 | ゲーム開発の価値の核心（ゲームフィール、面白さ）がLayer3に属すること |
| Unity MCPの貢献 | テスト実行・コンソール読み取り・スクリーンショットにより、従来不可能だったエディタ内検証ループをAIが自律的に回せるようになった |
| 実践的な戦略 | 仕様駆動で「正しく動く骨格」を高速構築し、人間は「面白くする」ことに集中する分業体制 |
