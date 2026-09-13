# データ辞書

## 収録範囲

- チーム: `Majkel1337`
- submission id: `56156662`
- 公開対局: 255試合
- 観測・行動ペア: 183,345件（255 × 719）
- 1試合: 30日 × 24ターン = 720ターン
- 作成日: 2026-09-14

## JSONL.GZとは

1行が1個のJSONオブジェクトになったテキストをgzip圧縮した形式です。全体を
メモリへ読み込まず、次のように順番に処理できます。

```python
import gzip, json

with gzip.open("data/rank1_compact_features_actions.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        print(row)
        break
```

## compactファイル

1行の概略:

```text
episode, step, opponent, features, positions, inventories, action
```

- `episode`: Kaggleの対局ID
- `step`: 0〜718。この観測から次の行動が選ばれた
- `opponent`: 対戦相手名
- `positions`: `[farmer, hand1, hand2, ...]`。各位置は`[x,y]`
- `inventories`: positionsと同じ順の個人持ち物
- `action`: その観測に対して1位が選んだ行動

主な`features`:

- `day`, `hour`, `seat`: 日、日内時刻、player 0/1
- `money`: 1位の現金
- `hands`, `opp_hands`: 雇用作業員数
- `land`: 使用可能タイル数
- `pasture`, `cow`, `sheep`, `goose`: 畜産構成
- `*_tiles`: 作物ごとの植付け済みタイル数
- `shed_*`: 倉庫内の主要在庫
- `price_*`: 現在の市場価格
- `milk_wool_spread`: milk価格 − wool価格
- `opp_*`: 相手の公開盤面から数えた状態
- `shops`: 解放済み店舗数
- `yarn_stores`: Yarn Storeが解放済みなら1

## fullファイル

先頭行は`type="metadata"`です。以降は`type="example"`で、次を持ちます。

- `episode`, `step`, `seat`, `opponent`
- `observation`: その時点で1位が見ていた完全な観測
- `action`: その観測から選ばれた行動

`observation`の主要部分:

- `day`, `hour`, `player`
- `farms[0]`, `farms[1]`: 両者の公開農場
- `farms[*].tiles[y][x]`: 10×10盤面。`null`は空き、`LOCKED`は未購入地
- `farms[*].farmer`, `hands`: 作業員座標
- `market.prices`, `market.inventory`: 市場
- `town.unlocked_shops`: 解放済み店舗
- `private.shed`: 1位だけが見られる倉庫在庫
- `private.seeds`: 購入済み種
- `private.inventories`: farmerとhandsの持ち物

タイル辞書でよく使うフィールド:

- `kind`: `PLANT`, `PASTURE`, `COOP`, `WEED`
- `crop`: 作物名
- `animal`: `COW`, `SHEEP`, `GOOSE`
- `yield_units`: 現在収穫可能な量
- `watered_today`, `fed_today`, `cared_today`
- `fertilizer_available`: 家畜から肥料回収可能か
- `planted_day`, `placed_day`: 設置日

## action

```json
{
  "farmer": ["WATER"],
  "hands": [["NORTH"], ["FEED"]],
  "market": [["SELL", "MILK", 3], ["HIRE"]]
}
```

- `farmer`: メインfarmerの1行動
- `hands`: 各handの1行動。位置・inventoryと同じ順番
- `market`: 最大10件の順序付き市場注文

全行動の意味と合法条件は`GAME_RULES.md`を参照してください。

## その他のファイル

- `data/manifest.json`: 255対局のID、日時、元リプレイ名
- `data/games.csv`: 対局単位の要約
- `sample/raw_replay_*.json`: Kaggle生形式の1試合見本
- `reports/*.md`: 人間向けの既存分析
- `reports/*.json`: 同じ分析の機械可読集計

## 生リプレイの時系列

生リプレイだけは次の対応です。

```text
steps[t][seat].observation  ->  steps[t+1][seat].action
```

同梱のcompact/fullデータは修正済みなので、同じ行の観測と行動をそのまま使えます。

