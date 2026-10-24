# Keyword mapping template (keyword → URL with intent and cannibalisation flags)

A free Google Sheets template by **Lazarina Stoy, MLforSEO**. It maps every keyword (or cluster) to one existing or planned URL, labels search intent, scores priority, and flags the mapping mistakes that turn into keyword cannibalisation. It's the step between [keyword clustering](https://www.mlforseo.com/glossary-term/keyword-clustering/) and content briefs.

**Get the Google Sheet:** the copy link will go here once the sheet is in Drive. Until then, download [`keyword-mapping-template.xlsx`](keyword-mapping-template.xlsx) and open it in Google Sheets or Excel (see [SETUP.md](SETUP.md)).

## What's inside

| Tab | What it does |
|---|---|
| Start here | Purpose, steps, how each flag works, legend, credits |
| Keyword Map | Paste zone (keyword, cluster, volume, KD, current ranking URL and position, target URL, page status, page type, keyword role, optional pasted intent, notes) and the calculated columns |
| URL Summary | One row per target URL: keywords mapped, primary keywords, volume, average priority, cannibalised keywords, intent mismatches, status |
| Cluster Summary | One row per cluster: keywords, volume, mapped vs not mapped, flags |
| Dashboard | Totals: mapped, unmapped, planned URLs, every flag, keywords by intent and by page type |
| Settings | Max primary keywords per URL, priority weights, the page type × intent fit grid, and the intent word lists |

## The flags

| Flag | Rule |
|---|---|
| Cannibalisation | The same keyword (case, spaces and `?` ignored) appears on another row with a different target URL |
| Too many primaries on URL | The target URL has more `Primary` keywords than the limit on Settings (default 1) |
| URL spans 2+ clusters | The same target URL also holds keywords from a different cluster |
| Intent mismatch | The keyword's final intent is `No` for that page type in the Settings grid (for example a transactional keyword on a blog post) |
| Ranking URL is not the target | Your Search Console or rank-tracker URL differs from the target (trailing slash and case ignored). Expected on planned pages |

**Intent** comes from a label you paste (for example from the [rule-based intent classifier](../search-intent-regex-classifier/)), otherwise from whole-word rules on Settings, checked in the order Navigational, Transactional, Commercial, Informational. The word lists match the classifier's dictionaries, plus `shop`, `sale` and `coupon code`. Edit the Navigational row with your own brand and product names.

**Priority score (0-100)** = volume points (log scale, full points at 5,000 searches) + ease points (100 − KD; a blank KD counts as 50) + intent points. Every weight is on Settings.

## Formulas

Works the same in Google Sheets and Excel: `INDEX`/`MATCH`, `COUNTIF(S)`, `SUMIFS`, `AVERAGEIFS`, `SUMPRODUCT`, `SEARCH`, `IF`, `IFERROR`. No `XLOOKUP`, `LET`, `LAMBDA`, `FILTER` or `UNIQUE`, so older Excel versions work too. The summary tabs list unique URLs and clusters with a running-index helper column instead of `UNIQUE`. Room for 1,000 keywords, 500 URLs and 300 clusters; copy the last formula row down for more.

## Sample data

Rows 3-29 hold 27 synthetic keywords for a fictional running shoe shop (`stride-example.com`), built so every flag fires at least once. Clear columns A-L on Keyword Map before you paste your own.

## Rebuild the workbook

```bash
pip install openpyxl
python build_template.py
```

`build_template.py` is the single source of truth for the formulas; `brand_style.py` holds the MLforSEO colours.

## Tested

Built with openpyxl 3.1.5 (Python 3.9, October 2026). Reloaded to confirm formulas, dropdowns, conditional formatting, frozen headers and filters. LibreOffice wasn't available on the build machine, so the formulas were recalculated with the Python [`formulas`](https://pypi.org/project/formulas/) engine instead: no `#REF!`, `#NAME?` or `#VALUE!` errors, and every sample flag and summary count matched the expected result. Not yet opened in a live Google Sheet: check the Dashboard numbers once after import (see SETUP.md).

## Related

* [How to turn semantic keyword research into an actionable SEO workflow](https://www.mlforseo.com/machine-learning-implementation-guides/keyword-research/how-to-turn-semantic-keyword-research-into-an-actionable-seo-workflow/) (MLforSEO)
* [Semantic ML-enabled Keyword Research](https://www.mlforseo.com/courses/semantic-ml-enabled-keyword-research/) (MLforSEO Academy course)
* [Search intent](https://www.mlforseo.com/glossary-term/search-intent/) and [keyword mapping](https://www.mlforseo.com/glossary-term/keyword-mapping/) in the MLforSEO glossary

MIT licence. Credit: Lazarina Stoy, MLforSEO.
