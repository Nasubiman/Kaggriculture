# Kaggriculture 1位データ分析キット

このZIPだけで、Kaggricultureのルールを知らない人でも、公開された1位
`Majkel1337`（submission id `56156662`）の255試合・183,345局面を分析できます。
追加ダウンロードやKaggle APIキーは不要です。

## 最初に読む順番

1. `GAME_RULES.md` — ゲームの目的、作物、家畜、行動、市場、ターン処理
2. `DATA_DICTIONARY_JA.md` — ファイルと各フィールドの意味
3. `reports/rank1_reactive_rules_20260914.md` — 既に確認できた行動規則
4. `reports/rank1_full_20260914_conditions.md` — 市場・店舗条件による行動差
5. `reports/rank1_full_20260914_branching.md` — 同じような局面で行動が分岐する場所

## まず動かす

Python 3.9以上だけで動き、追加ライブラリは不要です。ZIPを展開した
ディレクトリで次を実行してください。

```bash
python3 scripts/quick_analysis.py
```

Windowsでは次でも構いません。

```powershell
py scripts/quick_analysis.py
```

`analysis_output/`に次が生成されます。

- `summary.md`: データ件数と主な行動頻度
- `actions_by_day.csv`: 日ごとの作業行動数
- `market_by_day.csv`: 日ごとの市場行動数
- `actors.csv`: farmer/hand番号ごとの担当傾向

同梱データが壊れていないか確認する場合:

```bash
python3 scripts/verify_data.py
```

## どちらのデータを使うか

### 最初の分析には compact

`data/rank1_compact_features_actions.jsonl.gz` は約18万行の要約済みデータです。
お金、家畜数、作物数、市場価格、位置、持ち物、実際の行動が1行に入っています。
Excelへ出す集計、決定木、条件分岐の発見にはまずこちらを使います。

### 新しい仮説の検証には full

`data/rank1_full_observations_actions.jsonl.gz` は、各局面の完全な観測と行動を
保持しています。盤面の座標、各タイルの水やり・給餌・収穫量などを使う分析は
こちらを使います。展開せず、Pythonの`gzip.open`で1行ずつ読んでください。

## 最重要: 行動と観測の対応

Kaggleの生リプレイでは、観測`steps[t]`を見て選ばれた行動が
`steps[t+1].action`に保存されます。`steps[t].action`と組み合わせると1ターンずれ、
誤ったルールを学習します。

同梱の2つの`.jsonl.gz`は、このずれを修正済みです。各行の`observation`または
`features`と`action`は正しく対応しています。

## 分析時の注意

- `day`と`hour`は0始まりです。`day=0`が初日、`hour=23`がその日の最終ターンです。
- `actor=0`はメインfarmer、`actor=1`以降は`hands`の順番です。
- 相関はルールとは限りません。たとえば牛が多い局面はゲーム後半にも偏ります。
- 公開対局なので対戦相手と乱数に選択バイアスがあります。
- 1位は目の前の作業を常に即実行するわけではありません。担当区域と巡回経路を
  保つため、実行可能な作業を一時的に見送ることがあります。
- 最終所持品は勝敗に加算されず、最終的な現金が報酬です。

## 典型的な研究手順

1. `compact`で「日・時刻・市場・店舗・家畜構成 → 行動」を集計する
2. 興味のある条件を絞る
3. `full`で該当局面の盤面・作業員位置・持ち物を見る
4. 直前後10〜30ターンも確認し、単発行動ではなく経路として解釈する
5. 複数試合で再現する規則だけを候補ルールにする

`sample/raw_replay_episode_107673304.json`は生リプレイ形式の見本です。
通常の分析は、位置合わせ済みデータを利用してください。

