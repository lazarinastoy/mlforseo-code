# Free keyword clustering tool: SERP overlap + embeddings hybrid

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/keyword-clustering-serp-embeddings/keyword_clustering.ipynb)

A free alternative to paid keyword clustering tools, by **Lazarina Stoy, [MLforSEO](https://www.mlforseo.com/)**. It clusters a keyword list three ways and exports a keyword map you can open in Google Sheets.

## What it does

`keyword_clustering.ipynb` is a Colab-ready notebook:

| Section | What you get |
|---|---|
| 1. Settings and data | Load your keyword CSV (and optional SERP export), or the synthetic sample |
| 2. Embeddings clustering | `all-MiniLM-L6-v2` sentence embeddings + agglomerative clustering with a distance threshold (HDBSCAN as an alternative). Free, no SERP data needed |
| 3. SERP-overlap clustering | Keywords that share at least *k* top-10 URLs with a cluster's head keyword, with URL normalisation. Optional DataForSEO v3 fetcher for missing SERPs |
| 4. Disagreements | Agreement score (ARI) plus two tables: similar meaning but different SERPs (likely different intent), and different wording but the same SERPs (one page can rank for both) |
| 5. Hybrid | Blended similarity (SERP overlap where both keywords have data, meaning everywhere else) + agglomerative clustering |
| 6. Naming | Cluster label (highest-volume keyword), most central keyword, volume-weighted intent hint, volume totals |
| 7. Export | `keyword_clusters.csv`, `cluster_summary.csv`, `keyword_clusters.xlsx` (two tabs, import into Google Sheets) |

## Requirements

* Python 3.10+ (tested 24 October 2026 on Python 3.12 with sentence-transformers 6.2, scikit-learn 1.9, pandas 3.1, on a CPU; the sample run takes under a minute including the model download). Colab works out of the box.
* No API keys for the sample or for embeddings-only clustering.
* Optional: a DataForSEO account to fetch SERPs (about $0.002 per keyword in live mode, $0.0006 in the standard queue, at the time of writing). The notebook reads your login at runtime from Colab secrets (`DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`) or a hidden prompt.

```bash
pip install -r requirements.txt
```

## Inputs

* Keywords: CSV with `keyword` and (ideally) `volume`.
* SERPs (optional): long CSV with `keyword`, `rank`, `url`, one row per ranking URL. Most rank trackers and SEO tools can export this; so can the DataForSEO SERP API.

## Notes and limits

* SERP overlap reflects one location, device and moment. Re-pull before big decisions.
* The model is English. For other languages, swap in `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
* Default thresholds were tuned on short English keywords. Check a few clusters and adjust.
* The intent hint is a few regular expressions for a human to check.
* The sample data is synthetic: invented volumes and fictional `.example` URLs. See [`sample_data/README.md`](sample_data/README.md).

## Related

* Guide: [How to do keyword clustering with KeyBERT](https://www.mlforseo.com/machine-learning-implementation-guides/keyword-research/how-to-do-keyword-clustering-with-keybert/)
* Guide: [What ML clustering is and where it fits in SEO](https://www.mlforseo.com/machine-learning-tutorials/topic-modeling-clustering/what-ml-clustering-is-and-where-it-fits-in-seo/)
* Course: [Introduction to Machine Learning for SEO](https://www.mlforseo.com/courses/introduction-to-machine-learning-for-seo/)
* Topic-level clustering of whole pages: [`topic-modeling-bertopic/`](../topic-modeling-bertopic/)

## Files

* `keyword_clustering.ipynb`: the notebook (saved with outputs from the sample run)
* `requirements.txt`
* `sample_data/`: synthetic keywords and SERPs, plus the script that generated them

Made by Lazarina Stoy, MLforSEO. MIT licence.
