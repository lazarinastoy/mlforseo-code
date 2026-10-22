# Topic modelling for SEO with BERTopic (2026 refresh)

Companion code for the MLforSEO guide **"Topic Modelling for SEO with BERTopic"** by Lazarina Stoy. The guide merges the MLforSEO lesson write-up with Lazarina's 2021 article "8 Limitations of Topic Modelling Algorithms on Short Text", so Part B of this notebook is about short text.

## What it does

`topic_modeling_bertopic.ipynb` is a Colab-ready notebook:

| Section | What you get |
|---|---|
| **Part A: pages (full text)** | |
| 1. Load | Your crawl export or the demo dataset (same demo as the LDA notebook) |
| 2. Simplest run | `BERTopic(language="english", min_topic_size=10)` |
| 3. Build your own Lego | Pre-computed `all-MiniLM-L6-v2` embeddings, UMAP, HDBSCAN, `CountVectorizer`, `ClassTfidfTransformer(reduce_frequent_words=True)`, `KeyBERTInspired` representation |
| 4. Inspect + visualise | Topic info, topic map, bar chart, hierarchy (saved as HTML) |
| 5. Outliers + over-production | `reduce_outliers` + `update_topics`, `reduce_topics` |
| 6. Several topics per page | `approximate_distribution` (topic mix per page) |
| 7. Export | Page-level CSV with dominant topic + topic mix, topic info CSV |
| **Part B: short text** | |
| 8. Head to head | LDA vs NMF vs BERTopic on titles only, all scored with c_v coherence against the same reference corpus |
| 9. Topic-general words | Topic labels with and without `reduce_frequent_words` |
| 10. Human in the loop | Seed words (guided topic modelling), merging, custom topic labels |

## Results on the demo (run 22 October 2026)

Part A: 10 topics, 8% outliers before `reduce_outliers` and 0% after; 12% of posts have a second topic above 20% with `approximate_distribution`.

Part B, 1,373 de-duplicated titles averaging 3.6 content words:

| Model | Topics | c_v coherence | Unassigned |
|---|---|---|---|
| LDA | 8 (set) | 0.33 | 0% |
| NMF | 8 (set) | 0.41 | 0% |
| BERTopic | 7 (found) | 0.41 | 7% |

On titles alone, BERTopic matched NMF's coherence and beat LDA, found the topic count itself, and still left some titles unassigned. No model is good on three-word documents. That's the point of the article's limitations section.

## Requirements

* Python 3.10+ (BERTopic 0.17 needs 3.10; tested on 3.12.15, macOS, CPU only)
* `bertopic==0.17.4`, `sentence-transformers==6.2.0`, `umap-learn==0.5.12`, `hdbscan==0.8.44`, `scikit-learn==1.9.1`, `pandas==3.0.6`, `gensim==4.4.0` (Part B coherence only)
* No API keys. The embedding model (about 90 MB) downloads from Hugging Face on first run.

```bash
pip install -r requirements.txt
```

## Gotchas

* **`approximate_distribution` returns all zeros.** With `reduce_frequent_words=True`, c-TF-IDF similarities are small and the default `min_similarity=0.1` filters out every chunk. Use about `0.02` (at `0` the distributions go flat).
* **HDBSCAN settings decide the topic count.** On the demo, `min_cluster_size=15` merged graphics and space into one topic; `min_cluster_size=30, min_samples=5` gave 10 cleaner topics. Tune these for your data.
* **Pass `random_state` to UMAP** if you want the same topics on every run.
* **De-duplicate short texts** (duplicate page titles, thread replies) before modelling, or the duplicates form their own topics.
* `reduce_outliers` + `update_topics` should come after any manual topic changes; BERTopic warns you about this.

## Licence
MIT (see the repository LICENSE).
