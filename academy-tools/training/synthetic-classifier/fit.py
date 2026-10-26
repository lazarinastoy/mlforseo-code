#!/usr/bin/env python3
"""Fit the tool's ensemble: logistic regression on standardised Notebook 4 features, two weight sets.

    python3 fit.py --train out/generic.features.json [out/external_train.features.json ...] \
                   --test out/external_test.features.json --out out/model.json

* "base" uses the 38 features that need no embeddings (Notebooks 1 and 2); "emb" adds the 7 embedding
  features (Notebook 3). The tool uses "emb" when embeddings are switched on, "base" otherwise.
* C (inverse regularisation) is picked by grouped 5-fold cross-validation on the training rows, grouped by
  topic or template family, so the score rewards generalising to unseen topics rather than memorising one:
  the smallest C whose log loss is within 2% of the best.
* Classes are weighted to balance, so 0.5 means "as likely synthetic as not" whatever the list's mix.
* The model JSON holds, per set: feature names, StandardScaler mean and scale, coefficients, intercept,
  plus the training summary and held-out metrics. embed_model.py writes it into the tool.
"""
import argparse
import datetime
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

C_GRID = [0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


def load(paths):
    q, y, g, src, base, emb = [], [], [], [], [], []
    for p in paths:
        d = json.load(open(p))
        q += d["queries"]; y += d["labels"]; g += d["groups"]; src += d["sources"]
        base += d["base"]; emb += d["emb"] if d["emb"] else [[np.nan] * len(d["features_emb"])] * len(d["queries"])
        names_b, names_e = d["features_base"], d["features_emb"]
    base, emb = np.array(base, float), np.array(emb, float)
    return {"q": q, "y": np.array(y), "g": np.array(g), "src": np.array(src), "base": base,
            "emb": np.hstack([base, emb]), "names_base": names_b, "names_emb": names_b + names_e}


def fit_one(X, y, C):
    sc = StandardScaler().fit(X)
    lr = LogisticRegression(C=C, class_weight="balanced", max_iter=10000).fit(sc.transform(X), y)
    return sc, lr


def predict(sc, lr, X):
    return lr.predict_proba(sc.transform(X))[:, 1]


def pick_C(X, y, groups):
    n_groups = len(set(groups))
    cv = GroupKFold(n_splits=min(5, n_groups))
    scores = {}
    for C in C_GRID:
        ll, f1 = [], []
        for tr, va in cv.split(X, y, groups):
            sc, lr = fit_one(X[tr], y[tr], C)
            p = predict(sc, lr, X[va])
            ll.append(log_loss(y[va], np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1]))
            f1.append(f1_score(y[va], p >= 0.5, zero_division=0))
        scores[C] = (float(np.mean(ll)), float(np.mean(f1)))
    # the strongest regularisation whose log loss is within 2% of the best: nearly the same fit, but
    # smaller, steadier weights, which matters because the tool shows each weight's push to the user
    floor = min(v[0] for v in scores.values())
    best = min(c for c in C_GRID if scores[c][0] <= floor * 1.02)
    return best, scores


def metrics(y, p, thr=0.5):
    pred = p >= thr
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": round(float(thr), 4), "accuracy": (tp + tn) / len(y), "precision": prec, "recall": rec,
            "f1": f1, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def best_threshold(y, p):
    best = (-1, 0.5)
    for t in np.unique(p):
        f = metrics(y, p, t)["f1"]
        if f > best[0] + 1e-12:
            best = (f, t)
    return float(best[1])


def wordcount_rule(train_q, train_y, test_q, test_y):
    """Baseline: synthetic if the query has at least k words, k chosen on the training rows."""
    wc = lambda qs: np.array([len(q.split()) for q in qs], float)
    wtr, wte = wc(train_q), wc(test_q)
    k = max(range(1, 21), key=lambda k: metrics(train_y, (wtr >= k).astype(float), 0.5)["f1"])
    k_oracle = max(range(1, 21), key=lambda k: metrics(test_y, (wte >= k).astype(float), 0.5)["f1"])
    return {"k_from_training": k, "test": metrics(test_y, (wte >= k).astype(float), 0.5),
            "k_best_on_test": k_oracle, "test_at_best_k": metrics(test_y, (wte >= k_oracle).astype(float), 0.5),
            "auc": roc_auc_score(test_y, wte)}


def rnd(x, d=6):
    return float(f"{x:.{d}g}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--test", nargs="*", default=[])
    ap.add_argument("--out", default="out/model.json")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    tr = load(a.train)
    te = load(a.test) if a.test else None
    model = {"version": 1, "created": datetime.date.today().isoformat(), "note": a.note,
             "trained_on": {"rows": len(tr["y"]), "synthetic": int(tr["y"].sum()), "user": int((tr["y"] == 0).sum()),
                            "by_source": {s: int((tr["src"] == s).sum()) for s in sorted(set(tr["src"]))}},
             "sets": {}, "report": {}}
    for name in ("base", "emb"):
        X, names = tr[name], tr["names_" + name]
        if np.isnan(X).any():
            print(f"skip {name}: missing embedding features")
            continue
        C, cv_scores = pick_C(X, tr["y"], tr["g"])
        sc, lr = fit_one(X, tr["y"], C)
        model["sets"][name] = {"features": names, "mean": [rnd(v) for v in sc.mean_], "scale": [rnd(v) for v in sc.scale_],
                               "coef": [rnd(v) for v in lr.coef_[0]], "intercept": rnd(float(lr.intercept_[0])), "C": C}
        rep = {"C": C, "cv": {str(c): {"log_loss": round(v[0], 4), "f1_at_0.5": round(v[1], 4)} for c, v in cv_scores.items()}}
        if te is not None:
            p = predict(sc, lr, te[name])
            bt = best_threshold(te["y"], p)
            rep["test"] = {"rows": len(te["y"]), "at_0.5": metrics(te["y"], p), "best_threshold": bt,
                           "at_best": metrics(te["y"], p, bt), "auc": roc_auc_score(te["y"], p)}
        model["report"][name] = rep
        top = sorted(zip(names, lr.coef_[0]), key=lambda t: -abs(t[1]))[:8]
        print(f"[{name}] C={C}  top weights: " + ", ".join(f"{n} {w:+.2f}" for n, w in top))
        if te is not None:
            r = rep["test"]
            print(f"   held-out ({r['rows']}): acc {r['at_0.5']['accuracy']:.3f} P {r['at_0.5']['precision']:.3f} "
                  f"R {r['at_0.5']['recall']:.3f} F1 {r['at_0.5']['f1']:.3f} AUC {r['auc']:.3f} | best thr {bt:.3f} F1 {r['at_best']['f1']:.3f}")
    if te is not None:
        model["report"]["word_count_baseline"] = wordcount_rule(tr["q"], tr["y"], te["q"], te["y"])
        w = model["report"]["word_count_baseline"]
        print(f"   word count >= {w['k_from_training']} (k from training): F1 {w['test']['f1']:.3f} acc {w['test']['accuracy']:.3f};"
              f" best k on held-out = {w['k_best_on_test']}: F1 {w['test_at_best_k']['f1']:.3f} acc {w['test_at_best_k']['accuracy']:.3f}; AUC {w['auc']:.3f}")
    json.dump(model, open(a.out, "w"), indent=1)
    print("->", a.out)


if __name__ == "__main__":
    main()
