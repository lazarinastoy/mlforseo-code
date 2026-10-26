#!/usr/bin/env python3
"""Split a labelled query file (yours, or the course's test set) into a training share and a held-out share.

    python3 split_external.py --data "/path/to/Test Dataset and Results.xlsx" --train-share 0.3 --out out/

Reads the first sheet of an .xlsx, or a .csv. The query column is the first of keyword / query / search term,
and the label column the first of type / label / class (values such as User, Synthetic, human, AI, 0/1).

Template-made synthetic queries are near-copies of each other ("best padded harness for senior dogs under
{N} dollars in {YEAR}"), so a random split would put siblings on both sides and flatter the held-out score.
Synthetic rows are therefore grouped by template family (the first words of their word skeleton, with
names, numbers and rare words masked) and whole families go to one side. User rows are split one by one.

Writes <out>/external_train.csv and <out>/external_test.csv (query, label, source, group). Nothing is
written into the repository unless you point --out there: keep real search data out of git.
"""
import argparse
import collections
import csv
import os
import random
import re

QUERY_NAMES = ["keyword", "keywords", "query", "queries", "search term", "search query", "term"]
LABEL_NAMES = ["type", "label", "class", "category", "source", "is_synthetic", "y", "target"]


def map_label(v):
    s = str(v or "").strip().lower()
    if not s:
        return None
    if re.fullmatch(r"1|1\.0|true|yes|synthetic|synth|ai|llm|generated", s):
        return 1
    if re.fullmatch(r"0|0\.0|false|no|user|human|real|organic", s):
        return 0
    if re.search(r"(^|[^a-z])(user|human|real|organic|people|person)([^a-z]|$)", s):
        return 0
    if re.search(r"synthetic|llm|(^|[^a-z])ai([^a-z]|$)|gpt|generated|fan-?out|model", s):
        return 1
    return None


def read_rows(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = [["" if v is None else str(v) for v in r] for r in wb.worksheets[0].iter_rows(values_only=True)]
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    head = [h.strip().lower() for h in rows[0]]
    qi = next(head.index(n) for n in QUERY_NAMES if n in head)
    li = next(head.index(n) for n in LABEL_NAMES if n in head)
    out = []
    for r in rows[1:]:
        if len(r) <= max(qi, li):
            continue
        q, lab = r[qi].strip(), map_label(r[li])
        if q and lab is not None:
            out.append((q, lab))
    return out


TOK = re.compile(r"[A-Za-z0-9'-]+")


def families(synthetic):
    """Template family per synthetic query: skeleton of frequent words, names/numbers masked, first 4 slots."""
    df = collections.Counter(w.lower() for q in synthetic for w in set(TOK.findall(q)))
    frequent = {w for w, c in df.items() if c / max(len(synthetic), 1) > 0.02}
    fam = {}
    for q in synthetic:
        out = []
        for w in TOK.findall(q):
            keep = w.lower() in frequent and not w[0].isupper() and not w[0].isdigit()
            t = w.lower() if keep else "_"
            if not (t == "_" and out and out[-1] == "_"):
                out.append(t)
        fam[q] = " ".join(out[:4])
    return fam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--train-share", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    rows = read_rows(args.data)
    rnd = random.Random(args.seed)
    syn = [q for q, l in rows if l == 1]
    fam = families(syn)
    groups = sorted(set(fam.values()))
    rnd.shuffle(groups)
    target, taken, train_fams = args.train_share * len(syn), 0, set()
    sizes = collections.Counter(fam.values())
    for g in groups:
        if taken >= target:
            break
        train_fams.add(g)
        taken += sizes[g]
    users = [q for q, l in rows if l == 0]
    rnd.shuffle(users)
    train_users = set(users[:round(args.train_share * len(users))])
    os.makedirs(args.out, exist_ok=True)
    counts = collections.Counter()
    with open(os.path.join(args.out, "external_train.csv"), "w", newline="", encoding="utf-8") as ftr, \
         open(os.path.join(args.out, "external_test.csv"), "w", newline="", encoding="utf-8") as fte:
        wtr, wte = csv.writer(ftr), csv.writer(fte)
        for w in (wtr, wte):
            w.writerow(["query", "label", "source", "group"])
        for q, l in rows:
            g = ("fam:" + fam[q]) if l == 1 else "user"
            is_train = (fam[q] in train_fams) if l == 1 else (q in train_users)
            (wtr if is_train else wte).writerow([q, l, "external", g])
            counts[("train" if is_train else "test", l)] += 1
    print(f"{len(rows)} labelled rows, {len(groups)} synthetic template families")
    print(f"train: {counts[('train', 1)]} synthetic + {counts[('train', 0)]} user;"
          f" held out: {counts[('test', 1)]} synthetic + {counts[('test', 0)]} user -> {args.out}")


if __name__ == "__main__":
    main()
