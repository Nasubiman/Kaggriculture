# Test model round-robin

Each cell is the row model's result against the column model.
Every seed is played from both seats.

## Win rate

| model | public_v38_low_pressure_20260914 | public_v41_competitive_20260914 | public_v41_survival_20260914 | results5_20260913 | robust_seat_mix_v1 |
|---|---:|---:|---:|---:|---:|
| public_v38_low_pressure_20260914 | — | 4.5% | 4.5% | 100.0% | 93.0% |
| public_v41_competitive_20260914 | 95.5% | — | 10.5% | 100.0% | 95.5% |
| public_v41_survival_20260914 | 95.5% | 59.5% | — | 100.0% | 95.5% |
| results5_20260913 | 0.0% | 0.0% | 0.0% | — | 85.5% |
| robust_seat_mix_v1 | 7.0% | 4.5% | 4.5% | 14.5% | — |

## Mean margin

| model | public_v38_low_pressure_20260914 | public_v41_competitive_20260914 | public_v41_survival_20260914 | results5_20260913 | robust_seat_mix_v1 |
|---|---:|---:|---:|---:|---:|
| public_v38_low_pressure_20260914 | — | -413.2 | -419.4 | +25759.2 | +13639.5 |
| public_v41_competitive_20260914 | +413.2 | — | -6.3 | +26215.8 | +14054.2 |
| public_v41_survival_20260914 | +419.4 | +6.3 | — | +26210.6 | +14054.6 |
| results5_20260913 | -25759.2 | -26215.8 | -26210.6 | — | +885.4 |
| robust_seat_mix_v1 | -13639.5 | -14054.2 | -14054.6 | -885.4 | — |

## Overall

| model | games | win rate | mean reward | mean margin | errors |
|---|---:|---:|---:|---:|---:|
| public_v38_low_pressure_20260914 | 800 | 50.5% | 103880.0 | +9641.5 | 0 |
| public_v41_competitive_20260914 | 800 | 75.4% | 104299.9 | +10169.2 | 0 |
| public_v41_survival_20260914 | 800 | 87.6% | 104298.3 | +10172.7 | 0 |
| results5_20260913 | 800 | 21.4% | 91771.4 | -19325.0 | 0 |
| robust_seat_mix_v1 | 800 | 7.6% | 93025.1 | -10658.4 | 0 |
