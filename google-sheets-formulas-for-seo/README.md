# Google Sheets formulas for SEO keyword research and content analysis (2026 refresh)

Companion files for the MLforSEO post **"12 Google Sheets Formulas for SEO Keyword Research & Content Analysis"** by Lazarina Stoy (first published on lazarinastoy.com in March 2024, refreshed October 2026).

No Python is needed to use the formulas. Open [FORMULAS.md](FORMULAS.md), copy a formula, paste it into Google Sheets. The Python files are only here to keep the formulas consistent and tested.

## What's inside

| File | What it is |
|---|---|
| `FORMULAS.md` | Every formula, ready to copy, with the input cells it expects |
| `formulas.csv` | The same formulas as a CSV. Import it into a Google Sheet as a reference tab |
| `rules_intent.csv` | A ready-made **Rules** tab (label + pipe-separated words) for the rules-table intent formula |
| `rules_sections.csv` | A ready-made **Sections** tab (label + regex) for the XLOOKUP site-section formula |
| `sample_keywords.csv` | Seven sample rows (keyword, position, SERP features, URL) to try the formulas on |
| `formulas.py` | Single source of truth for the keyword lists and formulas |
| `build.py` | Regenerates `FORMULAS.md` and `formulas.csv` from `formulas.py` |
| `test_formulas.py` | 107 checks of the regex and bucket logic, including the bugs in the 2024 versions |

Cell conventions (same as the post): **C2** = keyword, **J2** = SERP features column from your Semrush or Ahrefs export, **A2** = URL (or the ranking position, for the rank buckets).

## What changed from the 2024 versions

| 2024 formula | Problem | 2026 fix |
|---|---|---|
| Intent lists with `REGEXMATCH(C2, "how\|why\|...")` | Case-sensitive ("How to" didn't match "how") and substring-based: "show" matched *how*, "whole" matched *who*, "laptop" matched *top*, "always" matched *ways* | `(?i)\b(...)\b`: case-insensitive, whole words only. RE2 (the engine behind Sheets' REGEX functions) supports both |
| `alternative*`, `feature*`, `benefit*`, `suppli*` | In regex `*` means "zero or more of the previous character", not a wildcard | `alternatives?`, `features?`, `benefits?`, `suppli\w*` |
| The "add more intent buckets" template | Unbalanced brackets and a missing comma, so it returned a formula parse error | Rewritten with `IFNA(IFS(...), "Unclassified")`; also a multi-label version |
| SERP features with `JOIN(", ", IF(...,""), ...)` | `JOIN` keeps empty strings, so you got ", , Informational Intent, ," | `TEXTJOIN(", ", TRUE, ...)` skips empties; wrapped in `LET` with a fallback label |
| SERP feature names | The two SERP formulas used "Sitelinks" and "Site links" inconsistently (Ahrefs writes the first, Semrush the second) and had no AI features | `Site ?links` matches both; added `AI overview` (Semrush code `aio`), `Popular products`, `Discussions and forums` |
| Site-section `IF(IF(IF(...)))` | Plain substrings (`tag` matched "vintage"), and the post said it used `ARRAYFORMULA` when it didn't | Path-anchored patterns (`/tag/`) in an `IFS`; plus an `XLOOKUP` over a rules tab |
| Rank buckets `AND(A2>=1, A2<=3)` ... | Gaps between buckets: a Search Console average position of 3.4 or 10.6 fell through to "Not ranked". Label said 10-20 for an 11-20 range | `IFS` with `<=` upper bounds only, so decimals land in the right bucket |
| Brand from URL `REGEXEXTRACT(..., "([^\.]+)")` | Returned the first label, so `blog.hubspot.com` became "blog" | Extract the host, then the label before the public suffix (handles `co.uk`, `com.au` and subdomains) |
| Language `IF(REGEXMATCH(A2, "/es/"), ...)` | Fine, but one nested IF per language | `REGEXEXTRACT` the language folder once, then `SWITCH` |

New in 2026: `LET`, `TEXTJOIN`, `IFS`, `SWITCH`, `XLOOKUP`, `FILTER`, and `BYROW` / `MAP` with `LAMBDA` to fill a whole column from one cell. Any formula can also be saved as a **Named function** (Data > Named functions) so your team types `=INTENT(C2)` instead of a 900-character regex.

## Run the tests

```bash
python3 test_formulas.py          # standard library only
pip install google-re2            # optional: run the same tests on RE2, the engine Sheets uses
python3 build.py                  # after editing formulas.py
```

## Tested with

Python 3.9 `re` (October 2026): 107 checks passed. `google-re2` failed to build on the test machine, so the RE2 run was skipped; the patterns use only syntax RE2 and Python share (`(?i)`, `\b`, groups, alternation, anchors, no lookarounds or backreferences).

**Not yet pasted into a live Google Sheet.** The formulas were checked for balanced brackets and quotes, and their regex and bucket logic was tested in Python, but please paste each one into Sheets once before publishing.

## Notes and caveats

* Rule-based labels are a quick first pass, not ground truth. Words like "cost", "deal" or "premium" sit in more than one intent list on purpose. For better labels see the MLforSEO guide [search intent classification with machine learning](https://www.mlforseo.com/machine-learning-implementation-guides/keyword-research/search-intent-classification-with-machine-learning-approaches/).
* Two-letter folders that aren't languages (`/us/`, `/uk/`, `/ai/`) will be read as language codes by the language formula. Add them to the `SWITCH` or exclude them.
* Google Sheets' `=AI()` function (Gemini, rolled out June-July 2025 on eligible Workspace and Google AI Pro/Ultra plans, up to 200 cells per run) can also label keywords. It is useful for a messy long tail, but results aren't deterministic and don't recalculate automatically. Use the regex formulas when the labels feed a report.
