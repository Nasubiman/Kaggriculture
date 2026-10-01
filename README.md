# Kaggriculture エージェント（チーム nasubiman）

Kaggle のシミュレーションコンペ **Kaggriculture**（2026 年、10,204 チーム）に出したエージェントと、
その改良に使った評価ツールです。2 人対戦の農場経営ゲームで、30 日（720 手）の終わりに所持金が多いほうが勝ちです。
作物と動物を育て、2 人で共有する市場に売ります。売るほど値段が下がるので、相手と同じものを同じ時期に売ると値を下げ合います。

## 結果

| 提出 | ファイル | 提出時刻（UTC） | 備考 |
|---|---|---|---|
| 56720443 | [`submissions/ahd27s2.py`](submissions/ahd27s2.py) | 2026-09-30 22:40 | 最終版 |
| 56707260 | [`submissions/d23a.py`](submissions/d23a.py) | 2026-09-30 12:24 | 1974（22:40 時点） |

最終順位は、締切後の対戦（10 月中旬まで）でレートが収束してから確定します。
ahd27s2 は直接対戦で d23a に 62 勝 4 分 14 敗、その前の提出（sh24_bfFW）に 64 勝 16 敗でした。

## 方針

レート 2000 前後の対戦相手の大半は、公開エージェント **results31** とその改造版でした。
そのため、results31 を土台にして、**ほぼ同じ動きの相手に僅差で勝つ**ことに集中しました。

results31 は、作業手順を事前に計算した 41 本の「台本」（各 719 手）を、状況に応じた修正層で包んだ構成です。
私たちの変更は次の 3 種類だけで、台本そのものには手を入れていません。

- 定数の調整
- ファイルの末尾に足した小さな「包み関数」（Kaggle はファイルの最後の関数を呼ぶので、各関数は直前の関数を包みます）
- results31 に入っていて無効だった層の有効化

改良の候補は、主に次の 3 つの方法で見つけました。

- 実戦で僅差で負けた試合の再現
- 同じ系統の上位チームの記録から、複数チームに共通する変更を探す
- ゲームのルール上の無駄を探す

## 改良の系譜

各段階は、直前の版に変更を 1 つずつ加えたものです（[`agents/lineage/`](agents/lineage/)）。

| # | 版 | 変更 |
|---|---|---|
| 0 | [results31](agents/results31.py) | 公開エージェント（土台） |
| 1 | sr24 | 夜の自動収納で小屋が溢れる前に先に売る層の余裕を、8 個から 24 個に（`_SR_MARGIN`） |
| 2 | h12 | その先売りを、21〜23 時だけでなく 12 時から行う（`_SR_HOURS`） |
| 3 | ch95 | 動物の生産が上限で無駄になる前に収穫する層の制限（小屋＋持ち物の上限）を、90 から 95 に（`_CH_SHED`） |
| 4 | cx8000 | トマトを始める見込み収入の基準を 9000 から 8000 に下げ、早めに始める（`_CXTB_MIN_REVENUE`） |
| 5 | sh24 | 注文枠が満杯のとき、相手とぶつかりやすい品目の売りを最大 24 手先から前倒しする（`_OR2_SLOT_H`、元は 6 手） |
| 6 | sh24_bfFW | 肥料・小麦の購入を、ほかの注文より先に並べる（同じ手番の相手より安く買える） |
| 7 | sh48 | 前倒しの範囲を 48 手に |
| 8 | sh48snk5 | 相手が同じ品目を 5 個以上売れそうなら、24 手以内に売る予定の分を今売る（`_OR2_SN_K`） |
| 9 | sncar | 「今売る」の対象に人参を追加 |
| 10 | **d23a** | 23 日目 23 時の肥料と小麦の買いすぎを削る（3 チームが独立に入れていた変更） |
| 11 | rgds_a | results31 で無効だった層を有効化：`room_guard`（23 時に溢れる分を先に売る）と `dead_stock`（最終日は届いた品物をすぐ売る） |
| 12 | ahd27 | 23 時に溢れそうなら、翌日に回しても損しない収穫（動物・苺）を見送る |
| 13 | **ahd27s2** | 店の組み合わせで台本を選ぶ表のうち、一貫して負けていた 6 か所を別の台本に差し替える |

各段階で実際に変えたコードは [`docs/changes.md`](docs/changes.md) で差分として読めます。
各段階の中身・評価の数字・試してだめだった案は [`docs/final_report.md`](docs/final_report.md) にまとめています。

## 評価の方法

- **ミラー対戦**（[`scripts/evaluate_agent_lc.py`](scripts/evaluate_agent_lc.py)）：results31 や過去の版と、決まったシードで両方の席を入れ替えて対戦させます。
- **テープ評価**（[`scripts/evaluate_vs_replay_tapes.py`](scripts/evaluate_vs_replay_tapes.py)）：実際の試合の相手の行動記録を再生し、それに対して候補を戦わせます。
  - 自分たちの試合なら結果を完全に再現できるので、実戦で負けた試合を「この変更で逆転できるか」確かめられます。
- **系統の判定**（[`scripts/classify_mirror_replays.py`](scripts/classify_mirror_replays.py)）：公開試合の記録に results31 を当てはめて、1 手ずつ比べます。
  - 同じ系統のプレイヤーかどうかと、どこで動きが分かれたかが分かります。
  - 分かれ方を集計すると、複数チームに共通する改良が見つかります。

## 構成

```
submissions/         最終提出の 2 件
agents/results31.py  土台の公開エージェント
agents/lineage/      results31 から最終版までの 13 段階
scripts/             評価・分析・派生版の生成
sim/                 テープ評価が使う高速なゲーム実行（公式のゲーム処理を直接呼ぶ）
docs/                各段階の差分（changes.md）と、経緯と根拠の詳細（final_report.md）
```

エージェントのファイルは台本のデータを埋め込んでいるため 1 本約 1.2MB あり、GitHub の画面では中身が表示されません（「View raw」で開けます）。

## 使い方

Python 3.11 以上が必要です。公開試合の記録を取得するスクリプトは Kaggle の認証が必要です（`kaggle auth login`、または [`.env.example`](.env.example) を参照）。

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

最終版と results31 を、シード 1 つ・両方の席で対戦させます（約 20 秒）。

```bash
.venv/bin/python scripts/evaluate_agent_lc.py --agent submissions/ahd27s2.py --opponents agents/results31.py --seeds 13700000
```

公開試合の記録（`kaggle competitions replay <episode_id> --path replays`）に対して評価します。

```bash
.venv/bin/python scripts/evaluate_vs_replay_tapes.py --replays "replays/episode-*-replay.json" --force-money --candidates submissions/ahd27s2.py --output-dir results/tapes
```

1 手あたりの計算時間を測ります（平均 2〜4 ms、最大 0.4 秒程度）。

```bash
.venv/bin/python scripts/timing.py submissions/ahd27s2.py
```

系譜の各段階は、`scripts/make_*_variants.py` で直前の版から作り直せます。
例えば ahd27 は、次のコマンドで rgds_a からバイト単位で同じものが作れます。

```bash
.venv/bin/python scripts/make_harvest_defer_variants.py --base agents/lineage/11_rgds_a.py --out-dir results/variants "ahd27=27:0"
```

## クレジット

土台の results31 は Kaggle で公開されているエージェントです（thomastschinkel, yhay81, destbreso, aurax7, tetsutani,
prvsiyan, Dmitrii Gluzdov, Ahmed Berat Ozer ほか、Apache License 2.0）。
各エージェントファイルの冒頭に、ライセンス全文と帰属の表記をそのまま残しています。
`sim/` は、kaggle-environments 1.32.7 の公式のゲーム処理を直接呼び出し、検証やリプレイ保存などの処理を省いて速くした実行器です（結果は公式と同じです）。

## 過去の実験

この形に整理する前の作業環境は、タグ [`archive-20261001`](https://github.com/Nasubiman/Kaggriculture/tree/archive-20261001) に残しています。
そこには、強化学習・遺伝的探索・4 区画戦略・独自シミュレーターなどの試行、約 1,200 本の候補、評価結果が含まれます。
