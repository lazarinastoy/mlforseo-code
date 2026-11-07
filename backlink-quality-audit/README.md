# Backlink Quality Audit with DataForSEO, Embeddings and Claude

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/backlink-quality-audit/backlink_quality_audit.ipynb)

A free notebook by Lazarina Stoy ([MLforSEO](https://www.mlforseo.com/)) that turns a backlink profile into a short, explainable list: which referring domains are worth knowing about, which are spam you can ignore, which need a human to look, and which broken backlinks you could reclaim. Clear cases are decided by transparent rules; only the ambiguous middle goes to Claude, so the whole audit of a site with about 300 referring domains costs well under a dollar.

## What it does

| Step | What you get |
|---|---|
| 1. Estimate the cost | Worst-case USD for the DataForSEO calls, before anything is spent |
| 2. Collect | Five DataForSEO Backlinks API calls: `summary/live`, `referring_domains/live`, `backlinks/live` (one link per domain), `anchors/live`, and `backlinks/live` filtered to broken links |
| 3. Guardrails | Spend caps for both APIs checked before every paid call, retries with back-off on 429/5xx (a dropped connection on a paid call is never retried), a local response cache so a re-run never pays twice, and a cost log using DataForSEO's own `cost` field and Claude's token usage |
| 4. Rule features | Spam score band, domain rank band, follow/nofollow, spam-prone TLD (a signal, not a verdict), semantic location on the page, anchor type (branded, keyword, generic, naked URL, image or empty, link-selling phrase), link age |
| 5. Relevance | Cosine similarity between each link (title + anchor + domain) and a one-line description of your site, from a small local sentence-transformers model (`all-MiniLM-L6-v2`), no key needed |
| 6. Claude review | Only the rows the rules can't settle, in batches of 25, to `claude-haiku-4-5` with structured JSON output: verdict, a reason of 20 words or fewer, confidence |
| 7. Buckets | Valuable, Neutral, Likely spam, Investigate, each with who decided it (rules or Claude) and why |
| 8. Link reclamation | Broken backlinks grouped by dead URL, re-checked today, with a suggested redirect target fuzzy-matched from your sitemap (`rapidfuzz`) |
| 9. Export | One CSV per table plus `backlink_audit.xlsx` (one tab each) for Google Sheets, and `cost_log.csv` |

## Requirements

* Python 3.10+ (tested 7 November 2026 on Python 3.12 with pandas 3.1, anthropic 2.6 and sentence-transformers 6.2; Colab works out of the box)
* `pip install -r requirements.txt`
* For live data: a DataForSEO account with Backlinks API access (API login and password from [app.dataforseo.com/api-access](https://app.dataforseo.com/api-access)) and an Anthropic API key. In Colab, store them as secrets named `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` and `ANTHROPIC_API_KEY`; otherwise the notebook reads environment variables with those names or asks with a hidden prompt. Never paste them into the notebook.

## Cost

November 2026 list prices (check the [DataForSEO pricing page](https://dataforseo.com/pricing/backlinks/backlinks) and [Anthropic pricing](https://www.anthropic.com/pricing), they change):

* DataForSEO Backlinks API: $0.024 per request plus $0.000036 per row returned. The five calls cost at most $0.20 with the default limits (1,000 referring domains, 1,000 backlinks, 100 anchors, 200 broken links).
* Claude Haiku 4.5: $1 per million input tokens, $5 per million output tokens.

The sample run on mlforseo.com (288 referring main domains) cost $0.146 at DataForSEO and $0.024 at Anthropic (64 ambiguous rows in 3 calls).

## Run it without a key

`USE_SAMPLE = True` (the default) replays a real audit of **mlforseo.com, collected 7 November 2026**: the five DataForSEO responses, the three Claude responses, the sitemap URL list and the status re-check, all saved in `sample_data/`. The DataForSEO responses keep every row (288 referring domains, 288 one-per-domain backlinks, the top 100 anchors, 33 broken backlinks) but are trimmed for size (nested breakdown objects and some per-link fields removed, `text_pre`/`text_post` cut to 100 characters); the structure is otherwise exactly what the API returns. Sample mode needs no credentials and costs nothing; it downloads the small embedding model from Hugging Face the first time.

## Files

* `backlink_quality_audit.ipynb`: the notebook (saved with sample-mode outputs)
* `backlink_audit.py`: the DataForSEO client, features, rules, Claude reviewer, reclamation and export functions, reusable in your own scripts
* `requirements.txt`
* `sample_data/`: the saved responses described above

## Notes

* **Disavow is rarely needed.** Google says it can usually work out which links to trust on its own, and that you should only disavow when you have a considerable number of spammy, artificial or low-quality links that have caused, or are likely to cause, a manual action ([Google Search Central](https://support.google.com/webmasters/answer/2648487)). The Likely spam bucket is a list to understand, not a disavow file.
* **Course and template sellers:** keep `download`, `sale page`, `group buy` and `course` in `REVIEW_PATTERNS`. Piracy and reseller sites copy your product names, so they look relevant and clean to every metric; this sends them to review instead of the Valuable bucket.
* **Every score here is a proxy.** DataForSEO's rank and spam score are its own metrics, the relevance score only sees metadata and is English-first, and Claude only sees metadata too. Spot-check anything you act on.
* Claude's verdicts vary a little between runs on identical input (54 of 64 matched in a repeat run on the sample data, with no disagreement on spam). `output/raw/claude/` keeps every response so you can act on a saved run.

MIT licence. Credit: Lazarina Stoy, MLforSEO.
