# Content audit template (GSC + GA4 + crawl → Keep / Update / Merge / Prune / Redirect)

A free Google Sheets template by **Lazarina Stoy, MLforSEO**. Paste a Screaming Frog crawl, two Search Console exports and a GA4 landing page export. The sheet joins them per URL, checks every page for decay, striking distance, thin content, overlap with another page and conversions, and suggests a decision with a plain-English reason. Every threshold sits on a **Rules** tab, and your **Override** column always wins.

**Get the Google Sheet:** the copy link will go here once the sheet is in Drive. Until then, download [`content-audit-template.xlsx`](content-audit-template.xlsx) and open it in Google Sheets or Excel (see [SETUP.md](SETUP.md)).

## What's inside

| File | What it is |
|---|---|
| `content-audit-template.xlsx` | The workbook, pre-filled with a synthetic sample site so every decision type shows up |
| `prepare_exports.py` | Optional helper: cleans the three exports, reports how well they join, and fills a copy of the workbook |
| `sample_data/` | Synthetic exports in the real formats (Search Console Pages CSV, GA4 CSV with its `#` header lines, Screaming Frog `internal_html.csv`) |
| `make_sample_data.py` | Regenerates `sample_data/` |
| `build_template.py`, `brand_style.py` | Rebuild the workbook (single source of truth for the formulas) |
| `requirements.txt` | `pandas`, `openpyxl` (only for the Python helpers) |

| Tab | What it does |
|---|---|
| Start here | Purpose, export steps, caveats, legend, credits |
| Audit | One row per crawled URL: crawl facts, clicks, impressions, CTR, position, previous-period clicks and change, sessions, engagement time, key events, six yes/no signals, suggested decision, reason, and your inputs (referring domains, override, notes, final decision) |
| Dashboard | URLs, clicks and sessions per decision; decay, striking distance, thin, overlap and converting counts; clicks on pages marked Prune; Search Console pages with clicks that the crawl missed; header problems |
| Rules | Ten editable thresholds, the column-name map (the sheet finds each column by its header, so a reordered export still works), and the decision order |
| Crawl, GSC current, GSC previous, GA4 | Paste zones with the exact export headers in row 1, plus purple helper columns on the right |

## Exports it expects

| Tab | Export | Headers used |
|---|---|---|
| Crawl | Screaming Frog SEO Spider > Internal > HTML > Export | `Address`, `Status Code`, `Indexability`, `Indexability Status`, `Word Count`, `Unique Inlinks`, `Closest Near Duplicate Match`, `No. Near Duplicates`, `Closest Semantically Similar Address`, `Semantic Similarity Score` |
| GSC current / previous | Search Console > Performance > Pages > Export (CSV, `Pages.csv` from the zip), two date ranges | `Top pages`, `Clicks`, `Impressions`, `CTR`, `Position` |
| GA4 | Reports > Engagement > Landing page > Share > Download CSV | `Landing page + query string`, `Sessions`, `Active users`, `New users`, `Average engagement time per session`, `Key events`, `Total revenue` |

If your export names a column differently, type the exact header on the Rules tab; the "Column # found" cell turns from NOT FOUND to a number. The near-duplicate and semantic similarity columns only fill when those Screaming Frog features are switched on (Config > Content > Duplicates; embeddings for semantic similarity) and Crawl Analysis has run. Without them, Merge never triggers and everything else still works.

## Decision rules (first match wins)

1. Status 3xx → **Redirect** (already redirects: update internal links).
2. Status 4xx/5xx → **Redirect** if it still gets clicks or has referring domains, otherwise **Prune**.
3. Non-indexable (noindex, canonicalised) → **Keep**, with a note to confirm it's intentional.
4. Overlaps a page with more clicks (near-duplicate, or semantic score at or above 0.9) and no key events → **Merge**.
5. Decaying (30%+ click drop on a page that had 20+ clicks), striking distance (position 4-20 with 200+ impressions), or thin (under 300 words) with search demand → **Update**.
6. Low value (under 10 clicks, under 200 impressions, under 20 sessions, no key events) → **Prune**, or **Redirect** if you've entered referring domains.
7. Everything else → **Keep**.

URLs are matched on their path: host, query string, `#fragment`, trailing slash and letter case are ignored, so GA4's paths and query-string variants line up with full URLs from the crawl and Search Console. Audit one host at a time.

## The helper script (optional)

```bash
pip install -r requirements.txt
python prepare_exports.py --demo     # runs on sample_data/
python prepare_exports.py --gsc Performance.zip --gsc-previous Previous.zip --ga4 ga4.csv \
    --crawl internal_html.csv --out prepared/ --fill content-audit-template.xlsx
```

It strips GA4's `#` comment lines, reads `Pages.csv` straight from the Search Console zip, renames common header variants (for example `Conversions` → `Key events`, `Page` → `Top pages`), turns `4.1%` and `1m 05s` into numbers, keeps HTML rows only from a crawl, and prints a join check. Demo output:

```
Join check (URLs are matched on path, ignoring host, query string, trailing slash and case)
  crawl URLs: 24
  GSC pages: 22
  GSC clicks matched to the crawl: 4,845 of 4,880
  GA4 sessions matched to the crawl: 8,035 of 8,075
  1 page(s) get clicks but are not in the crawl (orphans, or outside the crawl scope):
   - https://www.stride-example.com/blog/orphan-race-calendar/
```

With `--fill` it writes `content-audit-filled.xlsx` (sample rows and sample overrides cleared) for you to import to Drive.

## Formulas

`INDEX`/`MATCH`, `SUMIFS`, `COUNTIF(S)`, `SUMPRODUCT`, `IF`, `IFERROR`, `TEXT` and text functions only, so it behaves the same in Google Sheets and Excel (no `XLOOKUP`, `LET`, `LAMBDA` or `FILTER`). Room for 2,000 URLs per tab; copy the last formula row down on every tab for more. The Audit tab follows the Crawl tab row by row, so copy it as values before you re-paste a crawl in a different order, or your overrides won't line up.

## Limits

This is a decision aid built on transparent rules. It can't see seasonality, legal or campaign pages, or backlinks unless you add referring domains, so read the reason before removing anything and prefer a redirect whenever a page has links or traffic. The sample data is synthetic.

## Tested

Built with openpyxl 3.1.5 and pandas 2.3.3 (Python 3.9, October 2026). `prepare_exports.py --demo` ran on the sample exports. The workbook was reloaded to confirm formulas, dropdowns, conditional formatting and frozen headers. LibreOffice wasn't available, so formulas were recalculated with the Python [`formulas`](https://pypi.org/project/formulas/) engine: no `#REF!`, `#NAME?` or `#VALUE!` errors, and all 24 sample URLs got the expected decision. Not yet opened in a live Google Sheet: run the checks in SETUP.md after import.

## Related

* [Blog and site architecture for SEO and conversions in the AI search era](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/blog-site-architecture-ai-search/) and its code in [`blog-architecture-audit/`](../blog-architecture-audit/)
* Free MLforSEO templates that pair with it: [On-page Duplication Analysis](https://www.mlforseo.com/resource/on-page-duplication-analysis-google-sheets-template/), [LDA topic modelling output organiser](https://www.mlforseo.com/resource/no-code-lda-topic-modeling-output-organiser-google-sheets-template/), [Internal link opportunities quick-find](https://www.mlforseo.com/resource/internal-link-opportunities-quick-find-google-sheets-template/)
* [Introduction to Machine Learning for SEO](https://www.mlforseo.com/courses/introduction-to-machine-learning-for-seo/) (MLforSEO Academy course, including the lesson on entity analysis in web content audits)

MIT licence. Credit: Lazarina Stoy, MLforSEO.
