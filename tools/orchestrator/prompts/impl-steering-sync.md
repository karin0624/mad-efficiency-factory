
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## コアタスク

実装済みspecの内容に基づき、`.kiro/steering/` が最新であるかを検証し、必要に応じて更新する。

## 入力パラメータ

promptから以下を受け取る:
- `WORKTREE_PATH`: worktreeの絶対パス
- `FEATURE_NAMES`: 対象feature名（カンマ区切り対応）

## 実行手順

### 1. Spec読み込み

`FEATURE_NAMES` をカンマで分割し、各featureについて以下を読み込む:
- `{WORKTREE_PATH}/.kiro/specs/{feature}/requirements.md`
- `{WORKTREE_PATH}/.kiro/specs/{feature}/design.md`

### 2. Steering読み込み

`.kiro/steering/` 配下の全 `.md` ファイルを読み込む。

### 3. 差異検出

specの内容とsteeringの記述を比較し、以下の差異を検出:
- `product.md`: MVPスコープ、エンティティ定義、ゲームメカニクス
- `tech.md`: 技術選定、フレームワーク、ライブラリ
- `structure.md`: プロジェクト構成パターン、ディレクトリ構成
- その他のカスタムsteeringファイル: 該当する領域の差異

### 4. 差異なしの場合

差異が検出されない場合:
```
STEERING_SYNC_SKIPPED
```
と出力して終了。

### 5. 差異ありの場合

差異が検出された場合:
1. `.kiro/steering/steering-principles.md` を読み込み、steering更新の原則を確認
2. Edit toolを使用して該当するsteeringファイルを更新
3. specの記述が正（truth source）であり、steeringをspecに合わせる方向で更新する
4. steering更新は追加的な変更のみ（既存の無関係な記述は変更しない）

## 出力マーカー

更新完了時:
```
STEERING_SYNC_DONE
UPDATED_FILES: <更新したファイルのカンマ区切りリスト>
```

スキップ時:
```
STEERING_SYNC_SKIPPED
```
