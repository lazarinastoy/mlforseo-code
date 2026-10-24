# Generative Engine Optimisation (GEO) Checklist

A free, 44-point checklist for getting your content found, understood, trusted and cited by AI search systems: Google AI Overviews and AI Mode, ChatGPT, Perplexity, Claude, Gemini and Copilot. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/), built on [Beatrice Gamba](https://www.mlforseo.com/experts/beatrice-gamba/)'s AI search series. Checked October 2026.

**Google Sheets version:** *(Make a copy link coming soon. Until then, download `geo-checklist.xlsx` and open it in Google Sheets or Excel.)*
**Read it on GitHub:** [`checklist.md`](checklist.md)

## What's inside

| Tab | What it does |
|---|---|
| Start here | How to use it, status / priority / evidence legends, credits |
| Checklist | 44 checks in 8 areas: crawl access, indexing and eligibility, entity clarity, chunk extractability, claim quality, structured data, trust and corroboration, measurement. Each has why it matters, how to check it (tool and where), priority, evidence level, status dropdown, owner, notes and links to the MLforSEO article and official docs |
| AI crawlers | 15 user-agent tokens (Googlebot, Google-Extended, Bingbot, OAI-SearchBot, GPTBot, ChatGPT-User, Claude-SearchBot, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User, Applebot, Applebot-Extended, Meta-ExternalAgent, CCBot): what each does, what blocking it does, and your decision |
| Prompt tracker | Log real customer questions per assistant: mentioned, cited, accurate, how you appear, competitors named |
| Progress | % complete by area and priority, open High-priority checks, and mention, citation and accuracy rates by assistant |

Every check carries an **evidence level** so you know what's documented and what isn't: Google-documented, Platform-documented, Research-backed, MLforSEO practice, or Unconfirmed (optional). For example, llms.txt is marked Unconfirmed: it's a proposed standard that no major AI provider has confirmed reading, and Google says you don't need AI text files to appear in its AI features.

## How to use it

1. Make your own copy (Google Sheets) or download the `.xlsx`.
2. Work through the Checklist area by area: set Status, Owner and Notes. Mark anything irrelevant as N/A.
3. Filter by Priority = High and Status = Not started for your first sprint.
4. Fill in the AI crawlers tab while you check robots.txt, and start the Prompt tracker with 10 to 50 real customer questions.
5. Rerun the prompts monthly and watch the Progress tab.

## Files

| File | What it is |
|---|---|
| `geo-checklist.xlsx` | The workbook (Google-Sheets-ready: dropdowns, conditional formatting, COUNTIF/COUNTIFS formulas only) |
| `checklist.md` | The same 44 checks in plain Markdown |
| `checks.csv` | The checks as data (source for the workbook and the Markdown) |
| `build.py` | Rebuilds the `.xlsx` and `checklist.md` from `checks.csv` (`pip install openpyxl`, then `python build.py`) |
| `SETUP.md` | How to publish the workbook as a Google Sheets "Make a copy" template |

## Sources

Grounded first in MLforSEO's AI search articles (indexed vs selected, the five-stage retrieval funnel, the chunk not the page, vagueness, robots.txt and llms.txt, trust and corroboration, structured data consistency, agentic audiences, dark AI traffic, and the entity SEO series), then in official documentation: [Google's AI features guide](https://developers.google.com/search/docs/appearance/ai-features), [Google's common crawlers](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers), [OpenAI](https://platform.openai.com/docs/bots), [Anthropic](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) and [Perplexity](https://docs.perplexity.ai/guides/bots) crawler docs, [schema.org](https://schema.org/), and research including [Aggarwal et al., GEO (KDD 2024)](https://arxiv.org/abs/2311.09735). Links are in each row.

No checklist can guarantee citations: AI answers vary by prompt, location, account and run. Use it to remove the reasons you'd be skipped, then measure.

## Go deeper

[AI Search Optimisation & Agentic SEO](https://www.mlforseo.com/courses/ai-search-optimisation-agentic-seo/) on MLforSEO Academy.

## Credit and licence

Created by Lazarina Stoy · MLforSEO. MIT licence (see the repository root). Free to use and adapt; please keep the credit.
