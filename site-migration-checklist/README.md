# SEO Site Migration Checklist + Redirect Mapping Workbook

A free, phase-by-phase site migration checklist (43 checks from scoping to month twelve) linked to a redirect mapping workbook that takes the output of MLforSEO's fuzzy-matching notebooks and tracks QA for every URL. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/). Built on [Google's site move documentation](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes). Checked October 2026.

**Google Sheets version:** *(Make a copy link coming soon. Until then, download `site-migration-checklist.xlsx` and open it in Google Sheets or Excel.)*
**Read it on GitHub:** [`checklist.md`](checklist.md)

## What's inside

| Tab | What it does |
|---|---|
| Start here | How to use it, which fuzzy-matching tool to use, how notebook columns map to the workbook, legends, credits |
| Checklist | 43 checks in 7 phases: scope and plan, benchmark, redirect mapping, pre-launch (staging), launch day, first weeks, months 1 to 12 |
| Redirect map | 2,000 prepared rows. Paste old URLs and fuzzy-match suggestions, pick a Decision per URL, and it fills in old-URL priority (from clicks and referring domains), final destination, redirect type, source path, an Apache rule and warning flags, then tracks status code, hops and QA status |
| Progress | Completion by phase and priority, plus a redirect summary: decided vs undecided, overrides, 410s, flags (home page redirects, below-threshold accepts, chains, non-200 destinations, self-redirects) and % live and verified |

### Redirect map columns

| Column | Filled by | Notes |
|---|---|---|
| A Old URL, B Clicks, C Referring domains | You | From your crawl, Search Console and backlink exports |
| D Old URL priority | Formula | High / Medium / Low from the thresholds in row 2 |
| E Matched on, F Suggested new URL, G Similarity (0 to 100), H Match type, I Algorithm, J Algorithms agreeing | Paste from the notebook | Matches the triple fuzzy matching notebook output (Pre-Migration value, Post-Migration match, similarity score, match type, column). 404 notebook scores are 0 to 1, so multiply by 100 |
| K Decision, L Override URL | You | Accept suggestion / Override / 410 Gone / 404 / No change (same URL) |
| M Final destination, N Redirect type, O Source path, P Apache rule, T Flags | Formula | Check Apache rules before use: mod_alias `Redirect` matches by prefix |
| Q Status code, R Hops, S Final URL returns 200?, U QA status, V Reviewer, W Notes | You | From a list-mode crawl before and after launch |

## Which fuzzy-matching tool?

| Situation | Tool |
|---|---|
| Under about 300 URLs, no code | [Fuzzy Matching for SEO Google Sheets template](https://www.mlforseo.com/resource/fuzzy-matching-for-seo-google-sheets-template/) |
| Old crawl vs new crawl (URL, title, H1, H2, meta description) | [Triple fuzzy matching redirect notebook](https://www.mlforseo.com/resource/automated-redirect-mapping-with-triple-fuzzy-matching-for-site-migrations-notebook/) |
| 404s to live pages | [Mapping 404 URLs to live pages notebook](https://www.mlforseo.com/resource/mapping-404-urls-to-live-pages-with-fuzzy-matching-guide/) |
| Python, in this repository | [`fuzzy-matching-for-seo/`](../fuzzy-matching-for-seo/) |

Walkthrough: [404 and redirect mapping with fuzzy matching in Google Colab](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/). Fuzzy matching compares characters, not meaning, so review every partial match by hand.

## Files

| File | What it is |
|---|---|
| `site-migration-checklist.xlsx` | The workbook (Google-Sheets-ready: dropdowns, conditional formatting, formulas that work in Sheets and Excel) |
| `checklist.md` | The 43 checks in plain Markdown |
| `checks.csv` | The checks as data |
| `build.py` | Rebuilds the `.xlsx` and `checklist.md` from `checks.csv` (`pip install openpyxl`, then `python build.py`) |
| `SETUP.md` | How to publish the workbook as a Google Sheets "Make a copy" template |

## Sources

Google Search Central: [how to move a site with URL changes](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes), [redirects](https://developers.google.com/search/docs/crawling-indexing/301-redirects), [Change of Address tool](https://support.google.com/webmasters/answer/9370220), [HTTP status codes and soft 404s](https://developers.google.com/search/docs/crawling-indexing/http-network-errors), [canonicals](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) and [sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap); [Bing Webmaster Tools](https://www.bing.com/webmasters/) and [IndexNow](https://www.bing.com/indexnow); and MLforSEO's redirect mapping tutorial and notebooks.

## Go deeper

[Introduction to Machine Learning for SEO](https://www.mlforseo.com/courses/introduction-to-machine-learning-for-seo/) (fuzzy matching module) on MLforSEO Academy.

## Credit and licence

Created by Lazarina Stoy · MLforSEO. MIT licence (see the repository root). Free to use and adapt; please keep the credit.
