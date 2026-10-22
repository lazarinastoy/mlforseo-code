# Screaming Frog web scraping: from custom extraction to an NLP-ready dataset

Companion code for the MLforSEO guide **"Web scraping of page content in 3 easy steps with Screaming Frog"** by Lazarina Stoy (first published 2021, refreshed October 2026 for Screaming Frog SEO Spider v24).

The scraping in the guide is code-free. This notebook covers the steps either side of it.

## What it does

`screaming_frog_scraping_to_dataset.ipynb` (Colab-ready):

| Section | What you get |
|---|---|
| 1. Test your CSS selector | Fetches a few URLs (checks robots.txt, waits between requests) and shows what your selector would extract: number of matches, word count, preview. Catch a bad selector before a big crawl. |
| 2. Clean the export | Loads the Screaming Frog **Custom Extraction** export, merges multi-match columns (`Content 1`, `Content 2`...), normalises whitespace, drops thin pages and exact duplicates, adds word counts. |
| 3. Save | `page_content_dataset.csv` and `page_content_dataset.jsonl` for NLP, embeddings, topic modelling. |

## The Screaming Frog side (v24.3, checked 22 October 2026)

1. *Configuration > Custom > Custom Extraction*, click **Add**.
2. Name the extractor (the name becomes the column header), choose **CSSPath**, **XPath** or **Regex**, paste your expression, and pick **Extract Text** (other options: Extract HTML Element, Extract Inner HTML, Function Value). Or click the browser icon to open **Visual Custom Extraction** and click the element on the page instead.
3. Crawl, then open the **Custom Extraction** tab and export.

Custom extraction is a paid feature (licence £199 a year at the time of writing). The free version crawls up to 500 URLs and doesn't include it.

## Requirements

* Python 3.9+ (tested on 3.9; Colab runs 3.11/3.12)
* `pandas>=2.0`, `requests`, `beautifulsoup4`

## Tested

22 October 2026: section 1 against two live mlforseo.com posts with `.entry-content` (1 match each, 5,138 and 6,806 words), sections 2-3 on that output.

## Caveat

Section 1 reads raw HTML. If a site loads its content with JavaScript, the test returns nothing even though a Screaming Frog crawl in JavaScript rendering mode would work. Only scrape sites you're allowed to, and keep the request rate low.
