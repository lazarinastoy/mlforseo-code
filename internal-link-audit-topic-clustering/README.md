# Internal link audit + topic clustering with machine learning (2026 refresh)

Companion code for the MLforSEO guide **"How to do an SEO internal link audit and topic clustering using machine learning"** by Lazarina Stoy (first published 2022 as a write-up of her BrightonSEO Spring 2022 talk; refreshed October 2026).

The 2022 version pointed to LDA/LSA tutorials, a no-code LDA web app and a Google Sheets template. This notebook replaces that workflow with modern sentence embeddings, so you can do the whole audit in one place.

## What it does

`internal_link_audit_topic_clustering.ipynb` (Colab-ready, free CPU runtime is fine):

| Section | What you get | How |
|---|---|---|
| 3. Load data | Pages + internal links from a Screaming Frog crawl, or a demo dataset (about 70 mlforseo.com posts via the WordPress REST API) | pandas, requests, BeautifulSoup |
| 4. Link audit metrics | Inlinks, unique inlinks, in-content inlinks, orphan pages, broken / nofollow / UTM-tagged internal links | pandas |
| 5. Anchor text analysis | Generic, branded, mixed, exact-title and descriptive anchors; anchor length; top bigrams/trigrams | rules + scikit-learn `CountVectorizer` |
| 6. Embeddings | One vector per page; relative similarity threshold; possible duplicate pages (cosine >= 0.95) | sentence-transformers (`BAAI/bge-small-en-v1.5`), or embeddings exported from Screaming Frog |
| 7. Topic clustering | Clusters (auto k-means by silhouette, agglomerative or HDBSCAN), c-TF-IDF cluster names, pillar candidates, a 2D t-SNE map | scikit-learn |
| 8. Bridge pages | Pages close to two clusters (inter-cluster link candidates) | cosine similarity to cluster centroids |
| 9. Link opportunities | Similar page pairs that aren't linked yet, prioritised (pillars and pages without in-content inlinks first), with an anchor phrase found in the source page's own text | numpy, regex |
| 10. Export | CSVs + PNG for your audit deliverable | pandas, matplotlib |

## Using your own crawl (Screaming Frog SEO Spider)

Custom extraction and crawls over 500 URLs need a paid licence.

1. **Content:** *Configuration > Custom > Custom Extraction*, click *Add*, choose *CSSPath* (or *XPath*), paste the selector for your main content area (or use the visual browser to click it), set it to *Extract Text*, name it. Crawl, then export the **Custom Extraction** tab. You need `Address` and your extractor column (for example `Content 1`). Add `Title 1` if you can.
2. **Links:** *Bulk Export > Links > All Inlinks*.
3. In the notebook set `DATA_SOURCE = "screaming_frog"` and the file and column names.

Optional: if you generate embeddings inside the SEO Spider (v22+, *Config > API Access > AI* plus *Config > Content > Embeddings*) and export them as a column, set `SF_EMBEDDINGS_COL` and the notebook uses those instead of computing its own.

## Requirements

* Python 3.9+ (tested locally on 3.9; Colab runs 3.11/3.12)
* `sentence-transformers>=3.0`, `scikit-learn>=1.3` (for the built-in HDBSCAN), `pandas>=2.0`, `numpy`, `requests`, `beautifulsoup4`, `matplotlib`
* No API keys. The embedding model (about 130 MB) downloads from Hugging Face on first run.

```bash
pip install -r requirements.txt
```

In Colab, the first code cell installs what's missing.

## Tested

22 October 2026, end to end on both inputs: the demo dataset (68 mlforseo.com posts, 377 in-content links) and a synthetic Screaming Frog export with the real *All Inlinks* column layout. Versions: sentence-transformers 5.1.2, scikit-learn 1.6.1, pandas 2.3.3, numpy 1.26.4, torch 2.8.0. Embedding 68 pages took about 4 seconds on a laptop CPU.

Example outputs from the demo run are in `example_outputs/` (18 clusters chosen automatically, 219 link suggestions, 3 duplicate post pairs).

## Notes and caveats

* **Similarity thresholds are relative.** Different embedding models score differently (bge-small rates almost every pair above 0.6; MiniLM rarely does), so link suggestions use a percentile of your own site's similarity distribution (`SIMILARITY_PERCENTILE = 90`).
* **The demo only sees in-content links** (the WordPress API returns the post body, not menus or footers), so its orphan count is "pages with no contextual links", not true orphans. A Screaming Frog crawl gives you every link and its *Link Position*.
* **Suggestions are a shortlist, not a to-do list.** Read them before you add anything.

## Files

* `internal_link_audit_topic_clustering.ipynb`: the notebook (outputs cleared)
* `requirements.txt`
* `example_outputs/`: cluster map, cluster summary, link opportunities and duplicates from the demo run
