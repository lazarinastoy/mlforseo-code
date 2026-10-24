# YouTube keyword and tag research: autocomplete + competitor tags

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/youtube-keyword-research/youtube_keyword_research.ipynb)

Companion code for two MLforSEO guides by Lazarina Stoy: **[YouTube SEO: how to boost video visibility and grow your channel (free checklist)](https://www.mlforseo.com/machine-learning-implementation-guides/content-creation/youtube-seo-guide/)** and **[How to do a YouTube SEO audit](https://www.mlforseo.com/machine-learning-implementation-guides/content-audit/youtube-seo-audit/)**. It pairs with the free [YouTube SEO Checklist](https://www.mlforseo.com/resource/youtube-seo-checklist/) and extends the YouTube part of the [multi-platform autocomplete notebook](https://www.mlforseo.com/resource/multi-platform-autocomplete-keyword-research-with-google-search-youtube-and-places-apis-notebook/).

A data-backed alternative to "YouTube tag generator" sites: you see where every keyword, title phrase and tag comes from.

## What it does

| Section | What you get |
|---|---|
| 2. Autocomplete | YouTube autocomplete for each seed, expanded with a-z, question prefixes and modifiers; how many expansions returned each phrase; simple, editable topic groups |
| 3. Competitor videos | top videos per seed from the YouTube Data API v3 (`search.list` + `videos.list`): title, channel, tags, views, likes, comments, publish date, views per day, duration |
| 4. Tags | tag frequency (videos using, views behind them) and tag co-occurrence pairs |
| 5. Titles | title n-grams (1 to 3 words) and title patterns (numbers, years, questions, brackets, colons) with median views |
| 6. Gaps | autocomplete phrases that no top video targets in its title or tags |
| 7. Tag list | a suggested tag list with the reason for each tag, within YouTube's 500-character limit |
| 8. Export | one CSV per table and `youtube_keyword_research.xlsx` (open it in Google Sheets) |

## Tags are a minor signal

YouTube's own help page says the title, thumbnail and description "are more important pieces of metadata for your video's discovery", and that tags "play a minimal role" unless your video's topic is commonly misspelled ([YouTube Help: add tags to your YouTube videos](https://support.google.com/youtube/answer/146402)). Use this notebook mainly for keyword and title research; the tag list is the last, smallest step.

## Requirements

* Python 3.9+, `requests`, `pandas`, `openpyxl` (Colab has them).
* **Sample mode:** nothing else.
* **Live mode:** a YouTube Data API v3 key for the competitor part. Google Cloud console > APIs & Services > Library > enable **YouTube Data API v3** > Credentials > Create credentials > API key; restrict it to that API. The notebook reads it at runtime from Colab Secrets (`YOUTUBE_API_KEY`), then the `YOUTUBE_API_KEY` environment variable, then a hidden prompt. Never paste keys into a notebook you share.

## Quota and cost

Free within the default quota ([quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), page updated 15 October 2026):

* `search.list`: its own Search Queries bucket of **100 calls per day**, **1 unit per call**. One call per seed (more if you page through results).
* `videos.list`: **1 unit per call** from the general **10,000 units per day**; one call covers up to 50 video IDs.

So each competitor seed costs 1 search call and 1 videos call. Quotas reset at midnight Pacific Time. Raw API responses are saved to `my_data/` so you can re-run the analysis without spending quota.

## The autocomplete endpoint is undocumented

Autocomplete comes from `suggestqueries.google.com/complete/search?client=youtube&ds=yt`, the endpoint YouTube's search box uses. Google doesn't document or support it for developers, so it can change, rate-limit or block requests at any time. The code pauses 0.4 seconds between requests, records each failure, stops sending after five failures in a row, and the rest of the notebook keeps running. Each seed sends about 41 requests.

## Sample data

* `sample_data/autocomplete_sample.json`: **real** YouTube autocomplete responses for "youtube seo" and "youtube tags", collected on 24 October 2026 (hl=en, gl=GB).
* `sample_data/search_list_youtube-seo.json` and `videos_list_youtube-seo.json`: **sample** API responses with fictional channels and fake video IDs, written in the official YouTube Data API v3 response format (`youtube#searchListResponse`, `youtube#videoListResponse`). Each file is marked with a `_sample_note`. Numbers in sample mode illustrate the method only.

## Caveats

* Autocomplete shows predicted queries, not search volume, and changes daily.
* API search results aren't personalised and can differ from what you see on YouTube.
* 20 to 50 videos per seed describe a niche; they don't prove what causes views.
* The API returns tags for public videos; many creators don't use tags at all.
* Topic groups are rule-based on purpose, so you can read and edit them (`topic_bucket()` in the helper).

## Tested with

Python 3.12, requests 2.34, pandas 3.1, openpyxl 3.1.5 on 24 October 2026:

* The notebook ran end to end in sample mode (`jupyter nbconvert --execute`).
* Live autocomplete ran for both sample seeds (82 requests, no failures); the failure path was tested against a dead endpoint.
* The YouTube Data API calls were tested only for error handling (an invalid key returns a clear error). The live competitor pull has **not** been run with a real key yet.

## Files

* `youtube_keyword_research.ipynb`: the notebook (with sample-mode outputs)
* `youtube_keyword_research.py`: helper functions
* `sample_data/`: saved autocomplete responses and sample API responses
* `requirements.txt`

MIT licence. Credit: Lazarina Stoy, [MLforSEO](https://www.mlforseo.com).
