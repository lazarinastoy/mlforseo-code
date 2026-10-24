# DataForSEO SERP collection starter notebook

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/dataforseo-serp-collection/dataforseo_serp_collection.ipynb)

A free, beginner-friendly notebook by Lazarina Stoy ([MLforSEO](https://www.mlforseo.com/)) that pulls Google SERPs for a keyword list through the DataForSEO SERP API v3 and turns them into tidy tables. It's the data layer most SERP-based MLforSEO notebooks start from, and the free lite version of the SERP collection lab in the [Semantic ML-enabled Keyword Research course](https://www.mlforseo.com/courses/semantic-ml-enabled-keyword-research/).

## What it does

| Step | What you get |
|---|---|
| 1. Clean the keyword list | Lower-cased, trimmed, de-duplicated, so you never pay twice for one SERP |
| 2. Estimate the cost | Worst-case USD for the run, before anything is spent |
| 3. Collect | Google organic SERPs via **Live Advanced** (`/v3/serp/google/organic/live/advanced`, instant) or **Standard** (`task_post` + `task_get/advanced`, queued and cheaper) |
| 4. Guardrails | A spend cap checked before every paid call, a keyword-count cap, retries with back-off on 429/5xx, a pause between live calls, and a cost log using DataForSEO's own `cost` field |
| 5. Flatten | `organic`, `serp_features`, `paa` (People Also Ask), `ai_overview_citations`, `related_searches` |
| 6. Export | One CSV per table plus `serp_collection.xlsx` (one tab each) for Google Sheets, and `cost_log.csv` |

## Requirements

* Python 3.9+ (tested 24 October 2026 on Python 3.9 with pandas 2.3.3; Colab works out of the box)
* `pandas`, `requests`, `openpyxl` (`pip install -r requirements.txt`)
* For live data: a DataForSEO account. Your API login and password are on [app.dataforseo.com/api-access](https://app.dataforseo.com/api-access). In Colab, store them as secrets named `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`; otherwise the notebook reads environment variables with those names or asks with a hidden prompt. Never paste them into the notebook.

## Cost

October 2026 list prices (check the [pricing page](https://dataforseo.com/pricing/serp/google-organic-serp-api), they change):

* Live Advanced: $0.002 per keyword for the top 10
* Standard, normal priority: $0.0006 per keyword (high priority $0.0012)
* `load_async_ai_overview`: up to $0.002 extra in Live, $0.0006 in Standard, refunded when there is no asynchronous AI Overview to load
* `people_also_ask_click_depth`: $0.00015 per click

So 100 keywords cost at most about $0.40 in Live mode and $0.12 in Standard mode.

## Run it without a key

`USE_SAMPLE = True` (the default) replays three real Live Advanced responses saved in `sample_data/` ("what is entity seo", "best running shoes", "screaming frog download"; US, English, desktop, 24 October 2026). They are trimmed to keep the files small (no XPaths, pixel rectangles, markdown or long snippets); the structure is otherwise exactly what the API returns.

## Files

* `dataforseo_serp_collection.ipynb`: the notebook (saved with sample-mode outputs)
* `dataforseo_serp.py`: the client, cost estimate and flattening functions, reusable in your own scripts
* `requirements.txt`
* `sample_data/`: `keywords.csv` and the three saved responses

## Notes

* Live mode takes one task per call (the API enforces it). For hundreds of keywords, use Standard mode.
* A SERP is one snapshot for one location, language and device. Track over time before drawing conclusions, especially about AI Overviews.
* Next step for AI Overviews: [`ai-overview-tracker/`](../ai-overview-tracker/) (presence, cited domains, your citation share).

MIT licence. Credit: Lazarina Stoy, MLforSEO.
