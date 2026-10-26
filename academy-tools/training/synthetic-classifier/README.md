# Training the ensemble in the Synthetic vs User-generated Queries Classifier

The tool (`../../tools/synthetic-vs-user-generated-queries-classifier.html`) ships four methods that mirror
the course notebooks. Three are fixed formulas. The fourth, the ensemble (Notebook 4), is a logistic
regression whose weights are trained here, offline, and written into the tool as a small JSON object.

Nothing in this folder contains anyone's search data. Labelled files are read from a path you pass in,
and everything generated goes to `out/`, which git ignores.

## Why a logistic regression instead of LightGBM

Notebook 4 uses gradient-boosted trees and SHAP to explain single predictions. In a browser, a linear model
on standardised features gives the same kind of explanation exactly: every prediction is the intercept plus
one push per feature, `coefficient x (value - mean) / scale`, in log-odds. The tool draws those pushes as
the "why this score" chart. It also trains in the browser in under a second, which the "Train on your
labels" panel uses.

Two weight sets ship: `base` (the 38 features that need no model download, from Notebooks 1 and 2) and
`emb` (those plus Notebook 4's 7 embedding features). The tool uses `emb` only when embeddings are on.

## One feature code path

The features are not reimplemented here. `lib/core.cjs` cuts the block between `==== CORE START ====` and
`==== CORE END ====` out of the tool's inline script and runs it in Node with the same compromise version
the page loads. Embeddings come from the same model and settings (Xenova/all-MiniLM-L6-v2, quantised q8
ONNX, mean pooling, L2-normalised) through transformers.js for Node. The page runs onnxruntime-web and
Node runs onnxruntime-node, so embedding-based scores differ slightly (on the course's test set the
embeddings method moved by 0.003 on average and the ensemble's label changed for 4 of 2,449 queries).

## Setup and run

```bash
npm install                       # compromise 14.19.0, @huggingface/transformers 3.8.1
pip install -r requirements.txt   # scikit-learn, numpy, openpyxl
./run_all.sh "/path/to/Test Dataset and Results.xlsx"   # or ./run_all.sh with no file
```

`run_all.sh` does these steps, which you can also run one by one:

| Step | Script | What it does |
|---|---|---|
| 1 | `generate_training_set.py` | Notebook 4's training-set generator, copied verbatim (270 synthetic, 143 unique user queries), plus an extension (below). Writes `out/generic.csv`. |
| 2 | `split_external.py` | Optional. Splits a labelled file 30/70. Synthetic rows are grouped by template family so near-copies never sit on both sides. |
| 3 | `features.mjs` | The tool's features for each CSV, with and without embeddings. |
| 4 | `fit.py` | StandardScaler + LogisticRegression (balanced classes) per weight set. C is chosen by grouped 5-fold CV (the strongest regularisation within 2% of the best log loss). Reports held-out metrics next to a word-count rule. |
| 5 | `embed_model.py` | Writes the weights between `MODEL-JSON-START` and `MODEL-JSON-END` in the tool. |
| 6 | `evaluate.mjs` | Scores a labelled CSV with every method, as the tool's Evaluate tab does. `--refs-from-labels` draws Notebook 3's references from the labels, as the notebook does. |

Then rebuild the pages: `python3 academy-tools/build/compose.py` from the repo root.

## Training data in the shipped model

* **Notebook 4's generator, verbatim**: 15 software and product topics, the patent's query types as
  templates, navigational, short, typo and conversational human queries (413 rows).
* **Extension** (written for this tool): 32 more topics in other verticals, three or more templates per
  patent type (canonicalization included), human queries that are also comparisons and questions, typos,
  and mixed capitalisation on both sides so capital letters alone cannot separate the classes. No pet or
  dog topics, so the course's dog-harness test set stays out of domain (1,254 rows).
* **30% of the course's labelled test set** (`Test Dataset and Results.xlsx`, 796 rows: 546 synthetic in
  whole template families, 250 user). Its user queries are real searches, which the generated data lacks.

## Held-out results (the other 70% of the test set: 1,653 rows, never used for training)

At threshold 0.5, then at the threshold with the best F1 (picked on these same rows, so optimistic).

| Method | Accuracy | Precision | Recall | F1 | Best F1 | AUC |
|---|---|---|---|---|---|---|
| Rule-based (Notebook 1) | 0.585 | 0.997 | 0.359 | 0.528 | 0.987 at 0.40 | 0.994 |
| Entity & linguistic (Notebook 2) | 0.355 | 1.000 | 0.001 | 0.002 | 0.923 at 0.22 | 0.924 |
| Embeddings (Notebook 3, default references) | 0.363 | 1.000 | 0.014 | 0.028 | 0.846 at 0.41 | 0.832 |
| Ensemble, 38 features | 0.976 | 0.992 | 0.970 | 0.981 | 0.983 at 0.39 | 0.997 |
| Ensemble, 45 features (with embeddings) | 0.968 | 0.991 | 0.959 | 0.975 | 0.980 at 0.29 | 0.997 |
| **Word count only** (6+ words, cut-off from training) | 0.971 | 0.957 | 1.000 | 0.978 | 0.986 at 7+ words | 0.998 |

Other training choices, same held-out rows (F1 at 0.5): Notebook 4's 413 generated rows alone 0.845
(0.897 with embeddings); generator plus extension, no test-set rows 0.937 (0.929), and 0.943 on all
2,449 rows.

**Read this before quoting any of it.** In the course's test set every synthetic query has 6 to 17 words
and every user query 2 to 9, the synthetic ones come from a few templates, and they carry capitalised brand
and breed names while the user queries are lower case. A single word-count cut-off scores F1 0.986, as well
as anything here. The scores show the methods can sort this list; they do not show they can tell a short,
lower-case generated query from a long human one. Use the tool to rank a list and check samples by eye.

## Retrain on your own labels

Either use "Train on your labels" in the tool (and export the weights JSON), or pass your file to
`run_all.sh`: its query column must be called keyword or query, and its label column type or label.
