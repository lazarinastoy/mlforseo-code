# Knowledge Panel & Brand SERP Audit Checklist

A free, step-by-step audit of your Google knowledge panel eligibility and brand SERP: what page one shows for your name, whether Google's Knowledge Graph recognises you, Wikidata status, sameAs and markup, cross-platform consistency, claiming the panel, and a prioritised action plan. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/), built on [Beatrice Gamba](https://www.mlforseo.com/experts/beatrice-gamba/)'s entity SEO articles. Checked October 2026.

**Google Sheets version:** *(Make a copy link coming soon. Until then, download `knowledge-panel-audit-checklist.xlsx` and open it in Google Sheets or Excel.)*
**Read it on GitHub:** [`checklist.md`](checklist.md)
**Companion article:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

## What's inside

| Tab | What it does |
|---|---|
| Start here | How to use it, legends, realistic expectations, credits |
| Checklist | 36 checks in 8 areas: brand SERP baseline, Knowledge Graph status, Wikidata and Wikipedia, on-site entity markup, cross-platform consistency, corroboration, claim and manage, monitor |
| Fact sheet | Your single source of truth (name, legal name, founding date, founders, URL, description and more) compared across nine platforms. Cells that disagree turn red and are counted |
| Brand SERP log | One row per page-one result: owned, official profile, third party (positive / neutral / negative) or namesake, SERP feature, accuracy |
| KG lookup log | Dated Knowledge Graph Search API results: ID, name, type, description, resultScore, whether it's you, panel status |
| Action plan | Eight prioritised actions, from fixing your own markup to earning independent coverage, with owners and dates |
| Progress | Completion by area and priority, owned share of page one, negative and inaccurate results, fact mismatches, actions done |

Works for organisations and for people (founders, authors, consultants).

## How to use it

1. Make your own copy (Google Sheets) or download the `.xlsx`.
2. Fill in column B of the Fact sheet first: everything is checked against it.
3. Work through the Checklist in order, logging results in the Brand SERP log and KG lookup log.
4. Turn findings into the Action plan and track it on the Progress tab. Repeat monthly (quick) and quarterly (full).

For the Knowledge Graph lookups you can use Google's API Explorer, or the free [Knowledge Graph API notebook](https://www.mlforseo.com/resource/knowledge-graph-api-extraction-and-entity-relationship-analysis-for-semantic-keyword-research-notebook/) with your own API key.

## Files

| File | What it is |
|---|---|
| `knowledge-panel-audit-checklist.xlsx` | The workbook (Google-Sheets-ready: dropdowns, conditional formatting, COUNTIF / COUNTIFS / SUMPRODUCT formulas) |
| `checklist.md` | The same 36 checks and the action plan in plain Markdown |
| `checks.csv` | The checks as data |
| `build.py` | Rebuilds the `.xlsx` and `checklist.md` from `checks.csv` (`pip install openpyxl`, then `python build.py`) |
| `SETUP.md` | How to publish the workbook as a Google Sheets "Make a copy" template |

## Sources

MLforSEO's entity SEO articles (knowledge panels, Wikidata for brands, cross-platform consistency, schema.org @id, entity disambiguation, navigation and salience, trust and corroboration), then official documentation: [Google's knowledge panel help](https://support.google.com/knowledgepanel/answer/9163198), [Get verified on Google](https://support.google.com/knowledgepanel/answer/7534902), [Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization), the [Knowledge Graph Search API](https://developers.google.com/knowledge-graph), [Wikidata's notability policy](https://www.wikidata.org/wiki/Wikidata:Notability), [Wikipedia's conflict of interest guideline](https://en.wikipedia.org/wiki/Wikipedia:Conflict_of_interest) and [schema.org sameAs](https://schema.org/sameAs).

Google doesn't publish a threshold for showing a knowledge panel and you can't request one. In MLforSEO's experience it takes six to eighteen months of consistent signals for most brands.

## Go deeper

[AI Search & LLMs: Entity SEO and Knowledge Graph Strategies for Brands](https://www.mlforseo.com/courses/ai-search-llms-entity-seo-and-knowledge-graph-strategies-for-brands/) on MLforSEO Academy.

## Credit and licence

Created by Lazarina Stoy · MLforSEO. MIT licence (see the repository root). Free to use and adapt; please keep the credit.
