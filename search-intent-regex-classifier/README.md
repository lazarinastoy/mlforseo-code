# Rule-based search intent classifier (2026 refresh)

Companion code for the MLforSEO guide **"Search-Intent Classification with Machine Learning: The Approaches Explained"** by Lazarina Stoy.

## What it does

Applies the regex dictionaries behind the free [Search Intent Keyword Classifier Data Studio template](https://www.datastudioformarketers.com/product/search-intent-keyword-classifier-data-studio-template/) (2021) to any keyword export (Semrush, Ahrefs, Google Search Console):

| Step | Output |
|---|---|
| Classify | `intents` (all matches), `primary_intent`, `n_intents` for every keyword |
| Prioritise | `easy_keyword` (keyword difficulty < 65) and `money_keyword` (CPC >= $0.01), the template's thresholds |
| Reuse | Prints a Data Studio calculated field (`CASE` + `REGEXP_MATCH`) and a Google Sheets `IFS(REGEXMATCH())` formula built from the same dictionaries |
| Export | `keywords_with_intent.csv` |

## What changed since the 2021 template

* **Whole-word matching.** The template's filters were plain "RegExp Contains", so `top` matched *laptop* and `how` matched *showroom*. The script uses word boundaries.
* **Multi-label.** A keyword like *zendesk chatbot reviews* is both navigational and commercial; the script keeps both labels instead of letting the first filter win.
* **Cleaner dictionaries.** `which` was listed twice and `cheap` sat in both the transactional and commercial lists; it is now commercial only. Added `meaning`, `definition`, `compare`, `alternatives`, `discount`, `deal`, `free trial`, `demo`.
* **Navigational stays manual.** There is no generic navigational list: pass your brand, product and competitor names with `--brands`.

## Requirements

* Python 3.9+ (Colab works out of the box)
* `pandas>=2.0`

## Run it

```bash
pip install -r requirements.txt
python search_intent_classifier.py --demo
python search_intent_classifier.py my_semrush_export.csv --brands "monzo,revolut,starling"
```

Or open `search_intent_regex_classifier.ipynb` in Google Colab and run it top to bottom (step 2 uploads your own CSV).

The script looks for a `Keyword` (or `Query`) column, and optionally `Keyword Difficulty` / `KD` and `CPC (USD)` / `CPC`.

## Limits

Rule-based classification only sees the words in the query. It is auditable and fast, but it misses intent that isn't spelled out (*chatbot benefits* comes back unclassified) and it needs tuning per industry. For SERP-feature-based, transformer and entity-based approaches, see the guide and the [MLforSEO resources library](https://www.mlforseo.com/resources-library/).

## Files

* `search_intent_classifier.py`: command-line script (tested 22 October 2026 on Python 3.9, pandas 2.x)
* `search_intent_regex_classifier.ipynb`: Colab notebook (outputs cleared)
* `requirements.txt`
