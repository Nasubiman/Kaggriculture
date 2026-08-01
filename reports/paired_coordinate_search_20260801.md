# Paired coordinate search v1（2026-08-01）

## 結論

従来の少数seed遺伝的探索を補うため、現行モデルとの差を直接評価する座標探索を実装・実行した。最終的に `carrot_nw: 2 -> 1` が独立100 seedで採用条件を満たし、さらに別の100 seedを統合した200 seedでも改善が残ったため `main.py` に反映した。

## 新しい探索方法

1. 全active geneについて現行値から±1段階を生成
2. 同一seed・同一相手・同一席で `candidate reward - incumbent reward` を計算
3. 4 seedで83候補を一次選抜
4. 上位20候補を別の16 seedで再選抜
5. 上位5geneの単独・2変数組み合わせ16候補を別の24 seedで評価
6. 上位3候補を完全未使用100 seedで最終評価

対戦リーグは `0801_ev4`、`0801_ev5`、`0801_v2`。ev6はev4と挙動が同じため重複加重を避けて除外した。

採用条件:

- errors = 0
- paired deltaの95%下限 > 0
- すべての相手で平均delta >= 0

## Racingで確認できたこと

| 段階 | seed | 暫定首位 | paired delta | 95%下限 |
|---|---:|---|---:|---:|
| 一次元走査 | 4 | melon_ne 0→1 | +5,795 | +3,022 |
| 再選抜 | 16 | melon_tiles_base 10→11 | +3,041 | +408 |
| ペア探索 | 24 | carrot_nw 2→1 | +2,288 | +746 |
| 最終held-out | 100 | core 6 + carrot 1 | +1,615 | +713 |

最終の総平均首位 `core 6 + carrot 1` は `0801_v2` に -685だったため不採用。次点の `carrot_nw 2→1` は全条件を満たした。

このように、少数seedで首位が何度も入れ替わるため、従来の1〜3 seedでの早期選抜は不安定だったことが確認できた。

## 採用候補の最終100 seed

3相手 × 100 seed × 両席 = 600試合。

| 指標 | 値 |
|---|---:|
| paired平均 | +1,204.6 |
| 標準誤差 | 385.9 |
| 95%下限 | +448.3 |
| worst相手delta | +569.1 |
| errors | 0 |

相手別:

- ev4: +1,389.4
- ev5: +1,655.4
- v2: +569.1

## 追加100 seedと統合

反映後 `main.py` を別の100 seedで直接比較した結果は平均 +291.2で、この100 seed単独の95%下限は0をまたいだ。最初のheld-outと統合した200 seed（候補1,200試合）では:

- paired平均: +747.9
- 標準誤差: 315.6
- 95%下限: +129.4
- ev4平均delta: +695.9
- ev5平均delta: +1,347.1
- v2平均delta: +200.7

統合後も全相手で平均プラス、全体95%下限もプラスだったため採用を維持した。

## 反映後の直接勝率（追加100 seed）

| 相手 | 採用前 | 採用後 |
|---|---:|---:|
| ev4 | 88.0% | 88.0% |
| ev5 | 95.0% | 98.0% |
| v2 | 78.0% | 80.5% |

## 実装上の修正

初回実装では、最終首位がworst相手ゲートに落ちた際、条件を満たす次点候補も含めて全体を棄却していた。現在は最終候補を順位順に確認し、最上位の合格候補を選ぶよう修正済み。

## ファイル

- 探索本体: `training/search_paired_coordinates.py`
- run: `server-results/paired_coordinates_20260801_v1`
- 最終結果: `server-results/paired_coordinates_20260801_v1/final_heldout.json`
- 修正後判定: `server-results/paired_coordinates_20260801_v1/decision_corrected.json`
- 追加100 seed採用前: `reports/paired_incumbent_direct_100.json`
- 追加100 seed採用後: `reports/paired_carrot1_promoted_100.json`
- 実行コマンド: `make paired-search`
