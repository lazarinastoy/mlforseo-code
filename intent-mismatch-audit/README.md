# Search intent-first website architecture: the intent mismatch audit

Companion code for the MLforSEO guide **"How to Build a Search Intent-First Website Architecture"** by Lazarina Stoy (first given as a talk at the SEO Mastery Summit 2022; refreshed October 2026).

## What it does

`intent_mismatch_audit.ipynb` is a Colab-ready notebook that checks whether your pages attract the search intent they were built for, using a Search Console page + query export.

| Section | What you get |
|---|---|
| 1. Load Search Console data | Your page/query export, or a built-in example (a fictional SaaS site) |
| 2. Page types | URL rules that map pages to resource / company / product, and the intents each type should serve |
| 3. Query intent | Rule-based intent filters (informational, commercial, transactional, navigational); brand + modifier queries take the modifier's intent and are flagged as branded |
| 4. Mismatch audit | Click- (or impression-) weighted intent mix per page, dominant intent, and a verdict: match / mismatch / mixed |
| 5. KPI trade-offs | Clicks, impressions, CTR and average position per page type; optional GA4 sessions, engagement rate and key events |
| 6. Intent bridges | For each resource page, the product page with the most shared query vocabulary: a first candidate for a contextual link or CTA |
| 7. Export | `queries_with_intent.csv`, `page_intent_audit.csv`, `intent_bridges.csv` |

## Requirements

* Python 3.9+ (tested 22 October 2026 on Python 3.9 with pandas 2.3.3; Colab works out of the box)
* `pandas`. No API keys.

```bash
pip install -r requirements.txt
```

## Inputs

* Search Console export with the dimensions page and query: `page`, `query`, `clicks`, `impressions`, `position`. Get it from the Search Console API, the Search Analytics for Sheets add-on or the BigQuery bulk export (the web UI export doesn't combine page and query).
* Optional GA4 landing-page export: `page`, `sessions`, `engagement_rate`, `key_events`.

## Notes

* The intent filters are deliberately simple and English-only. For other languages, use the filters from [`multilingual-intent-classification/`](../multilingual-intent-classification/).
* The intent-bridge score is word overlap (Jaccard). Treat it as a shortlist for a human, not an automatic internal-linking rule.

## Files

* `intent_mismatch_audit.ipynb`: the notebook (outputs cleared)
* `requirements.txt`
