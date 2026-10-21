# Fuzzy matching for SEO

Companion notebook for the MLforSEO post **What Fuzzy Matching Is, and Where It Fits in SEO**
(which now includes Lazarina Stoy's *Ultimate End-to-End Guide to Fuzzy Matching for SEOs*, originally published on lazarinastoy.com in 2022).

## What it does

`fuzzy_matching_for_seo.ipynb` recreates every tab of the free Google Sheets template in Python and compares the main libraries:

| Section | What you get |
|---|---|
| 1. Scorers 101 | `ratio`, `partial_ratio`, `token_sort_ratio`, `token_set_ratio`, `WRatio`, raw Levenshtein and Jaro-Winkler, including the HARD / HAND / HARDER example |
| 2. String assessment | Nearest neighbour for every keyword or title in one list (duplicate and cannibalisation checks) |
| 3. Redirect mapping | Old URL to closest new URL on the path, with direct / partial / no-match buckets |
| 4. Internal linking opportunities | Most similar page per content extract, plus "does this link already exist?" from a Screaming Frog inlinks export |
| 5. Library comparison | RapidFuzz vs TheFuzz (renamed FuzzyWuzzy) vs PolyFuzz (multi-model + grouping), and a pandas + RapidFuzz replacement for fuzzy-pandas |
| 6. Phonetic matching | Metaphone and NYSIIS via `jellyfish` |
| 7. Keyword clustering caveat | Why character-level grouping misfires, with an optional embeddings comparison via PolyFuzz `SentenceEmbeddings` |
| 8. Export | CSVs of the assessment and redirect map |

All sections run on built-in sample data. Replace the lists marked `# YOUR DATA` with your own exports.

## Run it

- **Google Colab (easiest):** upload the notebook, or open it from GitHub, and run all cells. The first cell installs the libraries.
- **Locally:** `pip install -r requirements.txt jupyter` then `jupyter notebook fuzzy_matching_for_seo.ipynb`.

Python 3.9+ works (RapidFuzz 3.14+ needs Python 3.11+; pip picks a compatible version automatically).

## Library status (checked October 2026)

| Library | Status | Use it for |
|---|---|---|
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) 3.14 | Actively maintained, MIT, C++ backend | The default. Same scorers as FuzzyWuzzy, much faster, `process.cdist` for whole matrices |
| [TheFuzz](https://github.com/seatgeek/thefuzz) 0.22 | FuzzyWuzzy's new name since 2021; old `fuzzywuzzy` repo archived. Now runs on RapidFuzz | Legacy scripts: change `from fuzzywuzzy import fuzz` to `from thefuzz import fuzz` |
| [PolyFuzz](https://github.com/MaartenGr/PolyFuzz) 0.4.3 | Maintained (last release May 2025), slower release cadence | Comparing several models at once, grouping, TF-IDF n-grams, embeddings |
| [fuzzy-pandas](https://pypi.org/project/fuzzy-pandas/) 0.1 | Unmaintained since 2019 (wraps `csvmatch`) | Avoid for new work; see the `fuzzy_merge` helper in section 5 |

## Tested with

Python 3.9, RapidFuzz 3.13.0, TheFuzz 0.22.1, PolyFuzz 0.4.3, pandas 2.3.3, scikit-learn 1.6.1, jellyfish 0.9 (executed end to end, October 2026). The semantic cell is off by default and was not executed in testing.
