# Intent-driven international keyword research: multilingual search intent classification

Companion code for the MLforSEO guide **"How to Do Intent-driven International Keyword Research"** by Lazarina Stoy (first given as a talk at the International Search Summit, Barcelona, 2021; refreshed October 2026).

## What it does

`multilingual_intent_classification.ipynb` is a Colab-ready notebook that classifies keywords by search intent across markets and languages, using rule-based (regex) filters you translate and localise once, instead of translating every keyword.

| Section | What you get |
|---|---|
| 1. Load keywords | Your keyword export (keyword, market, language, volume) or a built-in example set |
| 2. Filter words | Starter intent filters for English, Spanish, German and French, market-specific extras (e.g. UK vs US), industry presets (e-commerce, SaaS, services) and brand terms |
| 3. Classifier | Accent- and case-insensitive whole-word matching, a primary intent by priority, plus every category matched |
| 4. Intent split per market | Share of search volume by intent, per market |
| 5. Unclassified gaps | Coverage per market and the most frequent words in unclassified keywords, i.e. what to add to your filters next |
| 6. Language traps | Flags false friends / homographs (e.g. German "Gift") and brand names that are everyday words in a market |
| 7. Search Console by country (optional) | Intent split of the same page's queries per country, to spot local intent mismatches |
| 8. Export | `keywords_with_intent.csv` and `intent_regex_per_market.csv` with RE2 patterns for Data Studio `REGEXP_MATCH` or Google Sheets `REGEXMATCH` |

The starter dictionaries are a starting point. Have a native speaker or SEO localisation expert review each market.

## Requirements

* Python 3.9+ (tested 22 October 2026 on Python 3.9 with pandas 2.3.3; Colab works out of the box)
* `pandas`. No API keys.

```bash
pip install -r requirements.txt
```

## Inputs

* Keywords CSV: `keyword`, `market` (e.g. `US`, `GB`, `ES`), `language` (e.g. `en`, `es`), `volume` (optional). Any keyword tool export works once the columns are renamed.
* Optional Search Console export with dimensions query, page and country: `query`, `page`, `country` (GSC's three-letter codes, e.g. `usa`, `esp`), `clicks`, `impressions`.

## Files

* `multilingual_intent_classification.ipynb`: the notebook (outputs cleared)
* `requirements.txt`
