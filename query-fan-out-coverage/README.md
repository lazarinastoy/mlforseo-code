# Query fan-out simulator and coverage checker

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/query-fan-out-coverage/query_fan_out_coverage.ipynb)

By **Lazarina Stoy, [MLforSEO](https://www.mlforseo.com/)**. Simulate the sub-queries an AI search system might fan a query out into, then check, passage by passage, how well your page(s) cover each one.

Google describes AI Mode and AI Overviews as using a "query fan-out" technique: "issuing multiple related searches concurrently across subtopics and multiple data sources" ([Google, March 2025](https://blog.google/products/search/ai-mode-search/); see also [May 2025](https://blog.google/products/search/google-search-ai-mode-update/) and Search Central's [AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)). Google does not publish the sub-queries themselves, so **this notebook simulates them**. Treat its output as a structured brainstorm and a content-gap check, not a view into Google.

## What it does

| Section | What you get |
|---|---|
| 1. Settings | Seed query, page URLs, fan-out method, LLM provider and model, thresholds |
| 2. Fan-out | Sub-queries from (a) a free rule-based expansion (product, concept and "how to" template sets) and/or (b) an LLM via a documented, editable prompt. Pluggable provider: OpenAI (Responses API), Anthropic (Messages API) or Gemini (Google Gen AI SDK) |
| 3. Passages | Fetches each page, extracts the main content (trafilatura, BeautifulSoup fallback) and splits it into heading-aware passages |
| 4. Coverage | Stage 1: `multi-qa-MiniLM-L6-cos-v1` embeddings shortlist the closest passages by cosine similarity. Stage 2: `ms-marco-MiniLM-L6-v2` cross-encoder reranks them. Each sub-query is labelled covered / partial / gap (cosine-only mode available) |
| 5. Gaps | Gap list with suggested actions, and a per-page view of which page "owns" which sub-queries |
| 6. Export | `fanout_coverage_<seed>.csv`, `fanout_gaps_<seed>.csv`, and an `.xlsx` with Coverage, Gaps and Passages tabs (import into Google Sheets) |

## Requirements

* Python 3.10+ (tested 24 October 2026 on Python 3.12 with sentence-transformers 6.2, trafilatura 2.3 and pandas 3.1, on a CPU; the sample run takes about a minute including model downloads). Colab works out of the box.
* No API key for the sample run or for rule-based fan-out.
* Optional LLM fan-out: an OpenAI, Anthropic or Gemini API key, read at runtime from Colab secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) or a hidden prompt. One short call per seed query. Default models (October 2026): `gpt-6-luna`, `claude-haiku-5-5`, `gemini-3.5-flash-lite`; change them in `LLM_MODELS`.

```bash
pip install -r requirements.txt
# plus the SDK for your provider: openai, anthropic or google-genai
```

## Notes and limits

* This simulates fan-out. Google's real sub-queries are not public, vary by user and context, and draw on sources beyond web pages.
* Scores measure relevance, not answer quality. Read the matched passages.
* Thresholds were set on the sample pages. Check 10 to 15 rows of your own output and adjust.
* Both default models are English. For other languages use a multilingual embedding model with `SCORING = "cosine"`.
* Pages that need JavaScript to render may come back empty; paste their text into a `.txt` file (see `sample_data/README.md`) and add it to `LOCAL_TEXT_FILES`.
* The sample pages and the example LLM output are fictional and labelled as such.

## Related

* Guide: [How entities power query fan-out in AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/how-entities-power-query-fan-out-in-ai-search/)
* Guide: [What are synthetic queries?](https://www.mlforseo.com/ml-fundamentals/what-are-synthetic-queries-semantic-seo-ai-search/)
* Course: [Semantic ML-enabled Keyword Research](https://www.mlforseo.com/courses/semantic-ml-enabled-keyword-research/)
* Course: [AI Search Optimisation & Agentic SEO](https://www.mlforseo.com/courses/ai-search-optimisation-agentic-seo/)

## Files

* `query_fan_out_coverage.ipynb`: the notebook (saved with outputs from the sample run)
* `requirements.txt`
* `sample_data/`: fictional sample pages and an illustrative fan-out example

Made by Lazarina Stoy, MLforSEO. MIT licence.
