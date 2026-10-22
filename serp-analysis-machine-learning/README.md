# ML-enabled SERP competitor analysis (2026 refresh)

Companion code for the MLforSEO tutorial **"4 ways to boost your SERP competitor analysis with machine learning"** by Lazarina Stoy (first presented at BrightonSEO, October 2022).

## What it does

`serp_analysis_machine_learning.ipynb` takes the top organic results for a set of keywords and runs the four analyses from the tutorial:

| Section | What you get | Method |
|---|---|---|
| 1. Get the SERP data | One row per ranking result, snippets cleaned of dates and "Read more" | Your CSV export, or a DataForSEO live pull |
| 2a. Starter taxonomy | Site type per domain, intent per result | Rule-based lookup + URL/title patterns (no key) |
| 2b. Custom categories | Your own site-type list, applied to the domains the rules can't place | LLM with structured outputs (Claude via the Anthropic SDK) |
| 2c. Share of search | Slot share and click-weighted share per domain, site type and intent, plus charts | pandas |
| 3. Prominent entities | Entity frequency, salience, sentiment, in-title vs in-description, average position | Google Cloud Natural Language API **v1** `analyzeEntitySentiment`; spaCy fallback with no key |
| 4. SERP sentiment | Sentiment score, magnitude and label for every title and description, a position-vs-sentiment chart, brand filter | Google Cloud Natural Language API **v2** `analyzeSentiment` |
| 5. N-grams | Title patterns (stop words kept: "what is", "vs") and topics (stop words removed), by intent and position bucket | scikit-learn `CountVectorizer` |
| 6. Export | Tidy CSVs for the Data Studio template | pandas |

`ngrams.gs` is the same n-gram analysis as a Google Sheets custom function (`=NGRAMS(B2:B100, 2)`), for anyone who'd rather stay in Sheets.

`sample_serp_data.csv` is a real pull of the US desktop top 10 for six machine-learning keywords (DataForSEO, 22 October 2026), so the notebook runs out of the box.

## Requirements

* Python 3.9+ (Colab works with no local setup)
* `pip install -r requirements.txt` and `python -m spacy download en_core_web_sm`
* Keys, all optional. Without them the notebook still runs end to end (rule-based categories, spaCy entities, n-grams):
  * `GOOGLE_NL_API_KEY`: a Cloud Natural Language API key ([setup](https://cloud.google.com/natural-language/docs/setup)). First 5,000 units a month free per feature; a unit is 1,000 characters.
  * `ANTHROPIC_API_KEY`: for LLM categorisation.
  * `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`: for a live SERP pull (about $0.002 per keyword on the live endpoint at depth 10, October 2026).

In Colab, add keys in the Secrets panel; locally, set them as environment variables.

## What changed since the 2022 version

| 2022 | 2026 |
|---|---|
| GPT-4 in Google Sheets (Danny Richman's GPT-3 classification script) for site categories | Rule-based starter taxonomy first, then an LLM with **structured outputs** (JSON schema with your category list as an enum), batched by domain with sample titles |
| Share of search as a count of results | Slot share **and** click-weighted share (editable CTR curve) |
| Entities and sentiment via the Cloud Next '18 Google Sheets template (Apps Script) | Same Natural Language API from Python. Entities stay on **v1** `analyzeEntitySentiment`, because v2 (Aug 2023) dropped salience, Wikipedia URLs and entity sentiment. Sentiment uses v2's newer model. Retries on 429/5xx |
| N-gram Apps Script formula generated in the OpenAI playground | `CountVectorizer` in Python, plus a clean `NGRAMS()` custom function for Sheets; two passes (patterns vs topics) |
| Manual export to Looker Studio | One tidy CSV per analysis |

## Testing notes (22 October 2026)

* Ran end to end with no keys (rule-based, spaCy, n-grams, exports).
* The Google NL API and Anthropic code paths were run against mocked responses in the documented response shapes (v1 `analyzeEntitySentiment`, v2 `analyzeSentiment`, Messages API `output_config.format`), not live calls. Run them once with your own keys before relying on them.
* `ngrams.gs` was tested with Node against the sample titles (same output as the Python cell).

## Files

* `serp_analysis_machine_learning.ipynb`: the notebook (outputs cleared)
* `ngrams.gs`: Google Sheets custom function
* `sample_serp_data.csv`: sample SERP data
* `requirements.txt`
