# PyTrends: the Google Trends API with Python (2026 refresh)

Companion code for the MLforSEO guide **"The Ultimate Guide to PyTrends: the Google Trends API (with Python code examples)"** by Lazarina Stoy.

## What it does

`pytrends_google_trends_api.ipynb` is a Colab-ready notebook that pulls Google Trends data with Python:

| Section | What you get | Library |
|---|---|---|
| 3. Keyword suggestions | Entities from the "Add a search term" box (mid, title, type) | PyTrends `suggestions()` |
| 4. Interest over time | Relative interest (0-100) for up to 5 keywords, plus a chart | PyTrends `interest_over_time()` |
| 4b. Hourly interest | Hourly data for windows of 7 days or less (replaces the removed `get_historical_interest()`) | PyTrends `interest_over_time()` |
| 4c. Long daily series | Month-by-month stitched daily data | PyTrends `dailydata.get_daily_data()` |
| 4d. Share of search | Each keyword's % of combined interest | pandas |
| 5. Interest by region | Country / region / city / DMA breakdown, plus a chart | PyTrends `interest_by_region()` |
| 6. Related queries | Top and rising queries for every keyword, in one tidy table | PyTrends `related_queries()` with TrendSpy fallback |
| 7. Related topics | Top and rising topics (with entity mids) | PyTrends `related_topics()` |
| 8. Trending now | Today's trending searches with volume, growth, topics | TrendSpy `trending_now()` and the official Trending now RSS feed |
| 9. Limitations workarounds | Topic vs search term (using mids), comparing >5 keywords with an anchor term | PyTrends |
| 10. Export | CSV files, auto-download in Colab | pandas |

## Requirements

* Python 3.9+ (tested on 3.9 locally; Colab runs 3.11/3.12)
* `pytrends==4.9.2`, `trendspy>=0.1.6`, `pandas>=2.0`, `matplotlib`, `requests`
* No API key needed.

```bash
pip install -r requirements.txt
```

In Colab, the first code cell installs everything.

## Status of each method (tested 21 October 2026)

| PyTrends method | Status |
|---|---|
| `suggestions`, `interest_over_time`, `interest_by_region`, `related_topics`, `categories` | Work |
| `related_queries` | Works, but Google returns HTTP 429 very quickly. The notebook retries with backoff and falls back to TrendSpy |
| `trending_searches`, `today_searches`, `realtime_trending_searches`, `top_charts` | HTTP 404 (Google retired the endpoints when it launched "Trending now" in Aug 2024) |
| `get_historical_interest` | Removed (raises `NotImplementedError`) |
| `TrendReq(retries=..., backoff_factor=...)` | Crashes on urllib3 2.x (`method_whitelist`). Use the notebook's `polite()` helper instead |

PyTrends' GitHub repo (GeneralMills/pytrends) was archived in April 2025, so these won't be fixed upstream.

## Rate limits

Google doesn't publish a quota for these (undocumented) endpoints. The notebook pauses 5 seconds after every request and backs off 30s / 60s / 120s / 240s on a 429. If you're still blocked, wait 15-60 minutes or restart the Colab runtime (often a new IP).

## The official alternative

Google announced the **Google Trends API (alpha)** in July 2025: five years of consistently scaled data, daily to yearly aggregation, region and sub-region breakdowns. Access is by application: https://developers.google.com/search/apis/trends

## Files

* `pytrends_google_trends_api.ipynb`: the notebook (outputs cleared)
* `requirements.txt`: pinned dependencies
