---
name: ai-citation-analysis
description: Run AI-citation (LLM mentions) analysis through the DataForSEO MCP without contaminated results — one topic per call, topic required in the question, a sample read before any aggregate, a known query to calibrate, cost confirmed before every call. Use when asked who is cited in AI answers for a topic, who is cited alongside a domain, or for an AI-visibility report.
---

# AI-citation analysis (The AI-powered Entity Audit, Practical 4.3)

## Before any call
1. Ask for: the topics (one per line, as a person would ask), the user's domain, the market
   (location and language), and one **known query** whose top cited sites the user can name.
2. Format each topic: lower case, no punctuation. **Refuse lines with several topics**
   ("a, b", "a and b") — split them. **Warn on a single generic word** ("entity", "semantic") and
   suggest a qualifier ("entity seo").
3. Show the plan as a table — endpoint, platform, target, why — with the cost:
   **$0.10 per task + $0.001 per row** (LLM Mentions, October 2026). Wait for "go".
4. ChatGPT data exists for United States + English only. Google = AI Overviews.

## The settings (calibrated 31 October 2026)
- Endpoint for samples: `POST /v3/ai_optimization/llm_mentions/search/live`
- Endpoint for aggregates: `POST /v3/ai_optimization/llm_mentions/top_domains/live`
- `target`: exactly one entity: `{"keyword": "<topic>", "search_scope": ["question"], "match_type": "word_match"}`
  — never put two keywords in one target array: they combine as AND.
- Scoped view: `{"domain": "<domain without www>", "search_scope": ["sources"]}` on `search/live`;
  count the other domains in each answer's `sources`.
- `links_scope: "sources"`; `items_list_limit: 10`; sample `limit: 20`, `order_by: ["ai_search_volume,desc"]`.
- `initial_dataset_filters` only take metadata (platform, location_code, language_code,
  ai_search_volume, first/last_response_at, model_name). They cannot fix a homonym — the
  question scope does.

## Order of work, every time
1. Scoped view first (reliable).
2. For each topic: **sample → show the questions → ask the user which are on-topic** → only
   then the `top_domains` aggregate.
3. Run the known query and ask whether the result matches what the user expected. If not,
   stop and say the instrument is not calibrated for this market.
4. After every call, report the response's `cost` and the running total.

## Reporting rules
- Label every topic result: **verified** (≥ 80% of sampled questions on-topic and the known
  query matched), otherwise **indicative** — and say indicative results are not for decisions.
- Date every number and state platform, location, language and the configuration.
- Never estimate a number that is not in a response. Never present AI search volume as traffic.
