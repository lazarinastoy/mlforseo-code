#!/usr/bin/env python3
"""Write a model from fit.py into the tool, between the MODEL-JSON markers of its inline script.

    python3 embed_model.py --model out/model.json [--tool ../../tools/synthetic-vs-user-generated-queries-classifier.html]

Only what the page needs goes in: the two weight sets and a short training and held-out summary.
"""
import argparse
import json
import pathlib
import re

DEFAULT_TOOL = pathlib.Path(__file__).resolve().parents[2] / "tools" / "synthetic-vs-user-generated-queries-classifier.html"


def compact(model):
    keep = {"version": model["version"], "created": model["created"], "note": model.get("note", ""),
            "trained_on": model["trained_on"], "sets": {}, "heldout": {}}
    for name, s in model["sets"].items():
        keep["sets"][name] = {k: s[k] for k in ("features", "mean", "scale", "coef", "intercept", "C")}
    for name, rep in model.get("report", {}).items():
        if name == "word_count_baseline":
            keep["heldout"]["word_count"] = {"k": rep["k_from_training"], "f1": round(rep["test"]["f1"], 4),
                                             "accuracy": round(rep["test"]["accuracy"], 4), "auc": round(rep["auc"], 4)}
        elif "test" in rep:
            t = rep["test"]
            keep["heldout"][name] = {"rows": t["rows"], "accuracy": round(t["at_0.5"]["accuracy"], 4),
                                     "precision": round(t["at_0.5"]["precision"], 4), "recall": round(t["at_0.5"]["recall"], 4),
                                     "f1": round(t["at_0.5"]["f1"], 4), "auc": round(t["auc"], 4)}
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tool", default=str(DEFAULT_TOOL))
    a = ap.parse_args()
    tool = pathlib.Path(a.tool)
    src = tool.read_text(encoding="utf-8")
    blob = json.dumps(compact(json.load(open(a.model))), separators=(",", ":"))
    new, n = re.subn(r"/\* MODEL-JSON-START \*/.*?/\* MODEL-JSON-END \*/",
                     lambda m: "/* MODEL-JSON-START */" + blob + "/* MODEL-JSON-END */", src, flags=re.S)
    if n != 1:
        raise SystemExit("MODEL-JSON markers not found exactly once in " + str(tool))
    tool.write_text(new, encoding="utf-8")
    print(f"wrote {len(blob):,} bytes of model JSON into {tool.name}")


if __name__ == "__main__":
    main()
