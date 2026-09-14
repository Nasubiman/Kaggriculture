# Rank-1 herd gate

- state: day 10, hour 0
- classified games: 253

- full-data price-sign accuracy: 226/253 (89.3%)

## Depth 1

- five-fold accuracy: 244/253 (96.4%)

```text
if yarn_stores <= 0.50:
  => cow-heavy (n=167, {'cow-heavy': 163, 'sheep-heavy': 4})
else:
  => sheep-heavy (n=86, {'sheep-heavy': 81, 'cow-heavy': 5})
```

## Depth 2

- five-fold accuracy: 244/253 (96.4%)

```text
if yarn_stores <= 0.50:
  if opp_herd_spread <= 1.50:
    => cow-heavy (n=25, {'cow-heavy': 22, 'sheep-heavy': 3})
  else:
    => cow-heavy (n=142, {'cow-heavy': 141, 'sheep-heavy': 1})
else:
  if opp_cow <= 6.50:
    => sheep-heavy (n=57, {'sheep-heavy': 57})
  else:
    => sheep-heavy (n=29, {'sheep-heavy': 24, 'cow-heavy': 5})
```

## Depth 3

- five-fold accuracy: 244/253 (96.4%)

```text
if yarn_stores <= 0.50:
  if opp_herd_spread <= 1.50:
    if milk_wool_spread <= 37.00:
      => cow-heavy (n=13, {'cow-heavy': 10, 'sheep-heavy': 3})
    else:
      => cow-heavy (n=12, {'cow-heavy': 12})
  else:
    if milk_wool_spread <= 24.50:
      => cow-heavy (n=18, {'cow-heavy': 17, 'sheep-heavy': 1})
    else:
      => cow-heavy (n=124, {'cow-heavy': 124})
else:
  if opp_cow <= 6.50:
    => sheep-heavy (n=57, {'sheep-heavy': 57})
  else:
    if seat <= 0.50:
      => sheep-heavy (n=13, {'sheep-heavy': 8, 'cow-heavy': 5})
    else:
      => sheep-heavy (n=16, {'sheep-heavy': 16})
```
