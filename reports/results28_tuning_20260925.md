# results28 ベースの先行販売チューニング（2026-09-25）

## 結論

`results (28).zip`（`test/results28_20260925`）を土台に、3定数を変更した
`candidates/r28_tuned_20260925/main.py` を作成した。未使用seed（9900000〜、30 seed×両座席）・全46相手の2,760局で **2,724勝・36敗（98.7%）**。
改良前の results28 は 2,611勝・95敗（94.6%）、現行 `main.py` はこの相手群に対して results28 より弱い。

| 定数 | results28 | 変更後 | 役割 |
| --- | ---: | ---: | --- |
| `_MP_H` | 8 | 40 | 10〜13時の先行販売で前倒しする売り予定のターン数 |
| `_DP_H` | 8 | 12 | 0〜2時の先行販売で前倒しする売り予定のターン数 |
| `V9_FERT_FIRST_DAY` | 14 | 10 | 若い小麦・人参への施肥を始める日 |

## なぜ results28 をベースにしたか

20 seed×両座席のリーグで、results28 は results11/13 を含むほぼ全相手に勝ち越した（results11/13 に 40/40、`main.py` 相当の experimental_fourq 系に 30/40）。現行 `main.py` は results11/13 に 2/40（平均 -13.0k）、results28 に 10/40 だった。results28 は `main.py` の古い版ではなく、V39＋v9 層から分岐して FLOWPX / DAWNPX / BUYDIP / MODELPX / SHIELD-MILK などを持つ別系統。

## 負け筋と対策

results28 の負けは4 seedに集中し、生産量は相手とほぼ同じだった。差は終盤の苺・卵の売却競争で、相手が価格回復時に20個前後をまとめて売り、results28 は毎時3個ずつ売って高値を先に取られていた。先行販売の幅を広げる定数が効いた。

## 探索の経過（探索用 seed 9700000〜、手強い8相手）

- 第1弾（1定数×36案）: `_MP_H=12`、`_DP_H=12` が有望。RACE・人参・家畜・CXD などはほぼ無効か悪化。
- 第2・3弾（組み合わせ）: `_MP_H=24〜48` と `_DP_H=12` が最良。時間帯の拡大は悪化。
- 第4弾（mp32_dp12 を基準に15案）: 改善は `_MP_H=40` と `V9_FERT_FIRST_DAY=10` のみ。定数調整としては頭打ち。

## 未使用seedでの検証（全46相手、2,760局）

| 案 | 勝 | 敗 | 平均得失点差 |
| --- | ---: | ---: | ---: |
| mp40_dp12_fert10（採用候補） | 2,724 | 36 | +3,827 |
| mp32_dp12 | 2,710 | 48 | +3,880 |
| mp24 | 2,670 | 90 | +4,000 |
| results28 | 2,611 | 95 | +4,041 |

残る取りこぼしは `main.py` 系列（incumbent_main 54/60、ca_margin15 56/60 など）と results20/23〜27（58/60）。平均得失点差がやや下がるのは、弱い相手にも早めに売るため。

通常版と高速版のシミュレータで4局の結果が完全一致した。Kaggle の読み込み器が選ぶ関数（`ig_agent`）は `kaggle_agent` と同一。`scripts/validate_submission.py` は関数名だけを見て失敗するが、results28 自体も同じ構造で提出済み。

## ツール

- `scripts/make_r28_variants.py`: 定数を置き換えた候補を生成する。
- `scripts/screen_variants.sh`: サーバーで候補を順番にリーグ評価する。
- `scripts/summarize_screen.py`, `scripts/summarize_league.py`: 同一局面での比較表を作る。
- 生データ: `server-results/r28var*_screen/`, `server-results/r28val_fresh/`。
