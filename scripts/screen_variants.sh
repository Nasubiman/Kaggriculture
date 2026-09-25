#!/bin/sh
# Usage (on the server repo): scripts/screen_variants.sh <variant_dir> <out_dir> <seeds> <seed_start> <models...>
set -eu
dir=$1; out=$2; seeds=$3; start=$4; shift 4
mkdir -p "$out"
for f in "$dir"/*.py; do
  name=$(basename "$f" .py)
  [ -f "$out/$name.json" ] && continue
  OMP_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python scripts/evaluate_test_models.py \
    --candidate "$f" --models-dir test --models "$@" --seeds "$seeds" --seed-start "$start" \
    --workers 20 --output "$out/$name.json" > "$out/$name.log" 2>&1 || echo "fail $name"
  echo "done $name"
done
echo ALLDONE
