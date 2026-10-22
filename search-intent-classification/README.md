# Search intent classification: rule-based, SERP-based and ML methods

Companion notebooks for the MLforSEO guide **"Search-Intent Classification with Machine Learning: The Approaches Explained"** by Lazarina Stoy, and for the search intent lessons of the [Semantic ML-enabled Keyword Research](https://academy.mlforseo.com/course/semantic-ml-enabled-keyword-research/) course on the MLforSEO Academy.

All five notebooks are free. Each one runs top to bottom in Google Colab: it asks you to upload a CSV, adds new columns, and downloads the enriched file.

## The methods

| # | Notebook | Method | Input CSV | Needs | Open |
|---|---|---|---|---|---|
| 1 | [`01_rule_based_query_intent.ipynb`](01_rule_based_query_intent.ipynb) | **Rule-based, from the query.** Regex dictionaries label each keyword with main intent, query type, query length, explicit content format, knowledge level, user persona, geo and device relevance, implicit problem/struggle and context | `Keyword` | pandas | [Colab](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/search-intent-classification/01_rule_based_query_intent.ipynb) |
| 2 | [`02_serp_feature_intent.ipynb`](02_serp_feature_intent.ipynb) | **Rule-based, from SERP features.** Maps 60+ SERP features to informational / navigational / transactional / commercial intent with percentage breakdowns, then classifies ranking domains by site type (20+ rules) into a holistic intent per SERP | `keyword`, `SERP Features`; optional SERP results with `url` | pandas | [Colab](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/search-intent-classification/02_serp_feature_intent.ipynb) |
| 3 | [`03_semantic_entity_intent_google_nl_spacy.ipynb`](03_semantic_entity_intent_google_nl_spacy.ipynb) | **Semantic, entity-based.** spaCy dependency parsing (main verb, interrogatives) plus Google Cloud Natural Language entity types, salience and sentiment, combined into one intent label | `Keyword` | spaCy `en_core_web_sm`, a Google Cloud API key with the Natural Language API enabled (entered at runtime, never stored) | [Colab](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/search-intent-classification/03_semantic_entity_intent_google_nl_spacy.ipynb) |
| 4 | [`04_transformer_zero_shot_intent_bart.ipynb`](04_transformer_zero_shot_intent_bart.ipynb) | **Transformer zero-shot + rules.** `facebook/bart-large-mnli` zero-shot classification, blended with regex rules and SERP-feature signals into a final intent, with a distribution chart | `Keyword`, `SERP Features` | transformers, torch; a GPU runtime (T4) is recommended | [Colab](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/search-intent-classification/04_transformer_zero_shot_intent_bart.ipynb) |
| 5 | [`05_serp_content_formats_and_platforms.ipynb`](05_serp_content_formats_and_platforms.ipynb) | **Desired content format and platform, from SERP features.** Counts SERP features across your keyword universe, then maps them through editable dictionaries to the content formats (video, FAQ, reviews...) and platforms (YouTube, Pinterest, Reddit...) Google serves | Keyword export with `SERP features`; two dictionary CSVs (`SERP snippet` → `Description` / `Content platform`) | pandas, matplotlib | [Colab](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/search-intent-classification/05_serp_content_formats_and_platforms.ipynb) |

For a refreshed, multi-label take on method 1 that also writes a Data Studio calculated field and a Google Sheets formula, see [`../search-intent-regex-classifier/`](../search-intent-regex-classifier/).

## Demo data and templates

These Google Sheets go with the notebooks. Open one and use **File → Make a copy**.

* [Rule-based search intent classification: Google Sheets template](https://docs.google.com/spreadsheets/d/1liqT07LLtxnHEaxanG3AZUWkq60uf89N0L8drR0vjTs/edit?usp=sharing) (the regex formulas for method 1, with a demo dataset)
* [SERP feature descriptions and dictionaries](https://docs.google.com/spreadsheets/d/1gK0r8oyyZEKqxtx2grq4Ub7iasvtRM_WdZpDAdf4srA/edit?usp=sharing) (methods 2 and 5)
* [Search intent from SERP features: demo data and results](https://docs.google.com/spreadsheets/d/16DcDVUj3ZABoFAjAp7H1Crs92tSl8XnFxXmyILBX70I/edit?usp=sharing) (method 2)
* [Top ranking domains classified by site type and intent](https://docs.google.com/spreadsheets/d/1Ee2dRAVqXwsHrf7kToVZWCsOGaz4gJCRBpykYhakHDM/edit?usp=sharing) (method 2)
* [Sample DataForSEO SERP export](https://drive.google.com/drive/folders/1jSvt9t5xG2gbRzvidtc5LcqtUEnwz-YI?usp=sharing) (method 2, ranked domains)
* [ML-enabled search intent classification: demo data and results](https://docs.google.com/spreadsheets/d/1jV-fnV6dRo_TXeGglPY-dGjHZmrCZcpuo_UsB0Auj3o/edit?usp=sharing) (methods 3 and 4)

## Where the SERP features come from

Methods 2, 4 and 5 expect a SERP features column, comma-separated (for example `Featured snippet, People also ask, Video`). Semrush and Ahrefs keyword exports include one; DataForSEO's SERP API gives you the raw results.

## Choosing a method

* **Start with rules** (1 and 2): fast, free, explainable, and easy to tune to your niche.
* **Add SERP features** (2, 4 and 5) when you want what Google actually serves, not only what the query says.
* **Use ML** (3 and 4) for the long tail your dictionaries miss. Check a sample by hand: zero-shot labels and entity heuristics both make confident mistakes.

## Learn the method
The full walkthrough (video lessons, how to adapt the dictionaries, and how to combine the outputs into your keyword universe) is in the search intent lessons of [Semantic ML-enabled Keyword Research](https://academy.mlforseo.com/course/semantic-ml-enabled-keyword-research/) on the MLforSEO Academy.

## Notes
* Notebooks are shared as originally built for the course (2024–2025), with outputs cleared. They use `google.colab.files` for upload and download, so run them in Colab or swap those lines for `pd.read_csv()` locally.
* Method 3 calls the Google Cloud Natural Language API v1 `analyzeEntitySentiment` endpoint, which is billed per request after the free tier. Keep your API key out of the notebook if you save a copy.
