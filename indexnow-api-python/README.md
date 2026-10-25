# IndexNow API with Python (2026 refresh)

Companion code for the MLforSEO guide **"The Ultimate Guide to the IndexNow API: Instant Indexing for Bing, Yandex and Other Search Engines (with Python)"** by Lazarina Stoy. The guide first appeared on lazarinastoy.com in June 2022 and was refreshed in October 2026.

## What's in here

| File | What it does |
|---|---|
| `indexnow_submit.py` | Generates a key and key file, checks the key file is live, collects URLs from a sitemap or a file, and bulk-submits them to IndexNow in batches of up to 10,000. It logs every URL it sends. |
| `check_indexation_gsc.py` | Checks whether the submitted URLs are indexed in Google, using the Search Console URL Inspection API. It replaces the 2022 `site:` Apps Script. Optional. |
| `requirements.txt` | `requests`, plus the Google client libraries for the optional checker. |

## Quick start

```bash
pip install -r requirements.txt

# 1. make a key (writes {key}.txt; upload it to your site root)
python indexnow_submit.py generate-key

# 2. check search engines will be able to read it
python indexnow_submit.py check-key --host www.example.com --key YOURKEY

# 3. dry run: see what would be sent, send nothing
python indexnow_submit.py submit --host www.example.com --key YOURKEY \
    --sitemap https://www.example.com/sitemap_index.xml --since 2026-10-01 --dry-run

# 4. submit for real
python indexnow_submit.py submit --host www.example.com --key YOURKEY \
    --sitemap https://www.example.com/sitemap_index.xml --since 2026-10-01
```

Other inputs:

```bash
# a crawler or log-analyser export (JSON lines, CSV or JSON). The URL column/field is found
# automatically (url, URL, Address, loc), or set it with --url-field
python indexnow_submit.py submit --host www.example.com --key YOURKEY --urls-file not_indexed.jsonl

# a plain text file, one URL per line
python indexnow_submit.py submit --host www.example.com --key YOURKEY --urls-file urls.txt

# one or two URLs
python indexnow_submit.py submit --host www.example.com --key YOURKEY \
    --url https://www.example.com/new-page/ --url https://www.example.com/updated-page/
```

You can set the key once with `export INDEXNOW_KEY=...` instead of passing `--key`.

**In Google Colab:** upload `indexnow_submit.py`, then run `!python indexnow_submit.py submit ...` in a cell.

### Useful options

| Option | Default | Notes |
|---|---|---|
| `--engine` | `indexnow` (api.indexnow.org) | Or `bing`, `yandex`, `seznam`, `naver`, `yep`, or a full endpoint URL. Every participating engine receives your URLs, whichever endpoint you use. |
| `--key-location` | key at the site root | Full URL of the key file if it isn't at the root. Its folder limits which URLs the key covers. |
| `--batch-size` | 10,000 | The protocol maximum per request |
| `--pause` | 10 s | Wait between batches |
| `--limit` | none | Send only the first N URLs (good for a first test) |
| `--log` | `indexnow_submissions.csv` | One row per URL: url, batch, status, submitted_at. Upload it to Google Sheets and use it in Data Studio. |

## What the script protects you from

| Problem | HTTP code | What the script does |
|---|---|---|
| URLs that aren't on your host | 422 | Filters them out before sending (and tells you how many) |
| Key file missing, unreachable or wrong | 403 | Checks the key file before the first batch and stops if it's wrong |
| Key in the wrong format | 422 | Checks it's 8-128 characters of a-z, A-Z, 0-9 and dashes |
| Sending too much too fast | 429 | Waits 30 s, 60 s, 120 s, 240 s (plus jitter) and retries |
| A batch fails | any non-2xx | Stops, so the rest of the list isn't wasted, and logs what was sent |
| Duplicates | - | Removes them, keeping the original order |

`200` means the URLs were received. `202` means they were received and the key is still being validated, which is normal for a new key. Neither one means "indexed".

## Tested

Tested on 22 October 2026 with Python 3.9 and requests 2.32:

* Full submit flow against a local mock endpoint: sitemap index, then child sitemap, then `--since` filter, then off-host URL removal, then key file check, then 3 batches, with one simulated 429 retried and recovered. The script stopped correctly on a simulated 403. All file formats (`.txt`, `.csv`, `.json`, `.jsonl`) were parsed.
* Dry run against a live 300-URL Rank Math sitemap index.
* Live error responses from `api.indexnow.org`, using a dummy key for `www.example.com` (no real site submitted): wrong key → 403 `UserForbiddedToAccessSite`, off-host URL → 422, malformed key → 422, non-JSON body → 400.
* Real submissions (25 October 2026): 219 new URLs on www.mlforseo.com and 412 URLs from the datastudioformarketers.com sitemap (two redirecting URLs filtered out first), both using Rank Math's existing IndexNow key file. Key check passed on both sites and each batch returned HTTP 200 ("URLs received").

We didn't send a real submission, because that needs a key file hosted on a site you own. Run `--limit 5` first on your own site.

`check_indexation_gsc.py` was tested for response parsing with a mocked API response. It needs your own service account with access to a Search Console property.

## What changed from the 2022 code

| 2022 | Problem | 2026 |
|---|---|---|
| `requests.post("https://bing.com/", data=data, ...)` | Posted to Bing's **home page**, not the IndexNow endpoint, and `data=` sent a form, not JSON. Bing still answers **200** (it's the home page), so it looked like it worked, but nothing was submitted. | `requests.post("https://api.indexnow.org/indexnow", json=payload)` |
| `"host": "www.bing.com"` | `host` must be **your** site's host, otherwise you get a 422 | `--host www.example.com` |
| `urlList` built from Oncrawl JSON lines (a list of objects) | `urlList` must be a list of URL strings | URLs are extracted from objects automatically |
| Split files into folders by hand, then loop over them | Extra steps, and the next file was sent even if the last one failed | Batching in memory; stops on the first failed batch |
| No key check | 403s with no explanation | `check-key` and an automatic pre-flight check |
| No retry | 429 meant starting again | Exponential backoff |
| `input()` prompts | Hard to automate | Command-line flags and an environment variable |
| `=isPageIndexed()` Apps Script that scraped `google.com/search?q=site:` | Breaks on CAPTCHAs, isn't reliable, and goes against Google's terms | `check_indexation_gsc.py` with the Search Console URL Inspection API (2,000 inspections per property per day) |

## Participating search engines (October 2026)

From [indexnow.org/searchengines.json](https://www.indexnow.org/searchengines.json): Microsoft Bing, Yandex, Seznam.cz, Naver, Yep, the Internet Archive and Amazonbot. Google doesn't participate.

## Licence

MIT (see the repository root).
