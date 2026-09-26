# Duplicate opponents removed from test/ (2026-09-25)

Each model below produced exactly the same result in every game as the kept model,
against both results28 and the tuned main.py (30 fresh seeds x both seats).

| Removed | Same behaviour as (kept in test/) |
| --- | --- |
| attack_roundtrip_first25, incumbent_roundtrip_first35, incumbent_v37_opening, results4_20260913, robust_seat_mix_v1 | public_v37 |
| results13_20260917 | results11_20260917 |
| results15_20260923 | results5_20260913 |
| results21_20260923 | results16_20260923 |
| results27_20260923 | results26_20260923 |

public_v31 and public_v36 also behave identically but both stay: Makefile search targets reference both.
Move a folder back into test/ to restore it.
