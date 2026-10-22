# Topic modelling for SEO with LDA (2026 refresh)

Companion code for the MLforSEO guide **"Topic Modelling for SEO with LDA (Latent Dirichlet Allocation)"** by Lazarina Stoy. The guide merges the MLforSEO lesson write-up with Lazarina's 2021 deep dive "Topic Modelling: A Deep Dive into LDA, hybrid-LDA, and non-LDA Approaches".

The 2021 post pointed readers to third-party LDA tutorials and the no-code jsLDA web app. This notebook gives you the whole Python workflow in one place, on current libraries.

## What it does

`topic_modeling_lda.ipynb` is a Colab-ready notebook:

| Section | What you get | Library |
|---|---|---|
| 1. Load | Your crawl export (URL + body text + title) or a demo dataset | pandas, scikit-learn (demo) |
| 2. Clean | Tokens, bigrams, custom stopwords, topic-general word filtering (`filter_extremes`) | gensim |
| 3. Word cloud | Top-level view of the cleaned corpus | wordcloud |
| 4. Train | LDA with learned (`"auto"`) alpha and eta priors | gensim `LdaModel` |
| 5. Evaluate + tune | Held-out perplexity (computed correctly as `2 ** -bound`) and c_v coherence; grid over topics, alpha, eta | gensim `CoherenceModel` |
| 6. pyLDAvis | Interactive inter-topic map saved as HTML | pyLDAvis |
| 7. Page topics | Soft membership per page, dominant topic, top pages per topic | gensim |
| 8. Internal links | Topic-to-topic correlation heatmap and top-5 link candidates per page (Hellinger similarity of topic mixes) | numpy |
| 9. NMF | TF-IDF + NMF comparison, scored with the same coherence | scikit-learn |
| 10. Short text | The same pipeline on titles only vs full text | gensim, scikit-learn |
| 11. Export | CSVs (page topics, topic keywords, link candidates, tuning) + pyLDAvis HTML | pandas |

## Demo data

Six groups of the public 20 Newsgroups dataset (cars, space, graphics, guns politics, hockey, medicine): about 3,400 user-written posts, each with a body and a short subject line. It downloads automatically through scikit-learn. Set `USE_DEMO = False` to use your own crawl.

## Results on the demo (run 22 October 2026)

| Model | c_v coherence |
|---|---|
| LDA, full text (8 topics, tuned) | 0.66 to 0.68 |
| NMF, full text | 0.65 to 0.71 |
| LDA, titles only (avg 3.4 words) | 0.37 |
| NMF, titles only | 0.33 |

Coherence roughly halves on short text: the data-sparsity problem in one table. (Titles are de-duplicated; for the short-text rows every model is scored against the same full-text reference corpus.)

## Requirements

* Python 3.10+ (tested on 3.12.15, macOS; Colab runs 3.12)
* `gensim==4.4.0`, `pyLDAvis==3.4.1`, `scikit-learn==1.9.1`, `pandas==3.0.6`, `numpy==2.5.4`, `matplotlib`, `wordcloud==1.9.6`
* No API keys.

```bash
pip install -r requirements.txt
```

In Colab, uncomment the install line in the first code cell.

## Notes and gotchas (what changed since the 2021 tutorials)

* gensim 4 renamed and removed a few things older tutorials use (`gensim.models.wrappers.LdaMallet` is gone; `Phrases` now takes `connector_words`). The notebook uses the current API.
* `pyLDAvis.gensim` became `pyLDAvis.gensim_models` in pyLDAvis 3.x. With recent NumPy/SciPy, the default `mds="pcoa"` can crash with `TypeError: Object of type complex128 is not JSON serializable`; the notebook uses `mds="mmds"`.
* `log_perplexity()` returns a negative per-word bound, not perplexity. Perplexity is `2 ** (-bound)`.
* gensim trains LDA with online variational Bayes. For Gibbs sampling, use `tomotopy`.
* Machine Learning Mastery's "Linear Discriminant Analysis With Python" (linked in the 2021 post) is a different LDA: a supervised classifier, not a topic model.

## Licence
MIT (see the repository LICENSE).
