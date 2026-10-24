# AI Overview tracker: presence, cited domains and your share

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/ai-overview-tracker/ai_overview_tracker.ipynb)

A free notebook by Lazarina Stoy ([MLforSEO](https://www.mlforseo.com/)) that checks, for a keyword list, whether Google shows an AI Overview, which domains and URLs it cites, whether your domain is among them, and each domain's share of citations. Companion to [Your rank tracker is lying to you about AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/rank-tracker-ai-search-measurement/).

## What it does

| Output | What it tells you |
|---|---|
| `aio_presence.csv` | Per keyword: AI Overview yes/no, cited URLs and domains, whether you're cited, your first citation position, your organic rank, the top cited domains |
| `citation_share.csv` + `citation_share.png` | Each domain's share of all cited URLs and the share of AI Overviews that cite it (keyword coverage), your domain highlighted |
| `citation_gaps.csv` | Keywords with an AI Overview that cites others and not you (optionally only where a named competitor is cited) |
| `cited_vs_ranking.csv` | Per keyword: domains cited and ranking in the top 10, cited without ranking, ranking without being cited |
| `aio_history.csv` | Each run appended by date, for week-by-week tracking |
| `ai_overview_tracker.xlsx` | All of the above as tabs, ready to import into Google Sheets |

## How AI Overview citations are read

Data comes from the DataForSEO SERP API v3, Google Organic, advanced results ([docs](https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/)). An AI Overview is an item with `type: "ai_overview"`. Its answer is split into `ai_overview_element` items, each with a `references` list (`source`, `domain`, `url`, `title`, `text`); the `ai_overview` item has its own `references` too (the source panel). The tracker reads both and keeps each URL once per keyword, in order of first appearance.

Requests set `load_async_ai_overview: true`. Without it you only receive AI Overviews already in the page, which undercounts presence. It costs up to $0.002 extra per Live call ($0.0006 in Standard) and is refunded when there's no asynchronous AI Overview.

## Requirements

* Python 3.9+ (tested 24 October 2026 on Python 3.9, pandas 2.3.3, matplotlib 3.9; Colab works out of the box)
* `pandas`, `requests`, `openpyxl`, `matplotlib` (`pip install -r requirements.txt`)
* For live data: a DataForSEO API login and password ([app.dataforseo.com/api-access](https://app.dataforseo.com/api-access)) as Colab secrets `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`, environment variables, or the hidden prompt. Never paste them into the notebook.

## Cost

About $0.002 per keyword in Live mode plus the AI Overview surcharge, so at most $0.40 per 100 keywords; Standard mode is about a third of that. The notebook estimates the worst case before running and stops at `MAX_SPEND_USD`. October 2026 prices; check the [pricing page](https://dataforseo.com/pricing/serp/google-organic-serp-api).

## Run it without a key

`USE_SAMPLE = True` (the default) replays three real SERPs from 24 October 2026 (US, English, desktop) saved in `sample_data/`, with `screamingfrog.co.uk` as the example domain. The responses are trimmed (no XPaths, rectangles, markdown or long snippets); the structure is what the API returns.

## Files

* `ai_overview_tracker.ipynb`: the notebook (saved with sample-mode outputs)
* `aio_tracker.py`: presence, share, gaps, cited-vs-ranking, chart and history functions
* `dataforseo_serp.py`: a copy of the client from [`dataforseo-serp-collection/`](../dataforseo-serp-collection/), so this folder runs on its own
* `requirements.txt`, `sample_data/`

## Limits

* AI Overviews change between pulls; one run is a snapshot. Schedule it and read the trend.
* One location, language and device per run.
* Citations show which sources Google displays, not how much of the answer each one shaped or whether anyone clicked.
* AI Mode is a separate surface and isn't covered here; see [`serp-analysis-machine-learning/`](../serp-analysis-machine-learning/) for an AI Mode pull.

MIT licence. Credit: Lazarina Stoy, MLforSEO.
