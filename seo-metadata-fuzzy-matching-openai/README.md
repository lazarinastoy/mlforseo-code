# Fuzzy Booster: SEO metadata optimisation with fuzzy matching and OpenAI

Companion code for the MLforSEO tutorial **[How to Automatically Optimize your SEO Metadata with FuzzyWuzzy and OpenAI in Google Colab](https://www.mlforseo.com/machine-learning-implementation-guides/onpage-seo/how-to-automatically-optimize-your-seo-metadata-with-fuzzywuzzy-and-openai-in-google-colab/)**.

## What it does

The "Fuzzy Booster" method checks whether each page's title, meta description and h1 contain the search query that brings it the most clicks, and suggests a better title where they don't.

| Step | What happens |
|---|---|
| 1. Query parameters | Last 16 months, page + query, home page and branded queries excluded |
| 2. Search Console | Upload your credentials, pull up to 25,000 rows, keep the most-clicked query per page |
| 3. Scrape metadata | `<title>`, meta description and first `<h1>` for each page (BeautifulSoup) |
| 4. Clean text | Lowercase, strip numbers, punctuation and accents, remove stopwords (NLTK, any language) |
| 5. Fuzzy similarity | `token_set_ratio` (0-100) between the query and each element: `title_similarity`, `meta_similarity`, `h1_similarity` |
| 6. New titles (optional) | For titles scoring 60 or below, an OpenAI model writes a new title under 60 characters that includes the query. Results go to `fuzzy_booster.csv` |

## Files

| File | What it is |
|---|---|
| `fuzzy_booster.ipynb` | The Colab notebook, one cell per step from the post |
| `fuzzy_booster.py` | The same workflow as a command-line script |
| `sample_gsc_metadata.csv` | Eight made-up Spanish Search Console rows with scraped metadata, so you can try it without your own data |
| `test_fuzzy_booster.py` | Offline tests for the script and the notebook (OpenAI is mocked) |
| `requirements.txt` | Libraries for running locally |

## Run it

**Google Colab (easiest)**
1. Open `fuzzy_booster.ipynb` in Colab (File > Open notebook > GitHub, or upload it).
2. Add your OpenAI key as a Colab secret named `OPENAI_API_KEY` (key icon in the left sidebar) and let the notebook access it. Never paste the key into a cell.
3. Run the setup cell and Step 1, edit `site` and `branded_queries`, then run the rest. Step 2 asks for your credentials file.
4. No Search Console access yet? Run the **Sample data** cell instead of Steps 2 and 3.

**Locally**
```bash
pip install -r requirements.txt
python fuzzy_booster.py --sample --no-openai          # sample data, no API calls

export OPENAI_API_KEY=sk-...
python fuzzy_booster.py --site https://www.example.com/ --brand "example|exampel" \
    --credentials credentials.json --lang english --threshold 60
```
`--site` also takes a Domain property (`sc-domain:example.com`). `--model` defaults to `gpt-4o-mini`.

**Tests:** `python -m unittest test_fuzzy_booster.py -v`

## Search Console credentials

Follow the Google Cloud steps in the post: enable the **Google Search Console API**, set up the OAuth consent screen with the read-only Search Console scope, and create an **OAuth client ID of type Desktop app**. Download the JSON.

When you run Step 2 with that file, the notebook prints a sign-in link. Approve access and you'll be sent to a `http://localhost/...` address that won't load. That's expected: copy the whole address from the browser bar and paste it into the prompt. The token is saved to `token.json`, so you only sign in once per session.

A **service-account key** works too, with no sign-in: add the service account's email as a user on the Search Console property first.

## What changed from the original 2024 notebook

- **FuzzyWuzzy to RapidFuzz.** FuzzyWuzzy was renamed TheFuzz and the old package is archived. RapidFuzz has the same `fuzz.token_set_ratio`, is faster and maintained. Scores are rounded to whole numbers as before.
- **Search Console sign-in.** Google retired the out-of-band (`urn:ietf:wg:oauth:2.0:oob`) copy-paste flow the original used, so that cell now fails. It now uses the localhost redirect described above, and accepts service-account keys. It calls the current `searchconsole` v1 API. Domain properties get a working home-page regex.
- **OpenAI.** Current SDK (`from openai import OpenAI`), key from a Colab secret or `OPENAI_API_KEY`, default model `gpt-4o-mini` (cheaper; swap in a larger model if you like). The prompt asks for the title only.
- **Small fixes.** Request timeout and user agent when scraping; accented stopwords are matched after accents are stripped; `strip_quotes` no longer crashes on rows that didn't get a new title; the CSV download only runs in Colab.

## Cost and care

Every page under the threshold is one API call. Run on a small sample first. Check the site's terms before scraping pages you don't own.

## Tested with

Python 3.9, pandas 2.3, RapidFuzz 3.13, NLTK 3.9, openai 2.48 (mocked), google-auth-oauthlib 1.3 (auth URL generation only). Steps 4-6 executed end to end on the sample data in October 2026; the live Search Console and OpenAI calls were not executed in testing.
