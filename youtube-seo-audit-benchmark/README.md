# YouTube SEO audit: competitor channel benchmark

Companion code for two MLforSEO guides by Lazarina Stoy:
**How to do a YouTube SEO audit (step-by-step guide)** and **YouTube SEO: how to boost video visibility and grow your channel (free checklist)**. Both were first published on lazarinastoy.com in February 2024 and refreshed in October 2026.

The free [YouTube SEO Checklist](https://www.mlforseo.com/resource/youtube-seo-checklist/) (72 steps, Google Sheets) is the companion for the optimisation side; this notebook automates the benchmarking side of the audit.

## What it does

`youtube_channel_benchmark.ipynb` (same code as `youtube_channel_benchmark.py`) uses the official **YouTube Data API v3** to build the Step 1 benchmark table from the audit guide for your channel and any competitors:

| Section | What you get |
|---|---|
| 2. Benchmark | Per channel: subscribers, videos, total views, playlists, posting frequency, average and median views, average likes and comments, engagement rate over the last 50 uploads, and the three best videos |
| 2. Audit checks | Share of the last 50 uploads with chapters (3+ timestamps starting at 0:00), uploaded captions, tags; Shorts-length share (3 minutes or less); average title length and description words; channel description and keywords present |
| 4. Export | `youtube_benchmark_channels.csv` and `youtube_benchmark_videos.csv` (one row per video), auto-download in Colab |
| 5. Optional | Which channels rank in YouTube search for your keywords (search.list, 100 quota units per keyword) |

Replaces the manual vidIQ / Social Blade copy-paste step in the 2024 guide. vidIQ is still handy for one-off checks.

## Requirements

* Python 3.9+, `requests`, `pandas` (Colab has both).
* A YouTube Data API v3 key: Google Cloud console > APIs & Services > Library > enable **YouTube Data API v3** > Credentials > Create credentials > API key. Restrict the key to that API.
* Set it as an environment variable `YOUTUBE_API_KEY` (in Colab: the key icon > Secrets, then `os.environ["YOUTUBE_API_KEY"] = userdata.get("YOUTUBE_API_KEY")`). Don't paste keys into notebooks you share.

## Quota

Default quota: 10,000 units per day per project. One channel costs about 4 units (channels, playlistItems, videos, playlists: 1 unit each). The optional keyword search costs 100 units per keyword.

## Caveats

* The API doesn't flag Shorts, so "Shorts-length share" counts uploads of 3 minutes or less (the Shorts maximum since 15 October 2024). Treat it as a proxy.
* `caption = true` only means uploaded captions; auto-generated captions aren't reported.
* Hidden like counts and disabled comments come back as 0.
* Channels can hide their subscriber count; the column is then empty.
* Subscriber counts from the API are rounded to three significant figures.

## Tested with

Python 3.9, requests 2.32, pandas 2.2.3, live YouTube Data API v3 on 22 October 2026: four channels (Google Search Central, Ahrefs, Semrush, Moz) and one keyword search ("youtube seo audit") ran end to end.
