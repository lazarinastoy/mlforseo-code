"""
YouTube keyword and tag research: autocomplete + competitor tags
================================================================

Companion code for the MLforSEO YouTube guides by Lazarina Stoy (MLforSEO, MIT licence).

1. YouTube autocomplete expansions for seed terms (seed, seed + a-z, question
   and modifier prefixes). The suggest endpoint is UNDOCUMENTED: Google can
   change or block it at any time, so every call is wrapped and failures are
   recorded instead of crashing the run.
2. Competitor video metadata from the official YouTube Data API v3:
   search.list (top videos for a seed) + videos.list (titles, tags, views,
   likes, comments, publish date, duration).
3. Analysis: grouped suggestions, tag frequency and co-occurrence, title
   n-grams and title patterns, gaps (autocomplete phrases no top video
   targets), and a suggested tag list that fits YouTube's 500-character limit.

Quota (YouTube Data API v3, as documented on 24 October 2026):
* search.list has its own "Search Queries" bucket: 100 calls per day by
  default, 1 unit per call (each extra page of results is another call).
* videos.list costs 1 unit per call from the general 10,000 units/day bucket,
  and one call covers up to 50 video IDs.
So one seed = 1 search call + 1 videos call.
"""

from __future__ import annotations

import itertools
import json
import re
import string
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import requests

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
API_BASE = "https://www.googleapis.com/youtube/v3"

QUESTION_PREFIXES = ["how to", "what is", "why", "best", "how does", "can you"]
SUFFIX_MODIFIERS = ["for beginners", "tutorial", "tips", "tools", "2026", "vs", "course", "checklist"]

# ---------------------------------------------------------------------------
# 1. Autocomplete (undocumented endpoint)
# ---------------------------------------------------------------------------


def parse_suggest(text: str) -> list[str]:
    """Parse the client=youtube JSONP response: window.google.ac.h([...])."""
    m = re.search(r"\((.*)\)\s*$", text.strip(), re.S)
    payload = json.loads(m.group(1) if m else text)
    items = payload[1]
    return [i[0] if isinstance(i, list) else i for i in items]


def youtube_autocomplete(query: str, hl: str = "en", gl: str = "GB",
                         session: requests.Session | None = None, timeout: int = 10) -> tuple[list[str], str]:
    """Return (suggestions, error). error is '' on success."""
    s = session or requests.Session()
    params = {"client": "youtube", "ds": "yt", "q": query, "hl": hl, "gl": gl}
    try:
        r = s.get(SUGGEST_URL, params=params, timeout=timeout,
                  headers={"User-Agent": "Mozilla/5.0 (MLforSEO YouTube keyword research notebook)"})
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        return parse_suggest(r.text), ""
    except (requests.RequestException, ValueError, IndexError, json.JSONDecodeError) as e:
        return [], f"{type(e).__name__}: {str(e)[:120]}"


def expansion_queries(seed: str, alphabet: bool = True, questions: bool = True,
                      modifiers: bool = True) -> list[str]:
    """The list of queries sent to autocomplete for one seed."""
    qs = [seed]
    if alphabet:
        qs += [f"{seed} {c}" for c in string.ascii_lowercase]
    if questions:
        qs += [f"{p} {seed}" for p in QUESTION_PREFIXES]
    if modifiers:
        qs += [f"{seed} {m}" for m in SUFFIX_MODIFIERS]
    return qs


def expand_seeds(seeds: list[str], hl: str = "en", gl: str = "GB", pause: float = 0.4,
                 max_consecutive_failures: int = 5, cache: dict | None = None,
                 **kwargs) -> tuple[pd.DataFrame, dict, list[dict]]:
    """Run autocomplete for every seed and expansion.

    cache: {query: [suggestions]} from a saved run (sample mode). Queries found in
    the cache are not sent. Returns (suggestions DataFrame, raw cache, errors).
    """
    raw = {} if cache is None else dict(cache)
    errors, rows = [], []
    session = requests.Session()
    fails = 0
    for seed in seeds:
        for q in expansion_queries(seed, **kwargs):
            if q in raw:
                sugg = raw[q]
            else:
                if fails >= max_consecutive_failures:
                    errors.append(dict(seed=seed, query=q, error="skipped: too many failures in a row"))
                    continue
                sugg, err = youtube_autocomplete(q, hl=hl, gl=gl, session=session)
                time.sleep(pause)
                if err:
                    fails += 1
                    errors.append(dict(seed=seed, query=q, error=err))
                    continue
                fails = 0
                raw[q] = sugg
            for rank, s in enumerate(sugg, 1):
                rows.append(dict(seed=seed, query_sent=q, rank=rank, suggestion=s.strip().lower()))
    df = pd.DataFrame(rows, columns=["seed", "query_sent", "rank", "suggestion"])
    return df, raw, errors


def unique_suggestions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per suggestion: how many expansions returned it and its best rank.
    Appearing for many different expansions is a rough proxy for popularity."""
    g = (df.groupby(["seed", "suggestion"])
           .agg(times_suggested=("query_sent", "nunique"), best_rank=("rank", "min"))
           .reset_index()
           .sort_values(["seed", "times_suggested", "best_rank"], ascending=[True, False, True]))
    return g


def modifier(suggestion: str, seed: str) -> str:
    """What the suggestion adds to the seed ('youtube seo tips' -> 'tips')."""
    s = suggestion.lower()
    seed_l = seed.lower()
    if seed_l in s:
        rest = s.replace(seed_l, " ").split()
    else:
        seed_words = set(seed_l.split())
        rest = [w for w in s.split() if w not in seed_words]
    return " ".join(rest).strip()


def topic_bucket(mod: str) -> str:
    """Simple, explainable topic groups. Edit the rules to suit your niche."""
    rules = [
        ("language / region", r"\b(hindi|bangla|bengali|urdu|tamil|telugu|malayalam|kannada|marathi|nepali|sinhala|"
                              r"spanish|español|arabic|indonesia|pakistan|india|kaise|kya|hai|in english)\b"),
        ("question", r"^(how|what|why|when|where|which|who|can|does|do|is|are|should)\b"),
        ("year / freshness", r"\b20\d\d\b|\blatest\b|\bnew\b|\bupdate"),
        ("tools / software", r"\btools?\b|\bsoftware\b|\bextension\b|\bapp\b|\bplugin\b|\bai\b|\bgenerator\b|\bchecker\b|\banalyzer\b"),
        ("learning / course", r"\bcourse\b|\btutorial\b|\bguide\b|\bfor beginners\b|\bclass\b|\btraining\b|\bexplained\b|\blearn"),
        ("tips / tactics", r"\btips?\b|\btricks?\b|\bhacks?\b|\bstrateg|\bchecklist\b|\boptimi[sz]ation\b|\branking\b|\brank\b"),
        ("career / money", r"\bjobs?\b|\bcareer\b|\bfreelanc|\bclients?\b|\bmonetization\b|\bmonetisation\b|\bearn|\bservices?\b|\bagency\b|\bsalary\b|\bfiverr\b|\bupwork\b"),
        ("comparison", r"\bvs\b|\bversus\b|\balternative|\bbest\b|\btop\b"),
        ("format / feature", r"\bshorts?\b|\btags?\b|\btitles?\b|\bdescription\b|\bthumbnail|\bkeywords?\b|\bhashtags?\b|\bchapters?\b"),
    ]
    for name, rx in rules:
        if re.search(rx, mod):
            return name
    return "other" if mod else "seed"


def group_suggestions(uniq: pd.DataFrame) -> pd.DataFrame:
    out = uniq.copy()
    out["modifier"] = [modifier(s, seed) for s, seed in zip(out["suggestion"], out["seed"])]
    out["topic_group"] = out["modifier"].map(topic_bucket)
    return out


# ---------------------------------------------------------------------------
# 2. YouTube Data API v3
# ---------------------------------------------------------------------------

class YouTubeAPIError(RuntimeError):
    pass


def _api_get(endpoint: str, params: dict, api_key: str) -> dict:
    r = requests.get(f"{API_BASE}/{endpoint}", params={**params, "key": api_key}, timeout=30)
    if r.status_code != 200:
        try:
            err = r.json()["error"]
            reason = err.get("errors", [{}])[0].get("reason", "")
            msg = err.get("message", "")
        except (ValueError, KeyError):
            reason, msg = "", r.text[:200]
        hint = {
            "quotaExceeded": "Daily quota used up. It resets at midnight Pacific Time.",
            "keyInvalid": "Check the API key.",
            "accessNotConfigured": "Enable 'YouTube Data API v3' for this Google Cloud project.",
        }.get(reason, "")
        raise YouTubeAPIError(f"{endpoint}: HTTP {r.status_code} {reason} {msg} {hint}".strip())
    return r.json()


def search_videos(query: str, api_key: str, max_results: int = 25, region: str = "GB",
                  language: str = "en", order: str = "relevance") -> dict:
    """search.list: the top videos for a query. 1 call, Search Queries bucket (100 calls/day)."""
    return _api_get("search", dict(part="snippet", q=query, type="video", maxResults=max_results,
                                   regionCode=region, relevanceLanguage=language, order=order), api_key)


def video_details(video_ids: list[str], api_key: str) -> dict:
    """videos.list: snippet (title, tags, publish date), statistics and duration. 1 unit per 50 IDs."""
    items = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        data = _api_get("videos", dict(part="snippet,statistics,contentDetails", id=",".join(batch),
                                       maxResults=50), api_key)
        items += data.get("items", [])
    return {"kind": "youtube#videoListResponse", "items": items}


def iso_duration_seconds(d: str) -> int | None:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return None
    days, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s


def videos_frame(seed: str, search_json: dict, videos_json: dict, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per video, in search-rank order."""
    rank = {it["id"]["videoId"]: i for i, it in enumerate(search_json.get("items", []), 1)
            if it.get("id", {}).get("videoId")}
    today = today or pd.Timestamp.now(tz="UTC")
    rows = []
    for v in videos_json.get("items", []):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        published = pd.Timestamp(sn.get("publishedAt"))
        views = int(st.get("viewCount", 0))
        age_days = max((today - published).days, 1)
        tags = [t.strip() for t in sn.get("tags", [])]
        rows.append(dict(
            seed=seed, search_rank=rank.get(v["id"]), video_id=v["id"],
            url=f"https://www.youtube.com/watch?v={v['id']}", title=sn.get("title", ""),
            channel=sn.get("channelTitle", ""), published=published.date().isoformat(), age_days=age_days,
            views=views, likes=int(st.get("likeCount", 0)), comments=int(st.get("commentCount", 0)),
            views_per_day=round(views / age_days, 1),
            duration_s=iso_duration_seconds(v.get("contentDetails", {}).get("duration", "")),
            n_tags=len(tags), tags=tags, tags_text=", ".join(tags),
        ))
    return pd.DataFrame(rows).sort_values(["seed", "search_rank"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. Analysis
# ---------------------------------------------------------------------------

def tag_stats(videos: pd.DataFrame) -> pd.DataFrame:
    """How many top videos use each tag, and the views behind it."""
    ex = videos.explode("tags").dropna(subset=["tags"])
    ex["tag"] = ex["tags"].str.lower().str.strip()
    g = (ex.groupby("tag")
           .agg(videos_using=("video_id", "nunique"), total_views=("views", "sum"),
                median_views=("views", "median"), best_rank=("search_rank", "min"))
           .reset_index())
    g["share_of_videos"] = (g["videos_using"] / videos["video_id"].nunique()).round(2)
    return g.sort_values(["videos_using", "total_views"], ascending=False).reset_index(drop=True)


def tag_cooccurrence(videos: pd.DataFrame, min_count: int = 2) -> pd.DataFrame:
    """Pairs of tags that appear on the same video."""
    c = Counter()
    for tags in videos["tags"]:
        uniq = sorted({t.lower().strip() for t in tags})
        c.update(itertools.combinations(uniq, 2))
    rows = [dict(tag_a=a, tag_b=b, videos_together=n) for (a, b), n in c.items() if n >= min_count]
    return pd.DataFrame(rows, columns=["tag_a", "tag_b", "videos_together"]).sort_values(
        "videos_together", ascending=False).reset_index(drop=True)


STOP = set("""a an and are as at be by for from how i in is it its me my of on or our that the this to
we what why with you your vs | - — & + : ? ! , . ' " ( ) [ ]""".split())


def tokenize(title: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", title.lower())]


def title_ngrams(videos: pd.DataFrame, n_values=(1, 2, 3), top: int = 25) -> pd.DataFrame:
    """Most common words and phrases in top-ranking titles (stop words removed at the edges)."""
    rows = []
    for n in n_values:
        c, views = Counter(), Counter()
        for title, v in zip(videos["title"], videos["views"]):
            toks = tokenize(title)
            grams = {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}
            grams = {g for g in grams if g.split()[0] not in STOP and g.split()[-1] not in STOP}
            c.update(grams)
            for g in grams:
                views[g] += v
        for g, k in c.most_common(top):
            rows.append(dict(n=n, ngram=g, titles=k, total_views=views[g]))
    return pd.DataFrame(rows)


def title_patterns(videos: pd.DataFrame) -> pd.DataFrame:
    """Share of top titles using common patterns."""
    t = videos["title"]
    checks = {
        "contains a number": t.str.contains(r"\d"),
        "contains a year (20xx)": t.str.contains(r"\b20\d\d\b"),
        "starts with How / What / Why": t.str.match(r"(?i)^(how|what|why)\b"),
        "uses brackets ( ) or [ ]": t.str.contains(r"[\(\[]"),
        "uses a colon or pipe": t.str.contains(r"[:|]"),
        "says 'for beginners'": t.str.contains(r"(?i)beginner"),
        "all-caps word (3+ letters)": t.str.contains(r"\b[A-Z]{3,}\b"),
    }
    rows = [dict(pattern=k, share_of_titles=round(float(v.mean()), 2),
                 median_views_with=int(videos.loc[v, "views"].median()) if v.any() else None,
                 median_views_without=int(videos.loc[~v, "views"].median()) if (~v).any() else None)
            for k, v in checks.items()]
    rows.append(dict(pattern="median title length (characters)", share_of_titles=None,
                     median_views_with=int(t.str.len().median()), median_views_without=None))
    return pd.DataFrame(rows)


def coverage_gaps(groups: pd.DataFrame, videos: pd.DataFrame) -> pd.DataFrame:
    """Autocomplete phrases and whether any top video already targets them in its title or tags."""
    corpus_titles = " || ".join(videos["title"].str.lower())
    corpus_tags = {t.lower() for tags in videos["tags"] for t in tags}
    out = groups.copy()
    out["in_a_top_title"] = out["suggestion"].map(lambda s: s in corpus_titles)
    out["in_top_tags"] = out["suggestion"].map(lambda s: s in corpus_tags)
    out["gap"] = ~(out["in_a_top_title"] | out["in_top_tags"])
    return out


def tag_field_length(tags: list[str]) -> int:
    """Length as YouTube counts it: commas count, and tags with spaces count as if wrapped in quotes."""
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


def suggest_tags(seed: str, groups: pd.DataFrame, tags: pd.DataFrame, limit_chars: int = 500,
                 max_tags: int = 15) -> pd.DataFrame:
    """A starting tag list: the seed; phrases both suggested by autocomplete and used by 2+ top videos;
    other tags used by 2+ top videos; then the remaining autocomplete phrases.
    Stops at YouTube's 500-character limit."""
    used = dict(zip(tags["tag"], tags["videos_using"]))
    auto = groups[groups["seed"] == seed].set_index("suggestion")["times_suggested"].to_dict()
    both = sorted((s for s in auto if s in used), key=lambda s: (-used[s], -auto[s]))
    comp_only = [t for t in tags.sort_values(["videos_using", "total_views"], ascending=False)["tag"]
                 if used[t] >= 2 and t not in auto]
    cands = [(seed.lower(), "seed")]
    cands += [(s, "autocomplete + competitor tag") for s in both if used[s] >= 2]
    cands += [(t, "competitor tag (2+ top videos)") for t in comp_only]
    cands += [(s, "autocomplete + competitor tag") for s in both if used[s] < 2]
    cands += [(s, "autocomplete") for s in sorted(auto, key=lambda s: -auto[s])]
    chosen, seen = [], set()
    for tag, why in cands:
        if tag in seen or len(chosen) >= max_tags:
            continue
        if tag_field_length([c[0] for c in chosen] + [tag]) > limit_chars:
            continue
        chosen.append((tag, why))
        seen.add(tag)
    df = pd.DataFrame(chosen, columns=["tag", "why"])
    df["used_by_top_videos"] = df["tag"].map(lambda t: used.get(t, 0))
    df["autocomplete_hits"] = df["tag"].map(lambda t: auto.get(t, 0))
    return df


# ---------------------------------------------------------------------------
# 4. Sample files
# ---------------------------------------------------------------------------

def slug(seed: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", seed.lower()).strip("-")


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def export(tables: dict[str, pd.DataFrame], out_dir: str | Path = "results") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    clean = {}
    for name, df in tables.items():
        df = df.copy()
        for col in df.columns:
            if df[col].map(lambda x: isinstance(x, list)).any():
                df[col] = df[col].map(lambda x: ", ".join(x) if isinstance(x, list) else x)
        clean[name] = df
        p = out_dir / f"youtube_{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    xlsx = out_dir / "youtube_keyword_research.xlsx"
    with pd.ExcelWriter(xlsx) as xw:
        for name, df in clean.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    written.append(xlsx)
    return written
