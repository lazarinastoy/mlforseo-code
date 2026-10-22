# Structured data automation with Python (2026)

Companion code for the MLforSEO guide **"Structured Data Automation with Python: Detect, Generate and Validate JSON-LD at Scale"** by Lazarina Stoy. Lazarina started the guide as a draft in 2024 and finished it in October 2026.

One script, `sd_toolkit.py`, with three commands that follow the three steps of the guide.

| Command | What it does |
|---|---|
| `audit` | For each URL: extracts the structured data already on the page (JSON-LD, Microdata, RDFa via `extruct`), runs a **rule-based page classifier** to flag structured data opportunities, marks whether Google still shows a rich result for each one, and validates what's there. Writes one CSV row per URL. |
| `generate` | Builds JSON-LD from a **data source** (a CSV, or any SQL query; SQLite example included) instead of typing it into a generator page by page. Each page gets one connected `@graph`: Organization, WebSite, WebPage, BreadcrumbList (from the URL), and the main entity (Article/BlogPosting, Product, Event or Course). Writes a `.json` and a ready-to-paste `<script>` tag per page. |
| `validate` | Validates a JSON-LD file or a live URL against (a) the **current schema.org vocabulary** (unknown types, unknown, superseded or misplaced properties), (b) **Google's required and recommended properties** for the rich results that still exist, and (c) the page's **visible text** (markup that doesn't match the page is a structured data policy violation). |

## Quick start

```bash
pip install -r requirements.txt

# audit some pages
printf "https://www.example.com/\nhttps://www.example.com/blog/some-post/\n" > urls.txt
python sd_toolkit.py audit --urls urls.txt --out structured_data_audit.csv

# generate JSON-LD from the sample CSV
python sd_toolkit.py generate --csv example_data/pages.csv --site example_data/site.json --out-dir jsonld/

# ...or from a database
python example_data/make_demo_db.py
python sd_toolkit.py generate --sqlite example_data/demo.db --query "SELECT * FROM products" \
    --site example_data/site.json --out-dir jsonld/

# validate a file, or the markup on a live page
python sd_toolkit.py validate --file jsonld/shop__seo-workbook.json
python sd_toolkit.py validate --url https://www.example.com/blog/some-post/
```

**In Google Colab:** upload `sd_toolkit.py` and `example_data/`, run `!pip install -q extruct` and then `!python sd_toolkit.py ...`. Or `from sd_toolkit import *` and call `audit_url()`, `page_graph()` and `validate_jsonld()` directly.

The first validation downloads the schema.org vocabulary (about 1.5 MB, `schemaorg-current-https.jsonld`) and caches it next to the script. Delete the cache file to pick up a new schema.org release.

## Data source format

Columns are named after schema.org properties so the mapping stays obvious. `example_data/pages.csv`:

| Column | Used for |
|---|---|
| `url`, `type` | Required. `type` is `BlogPosting`, `Article`, `NewsArticle`, `Product`, `Event` or `Course` |
| `title`, `description`, `image`, `datePublished`, `dateModified`, `author_name`, `author_url` | Articles |
| `name`, `description`, `image`, `price`, `priceCurrency`, `availability` (e.g. `InStock`), `sku`, `brand` | Products |
| `name`, `startDate`, `endDate`, `location_name`, `location_address`, `online_url` | Events |
| `name`, `description` | Courses (Google needs at least three on a list page for the course carousel) |

`site.json` holds the shared Organization/WebSite details and optional labels for URL segments in breadcrumbs.

Empty values are dropped, so the markup only states what you actually know. To add a page type, add a branch to `page_graph()`.

## Google rich result status used by the checks (22 October 2026)

| Status | Types |
|---|---|
| Still a Google Search feature | Article/BlogPosting/NewsArticle, Breadcrumb, Product (snippets and merchant listings), Event, JobPosting, VideoObject, Recipe, Course list, Organization, LocalBusiness, ProfilePage, DiscussionForumPosting, Q&A, Review snippet, Software app, WebSite (site names) |
| Retired from Google Search (still valid schema.org) | **FAQPage** (stopped 7 May 2026), **HowTo** (2023), Course info, Vehicle listing, Estimated salary, Learning video, Special announcement (2025), Practice problems (Jan 2026), sitelinks search box (Nov 2024); ClaimReview is being phased out (Fact Check Explorer still uses it) |
| Other | Dataset is only used by Dataset Search, not Google Search (Nov 2025) |

Sources: Google Search Central [documentation updates](https://developers.google.com/search/updates), [Simplifying the search results page (June 2025)](https://developers.google.com/search/blog/2025/06/simplifying-search-results), [update (Nov 2025)](https://developers.google.com/search/blog/2025/11/update-on-our-efforts), and the [search gallery](https://developers.google.com/search/docs/appearance/structured-data/search-gallery). Retired markup does no harm. Other consumers (Bing, AI assistants, knowledge graphs) can still read it, so keep it if it matches the page. Just don't expect a Google rich result from it.

## Limits

* The classifier is rule-based on purpose: every suggestion says which signal fired, so you can check it. It suggests; it doesn't decide. Review the audit before you generate anything.
* `validate` checks the vocabulary, Google's required and recommended properties for the top-level node (plus breadcrumb list items), and a visible-text match for names, headlines and prices. It doesn't replace Google's [Rich Results Test](https://search.google.com/test/rich-results), which has no public API. Spot-check a sample of templates there, and use the [Schema Markup Validator](https://validator.schema.org/) for anything outside Google's features.
* `audit` reads the HTML the server returns. Markup injected by JavaScript (for example through Google Tag Manager) won't show up. Render those pages first (Playwright) or test them in the Rich Results Test.

## Tested

Tested on 22 October 2026 with Python 3.9, extruct 0.18, beautifulsoup4 4.15, lxml 6.1, pandas 2.3 and schema.org V30.1 (2026-09-16). `generate` ran on the sample CSV (5 pages) and the SQLite demo (2 products). `validate` ran on generated files and on a deliberately broken file (unknown type, unknown property, missing Offer price, invalid JSON, FAQPage); every problem was caught. `audit` ran on five live pages (WordPress with Rank Math, Astra and Sensei/WooCommerce templates).

## Licence

MIT (see the repository root).
