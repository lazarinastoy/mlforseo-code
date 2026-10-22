# %% [markdown]
# # YouTube SEO audit: competitor channel benchmark (YouTube Data API v3)
#
# Companion to the MLforSEO guide **How to do a YouTube SEO audit** by Lazarina Stoy.
#
# It builds the Step 1 benchmark table from the guide (subscribers, number of videos,
# posting frequency, average views / likes / comments over the last 50 videos, best videos)
# for your channel and your competitors, plus the "qualitative" checks from Step 2 that
# can be read from public data: chapters in descriptions, uploaded captions, title and
# description length, tags, Shorts-length share, playlists.
#
# **You need:** a free YouTube Data API v3 key (Google Cloud console > APIs & Services >
# enable "YouTube Data API v3" > Credentials > API key). The default quota is 10,000 units
# a day; benchmarking one channel costs about 4 units. The optional keyword search in
# section 5 costs 100 units per keyword.

# %%
# !pip install -q requests pandas   # (Colab already has both)
import os, re, statistics
from datetime import datetime, timezone

import pandas as pd
import requests

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")  # or paste it here (don't commit it)
API = "https://www.googleapis.com/youtube/v3"

# YOUR DATA: your channel first, then competitors. Handles (@name), channel IDs (UC...)
# or channel URLs all work.
CHANNELS = [
    "@GoogleSearchCentral",
    "@AhrefsCom",
    "@semrush",
    "@Moz",
]
LAST_N_VIDEOS = 50  # the guide's benchmark uses the last 50 uploads

# %% [markdown]
# ## 1. Helpers

# %%
def yt(endpoint, **params):
    """GET a YouTube Data API endpoint and return the JSON (raises on HTTP errors)."""
    params["key"] = API_KEY
    r = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
    if r.status_code == 403 and "quota" in r.text.lower():
        raise RuntimeError("Daily YouTube API quota used up. It resets at midnight Pacific time.")
    r.raise_for_status()
    return r.json()


def resolve_channel(ref):
    """Turn a handle, channel ID or channel URL into a channels.list item."""
    ref = ref.strip()
    m = re.search(r"youtube\.com/(?:channel/)?(@[\w.\-]+|UC[\w-]{22})", ref)
    if m:
        ref = m.group(1)
    parts = "snippet,statistics,contentDetails,brandingSettings"
    if ref.startswith("UC") and len(ref) == 24:
        data = yt("channels", part=parts, id=ref)
    else:
        data = yt("channels", part=parts, forHandle=ref if ref.startswith("@") else "@" + ref)
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No channel found for {ref!r}")
    return items[0]


def iso_duration_seconds(d):
    """PT1H2M3S -> 3723"""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s


TIMESTAMP = re.compile(r"(?m)^\s*\(?(\d{1,2}:)?\d{1,2}:\d{2}\)?\s")


def has_chapters(description):
    """YouTube needs at least 3 timestamps, the first at 0:00, to show chapters."""
    stamps = TIMESTAMP.findall(description or "")
    return len(stamps) >= 3 and re.search(r"(?m)^\s*\(?0?0:00", description or "") is not None


def recent_videos(uploads_playlist, n=LAST_N_VIDEOS):
    ids, token = [], None
    while len(ids) < n:
        page = yt("playlistItems", part="contentDetails", playlistId=uploads_playlist,
                  maxResults=min(50, n - len(ids)), pageToken=token or "")
        ids += [it["contentDetails"]["videoId"] for it in page.get("items", [])]
        token = page.get("nextPageToken")
        if not token:
            break
    videos = []
    for i in range(0, len(ids), 50):
        videos += yt("videos", part="snippet,statistics,contentDetails",
                     id=",".join(ids[i:i + 50]))["items"]
    return videos

# %% [markdown]
# ## 2. Benchmark each channel

# %%
def benchmark(ref):
    ch = resolve_channel(ref)
    stats, snip = ch["statistics"], ch["snippet"]
    vids = recent_videos(ch["contentDetails"]["relatedPlaylists"]["uploads"])
    playlists = yt("playlists", part="id", channelId=ch["id"], maxResults=1)["pageInfo"]["totalResults"]

    rows = []
    for v in vids:
        s, c, d = v.get("statistics", {}), v["contentDetails"], v["snippet"]
        views = int(s.get("viewCount", 0))
        rows.append({
            "title": d["title"],
            "url": f"https://www.youtube.com/watch?v={v['id']}",
            "published": d["publishedAt"],
            "views": views,
            "likes": int(s.get("likeCount", 0)),        # hidden likes come back as 0
            "comments": int(s.get("commentCount", 0)),  # disabled comments come back as 0
            "seconds": iso_duration_seconds(c.get("duration")),
            "captions": c.get("caption") == "true",     # uploaded captions, not auto-generated
            "chapters": has_chapters(d.get("description")),
            "tags": len(d.get("tags", [])),
            "title_chars": len(d["title"]),
            "description_words": len((d.get("description") or "").split()),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return {"channel": snip["title"]}, df

    first = datetime.fromisoformat(df["published"].min().replace("Z", "+00:00"))
    days = max((datetime.now(timezone.utc) - first).days, 1)
    eng = (df["likes"] + df["comments"]).sum() / max(df["views"].sum(), 1)
    best = df.nlargest(3, "views")

    summary = {
        "channel": snip["title"],
        "handle": snip.get("customUrl", ""),
        "subscribers": None if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
        "total_views": int(stats.get("viewCount", 0)),
        "playlists": playlists,
        f"videos_per_day (last {len(df)})": round(len(df) / days, 2),
        "avg_views": round(df["views"].mean()),
        "median_views": round(df["views"].median()),
        "avg_likes": round(df["likes"].mean()),
        "avg_comments": round(df["comments"].mean()),
        "engagement_rate_%": round(100 * eng, 2),
        "shorts_length_share_%": round(100 * (df["seconds"] <= 180).mean()),
        "chapters_%": round(100 * df["chapters"].mean()),
        "uploaded_captions_%": round(100 * df["captions"].mean()),
        "uses_tags_%": round(100 * (df["tags"] > 0).mean()),
        "avg_title_chars": round(df["title_chars"].mean()),
        "avg_description_words": round(df["description_words"].mean()),
        "has_channel_description": bool(snip.get("description")),
        "has_channel_keywords": bool(ch.get("brandingSettings", {}).get("channel", {}).get("keywords")),
        "best_videos": " | ".join(f"{t} ({v:,} views)" for t, v in zip(best["title"], best["views"])),
    }
    df.insert(0, "channel", snip["title"])
    return summary, df


summaries, all_videos = [], []
for ref in CHANNELS:
    try:
        s, vids = benchmark(ref)
        summaries.append(s)
        all_videos.append(vids)
        print(f"OK  {s['channel']}")
    except Exception as e:  # keep going if one channel fails
        print(f"ERR {ref}: {e}")

bench = pd.DataFrame(summaries).set_index("channel")
bench.T  # one column per channel, like the table in the guide

# %% [markdown]
# ## 3. Read the table
#
# * **Posting frequency vs average views**: is anyone winning with fewer, better videos?
# * **Median vs average views**: a big gap means one or two hits carry the channel.
# * **Chapters %, uploaded captions %, average description words**: quick wins you control.
# * **Shorts-length share**: the API doesn't say "this is a Short", so this counts uploads of
#   3 minutes or less (the Shorts limit since October 2024). Treat it as a proxy.
# * **Uses tags %**: YouTube says tags play a minimal role in discovery. A low number isn't a problem.
# * Likes or comments of 0 can mean they're hidden or turned off, not that nobody engaged.

# %% [markdown]
# ## 4. Export

# %%
bench.to_csv("youtube_benchmark_channels.csv")
pd.concat(all_videos, ignore_index=True).to_csv("youtube_benchmark_videos.csv", index=False)
try:
    from google.colab import files
    files.download("youtube_benchmark_channels.csv")
    files.download("youtube_benchmark_videos.csv")
except ImportError:
    print("Saved youtube_benchmark_channels.csv and youtube_benchmark_videos.csv")

# %% [markdown]
# ## 5. Optional: find who you compete with on YouTube for your keywords
#
# Step 1 of the guide: which channels show up when people search YouTube for your keywords?
# Each keyword costs **100 quota units** (search.list), so start with 5-10 keywords.

# %%
KEYWORDS = []  # YOUR DATA, e.g. ["seo audit", "keyword research tutorial"]
REGION = "US"


def search_competitors(keywords, region=REGION, per_keyword=25):
    hits = []
    for kw in keywords:
        res = yt("search", part="snippet", q=kw, type="video", maxResults=per_keyword,
                 regionCode=region, relevanceLanguage="en")
        for rank, it in enumerate(res.get("items", []), 1):
            hits.append({"keyword": kw, "rank": rank,
                         "channel": it["snippet"]["channelTitle"],
                         "channel_id": it["snippet"]["channelId"]})
    df = pd.DataFrame(hits)
    if df.empty:
        return df
    return (df.groupby(["channel", "channel_id"])
              .agg(keywords=("keyword", "nunique"), appearances=("rank", "size"), best_rank=("rank", "min"))
              .sort_values(["keywords", "appearances"], ascending=False)
              .reset_index())


if KEYWORDS:
    competitors = search_competitors(KEYWORDS)
    competitors.head(20)
