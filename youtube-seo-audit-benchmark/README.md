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

## New: AI transcript audit (`ai_transcript_audit.py`)

Companion to the "How to use AI to run your YouTube SEO audit" section of the audit guide. It runs one structured prompt over a folder of video transcripts with the Claude API and saves one row per video to `transcript_audit.csv`:

* main topic, subtopics covered and entities mentioned;
* whether the title's promise is delivered (yes / partly / no), with a quote as evidence;
* the hook in the first 30 seconds, and whether it makes a clear promise;
* retention cues (open loops, signposting) with timestamps and quotes;
* the first CTA timestamp and suggested chapters.

Every finding has to quote the transcript, so you can spot-check it. Put it next to your audience retention graph in YouTube Studio to see *why* viewers leave where they do.

```bash
pip install anthropic pandas
export ANTHROPIC_API_KEY=...   # your own key; never paste it into the script
python ai_transcript_audit.py transcripts/ --out transcript_audit.csv
python ai_transcript_audit.py transcripts/ --dry-run   # list files, no API calls
```

* **Input:** one `.txt`, `.srt` or `.vtt` file per video, named after the video title. Download captions for your own videos from YouTube Studio, or transcribe the files with Whisper. (The YouTube Data API only lets you download captions for videos you own, at 200 quota units each.)
* **Settings** at the top of the script: `MODEL` (default `claude-opus-5-5`), `EFFORT` (`medium`; `low` is cheaper for big catalogues), `USE_FALLBACKS` (re-runs a declined request on another model; set `False` if your account or platform doesn't support it), `MAX_CHARS` (longer transcripts are skipped, not truncated).
* **Cost:** you pay per token on your own Anthropic account. Try two or three videos first.
* **Caveats:** models can still misread a transcript. Check the quotes, keep a human in the loop, and strip personal data before sending anything that isn't your own content.
* Needs a recent `anthropic` SDK (1.x needs Python 3.10+). Tested with a mocked client only; not yet run against the live API.

## Requirements

* Python 3.9+, `requests`, `pandas` (Colab has both).
* A YouTube Data API v3 key: Google Cloud console > APIs & Services > Library > enable **YouTube Data API v3** > Credentials > Create credentials > API key. Restrict the key to that API.
* Set it as an environment variable `YOUTUBE_API_KEY` (in Colab: the key icon > Secrets, then `os.environ["YOUTUBE_API_KEY"] = userdata.get("YOUTUBE_API_KEY")`). Don't paste keys into notebooks you share.

## Quota

Default quota: 10,000 units per day per project. One channel costs about 4 units (channels, playlistItems, videos, playlists: 1 unit each). The optional keyword search (`search.list`) now has its own bucket: 1 unit per call, 100 calls per day by default ([quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), updated 15 Oct 2026).

## Caveats

* The API doesn't flag Shorts, so "Shorts-length share" counts uploads of 3 minutes or less (the Shorts maximum since 15 October 2024). Treat it as a proxy.
* `caption = true` only means uploaded captions; auto-generated captions aren't reported.
* Hidden like counts and disabled comments come back as 0.
* Channels can hide their subscriber count; the column is then empty.
* Subscriber counts from the API are rounded to three significant figures.

## Tested with

Python 3.9, requests 2.32, pandas 2.2.3, live YouTube Data API v3 on 22 October 2026: four channels (Google Search Central, Ahrefs, Semrush, Moz) and one keyword search ("youtube seo audit") ran end to end.
