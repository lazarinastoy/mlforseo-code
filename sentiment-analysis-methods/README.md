# Sentiment analysis methods, side by side

Companion code for the MLforSEO guide **"Sentiment Analysis: A Deep Dive Into the Theory, Methods, and Applications"** by Lazarina Stoy.

## What it does

`sentiment_analysis_methods.ipynb` runs every family of sentiment analysis method from the guide on the same text, benchmarks them, and then applies the best one to an SEO project.

| Section | What you get | Library / model |
|---|---|---|
| 1. Lexicon-based | Word-dictionary scores and labels | VADER, AFINN |
| 2. Classic machine learning | A TF-IDF + logistic regression classifier trained on ~45k labelled tweets | scikit-learn, TweetEval |
| 3. Deep learning | Context-aware labels with confidence | `cardiffnlp/twitter-roberta-base-sentiment-latest` (Hugging Face) |
| 4. Benchmark | Accuracy and macro-F1 of all methods on the same TweetEval test sample, plus a chart | scikit-learn |
| 5. Document vs sentence level | Per-sentence labels for a mixed review | transformer |
| 6. Google Cloud Natural Language API (optional) | Score and magnitude from API v1 and v2, side by side | REST |
| 7. Brand SERP sentiment | Sentiment of titles ranking for branded queries, bubble chart by position, negative-title list, domain breakdown | transformer, pandas, matplotlib |
| 8. Export | CSVs (auto-download in Colab) | pandas |

`example_serp_titles.csv` is a **fictional** brand ("Northwind Coffee", `.example` domains) so section 7 runs out of the box. Replace it with your own export: columns `keyword, position, title, url`.

## Results from the test run (22 October 2026)

TweetEval sentiment, random sample of 2,000 test tweets (`random_state=42`):

| Method | Accuracy | Macro-F1 |
|---|---|---|
| VADER (lexicon + rules) | 0.518 | 0.519 |
| AFINN (lexicon) | 0.534 | 0.531 |
| TF-IDF + logistic regression | 0.599 | 0.578 |
| RoBERTa (transformer) | 0.708 | 0.708 |

The RoBERTa model was fine-tuned on TweetEval's training split, so it has a home advantage here. Test on your own data before choosing.

## Requirements

* Python 3.9+ (tested locally on 3.9 with torch 2.8, transformers 4.57, datasets 4.5, scikit-learn 1.6; Colab runs 3.11/3.12)
* No API key needed except for section 6 (Google Cloud project with the Natural Language API and billing enabled; first 5,000 units a month are free)

```bash
pip install -r requirements.txt
```

In Colab, the first code cell installs what's missing. A GPU runtime speeds up sections 3–4 but isn't required (CPU: a few minutes for the 2,000-tweet benchmark).

## Files

* `sentiment_analysis_methods.ipynb`: the notebook (outputs cleared)
* `example_serp_titles.csv`: fictional SERP export for section 7
* `requirements.txt`
* `build_notebook.py`: regenerates the notebook from source (handy for edits and diffs)
