# cc-sdd × Unity 適合性分析・カスタマイズ計画

> cc-sdd: https://github.com/gotalab/cc-sdd
> 前提資料: [unity-sdd-analysis.md](unity-sdd-analysis.md), [unity-mcp-capabilities.md](unity-mcp-capabilities.md)

## 結論

**cc-sddのカスタマイズで対応可能。1から作る必要はない。**

cc-sddのコアアーキテクチャ（Requirements → Design → Tasks → TDD実装）は言語・フレームワーク非依存設計であり、Unity向けに必要なのは「テンプレート層とエージェントプロンプト層のカスタマイズ」＋「Unity固有のバリデーションコマンド1〜2個の追加」。

---

## 1. cc-sdd の構造概要

### コアワークフロー

```
Steering (プロジェクト記憶) → Spec Init → Requirements → Design → Tasks → Implementation
```

### コマンド体系

| コマンド | フェーズ | 機能 |
|---------|---------|------|
| `/kiro:steering` | Phase 0 | プロジェクトメモリの初期化/同期 |
| `/kiro:steering-custom` | Phase 0 | ドメイン固有ステアリング文書生成 |
| `/kiro:spec-init` | Phase 1 | 仕様ワークスペースの初期化 |
| `/kiro:spec-requirements` | Phase 1 | EARS形式の要件生成 |
| `/kiro:spec-design` | Phase 1 | 技術設計書の生成 |
| `/kiro:spec-tasks` | Phase 1 | 実装タスクの生成 |
| `/kiro:spec-impl` | Phase 2 | TDD方式での実装実行 |
| `/kiro:spec-status` | Phase 2 | 進捗・承認状態の確認 |
| `/kiro:spec-quick` | All | 全フェーズ一括実行 |
| `/kiro:validate-design` | QA | 設計品質レビュー（GO/NO-GO） |
| `/kiro:validate-gap` | QA | ギャップ分析 |
| `/kiro:validate-impl` | QA | 実装検証 |

### 仕様ファイル構成

各フィーチャーごとに `.kiro/specs/<feature>/` ディレクトリ:

| ファイル | 役割 |
|---------|------|
| `spec.json` | メタデータ（フェーズ状態、承認状態） |
| `requirements.md` | EARS形式の要件定義 |
| `research.md` | 調査ログ・設計判断の記録 |
| `design.md` | 技術設計書 |
| `tasks.md` | 実装タスク（チェックボックス付き） |

### カスタマイズレイヤー（5段階）

1. テンプレート/ルール（`.kiro/settings/templates/`, `.kiro/settings/rules/`）
2. ステアリング文書（`.kiro/steering/`）
3. エージェントプロンプト（`.claude/commands/kiro/`）
4. CLI設定（`--lang`, `--profile`, `--manifest`等）
5. マニフェスト（最低レベル、配布構造を定義）

---

## 2. そのまま使える部分

| cc-sddの機能 | Unity適用可否 |
|---|---|
| 仕様フォーマット (Markdown + JSON) | そのまま使える |
| EARS要件形式 | ゲームロジックの仕様記述に適合 |
| Requirements → Design → Tasks フロー | そのまま適用可能 |
| `spec.json` によるフェーズ管理 | 変更不要 |
| 人間承認ゲート | Layer3レビューに本質的に必要 |
| ステアリング（プロジェクトメモリ） | Unity技術スタック・規約の記述に使える |
| 並列タスク分析 `(P)` マーカー | そのまま使える |
| `--lang ja` 日本語対応 | そのまま使える |

---

## 3. カスタマイズが必要な部分

### レベル1: テンプレート書き換え（軽い変更）

#### 3.1 `.kiro/settings/rules/design-principles.md`

**現状:** TypeScript前提（`any`禁止、型安全の例がTS記法）

**変更内容:** C#/Unity設計原則に書き換え

```markdown
## Unity設計原則

### テスタビリティ
- ロジックはPure C#クラス(POCO)に分離し、MonoBehaviourは薄いアダプタに留める
- SerializeFieldの値に依存するロジックは、値を引数として受け取る設計にする
- Update()内に分岐ロジックを書かず、ステートマシンに委譲する

### アーキテクチャ
- staticなシングルトンを避け、ScriptableObjectまたはDIでの依存注入を使う
- イベント駆動を推奨: UnityEvent / C# event / ScriptableObject Event Channel
- コンポーネント間の直接参照を避け、インターフェース経由で疎結合にする

### Unity固有
- Awake()で自己初期化、Start()で他コンポーネント参照を取得
- Destroyは必ずnullチェックと併用
- Resources.Loadを避け、Addressables / AssetReferenceを使う
```

#### 3.2 `.kiro/settings/templates/specs/design.md`

**変更内容:** Testing Strategyセクションを3層テストモデルに拡張

```markdown
## Testing Strategy

### Layer 1: EditMode Tests (Pure Logic)
- 対象: 計算ロジック、ステートマシン、データバリデーション
- フレームワーク: NUnit (Unity Test Framework)
- POCOクラスに対してテスト。MonoBehaviour不要
- 完全自動検証: run_tests で実行

### Layer 2: PlayMode Tests (制約検証)
- 対象: 物理挙動の範囲検証、UI配置、コンポーネント連携
- 許容範囲付きアサーション (Assert.AreEqual with tolerance)
- screenshot-game-view による目視確認ポイントの明示

### Layer 3: Human Review (非テスト対象)
- 対象: ビジュアル品質、ゲームフィール、操作感
- レビュー方法とレビュー基準を記述
- スクリーンショットを添えて人間に提示
```

#### 3.3 `.kiro/settings/templates/specs/requirements.md`

**変更内容:** 各要件に Testability Level 分類を追加

```markdown
### Requirement X.X: [要件名]
- **Testability: Layer N (Fully Testable / Range-Testable / Human Review)**
- [EARS形式の要件記述]
- Acceptance Criteria: ...
- Non-testable aspects (Layer 2/3のみ): ...
```

#### 3.4 `.kiro/settings/rules/tasks-generation.md`

**変更内容:** Unity固有のタスク生成ルールを追加

```markdown
## Unity固有ルール

### Layer別タスク構成
- Layer1タスク: テストタスクを実装タスクの前に配置する（TDD必須）
- Layer2タスク: PlayModeテスト + スクリーンショット確認チェックポイントを含める
- Layer3タスク: 末尾に「人間レビュー」チェックポイントを必ず含める

### シーン構築とロジックの分離
- ロジック実装タスクとシーン構築タスクは別タスクとして分離する
- シーン構築タスクには使用するMCPツール (manage_gameobject等) を明記する

### Prefab / ScriptableObject
- Prefab作成タスクはシーン構築タスクの後、結合テストの前に配置する
- ScriptableObject定義タスクはデータ構造設計後、ロジック実装前に配置する
```

#### 3.5 ステアリング用テンプレート: `testing.md`

**現状:** テスト例がTypeScript/Jest風

**変更内容:** Unity Test Runner前提に書き換え

```markdown
## テスト方針

### テストフレームワーク
- Unity Test Framework (com.unity.test-framework)
- NUnit 3.x

### テストの配置
- EditModeテスト: Tests/EditMode/
- PlayModeテスト: Tests/PlayMode/

### テスト実行
- Unity MCP `run_tests` で実行
- CI: Unity Test Runner CLI (`-runTests -testPlatform EditMode`)

### テスト命名規約
- [メソッド名]_[条件]_[期待結果]
- 例: CalculateDamage_CriticalHit_Returns150PercentDamage
```

---

### レベル2: ステアリング文書の追加（中程度の変更）

`/kiro:steering-custom` で生成されるドメイン固有文書として以下を追加:

#### 3.6 `steering/unity-architecture.md` (新規)

```markdown
# Unityアーキテクチャ規約

## フォルダ構成
Assets/
  Scripts/
    Core/         # Pure C#ロジック (POCO) - Layer1テスト対象
    Components/   # MonoBehaviourアダプタ
    Data/         # ScriptableObject定義
    Events/       # イベントチャネル
    UI/           # UIコンポーネント
  Prefabs/
  Scenes/
  Tests/
    EditMode/     # Layer1テスト
    PlayMode/     # Layer2テスト

## MonoBehaviour分離パターン
- 全てのゲームロジックはCore/配下のPOCOクラスに実装
- MonoBehaviourはSerializeFieldの値をPOCOに渡すアダプタ
- これにより、ロジックの単体テストがnewだけで可能になる
```

#### 3.7 `steering/unity-mcp.md` (新規)

```markdown
# Unity MCP ツール使用ガイド

## 実装ループ
1. manage_script でテストファイル作成
2. run_tests で失敗を確認 (RED)
3. manage_script で実装コード作成
4. run_tests で成功を確認 (GREEN)
5. 失敗時: read_console でエラー詳細取得 → 修正 → 再テスト

## シーン構築
1. manage_gameobject で GameObject 作成
2. manage_components でコンポーネント追加・設定
3. manage_prefabs で Prefab 化
4. screenshot-game-view で結果確認

## バリデーション
1. run_tests で全テスト実行
2. manage_editor → play でPlayMode確認
3. screenshot-game-view でスクリーンショット取得
4. read_console でエラー/警告確認
```

---

### レベル3: エージェントプロンプトの拡張（重要な変更）

#### 3.8 `.claude/commands/kiro/spec-impl.md` の拡張

**これが最も重要なカスタマイズ。** 現在のspec-implエージェントは「Bashでテスト実行」を前提としているが、Unity MCPツールを使ったTDDループに拡張する必要がある。

追加すべきプロンプト内容:

```markdown
## Unity TDD実装ループ

### RED: テストを書く
1. 仕様のLayer1要件からNUnitテストを生成
2. Unity MCP `manage_script` でテストファイルを作成 (Tests/EditMode/ or Tests/PlayMode/)
3. Unity MCP `run_tests` で失敗を確認

### GREEN: 実装する
1. `manage_script` で実装コードを作成
2. `run_tests` でテスト通過を確認
3. 失敗時 → `read_console` でエラー詳細取得 → 修正 → 再テスト

### シーン構築 (Layer2/3の要件がある場合)
1. `manage_gameobject` / `manage_components` でシーン構築
2. `manage_prefabs` でPrefab化
3. `screenshot-game-view` でスクリーンショット取得
4. Layer2: 制約テスト結果を報告
5. Layer3: スクリーンショットを添えて人間レビューを要求

### Layer判定ルール
- Layer1要件: TDDサイクルを完全自動で回す。人間の介入なし
- Layer2要件: テスト可能な制約はテストで検証。非テスト部分はスクリーンショット + 報告
- Layer3要件: AIは作業を実行するが、結果の判断は人間に委ねる。必ずレビューポイントを設ける
```

#### 3.9 `.claude/commands/kiro/spec-requirements.md` の微修正

要件生成時に Testability Level の分類を必須にするプロンプト追加:

```markdown
## 追加ルール: Testability分類
各要件に以下のいずれかを付与すること:
- **Layer 1 (Fully Testable)**: 純粋ロジック。EditModeテストで完全検証可能
- **Layer 2 (Range-Testable)**: 制約・数値範囲のみテスト可能。非テスト部分を明記
- **Layer 3 (Human Review)**: テスト不可。レビュー方法と判断基準を明記
```

#### 3.10 `.claude/commands/kiro/spec-tasks.md` の微修正

タスク生成時の追加ルール:

```markdown
## 追加ルール: Unity固有タスク構成
- Layer1タスクは必ずテストタスクを先行させる(TDD)
- Layer3タスクは必ず末尾に「人間レビュー」チェックポイントを含める
- シーン構築タスクとロジック実装タスクは分離する
- シーン構築タスクには使用するUnity MCPツールを明記する
```

---

### レベル4: 新規コマンドの追加（1〜2個）

#### 3.11 `/kiro:validate-unity` (新規コマンド + エージェント)

Unity固有の包括的バリデーション。既存の`validate-impl`を補完する形で追加。

```markdown
## validate-unity エージェントの動作

1. run_tests で全テスト実行 (EditMode + PlayMode)
   - テスト結果をサマリとして報告
   - 失敗テストがあれば詳細（スタックトレース含む）を報告

2. read_console でエラー/警告を収集
   - コンパイルエラーがないか確認
   - ランタイム警告がないか確認

3. manage_editor → play → 一定時間後 → screenshot-game-view → stop
   - ゲームが起動・動作することを確認

4. 仕様のLayer2制約をスクリーンショット/ログと照合
   - 制約テスト結果を報告

5. Layer3項目のレビューチェックリストを生成して人間に提示
   - スクリーンショットを添付
   - 各Layer3要件について確認すべき点をリスト化
```

#### 3.12 `/kiro:scene-review` (オプション・新規)

シーン構築結果のスクリーンショットベースレビュー。Layer2/3のイテレーションを効率化する。

---

## 4. 1から作るべきではない理由

| 観点 | cc-sddカスタマイズ | 1から構築 |
|---|---|---|
| ワークフロー設計 | 実績のある設計をそのまま使える | 再発明が必要 |
| マルチエージェント対応 | 8エージェント対応済み | 各エージェントごとに実装 |
| フェーズ管理 (spec.json) | そのまま使える | 再実装 |
| 承認フロー | 実装済み | 再実装 |
| 多言語対応 | 日本語含め13言語対応済み | 再実装 |
| 上流の進化に追従 | cc-sddのアプデを取り込める | 独自メンテ |
| カスタマイズ工数 | テンプレート数ファイル + エージェント2-3ファイル | 全体設計から |

cc-sddの設計思想自体がUnityに適合しないのではなく、具体的なテンプレート内容がTypeScript/Webを前提としているだけなので、テンプレート差し替えで対応できる。

---

## 5. カスタマイズ作業一覧

| # | 対象 | レベル | 作業内容 |
|---|---|---|---|
| 1 | `design-principles.md` | テンプレート | C#/Unity設計原則に書き換え |
| 2 | `design.md` テンプレート | テンプレート | 3層テストモデル追加 |
| 3 | `requirements.md` テンプレート | テンプレート | Testability分類追加 |
| 4 | `tasks-generation.md` | ルール | Unity固有タスク生成ルール追加 |
| 5 | `testing.md` ステアリング | テンプレート | Unity Test Runner前提に書き換え |
| 6 | `unity-architecture.md` | ステアリング | 新規作成 |
| 7 | `unity-mcp.md` | ステアリング | 新規作成 |
| 8 | `spec-impl.md` | エージェント | Unity MCP TDDループ追加 |
| 9 | `spec-requirements.md` | エージェント | Testability分類必須化 |
| 10 | `spec-tasks.md` | エージェント | Layer別タスク生成ルール追加 |
| 11 | `validate-unity.md` | 新規コマンド | Unity包括バリデーション |
| 12 | `scene-review.md` | 新規コマンド | スクリーンショットレビュー（オプション） |

**合計: 約12ファイルの作成/修正**

---

## 6. 注意点・リスク

- cc-sddは活発に開発中のため、上流の変更でテンプレート構造が変わる可能性がある
- Unity MCP自体がpre.1（プレリリース）のため、ツール名やAPIが変更される可能性がある
- カスタマイズしたテンプレートは `npx cc-sdd@latest` の再実行で上書きされる可能性がある → `--overwrite skip` の活用、またはfork管理を検討
- `[McpTool]`によるカスタムツール追加でバリデーション自動化を強化できる余地がある
