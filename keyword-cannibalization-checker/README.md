# Keyword cannibalization checker (Search Console API + Sheets report)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/keyword-cannibalization-checker/keyword_cannibalization_checker.ipynb)

A free notebook by **Lazarina Stoy, MLforSEO**. It finds queries where two or more of your pages split clicks and impressions, separates real cannibalisation from healthy cases (brand sitelinks, mixed-intent results, one clear winner) and suggests what to do about each one.

Most "cannibalisation" in a Search Console export isn't a problem. This notebook is built to find the cases that are.

## What it does

| Step | What you get |
|---|---|
| 1. Load data | Search Console API pull (query + page, optional date, paginated 25,000 rows at a time), your own CSV export, or the synthetic sample |
| 2. Merge URL variants | `#fragments`, tracking parameters and slash variants merged into one page, so jump links don't look like rivals |
| 3. Page types | URL rules map pages to home / product / company / resource (same idea as [`intent-mismatch-audit/`](../intent-mismatch-audit/)) |
| 4. Competing pages | Queries where 2+ pages each get a meaningful share of impressions (thresholds you can change) |
| 5. Rotation | With the date dimension: which page led each day, how often the leader changed, and how often pages appeared together |
| 6. Severity + action | 0-100 score (split, rotation, position proximity, demand), a case label (cannibalisation candidate / different page types / one clear winner / brand + sitelinks) and an action: consolidate, differentiate, internal-link or leave |
| 7. Page pairs | Pairs of pages that keep colliding, with shared queries and query overlap (from the On-page Duplication sheet's OverlapSummary idea) |
| 8. Export | `cannibalization_report.xlsx` (Sheets-ready, conditional formatting, `COUNTIF` summary, a Decision column) plus CSVs |

## Run it

**Google Colab:** click the badge above and run all cells. It runs on the synthetic sample with no account or key.

**Locally:**

```bash
pip install -r requirements.txt
jupyter notebook keyword_cannibalization_checker.ipynb
```

Tested 24 October 2026 on Python 3.9 with pandas 2.3.3 and openpyxl 3.1.5 (sample mode and CSV mode without dates). The API path follows the official `searchanalytics.query` reference but wasn't run against a live property for this release.

## Your own data

Set `SOURCE` in the first settings cell:

* `'csv'`: an export with `query`, `page`, `clicks`, `impressions`, `position` and, ideally, `date`. Exports from the Search Console API, the Search Analytics for Sheets add-on or the BigQuery bulk export work, and common column names (`Landing Page`, `Avg. Position`, ...) are mapped automatically. The Search Console web interface can't export query and page together.
* `'api'`: pulls from the Search Console API (`searchconsole` v1, `searchanalytics.query`), read-only scope `webmasters.readonly`. Two ways to sign in:
  * **Service account** (recommended): enable the Google Search Console API in a Cloud project, create a service account, download its JSON key, and add its email as a Restricted user in Search Console > Settings > Users and permissions.
  * **Your own Google account (OAuth)**: create a Desktop-app OAuth client and download `client_secret.json`. Locally, a browser window opens. In Colab, the notebook shows the `gcloud auth application-default login` command to run first. Colab's one-click `google.colab.auth.authenticate_user()` doesn't include the Search Console scope on its own, which is why this extra step exists.

Keys and client files are read from files at runtime. Never commit them (this folder's `.gitignore` ignores `*.json` outside `sample_data/`).

## Files

| File | What it is |
|---|---|
| `keyword_cannibalization_checker.ipynb` | The notebook, with outputs from the sample run |
| `sample_data/gsc_sample_SYNTHETIC.csv` | **Synthetic** Search Console export (date, query, page) for a made-up coffee shop, "Brewly". No real data. |
| `sample_data/make_sample_data.py` | The script that generated it, with the scenarios it simulates |
| `sample_data/example_report_SYNTHETIC.xlsx` | The report the notebook produces from the sample, so you can see it before running anything |
| `requirements.txt` | `pandas`, `openpyxl`; Google client libraries for the API option |

## Limits

* The Search Console API returns the top rows, not all of them, and leaves out anonymised queries. Long-tail cases can be missing.
* Severity, page types and case labels are heuristics. Use them as a shortlist and check the live SERP before merging or redirecting anything.
* Without the date dimension, rotation can't be measured, so severity scores run lower.

## Related

* [On-page Duplication Analysis (Google Sheets Template)](https://www.mlforseo.com/resource/on-page-duplication-analysis-google-sheets-template/): duplicate and near-duplicate titles, H1s and meta descriptions
* [`intent-mismatch-audit/`](../intent-mismatch-audit/) and the guide [How to Build a Search Intent-First Website Architecture](https://www.mlforseo.com/machine-learning-implementation-guides/onpage-seo/search-intent-first-website-architecture/)
* Course: [Semantic ML-enabled Keyword Research](https://www.mlforseo.com/courses/semantic-ml-enabled-keyword-research/)

## Licence

MIT, like the rest of this repository. Credit: Lazarina Stoy, MLforSEO.
