# SERP analysis with machine learning and AI (2026)

Companion code for two MLforSEO guides by Lazarina Stoy:

* **"10 ways to automate SERP analysis with AI"**: the automation toolkit (SERP APIs and scheduled collection, LLM classification, entity and n-gram gaps, People Also Ask mining, AI Overview and AI Mode citation tracking, brand monitoring in ChatGPT and Perplexity answers, share of search over time, volatility alerts, SERP-overlap clustering and market comparison, scripted and agentic pipelines).
* **"4 ways to boost your SERP competitor analysis with machine learning"** (first presented at BrightonSEO, October 2022): the original four methods, refreshed. That guide is being folded into the automation guide; its notebook stays here.

The talk itself is written up on [lazarinastoy.com](https://lazarinastoy.com/how-to-incorporate-machine-learning-into-your-serp-analysis/).

## Part 1: the automation toolkit

| File | What it does |
|---|---|
| `serp_automation.py` | All the functions, on plain pandas DataFrames: DataForSEO client (organic + AI Overview + People Also Ask, AI Mode, historical SERPs, LLM responses) with a spend cap, parsers, a CSV snapshot store, LLM classification and question clustering with structured outputs (with token and cost logging), n-gram and entity gaps, citation overlap, brand mentions, share of search, volatility scores, market comparison, SERP-overlap clustering, a change report |
| `automate_serp_analysis_ai.ipynb` | Walks through the ten methods on the sample data (no keys needed) |
| `run_pipeline.py` | The scripted pipeline: collect, store, measure, write `report.md`. `--demo` runs on the sample data |
| `github-actions-serp-tracker.yml` | Weekly schedule for the pipeline that commits the snapshots back to your repo |
| `serp_agent.py` | The agentic version: Claude gets read-only tools over your snapshots, plus one capped, paid live-pull tool, and writes a brief. Prints the tools it called and the estimated cost; `--max-turns` caps model calls |
| `sample_data/` | Real data for the keyword "serp analysis" (US, English, desktop): organic top 10, SERP features and AI Overview citations for Jan, Mar, May and Aug 2026 (DataForSEO historical SERPs) plus a live pull with AI Overview and AI Mode on 22 Oct 2026 (`serp_snapshots.csv`, `serp_features.csv`, `ai_citations.csv`); two more keywords for the overlap demo (`overlap_keywords.csv`); People Also Ask questions from three live SERPs (`paa_questions.csv`); the same keyword pulled twice in the US and once in the UK on 22 Oct (`multi_market.csv`); one ChatGPT and one Perplexity answer (`llm_answers.json`); `my_page.txt` (an MLforSEO SERP guide) for the gap demo |

The ten methods map to the module like this:

| # | Method | Functions |
|---|---|---|
| 1 | SERP APIs and scheduled collection | `DataForSEO.organic / ai_mode / historical`, `parse_serp`, `save_snapshot`, `collect` |
| 2 | LLM structured-output classification | `feature_matrix` (no AI needed), `classify_serp`, `classify_latest` (JSON schema with enums) |
| 3 | Entity and n-gram gap analysis | `ngram_gap`, `entity_gap` with `entities_spacy` or `entities_google` |
| 4 | People Also Ask mining and clustering | `parse_serp` (questions table), `organic(paa_clicks=...)`, `question_table`, `cluster_questions` |
| 5 | AI Overview and AI Mode citation tracking | `citation_overlap`, `citation_presence`, `my_citation_rate` |
| 6 | Brand monitoring in LLM answers | `DataForSEO.llm_response`, `parse_llm_answer`, `brand_mentions` |
| 7 | Share of search over time | `share_of_search` (slots or click-weighted), `biggest_movers` |
| 8 | Volatility scores and alerts | `serp_volatility`, `volatility_alerts`, `ALERT_THRESHOLD`, the volatility line in `change_report` |
| 9 | Clustering SERPs by overlap, comparing markets | `serp_overlap`, `cluster_by_overlap`, `dendrogram_data`, `compare_markets` |
| 10 | Scripted and agentic pipelines | `run_pipeline.py`, `change_report`, `serp_agent.py` |

### Quick start

```bash
pip install -r requirements.txt && python -m spacy download en_core_web_sm
python run_pipeline.py --demo --data-dir demo_out          # no keys
# your own keywords, one per line in keywords.txt:
export DATAFORSEO_LOGIN=... DATAFORSEO_PASSWORD=...
python run_pipeline.py --keywords keywords.txt --data-dir data --ai-mode --paa-clicks 1 --my-domain example.com --max-spend 0.25
export ANTHROPIC_API_KEY=...
python serp_agent.py --data-dir data --my-domain example.com
```

### Costs (October 2026; check the providers' pricing pages)

* DataForSEO live organic SERP, depth 10: about $0.002 per keyword; loading the asynchronous AI Overview adds $0.002 (refunded when there is none); each People Also Ask click adds $0.00015.
* DataForSEO AI Mode: charged per request; see https://dataforseo.com/pricing/serp/google-ai-mode-serp-api.
* DataForSEO historical SERPs (Labs): $0.00012 per monthly snapshot, per their pricing FAQ.
* DataForSEO LLM responses: a base fee plus the provider's token price. Measured on 22 Oct 2026: ChatGPT (gpt-4.1-mini, no web search) $0.00086 for one short answer; Perplexity (sonar, searches the web) $0.0058.
* Claude (claude-opus-5-5, $4 / $20 per million input / output tokens): measured below. `sa.LLM_USAGE` logs every call's tokens and estimated cost.

### Live test (22 October 2026)

Run with real keys on the sample data. Total spend: about $0.17 of Claude and about $0.013 of DataForSEO.

**Classification (`classify_serp`, effort low).** Four SERPs, 33 results, hand-labelled before the run (`page_type` and `intent`; where two answers were defensible, both were accepted).

| | Result |
|---|---|
| Page type | 33/33 (32/33 counting only my first-choice label) |
| Intent | 32/33 (31/33 first choice) |
| Cost and speed | $0.010 to $0.013 per SERP (about 1,000 to 1,400 input and 300 to 370 output tokens), 3 to 8 seconds |
| SERP-level labels | "serp analysis": informational / mixed (both dates); "serp checker": transactional / do (use a tool); "how to do serp analysis": informational / read |

Failure modes seen: the one miss was a Quora thread titled "How do you analyze your SERP performance? Which tool do you use?", labelled commercial; a re-run of the same SERP labelled it informational, and nothing else changed. Borderline results are where labels flip between runs, so spot-check them (or run twice and flag disagreements). The commercial/transactional line for free tools is a convention: write yours into the prompt. 17 of the 33 results had no snippet (the overlap file only has titles), and the labels held up anyway.

**Question clustering (`cluster_questions`).** 14 unique People Also Ask questions from three SERPs, grouped into 7 themes, all questions placed, 5 marked off-topic (general SEO questions such as "Can ChatGPT do SEO?"). $0.011.

**Agent (`serp_agent.py`, effort medium, no live pulls).** 3 model calls (the second ran four tools in parallel), 27 seconds, $0.097. Every figure in its brief checked out against the data (share of search, citation counts, first-place domains). Without being asked, it flagged that the historical snapshots hold only 6 or 7 organic results, and that the 22 October reshuffle might be a collection artefact rather than a real change, giving three reasons. With the default `--my-domain`, the brief spends a paragraph on a domain that isn't in the data; point it at a domain you track.

**Bugs the live run found, now fixed:** `serp_prompt` crashed on SERPs stored without a `description` column (the overlap file); `classify_serp` didn't check for `max_tokens`; neither script reported token use or cost; the agent loop had no turn cap.

### Testing notes (22 October 2026, Python 3.9: pandas 2.3.3, scikit-learn 1.6.1, scipy 1.13.1, spaCy 3.7.5, anthropic 0.125.0; the live Claude calls ran on anthropic 0.116.0)

* `automate_serp_analysis_ai.ipynb` executed end to end with no keys: no errors (outputs cleared).
* `run_pipeline.py --demo` ran end to end.
* `parse_serp` and `save_snapshot` tested on real DataForSEO historical responses and on the People Also Ask block of a live response (de-duplication checked).
* `classify_serp`, `cluster_questions` and `serp_agent.py` run live (above). The agent's paid `fetch_live_serp` tool was not exercised (live pulls off).
* `DataForSEO._post` (including `llm_response`) and the GitHub Actions workflow were not run live from this code: the sample data was pulled through the DataForSEO API directly, with the same request bodies. Run once with your keys.

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
