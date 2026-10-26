#!/bin/sh
# Rebuild the shipped ensemble from scratch and write it into the tool.
#   ./run_all.sh                                     generated queries only
#   ./run_all.sh "/path/to/Test Dataset and Results.xlsx"   plus 30% of a labelled file, 70% held out
# Set TOOL=/path/to/tool.html to train against another copy of the tool.
set -e
cd "$(dirname "$0")"
TOOL="${TOOL:-../../tools/synthetic-vs-user-generated-queries-classifier.html}"
DATA="$1"
python3 generate_training_set.py --out out/generic.csv
node features.mjs --tool "$TOOL" --in out/generic.csv --out out/generic.features.json
if [ -n "$DATA" ]; then
  python3 split_external.py --data "$DATA" --train-share 0.3 --out out
  node features.mjs --tool "$TOOL" --in out/external_train.csv --out out/external_train.features.json
  node features.mjs --tool "$TOOL" --in out/external_test.csv --out out/external_test.features.json
  python3 fit.py --train out/generic.features.json out/external_train.features.json --test out/external_test.features.json \
    --out out/model.json --note "Generated queries (Notebook 4's generator plus an extension) and 30% of a labelled test set, split by template family"
else
  python3 fit.py --train out/generic.features.json --out out/model.json --note "Generated queries (Notebook 4's generator plus an extension)"
fi
python3 embed_model.py --model out/model.json --tool "$TOOL"
if [ -n "$DATA" ]; then node evaluate.mjs --tool "$TOOL" --in out/external_test.csv; fi
