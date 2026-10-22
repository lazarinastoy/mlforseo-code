# Internal link audit, topic clustering and internal linking automation with AI

Companion code for the MLforSEO guide **"7 ways to automate internal linking with AI"** by Lazarina Stoy (October 2026). The strategy behind it, and the audit framework from her BrightonSEO Spring 2022 talk, is written up on [lazarinastoy.com](https://lazarinastoy.com/how-to-incorporate-machine-learning-in-internal-linking-audits/).

Two pieces of code live here:

* **`internal_link_audit_topic_clustering.ipynb`**: the audit. Link metrics, anchor text classification, embeddings, topic clusters (hubs), bridge pages and unlinked similar pages. Colab-ready, no API keys.
* **`automate_internal_linking.py`**: the automation. A command-line script for the repeatable jobs: orphan and weak-page detection, passage-level link suggestions with anchor text (extractive or LLM) checked by guardrails, applying approved links to WordPress, and measuring the impact. Built to run on a schedule or be called by an agent.

## The audit notebook: what it does

`internal_link_audit_topic_clustering.ipynb` (Colab-ready, free CPU runtime is fine):

| Section | What you get | How |
|---|---|---|
| 3. Load data | Pages + internal links from a Screaming Frog crawl, or a demo dataset (about 70 mlforseo.com posts via the WordPress REST API) | pandas, requests, BeautifulSoup |
| 4. Link audit metrics | Inlinks, unique inlinks, in-content inlinks, orphan pages, broken / nofollow / UTM-tagged internal links | pandas |
| 5. Anchor text analysis | Generic, branded, mixed, exact-title and descriptive anchors; anchor length; top bigrams/trigrams | rules + scikit-learn `CountVectorizer` |
| 6. Embeddings | One vector per page; relative similarity threshold; possible duplicate pages (cosine >= 0.95) | sentence-transformers (`BAAI/bge-small-en-v1.5`), or embeddings exported from Screaming Frog |
| 7. Topic clustering | Clusters (auto k-means by silhouette, agglomerative or HDBSCAN), c-TF-IDF cluster names, pillar candidates, a 2D t-SNE map | scikit-learn |
| 8. Bridge pages | Pages close to two clusters (inter-cluster link candidates) | cosine similarity to cluster centroids |
| 9. Link opportunities | Similar page pairs that aren't linked yet, prioritised (pillars and pages without in-content inlinks first), with an anchor phrase found in the source page's own text | numpy, regex |
| 10. Export | CSVs + PNG for your audit deliverable | pandas, matplotlib |

## The automation script: `automate_internal_linking.py`

```bash
pip install -r requirements.txt          # plus `pip install anthropic` if you want LLM anchors
python automate_internal_linking.py orphans --site https://www.example.com --sitemap https://www.example.com/post-sitemap.xml
python automate_internal_linking.py suggest --site https://www.example.com --brand "example" "example brand"
# review link_suggestions.csv, put "yes" in the approve column for the links you want
WP_USER=me WP_APP_PASSWORD=xxxx python automate_internal_linking.py apply --site https://www.example.com            # dry run: prints a diff
WP_USER=me WP_APP_PASSWORD=xxxx python automate_internal_linking.py apply --site https://www.example.com --write    # saves
python automate_internal_linking.py measure --gsc-daily gsc_pages_by_date.csv --changes changed_pages.csv
```

Every command reads either a WordPress site's public REST API (`--site`, posts only, in-content links only) or Screaming Frog exports (`--sf-pages` custom extraction + `--sf-inlinks` All Inlinks, which also gives you menus, footers and `Crawl Depth`).

| Command | What it does | Output |
|---|---|---|
| `orphans` | Compares the crawl with your XML sitemap (and optionally a Search Console Pages export). Flags pages with no internal links, pages with no *contextual* links (only nav/footer/related posts), pages with one contextual link, pages deeper than 4 clicks (SF only) and crawled pages missing from the sitemap. | `orphan_report.csv` |
| `suggest` | Embeds every page and every paragraph (`BAAI/bge-small-en-v1.5`). For each similar page pair that isn't linked yet (top 10% of the site's similarity distribution, duplicates >= 0.95 excluded), finds the paragraph in the source that best matches the target, then picks an anchor: by default an **extractive** span from that paragraph ranked by similarity to the target title; with `--llm`, Claude picks the span. Pages with the fewest inlinks get first pick. | `link_suggestions.csv` with an empty `approve` column |
| `apply` | For rows marked `yes`: fetches the post's raw content (application password), links the first plain-text occurrence of the anchor inside a `<p>`/`<li>` (never inside an existing link, heading, code or button; skips posts that already link to the target), prints a diff. Saves only with `--write`; WordPress keeps a revision. | diff + `apply_log.csv` |
| `measure` | Daily Search Console clicks/impressions for the pages that got links vs pages you didn't touch, before vs after (with a lag for recrawling): a difference-in-differences sanity check. | `impact_summary.csv` |

### Anchor guardrails

Every anchor, from either method, must pass all of these or it is dropped with a reason in `llm_rejected`:

* found **verbatim** in the paragraph (the LLM may not rewrite or invent copy),
* 2 to 7 words, not generic ("click here", "read more"...), not the brand on its own, no stop word at either end,
* at most 3 new links per source page per run, one new link per paragraph (no chained links),
* the same anchor used for a target at most twice (counting existing links), and never one anchor pointing to two different targets from the same page.

These follow Google's guidance that good anchor text is "descriptive, reasonably concise, and relevant", and its warnings against keyword-stuffed anchors and chained links ([Link best practices](https://developers.google.com/search/docs/crawling-indexing/links-crawlable)).

### LLM anchors (`--llm`)

Uses the Anthropic Python SDK (`pip install anthropic`, `ANTHROPIC_API_KEY` set). Default model `claude-opus-5-5` at low effort with JSON structured output; change it with `--llm-model`. `--llm-limit` (default 50) caps the calls per run. Server-side refusal fallback is switched on (`fallbacks="default"`). If the call fails or the anchor fails the guardrails, the extractive anchor is kept and the rejection is logged.

### Scheduling and agents

`examples/weekly-internal-link-suggestions.yml` is a GitHub Actions workflow that runs `orphans` + `suggest` every Monday and attaches the CSVs to the run. The same commands work as tools for an agent (Claude Code, or an MCP client alongside the Screaming Frog SEO Spider MCP server in v24+): let the agent run the crawl and the script, and keep `apply --write` behind a human approval.

### Tested (automation script)

22 October 2026 on mlforseo.com via the REST API (79 posts, 643 in-content links, 5,375 paragraphs): `orphans` found 24 posts with no in-content links from other posts, 19 with one, and 12 crawled posts missing from the XML sitemap; `suggest` turned 432 unlinked similar pairs into 153 guardrail-passing suggestions across 64 source posts in under 2 minutes on a laptop CPU, and skipped 3 duplicate post pairs. `apply` was tested offline on sample block markup (it was not run against a live site). `measure` was tested on synthetic data with a known uplift. The `--llm` path was tested with a mocked client (request shape, JSON parsing, guardrail rejections of invented and generic anchors); it has not been run against the live API. Samples: `example_outputs/orphan_report.csv`, `example_outputs/link_suggestions_sample.csv`.

Honest caveat from the test run: the extractive anchors are a shortlist. Some read well ("semantic keyword research", "entity recognition"), others are clumsy fragments of a sentence. That's why `approve` starts empty.

## Using your own crawl (Screaming Frog SEO Spider)

Custom extraction and crawls over 500 URLs need a paid licence.

1. **Content:** *Configuration > Custom > Custom Extraction*, click *Add*, choose *CSSPath* (or *XPath*), paste the selector for your main content area (or use the visual browser to click it), set it to *Extract Text*, name it. Crawl, then export the **Custom Extraction** tab. You need `Address` and your extractor column (for example `Content 1`). Add `Title 1` if you can.
2. **Links:** *Bulk Export > Links > All Inlinks*.
3. In the notebook set `DATA_SOURCE = "screaming_frog"` and the file and column names.

Optional: if you generate embeddings inside the SEO Spider (v22+, *Config > API Access > AI* plus *Config > Content > Embeddings*) and export them as a column, set `SF_EMBEDDINGS_COL` and the notebook uses those instead of computing its own.

## Requirements

* Python 3.9+ (tested locally on 3.9; Colab runs 3.11/3.12)
* `sentence-transformers>=3.0`, `scikit-learn>=1.3` (for the built-in HDBSCAN), `pandas>=2.0`, `numpy`, `requests`, `beautifulsoup4`, `matplotlib`
* No API keys. The embedding model (about 130 MB) downloads from Hugging Face on first run.

```bash
pip install -r requirements.txt
```

In Colab, the first code cell installs what's missing.

## Tested

22 October 2026, end to end on both inputs: the demo dataset (68 mlforseo.com posts, 377 in-content links) and a synthetic Screaming Frog export with the real *All Inlinks* column layout. Versions: sentence-transformers 5.1.2, scikit-learn 1.6.1, pandas 2.3.3, numpy 1.26.4, torch 2.8.0. Embedding 68 pages took about 4 seconds on a laptop CPU.

Example outputs from the demo run are in `example_outputs/` (18 clusters chosen automatically, 219 link suggestions, 3 duplicate post pairs).

## Notes and caveats

* **Similarity thresholds are relative.** Different embedding models score differently (bge-small rates almost every pair above 0.6; MiniLM rarely does), so link suggestions use a percentile of your own site's similarity distribution (`SIMILARITY_PERCENTILE = 90`).
* **The demo only sees in-content links** (the WordPress API returns the post body, not menus or footers), so its orphan count is "pages with no contextual links", not true orphans. A Screaming Frog crawl gives you every link and its *Link Position*.
* **Suggestions are a shortlist, not a to-do list.** Read them before you add anything.

## Files

* `internal_link_audit_topic_clustering.ipynb`: the audit notebook (outputs cleared)
* `automate_internal_linking.py`: the automation script (orphans, suggest, apply, measure)
* `examples/weekly-internal-link-suggestions.yml`: scheduled GitHub Actions example
* `requirements.txt` (`anthropic` is optional, only for `--llm`)
* `example_outputs/`: cluster map, cluster summary, link opportunities and duplicates from the notebook demo run; orphan report and a link-suggestion sample from the script
