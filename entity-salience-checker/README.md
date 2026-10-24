# Entity salience checker (Google Cloud Natural Language API v1, page vs target entity)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/entity-salience-checker/entity_salience_checker.ipynb)

A free notebook by **Lazarina Stoy, MLforSEO**. It checks whether a page is about the entity you think it is, as far as Google's Natural Language API can tell, and compares it with competitor pages on the same topic.

It's a lite version of one check from the **Clarity** step of the 5C framework (Clarity, Coverage, Consistency, Connection, Corroboration) taught in the course [The AI-powered Entity Audit](https://www.mlforseo.com/courses/the-ai-powered-entity-audit/).

## What it does

| Step | What you get |
|---|---|
| 1. Fetch and extract | Main text with `trafilatura`, full visible text, title, H1, H2/H3 and the nav/header/footer/sidebar text |
| 2. Estimate cost | Billable units (1,000 characters per unit, rounded up per request) before any call |
| 3. Analyse | Cloud Natural Language API **v1** `documents:analyzeEntities` (`encodingType: UTF32`), responses cached locally |
| 4. Entities | Ranked by salience, with type, mentions, Knowledge Graph MID and Wikipedia URL when returned, first-mention position and a boilerplate flag |
| 5. Clarity check | Target rank and salience, whether it's split across synonyms, KG link, first mention, title/H1/subheading use, boilerplate entities above it, a lite 0-3 score and plain-English tips |
| 6. Competitors | Your page's target salience vs competitor pages for the same target |
| 7. Main vs full text | How much the page template changes what the page looks like it's about |
| 8. Export | `entity_salience_report.xlsx` (Sheets-ready, conditional formatting) plus CSVs |

## Why v1, and what salience is

Salience is only in the **v1** API. The v2 `Entity` object has `name`, `type`, `metadata`, `mentions` and `sentiment`, and no `salience` field. I checked this against the official v1 and v2 REST references and the v1/v2 discovery documents (revision 20260614) in October 2026.

Salience is the Natural Language API's estimate (0 to 1) of how central an entity is to the text you send. It's a useful, repeatable diagnostic for "what is this page about to a machine". Google hasn't said that Search or its AI features use this score, and LLM-based assistants don't call this API, so don't treat it as a ranking factor.

## Run it

**Google Colab:** click the badge and run all cells. With `USE_SAMPLE = True` (the default) it needs no key.

**Locally:**

```bash
pip install -r requirements.txt
jupyter notebook entity_salience_checker.ipynb
```

Tested 24 October 2026 on Python 3.9 with pandas 2.3.3, trafilatura 2.0.0 and openpyxl 3.1.5, in sample mode end to end. The live path (fetch, API call, caching) was tested with a mocked API response; it wasn't run against the paid API for this release.

## Live mode

1. Enable the **Cloud Natural Language API** in a Google Cloud project with billing on.
2. Create an API key (restrict it to that API) and add it as a Colab secret named `GOOGLE_NL_API_KEY`. Otherwise the notebook asks for it with a hidden prompt. It's sent in a request header and never printed or saved.
3. Set `USE_SAMPLE = False` and fill in `PAGES` (or a CSV): `url`, `role` (`yours` / `competitor`), `target_entity`, `target_aliases` (`;`-separated) and, optionally, `target_wikipedia_url` or `target_mid`.

**Cost:** entity analysis is billed per unit of up to 1,000 characters per request, rounded up. The first 5,000 units each month are free; check the [official pricing page](https://cloud.google.com/natural-language/pricing) for the rate above that. A typical article is a handful of units, and `COMPARE_FULL_TEXT` adds one more request per page of yours.

## Sample data

Everything in `sample_data/` is labelled sample:

* `html/`: three **fictional** pages about the French press (Brewly, Coffee One, Daily Grind Notes are made up).
* `responses/`: **sample** API responses for each page's main and full text. They follow the v1 `analyzeEntities` response schema exactly (`entities[].name/type/metadata/salience/mentions[].text.content/beginOffset/type`, `language`), but the salience values come from a stand-in formula in `make_sample_responses.py`, not from Google. The Knowledge Graph MIDs and Wikipedia URLs are real (looked up from Wikidata's Freebase ID property, P646).
* `pages_SAMPLE.csv`: the page list with targets and aliases.
* `example_report_SAMPLE.xlsx`: the report the notebook produces from the sample.

## Limits

* Main-text extraction can miss content (tabs, accordions, JavaScript-rendered text) or keep in-article boilerplate. JavaScript-heavy pages may need a rendered crawl.
* Salience is relative within one document, so ranks compare better across pages than raw values do.
* Many valid entities come back without a MID, especially niche terms and small brands.
* Entity analysis supports a limited set of languages.
* The lite clarity score and tips are this notebook's own simple rubric. The full Clarity scoring in the course goes further.

## Related

* Beatrice Gamba: [Why Navigation Elements Outrank Your Brand in Entity Analysis](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/why-navigation-elements-outrank-your-brand-in-entity-analysis/)
* [Entity Analysis with Google Cloud Natural Language API (No-Code Template)](https://www.mlforseo.com/resource/entity-analysis-with-with-google-cloud-natural-language-api-no-code-template/)
* [Extracting Entities with Google Cloud Natural Language API in Python](https://www.mlforseo.com/resource/extracting-entities-with-google-cloud-natural-language-api-in-python-tutorial/)
* Course: [The AI-powered Entity Audit](https://www.mlforseo.com/courses/the-ai-powered-entity-audit/)

## Licence

MIT, like the rest of this repository. Credit: Lazarina Stoy, MLforSEO.
