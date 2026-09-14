# Rank-1 herd gate

- state: day 6, hour 0
- classified games: 253

- full-data price-sign accuracy: 85/253 (33.6%)

## Depth 1

- five-fold accuracy: 227/253 (89.7%)

```text
if yarn_stores <= 0.50:
  => cow-heavy (n=190, {'cow-heavy': 166, 'sheep-heavy': 24})
else:
  => sheep-heavy (n=63, {'sheep-heavy': 61, 'cow-heavy': 2})
```

## Depth 2

- five-fold accuracy: 227/253 (89.7%)

```text
if yarn_stores <= 0.50:
  if milk_wool_spread <= -25.00:
    => cow-heavy (n=106, {'sheep-heavy': 20, 'cow-heavy': 86})
  else:
    => cow-heavy (n=84, {'cow-heavy': 80, 'sheep-heavy': 4})
else:
  if price_wheat <= 22.50:
    => sheep-heavy (n=10, {'sheep-heavy': 8, 'cow-heavy': 2})
  else:
    => sheep-heavy (n=53, {'sheep-heavy': 53})
```

## Depth 3

- five-fold accuracy: 227/253 (89.7%)

```text
if yarn_stores <= 0.50:
  if milk_wool_spread <= -25.00:
    if money <= 793.50:
      => cow-heavy (n=83, {'sheep-heavy': 20, 'cow-heavy': 63})
    else:
      => cow-heavy (n=23, {'cow-heavy': 23})
  else:
    if seat <= 0.50:
      => cow-heavy (n=44, {'cow-heavy': 44})
    else:
      => cow-heavy (n=40, {'cow-heavy': 36, 'sheep-heavy': 4})
else:
  if price_wheat <= 22.50:
    => sheep-heavy (n=10, {'sheep-heavy': 8, 'cow-heavy': 2})
  else:
    => sheep-heavy (n=53, {'sheep-heavy': 53})
```
