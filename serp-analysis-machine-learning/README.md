# SERP analysis with machine learning and AI (2026)

Companion code for two MLforSEO guides by Lazarina Stoy:

* **"7 ways to automate SERP analysis with AI"**: the automation toolkit (SERP APIs and scheduled collection, LLM classification, entity and n-gram gaps, AI Overview and AI Mode citation tracking, share of search over time, SERP-overlap clustering, scripted and agentic pipelines).
* **"4 ways to boost your SERP competitor analysis with machine learning"** (first presented at BrightonSEO, October 2022): the original four methods, refreshed. That guide is being folded into the automation guide; its notebook stays here.

The talk itself is written up on [lazarinastoy.com](https://lazarinastoy.com/how-to-incorporate-machine-learning-into-your-serp-analysis/).

## Part 1: the automation toolkit

| File | What it does |
|---|---|
| `serp_automation.py` | All the functions, on plain pandas DataFrames: DataForSEO client (organic + AI Overview, AI Mode, historical SERPs) with a spend cap, parsers, a CSV snapshot store, LLM classification with structured outputs, n-gram and entity gaps, citation overlap, share of search, SERP-overlap clustering, a change report |
| `automate_serp_analysis_ai.ipynb` | Walks through the seven methods on the sample data (no keys needed) |
| `run_pipeline.py` | The scripted pipeline: collect, store, measure, write `report.md`. `--demo` runs on the sample data |
| `github-actions-serp-tracker.yml` | Weekly schedule for the pipeline that commits the snapshots back to your repo |
| `serp_agent.py` | The agentic version: Claude gets read-only tools over your snapshots, plus one capped, paid live-pull tool, and writes a brief |
| `sample_data/` | Real data for the keyword "serp analysis" (US, English, desktop): organic top 10, SERP features and AI Overview citations for Jan, Mar, May and Aug 2026 (DataForSEO historical SERPs) plus a live pull with AI Overview and AI Mode on 22 Oct 2026; two more keywords for the overlap demo; `my_page.txt` (the MLforSEO SERP guide) for the gap demo |

The seven methods map to the module like this:

| # | Method | Functions |
|---|---|---|
| 1 | SERP APIs and scheduled collection | `DataForSEO.organic / ai_mode / historical`, `parse_serp`, `save_snapshot`, `collect` |
| 2 | LLM structured-output classification | `feature_matrix` (no AI needed), `classify_serp`, `classify_latest` (JSON schema with enums) |
| 3 | Entity and n-gram gap analysis | `ngram_gap`, `entity_gap` with `entities_spacy` or `entities_google` |
| 4 | AI Overview and AI Mode citation tracking | `citation_overlap`, `citation_presence`, `my_citation_rate` |
| 5 | Share of search over time | `share_of_search` (slots or click-weighted), `biggest_movers` |
| 6 | Clustering SERPs by overlap | `serp_overlap`, `cluster_by_overlap`, `dendrogram_data` |
| 7 | Scripted and agentic pipelines | `run_pipeline.py`, `change_report`, `serp_agent.py` |

### Quick start

```bash
pip install -r requirements.txt && python -m spacy download en_core_web_sm
python run_pipeline.py --demo --data-dir demo_out          # no keys
# your own keywords, one per line in keywords.txt:
export DATAFORSEO_LOGIN=... DATAFORSEO_PASSWORD=...
python run_pipeline.py --keywords keywords.txt --data-dir data --ai-mode --my-domain example.com --max-spend 0.25
export ANTHROPIC_API_KEY=...
python serp_agent.py --data-dir data --my-domain example.com
```

### Costs (DataForSEO, October 2026; check their pricing page)

* Live organic SERP, depth 10: about $0.002 per keyword; loading the asynchronous AI Overview adds $0.002 (refunded when there is none).
* AI Mode: charged per request; see https://dataforseo.com/pricing/serp/google-ai-mode-serp-api.
* Historical SERPs (Labs): $0.00012 per monthly snapshot, per their pricing FAQ.
* The whole sample dataset cost a few cents to collect.

### Testing notes (22 October 2026, Python 3.9: pandas 2.3.3, scikit-learn 1.6.1, scipy 1.13.1, spaCy 3.7.5, anthropic 0.125.0)

* `automate_serp_analysis_ai.ipynb` executed end to end with no keys: no errors (outputs cleared).
* `run_pipeline.py --demo` ran end to end.
* `parse_serp` and `save_snapshot` tested on real DataForSEO historical responses (de-duplication checked).
* The Anthropic paths (`classify_serp` structured output, `serp_agent.py` tool runner, including a parallel tool call and the live-pull guard) were run against a mocked HTTP transport in the documented response shapes, **not** live. Run them once with your own key.
* `DataForSEO._post` and the GitHub Actions workflow were not run live from this code (the sample data was pulled through the DataForSEO API directly). Run once with your keys.

## Part 2: the original four methods (BrightonSEO 2022, refreshed)

`serp_analysis_machine_learning.ipynb` takes the top organic results for a set of keywords and runs the four analyses from the original tutorial:

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

### Requirements

* Python 3.9+ (Colab works with no local setup)
* `pip install -r requirements.txt` and `python -m spacy download en_core_web_sm`
* Keys, all optional. Without them the notebook still runs end to end (rule-based categories, spaCy entities, n-grams):
  * `GOOGLE_NL_API_KEY`: a Cloud Natural Language API key ([setup](https://cloud.google.com/natural-language/docs/setup)). First 5,000 units a month free per feature; a unit is 1,000 characters.
  * `ANTHROPIC_API_KEY`: for LLM categorisation.
  * `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`: for a live SERP pull.

In Colab, add keys in the Secrets panel; locally, set them as environment variables.

### What changed since the 2022 version

| 2022 | 2026 |
|---|---|
| GPT-4 in Google Sheets (Danny Richman's GPT-3 classification script) for site categories | Rule-based starter taxonomy first, then an LLM with **structured outputs** (JSON schema with your category list as an enum), batched by domain with sample titles |
| Share of search as a count of results | Slot share **and** click-weighted share (editable CTR curve) |
| Entities and sentiment via the Cloud Next '18 Google Sheets template (Apps Script) | Same Natural Language API from Python. Entities stay on **v1** `analyzeEntitySentiment`, because v2 (Aug 2023) dropped salience, Wikipedia URLs and entity sentiment. Sentiment uses v2's newer model. Retries on 429/5xx |
| N-gram Apps Script formula generated in the OpenAI playground | `CountVectorizer` in Python, plus a clean `NGRAMS()` custom function for Sheets; two passes (patterns vs topics) |
| Manual export | One tidy CSV per analysis, for the Data Studio template |

### Testing notes (22 October 2026)

* Ran end to end with no keys (rule-based, spaCy, n-grams, exports).
* The Google NL API and Anthropic code paths were run against mocked responses in the documented response shapes (v1 `analyzeEntitySentiment`, v2 `analyzeSentiment`, Messages API `output_config.format`), not live calls. Run them once with your own keys before relying on them.
* `ngrams.gs` was tested with Node against the sample titles (same output as the Python cell).

## Files

* Automation toolkit: `serp_automation.py`, `run_pipeline.py`, `serp_agent.py`, `github-actions-serp-tracker.yml`, `automate_serp_analysis_ai.ipynb`, `sample_data/`
* Original four methods: `serp_analysis_machine_learning.ipynb`, `ngrams.gs`, `sample_serp_data.csv`
* `requirements.txt`
