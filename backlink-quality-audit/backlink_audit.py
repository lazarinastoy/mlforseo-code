"""
backlink_audit.py: a readable backlink quality audit for SEOs, built on the
DataForSEO Backlinks API, a small local embedding model and Claude.

Part of the MLforSEO free resource library (Lazarina Stoy, MLforSEO, MIT licence).
https://github.com/lazarinastoy/mlforseo-code

What it does
  * Pulls a backlink profile from the DataForSEO Backlinks API (summary,
    referring domains, one backlink per domain, anchors, broken backlinks),
    with a worst-case cost estimate, a spend cap checked before every paid
    call and a cost log built from DataForSEO's own `cost` field.
  * Adds transparent rule flags: spam score band, rank band, follow / nofollow,
    spam-prone TLD, where on the page the link sits, anchor type, link age.
  * Scores topical relevance with a small local sentence-transformers model.
  * Sends only the ambiguous middle to Claude (claude-haiku-4-5 by default) in
    batches, with a strict JSON schema, and logs tokens and cost.
  * Puts every referring domain in one of four buckets (Valuable, Neutral,
    Likely spam, Investigate) and builds a link reclamation table: broken
    backlinks with a suggested redirect target fuzzy-matched from your sitemap.

Docs used (checked 7 November 2026):
  https://docs.dataforseo.com/v3/backlinks/summary/live/
  https://docs.dataforseo.com/v3/backlinks/referring_domains/live/
  https://docs.dataforseo.com/v3/backlinks/backlinks/live/
  https://docs.dataforseo.com/v3/backlinks/anchors/live/
  https://docs.dataforseo.com/v3/backlinks/filters/
  https://dataforseo.com/pricing/backlinks/backlinks
  https://platform.claude.com/docs (Messages API, structured outputs)

Never paste a password or API key into this file. They are read at runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import pandas as pd
import requests

API = "https://api.dataforseo.com/v3"

# DataForSEO Backlinks API list prices in November 2026 (all endpoints):
# $0.024 per request (task) + $0.000036 per row returned. They change: check
# https://dataforseo.com/pricing/backlinks/backlinks. Only used for the up-front
# ESTIMATE and the spend cap; the cost log uses the real `cost` the API returns.
PRICES = {"per_task": 0.024, "per_row": 0.000036}

# Claude prices in USD per million tokens (claude-haiku-4-5, November 2026).
# Check https://www.anthropic.com/pricing. Used for the estimate and the cost log.
LLM_PRICES = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}


# ---------------------------------------------------------------------------
# Credentials: read at runtime, never stored in the notebook or the repo
# ---------------------------------------------------------------------------
def _secret(name: str) -> str | None:
    """Colab secret, then environment variable. Returns None if neither is set."""
    try:  # Google Colab: the key icon in the left sidebar
        from google.colab import userdata  # type: ignore
        value = userdata.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(name)


def get_credentials() -> tuple[str, str]:
    """Return (login, password) for the DataForSEO API.

    Order: Colab secrets (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD), then
    environment variables with the same names, then a hidden prompt.
    Your API login and password are on https://app.dataforseo.com/api-access
    (the API password is NOT your dashboard password).
    """
    login, password = _secret("DATAFORSEO_LOGIN"), _secret("DATAFORSEO_PASSWORD")
    if not (login and password):
        from getpass import getpass
        login = login or input("DataForSEO API login (email): ").strip()
        password = password or getpass("DataForSEO API password: ").strip()
    return login, password


def get_anthropic_key() -> str:
    """ANTHROPIC_API_KEY from Colab secrets, the environment, or a hidden prompt."""
    key = _secret("ANTHROPIC_API_KEY")
    if not key:
        from getpass import getpass
        key = getpass("Anthropic API key: ").strip()
    return key


# ---------------------------------------------------------------------------
# Cost estimate
# ---------------------------------------------------------------------------
def call_cost_max(limit: int = 1) -> float:
    """Worst-case cost of one Backlinks API call that returns up to `limit` rows."""
    return PRICES["per_task"] + PRICES["per_row"] * max(1, limit)


def estimate_cost(plan: dict[str, int]) -> pd.DataFrame:
    """Worst-case USD for a collection plan {call name: row limit}. Assumes every
    call returns its full limit (smaller sites return fewer rows and cost less)."""
    rows = [{"call": name, "row_limit": lim, "usd_max": round(call_cost_max(lim), 5)}
            for name, lim in plan.items()]
    df = pd.DataFrame(rows)
    total = pd.DataFrame([{"call": "TOTAL", "row_limit": df["row_limit"].sum(),
                           "usd_max": round(df["usd_max"].sum(), 5)}])
    return pd.concat([df, total], ignore_index=True)


# ---------------------------------------------------------------------------
# The DataForSEO client
# ---------------------------------------------------------------------------
class DataForSEOClient:
    """Minimal DataForSEO Backlinks client with a spend cap, a cost log and a
    local response cache (so re-running a cell never pays twice for the same request).

    client = DataForSEOClient(*get_credentials(), max_spend_usd=0.30)
    data = client.live("referring_domains", {"target": "example.com", "limit": 100})
    client.cost_log   # one row per paid call with the cost DataForSEO reported
    """

    def __init__(self, login: str, password: str, max_spend_usd: float = 0.30,
                 pause_seconds: float = 0.5, timeout: int = 120, cache_dir: str | Path | None = "output/raw"):
        self.session = requests.Session()
        self.session.auth = (login, password)          # HTTP Basic auth
        self.max_spend_usd = max_spend_usd             # hard stop for runaway loops
        self.pause_seconds = pause_seconds             # polite gap between calls
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.spent = 0.0
        self.cost_log: list[dict] = []

    # -- low level ----------------------------------------------------------
    def _request(self, path: str, payload: list, label: str = "", expected_cost: float = 0.0,
                 retries: int = 3) -> dict:
        """One paid POST with retries on rate limits / server errors, cost logging
        and the spend cap. The call is refused if its worst-case cost would take
        the run over the cap. A dropped connection is NOT retried: the request may
        already have been charged, so the error is raised for you to decide."""
        if self.spent + expected_cost > self.max_spend_usd + 1e-9:
            raise RuntimeError(f"Spend cap: ${self.spent:.4f} spent, the next call could cost up to "
                               f"${expected_cost:.4f} and the cap is ${self.max_spend_usd}. "
                               "Raise MAX_SPEND_USD if you meant to spend more.")
        for attempt in range(retries):
            r = self.session.post(f"{API}{path}", json=payload, timeout=self.timeout)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)           # back off: 2s, 4s ...
                continue
            if r.status_code >= 400:                   # show DataForSEO's own message
                try:
                    msg = r.json().get("status_message") or r.reason
                except ValueError:
                    msg = r.reason
                hint = (" Check DATAFORSEO_LOGIN (your account email) and DATAFORSEO_PASSWORD: it must be the "
                        "API password from https://app.dataforseo.com/api-access, not your dashboard password."
                        if r.status_code == 401 else "")
                raise RuntimeError(f"DataForSEO HTTP {r.status_code}: {msg}{hint}")
            data = r.json()
            if data.get("status_code") != 20000:       # account-level problems (auth, balance)
                raise RuntimeError(f"DataForSEO {data.get('status_code')}: {data.get('status_message')}")
            cost = float(data.get("cost") or 0)
            self.spent += cost
            self.cost_log.append({"endpoint": path.replace("/backlinks/", "", 1), "label": label,
                                  "cost_usd": cost, "spent_so_far_usd": round(self.spent, 5),
                                  "source": "live API"})
            task = (data.get("tasks") or [{}])[0]
            if task.get("status_code") != 20000:       # task-level problems (e.g. no Backlinks access)
                raise RuntimeError(f"DataForSEO task error {task.get('status_code')}: {task.get('status_message')}")
            return data
        raise RuntimeError("Request failed after retries")

    def _cache_path(self, endpoint: str, task: dict) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1(json.dumps([endpoint, task], sort_keys=True).encode()).hexdigest()[:12]
        return self.cache_dir / f"{endpoint.replace('/', '_')}-{key}.json"

    def live(self, endpoint: str, task: dict, label: str = "") -> dict:
        """POST /v3/backlinks/{endpoint}/live with one task. Reuses a cached
        response for an identical request (logged at $0, with the original cost noted)."""
        cache = self._cache_path(endpoint, task)
        if cache and cache.exists():
            data = json.loads(cache.read_text())
            self.cost_log.append({"endpoint": f"{endpoint}/live", "label": label or endpoint, "cost_usd": 0.0,
                                  "spent_so_far_usd": round(self.spent, 5),
                                  "source": f"cache (cost ${float(data.get('cost') or 0):.4f} when collected)"})
            return data
        worst = call_cost_max(int(task.get("limit", 1)))
        data = self._request(f"/backlinks/{endpoint}/live", [task], label=label or endpoint, expected_cost=worst)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
        time.sleep(self.pause_seconds)
        return data


class SampleClient:
    """Stands in for DataForSEOClient when USE_SAMPLE = True. It replays real
    responses saved in sample_data/ (mlforseo.com, 7 November 2026), so the
    notebook runs end to end without a key and without spending anything."""

    FILES = {"summary": "summary.json", "referring_domains": "referring_domains.json",
             "backlinks": "backlinks_one_per_domain.json", "anchors": "anchors.json",
             "broken_backlinks": "broken_backlinks.json"}

    def __init__(self, sample_dir: str | Path = "sample_data"):
        self.sample_dir = Path(sample_dir)
        self.spent = 0.0
        self.cost_log: list[dict] = []

    def live(self, endpoint: str, task: dict, label: str = "") -> dict:
        name = label or endpoint
        data = json.loads((self.sample_dir / self.FILES[name]).read_text())
        # what the call cost when it was collected (it costs nothing to replay)
        self.cost_log.append({"endpoint": f"{endpoint}/live", "label": name,
                              "cost_usd": float(data.get("cost") or 0), "spent_so_far_usd": 0.0,
                              "source": "sample replay (cost when collected)"})
        return data


# ---------------------------------------------------------------------------
# Collection: the five calls the audit needs
# ---------------------------------------------------------------------------
def collection_plan(rd_limit: int = 1000, bl_limit: int = 1000, anchor_limit: int = 100,
                    broken_limit: int = 200) -> dict[str, int]:
    return {"summary": 1, "referring_domains": rd_limit, "backlinks": bl_limit,
            "anchors": anchor_limit, "broken_backlinks": broken_limit}


def collect_profile(client, target: str, include_subdomains: bool = True, rd_limit: int = 1000,
                    bl_limit: int = 1000, anchor_limit: int = 100, broken_limit: int = 200) -> dict[str, dict]:
    """Run the five Backlinks API calls and return the raw responses by name.
    Only live backlinks are counted (DataForSEO's default backlinks_status_type)."""
    base = {"target": target, "include_subdomains": include_subdomains}
    calls = {
        # profile totals: backlinks, referring domains, spam score, TLD / location breakdowns
        "summary": ("summary", {**base}),
        # one row per referring domain, strongest first
        "referring_domains": ("referring_domains", {**base, "limit": rd_limit, "order_by": ["rank,desc"]}),
        # one representative backlink per referring domain (the strongest link from it)
        "backlinks": ("backlinks", {**base, "mode": "one_per_domain", "limit": bl_limit,
                                    "order_by": ["rank,desc"]}),
        # most-used anchors
        "anchors": ("anchors", {**base, "limit": anchor_limit, "order_by": ["backlinks,desc"]}),
        # every live backlink that points at a URL answering 4xx/5xx
        "broken_backlinks": ("backlinks", {**base, "mode": "as_is", "limit": broken_limit,
                                           "filters": ["is_broken", "=", True],
                                           "order_by": ["domain_from_rank,desc"]}),
    }
    out = {}
    for name, (endpoint, task) in calls.items():
        data = client.live(endpoint, task, label=name)
        out[name] = data
        res = first_result(data)
        what = (f"{res.get('backlinks')} backlinks, {res.get('referring_main_domains')} referring main domains"
                if name == "summary" else
                f"total {res.get('total_count')}, returned {len(res.get('items') or [])}")
        print(f"  {name:18s} {what:52s} cost ${client.cost_log[-1]['cost_usd']:.4f}")
    return out


def first_result(data: dict) -> dict:
    """The first `result` object of a one-task response (or {})."""
    task = (data.get("tasks") or [{}])[0]
    return (task.get("result") or [{}])[0] or {}


def items(data: dict) -> list[dict]:
    return first_result(data).get("items") or []


# ---------------------------------------------------------------------------
# Flattening and features
# ---------------------------------------------------------------------------
def bare_domain(domain: str | None) -> str:
    """'www.example.co.uk' -> 'example.co.uk' so www and non-www count as one site."""
    d = (domain or "").lower().strip()
    return d[4:] if d.startswith("www.") else d


def summary_table(data: dict) -> pd.DataFrame:
    """Headline numbers from summary/live as a two-column table."""
    r = dict(first_result(data))
    r.update({k: v for k, v in (r.get("info") or {}).items() if k not in r})  # target_spam_score, cms ...
    keys = ["target", "rank", "backlinks", "referring_domains", "referring_main_domains",
            "referring_domains_nofollow", "referring_ips", "referring_subnets", "referring_pages",
            "backlinks_spam_score", "target_spam_score", "broken_backlinks", "broken_pages",
            "crawled_pages", "first_seen"]
    return pd.DataFrame([{"metric": k, "value": r.get(k)} for k in keys])


def summary_breakdown(data: dict, key: str, top: int = 15) -> pd.DataFrame:
    """One of the summary's breakdown objects (e.g. referring_links_tld) as a
    sorted table with a share column."""
    obj = first_result(data).get(key) or {}
    df = pd.DataFrame(sorted(obj.items(), key=lambda kv: -(kv[1] or 0)), columns=[key.split("_")[-1], "links"])
    if not df.empty:
        df["share"] = (df["links"] / df["links"].sum()).round(3)
    return df.head(top)


def referring_domains_df(data: dict) -> pd.DataFrame:
    rows = []
    for it in items(data):
        rows.append({"domain": bare_domain(it.get("domain")), "domain_rank": it.get("rank"),
                     "domain_backlinks": it.get("backlinks"), "domain_spam_score": it.get("backlinks_spam_score"),
                     "domain_first_seen": (it.get("first_seen") or "")[:10],
                     "domain_broken_backlinks": it.get("broken_backlinks"),
                     "referring_pages": it.get("referring_pages"),
                     "domain_nofollow_pages": it.get("referring_pages_nofollow")})
    return pd.DataFrame(rows)


BACKLINK_COLS = ["domain_from", "url_from", "page_from_title", "anchor", "item_type", "alt", "dofollow",
                 "attributes", "rank", "page_from_rank", "domain_from_rank", "backlink_spam_score",
                 "tld_from", "semantic_location", "first_seen", "last_seen", "is_new", "is_lost",
                 "is_broken", "url_to", "url_to_status_code", "url_to_redirect_target", "page_from_language",
                 "page_from_external_links", "domain_from_platform_type", "domain_from_country",
                 "group_count", "links_count", "text_pre", "text_post"]


def backlinks_df(data: dict) -> pd.DataFrame:
    rows = []
    for it in items(data):
        row = {c: it.get(c) for c in BACKLINK_COLS}
        row["domain_from"] = bare_domain(row["domain_from"])
        for c in ("attributes", "domain_from_platform_type"):
            row[c] = ", ".join(row[c] or []) if isinstance(row[c], list) else (row[c] or "")
        row["first_seen"] = (row["first_seen"] or "")[:10]
        row["last_seen"] = (row["last_seen"] or "")[:10]
        rows.append(row)
    return pd.DataFrame(rows, columns=BACKLINK_COLS)


def anchors_df(data: dict) -> pd.DataFrame:
    return pd.DataFrame([{"anchor": it.get("anchor"), "backlinks": it.get("backlinks"),
                          "referring_domains": it.get("referring_main_domains"),
                          "spam_score": it.get("backlinks_spam_score"), "rank": it.get("rank"),
                          "first_seen": (it.get("first_seen") or "")[:10]} for it in items(data)])


# Cheap TLDs that spam networks favour. A SIGNAL, not a verdict: plenty of real
# sites use them. Edit the list for your market.
SPAM_PRONE_TLDS = {"xyz", "top", "click", "buzz", "icu", "cyou", "cfd", "sbs", "monster", "rest", "bond",
                   "quest", "lol", "tk", "ml", "ga", "cf", "gq", "work", "loan", "win", "bid", "men",
                   "date", "racing", "review", "party", "stream", "download", "kim", "uno", "pw"}

CONTENT_LOCATIONS = {"article", "main", "section", "summary", "details", "figure", "figcaption", "p", "blockquote"}
BOILERPLATE_LOCATIONS = {"header", "footer", "nav", "aside"}

GENERIC_ANCHORS = {"click here", "here", "this", "read more", "more", "link", "website", "site", "source",
                   "this article", "this post", "this guide", "learn more", "view", "visit", "see", "check",
                   "check out", "check it out", "homepage", "home", "blog", "url", "web", "page", "this page",
                   "article", "post", "read", "details", "more info", "go", "via", "the website", "this tool",
                   "this site", "their website", "official website", "visit website", "visit site", "continue reading",
                   "this course", "the course", "this template", "this resource", "this list", "this one"}

# Phrases that only show up in automated link-selling anchors. Edit for your market.
SPAM_ANCHOR_TERMS = ["telegram", "t.me/", "backlinks", "pbn", "black hat", "black-links", "link building",
                     "casino", "betting", "viagra", "porn", "escort", "loan"]

URL_RE = re.compile(r"^(https?://|www\.)|^[\w-]+(\.[\w-]+)+(/\S*)?$", re.I)


def anchor_type(anchor: str | None, item_type: str | None, brand_terms: list[str], keyword_terms: list[str]) -> str:
    """branded / keyword / generic / naked_url / image_or_empty / spam_phrase / other.
    Order matters: an image link or an empty anchor is classed first, then
    link-selling phrases, URLs, brand, generic phrases and finally topic keywords."""
    a = anchor if isinstance(anchor, str) else ""      # None / NaN = no anchor text
    a = re.sub(r"\s+", " ", a).strip().lower()
    if item_type == "image" or not a:
        return "image_or_empty"
    if any(t in a for t in SPAM_ANCHOR_TERMS):
        return "spam_phrase"
    if URL_RE.search(a):
        return "naked_url"
    if any(b in a for b in brand_terms):
        return "branded"
    if a.strip(" .:!>»→-") in GENERIC_ANCHORS:
        return "generic"
    if any(re.search(rf"\b{re.escape(k)}\b", a) for k in keyword_terms):
        return "keyword"
    return "other"


def band(value, edges: list[tuple[float, str]], missing: str = "unknown") -> str:
    """Return the label of the first (upper_bound, label) whose bound the value is under."""
    if value is None or pd.isna(value):
        return missing
    for upper, label in edges:
        if value < upper:
            return label
    return edges[-1][1]


SPAM_BANDS = [(15, "low (0-14)"), (30, "moderate (15-29)"), (60, "elevated (30-59)"), (101, "high (60-100)")]
RANK_BANDS = [(50, "very low (<50)"), (150, "low (50-149)"), (300, "medium (150-299)"), (1001, "high (300+)")]


def match_main_domain(host: str, main_domains: set[str]) -> str:
    """'newsletter.example.com' -> 'example.com' if that main domain is in the set."""
    parts = host.split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in main_domains:
            return cand
    return host


def add_features(bl: pd.DataFrame, rd: pd.DataFrame, brand_terms: list[str], keyword_terms: list[str],
                 owned_domains: list[str] | None = None, review_patterns: list[str] | None = None,
                 today: str | None = None) -> pd.DataFrame:
    """Join domain-level metrics onto the one-per-domain backlinks and add the
    transparent rule features. Every column is something you can explain to a client."""
    # referring_domains/live lists main domains (example.com); backlinks/live gives
    # the host (blog.example.com), so match each host to the main domain it sits under
    df = bl.copy()
    df["main_domain"] = [match_main_domain(h, set(rd["domain"])) for h in df["domain_from"]]
    df = df.merge(rd, how="left", left_on="main_domain", right_on="domain").drop(columns=["domain"])
    brand_terms = [b.lower() for b in brand_terms]
    keyword_terms = [k.lower() for k in keyword_terms]
    today_ts = pd.Timestamp(today or datetime.now(timezone.utc).date().isoformat())
    df["anchor_type"] = [anchor_type(a, t, brand_terms, keyword_terms) for a, t in zip(df["anchor"], df["item_type"])]
    df["spam_band"] = df["backlink_spam_score"].map(lambda v: band(v, SPAM_BANDS))
    df["rank_band"] = df["domain_from_rank"].map(lambda v: band(v, RANK_BANDS))
    df["tld"] = df["tld_from"].fillna("").str.lower()
    df["spam_prone_tld"] = df["tld"].isin(SPAM_PRONE_TLDS)
    loc = df["semantic_location"].fillna("").str.lower()
    df["location_group"] = loc.map(lambda s: "content" if s in CONTENT_LOCATIONS
                                   else "boilerplate" if s in BOILERPLATE_LOCATIONS
                                   else "unknown" if not s else "other")
    df["link_age_days"] = (today_ts - pd.to_datetime(df["first_seen"], errors="coerce")).dt.days
    df["dofollow"] = df["dofollow"].fillna(False).astype(bool)
    owned = [o.lower() for o in (owned_domains or [])]
    df["owned"] = df["domain_from"].map(lambda d: any(d == o or d.endswith("." + o) for o in owned))
    text = (df["domain_from"].fillna("") + " " + df["page_from_title"].fillna("") + " "
            + df["anchor"].fillna("") + " " + df["url_from"].fillna("")).str.lower()
    pats = [p.lower() for p in (review_patterns or [])]
    df["review_hint"] = text.map(lambda t: ", ".join(p for p in pats if re.search(p, t)))
    return df


# ---------------------------------------------------------------------------
# Topical relevance with a small local embedding model
# ---------------------------------------------------------------------------
def relevance_text(row) -> str:
    parts = [str(row.get("page_from_title") or ""), str(row.get("anchor") or ""), str(row.get("domain_from") or "")]
    return " | ".join(p for p in parts if p and p != "nan")


def embed_relevance(df: pd.DataFrame, site_topic: str, model_name: str = "all-MiniLM-L6-v2") -> pd.Series:
    """Cosine similarity (clipped to 0-1) between each link's title + anchor +
    domain and a one-line description of your site. A proxy for topical fit,
    computed from metadata only; it never sees the linking page's body text."""
    import logging
    import warnings
    warnings.filterwarnings("ignore", message="IProgress not found")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")   # keep notebook output readable
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
    from sentence_transformers import SentenceTransformer
    try:
        from transformers.utils import logging as hf_logging
        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
    except Exception:
        pass
    model = SentenceTransformer(model_name)
    texts = [relevance_text(r) for _, r in df.iterrows()]
    vecs = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    topic = model.encode([site_topic], normalize_embeddings=True)[0]
    return pd.Series((vecs @ topic).clip(0, 1).round(3), index=df.index)


# ---------------------------------------------------------------------------
# Transparent rules: the clear cases. Everything else goes to Claude.
# ---------------------------------------------------------------------------
DEFAULT_RULES = {
    "spam_score_spam": 60,       # backlink spam score at or above this = likely spam
    "spam_score_tld": 30,        # ... or this high AND on a spam-prone TLD
    "spam_score_clean": 15,      # under this counts as clean for the Valuable rule
    "rank_valuable": 150,        # referring domain rank (0-1000 scale) for the Valuable rule
    "relevance_valuable": 0.30,  # topical relevance for the Valuable rule
    "relevance_floor": 0.10,     # under this, with an elevated spam score, = likely spam
}


def rule_bucket(row, rules: dict = DEFAULT_RULES) -> tuple[str, str]:
    """(bucket, reason) from the rules alone: 'own_site', 'likely_spam', 'valuable'
    or 'ambiguous'. A row with a review_hint (e.g. 'download', 'course') is never
    auto-valued: resellers and piracy sites look relevant, so a reviewer checks them."""
    spam = row.get("backlink_spam_score")
    spam = -1 if spam is None or pd.isna(spam) else spam
    rank = row.get("domain_from_rank") or 0
    rel = row.get("relevance") or 0
    if row.get("owned"):
        return "own_site", "one of your own sites (OWNED_DOMAINS)"
    if spam >= rules["spam_score_spam"]:
        return "likely_spam", f"spam score {int(spam)} >= {rules['spam_score_spam']}"
    if row.get("spam_prone_tld") and spam >= rules["spam_score_tld"]:
        return "likely_spam", f".{row.get('tld')} TLD with spam score {int(spam)}"
    if spam >= rules["spam_score_tld"] and rel < rules["relevance_floor"]:
        return "likely_spam", f"spam score {int(spam)} and off-topic (relevance {rel:.2f})"
    if (0 <= spam < rules["spam_score_clean"] and rank >= rules["rank_valuable"]
            and rel >= rules["relevance_valuable"] and not row.get("review_hint")):
        return "valuable", f"rank {int(rank)}, spam {int(spam)}, relevance {rel:.2f}"
    return "ambiguous", ""


def apply_rules(df: pd.DataFrame, rules: dict = DEFAULT_RULES) -> pd.DataFrame:
    out = df.copy()
    res = [rule_bucket(r, rules) for _, r in out.iterrows()]
    out["rule_bucket"] = [b for b, _ in res]
    out["rule_reason"] = [r for _, r in res]
    return out


# ---------------------------------------------------------------------------
# Claude review of the ambiguous middle
# ---------------------------------------------------------------------------
VERDICTS = ["keep_valuable", "keep_neutral", "ignore_spam", "investigate"]

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "verdict": {"type": "string", "enum": VERDICTS},
                    "reason": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["id", "verdict", "reason", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reviews"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You review backlinks for an SEO audit of the website {target}.
The site is about: {site_topic}

You only see metadata about each link (referring domain, page title, anchor text,
follow status, where on the page the link sits, DataForSEO rank and spam score,
TLD, first-seen date). You do NOT see the linking page itself. Do not invent facts about a site you cannot see; if the
metadata is not enough to decide, say so and choose "investigate".

For each link choose one verdict:
- keep_valuable: a real, relevant site or page that a person might follow to {target}
  (industry blogs, publications, courses, tools, communities, directories that real people use).
- keep_neutral: real but low value (generic directories, scrapers that copy titles,
  profile pages, aggregators, unrelated but harmless sites). Nothing to do.
- ignore_spam: clear signs of automated spam (gibberish or keyword-stuffed domains,
  link farms, casino/adult/pharma, SEO "stats" sites listing millions of domains).
  Google says it ignores most of these; no action needed.
- investigate: unusual enough that a human should look (for example a possible paid
  link, a hacked page, or a strong site with a spammy-looking anchor).

Notes on the fields: judge the topic from the title and anchor yourself, in any
language; an on-topic article in German, Japanese or Spanish is as good as one in
English. domain_rank (0-1000) and spam_score (0-100) are DataForSEO metrics, not
Google's. links_from_domain is how many links this domain sends to {target}. review_hint lists words such as "download", "sale page", "group buy" or
"course" found in the URL, title or anchor. Sites that list someone else's paid
courses as downloads, "sale pages" or group buys are often piracy or resellers,
even when they look on-topic: choose investigate for those and say why.

Reason: at most 20 words, based only on the metadata shown. Confidence: low, medium or high.
Return one review per link id, in the same order."""


def _row_for_llm(i: int, r) -> dict:
    def val(x):
        if hasattr(x, "item"):          # numpy int / float -> plain Python, so json.dumps works
            x = x.item()
        return None if x is None or (isinstance(x, float) and pd.isna(x)) else x
    return {"id": int(i), "domain": r.get("domain_from"), "title": (val(r.get("page_from_title")) or "")[:120],
            "anchor": (val(r.get("anchor")) or "")[:80], "dofollow": bool(r.get("dofollow")),
            "location": val(r.get("semantic_location")) or "unknown", "domain_rank": val(r.get("domain_from_rank")),
            "spam_score": val(r.get("backlink_spam_score")), "tld": r.get("tld"),
            "first_seen": r.get("first_seen"),
            "links_from_domain": val(r.get("group_count")), "review_hint": r.get("review_hint") or None}


class ClaudeReviewer:
    """Batch reviewer for the ambiguous rows. Uses the Messages API with
    structured outputs (output_config.format = json_schema), so every response
    parses. Logs tokens and cost per call and stops at its own spend cap.
    Responses are cached on disk by batch content, so a re-run does not pay twice."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5", max_spend_usd: float = 0.25,
                 cache_dir: str | Path | None = "output/raw/claude"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3)  # SDK retries 429/5xx with back-off
        self.model = model
        self.max_spend_usd = max_spend_usd
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.spent = 0.0
        self.cost_log: list[dict] = []
        self.raw: list[dict] = []          # every response, for saving sample data

    def price(self, usage_in: int, usage_out: int) -> float:
        p = LLM_PRICES.get(self.model, {"input": 1.0, "output": 5.0})
        return usage_in / 1e6 * p["input"] + usage_out / 1e6 * p["output"]

    def review_batch(self, batch: list[dict], system: str, max_tokens: int = 4000) -> list[dict]:
        key = hashlib.sha1(json.dumps([self.model, system, batch], sort_keys=True).encode()).hexdigest()[:12]
        cache = self.cache_dir / f"batch-{key}.json" if self.cache_dir else None
        if cache and cache.exists():
            rec = json.loads(cache.read_text())
            self.cost_log.append({"endpoint": "messages", "label": f"{len(batch)} rows", "model": self.model,
                                  "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                                  "source": f"cache (cost ${rec['cost_usd']:.4f} when collected)"})
            self.raw.append(rec)
            return rec["reviews"]
        # worst case for this call: input estimated at 4 characters per token, full max_tokens out
        worst = self.price(len(system + json.dumps(batch)) // 3, max_tokens)
        if self.spent + worst > self.max_spend_usd + 1e-9:
            raise RuntimeError(f"LLM spend cap: ${self.spent:.4f} spent, next call could cost ${worst:.4f}, "
                               f"cap ${self.max_spend_usd}. Raise MAX_LLM_SPEND_USD or review fewer rows.")
        user = ("Review these links. Each line is one link as JSON.\n\n"
                + "\n".join(json.dumps(b, ensure_ascii=False) for b in batch))
        resp = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        )
        if resp.stop_reason not in ("end_turn", "stop_sequence"):
            raise RuntimeError(f"Claude stopped early ({resp.stop_reason}); try a smaller BATCH_SIZE.")
        text = next(b.text for b in resp.content if b.type == "text")
        reviews = json.loads(text)["reviews"]
        cost = self.price(resp.usage.input_tokens, resp.usage.output_tokens)
        self.spent += cost
        self.cost_log.append({"endpoint": "messages", "label": f"{len(batch)} rows", "model": resp.model,
                              "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                              "cost_usd": round(cost, 6), "source": "live API"})
        rec = {"model": resp.model, "input_tokens": resp.usage.input_tokens,
               "output_tokens": resp.usage.output_tokens, "cost_usd": round(cost, 6),
               "domains": [b["domain"] for b in batch], "reviews": reviews}
        self.raw.append(rec)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(rec))
        return reviews


class SampleReviewer:
    """Replays the saved Claude reviews in sample_data/claude_reviews.json
    (one record per batch, keyed by referring domain). No key needed."""

    def __init__(self, path: str | Path = "sample_data/claude_reviews.json"):
        self.records = json.loads(Path(path).read_text())
        self.by_domain = {}
        for rec in self.records:
            for d, rv in zip(rec["domains"], rec["reviews"]):
                self.by_domain[d] = rv
        self.model = self.records[0]["model"] if self.records else "claude-haiku-4-5"
        self.spent = 0.0
        self.cost_log = [{"endpoint": "messages", "label": f"{len(r['domains'])} rows", "model": r["model"],
                          "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                          "cost_usd": r["cost_usd"], "source": "sample replay (cost when collected)"}
                         for r in self.records]

    def review_batch(self, batch: list[dict], system: str, max_tokens: int = 4000) -> list[dict]:
        out = []
        for b in batch:
            rv = self.by_domain.get(b["domain"])
            out.append({**rv, "id": b["id"]} if rv else
                       {"id": b["id"], "verdict": "investigate", "reason": "no saved review in sample data",
                        "confidence": "low"})
        return out


def estimate_llm_cost(n_rows: int, batch_size: int = 25, model: str = "claude-haiku-4-5",
                      tokens_in_per_row: int = 140, tokens_out_per_row: int = 45, system_tokens: int = 800) -> dict:
    """Rough worst-case cost of reviewing n_rows with Claude (token counts per row
    measured on the mlforseo.com run, rounded up)."""
    calls = -(-n_rows // batch_size) if n_rows else 0
    p = LLM_PRICES.get(model, {"input": 1.0, "output": 5.0})
    tin = calls * system_tokens + n_rows * tokens_in_per_row
    tout = n_rows * tokens_out_per_row
    return {"rows": n_rows, "calls": calls, "input_tokens_est": tin, "output_tokens_est": tout,
            "usd_est": round(tin / 1e6 * p["input"] + tout / 1e6 * p["output"], 4)}


def review_ambiguous(df: pd.DataFrame, reviewer, target: str, site_topic: str, batch_size: int = 25,
                     max_rows: int = 400) -> pd.DataFrame:
    """Send the rule-ambiguous rows (strongest domains first, up to max_rows) to
    the reviewer in batches. Returns the input with llm_* columns added."""
    out = df.copy()
    for c in ("llm_verdict", "llm_reason", "llm_confidence"):
        out[c] = None
    todo = out[out["rule_bucket"] == "ambiguous"].sort_values("domain_from_rank", ascending=False).head(max_rows)
    system = SYSTEM_PROMPT.format(target=target, site_topic=site_topic)
    idx = list(todo.index)
    for start in range(0, len(idx), batch_size):
        chunk = idx[start:start + batch_size]
        batch = [_row_for_llm(i, out.loc[i]) for i in chunk]
        reviews = reviewer.review_batch(batch, system)
        got = {rv["id"]: rv for rv in reviews}
        for i in chunk:
            rv = got.get(i)
            if rv:
                out.loc[i, ["llm_verdict", "llm_reason", "llm_confidence"]] = [rv["verdict"], rv["reason"],
                                                                               rv["confidence"]]
        print(f"  batch {start // batch_size + 1}: {len(chunk)} rows, {len(got)} reviews back"
              f"  (spent ${reviewer.spent:.4f})")
    return out


BUCKETS = {"keep_valuable": "Valuable", "keep_neutral": "Neutral", "ignore_spam": "Likely spam",
           "investigate": "Investigate"}


def final_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """One bucket per referring domain, with who decided it and why."""
    out = df.copy()
    bucket, by, why = [], [], []
    for _, r in out.iterrows():
        if r["rule_bucket"] == "own_site":
            bucket.append("Neutral"); by.append("rules (own site)"); why.append(r["rule_reason"])
        elif r["rule_bucket"] == "valuable":
            bucket.append("Valuable"); by.append("rules"); why.append(r["rule_reason"])
        elif r["rule_bucket"] == "likely_spam":
            bucket.append("Likely spam"); by.append("rules"); why.append(r["rule_reason"])
        elif r.get("llm_verdict") in BUCKETS:
            bucket.append(BUCKETS[r["llm_verdict"]]); by.append("claude"); why.append(r["llm_reason"])
        else:
            bucket.append("Neutral"); by.append("not reviewed"); why.append("ambiguous, over the review limit")
    out["bucket"], out["decided_by"], out["why"] = bucket, by, why
    return out


# ---------------------------------------------------------------------------
# Link reclamation: broken backlinks -> suggested redirect from the sitemap
# ---------------------------------------------------------------------------
def fetch_sitemap_urls(index_url: str, timeout: int = 30, max_sitemaps: int = 50) -> list[str]:
    """All <loc> URLs from a sitemap index (or a plain sitemap). Free, no key."""
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    headers = {"User-Agent": "Mozilla/5.0 (backlink-quality-audit; MLforSEO notebook)"}
    root = ElementTree.fromstring(requests.get(index_url, timeout=timeout, headers=headers).content)
    if root.tag.endswith("sitemapindex"):
        urls = []
        for loc in [e.text.strip() for e in root.iter(f"{ns}loc")][:max_sitemaps]:
            sub = ElementTree.fromstring(requests.get(loc, timeout=timeout, headers=headers).content)
            urls += [e.text.strip() for e in sub.iter(f"{ns}loc")]
        return sorted(set(urls))
    return sorted({e.text.strip() for e in root.iter(f"{ns}loc")})


def url_path(url: str) -> str:
    """'/blog/some-post/' -> 'blog some post' for fuzzy matching on words."""
    p = urlparse(url).path.lower()
    return re.sub(r"[\W_]+", " ", p).strip()


def check_status(urls: list[str], timeout: int = 15) -> pd.DataFrame:
    """Today's status for each dead URL (free): HTTP code after redirects and
    where it ends up. DataForSEO's url_to_status_code is from its last crawl."""
    rows = []
    headers = {"User-Agent": "Mozilla/5.0 (backlink-quality-audit; MLforSEO notebook)"}
    for u in urls:
        try:
            r = requests.get(u, timeout=timeout, allow_redirects=True, headers=headers)
            rows.append({"url_to": u, "status_now": r.status_code, "final_url_now": r.url,
                         "redirected_now": len(r.history) > 0})
        except requests.RequestException as e:
            rows.append({"url_to": u, "status_now": None, "final_url_now": None, "redirected_now": None,
                         "error": type(e).__name__})
        time.sleep(0.3)
    return pd.DataFrame(rows)


def suggest_redirects(broken: pd.DataFrame, live_urls: list[str], min_score: int = 60) -> pd.DataFrame:
    """One row per dead target URL: how many broken backlinks point at it, from
    how many domains, the strongest linking domain, and the closest live URL by
    fuzzy match on the path words (rapidfuzz token_set_ratio, 0-100)."""
    from rapidfuzz import fuzz, process
    if broken.empty:
        return pd.DataFrame()
    live_paths = {u: url_path(u) for u in live_urls}
    g = (broken.groupby("url_to")
         .agg(broken_backlinks=("url_from", "count"), referring_domains=("domain_from", "nunique"),
              status_code=("url_to_status_code", "first"), best_domain_rank=("domain_from_rank", "max"),
              example_linking_domain=("domain_from", "first"), dofollow_links=("dofollow", "sum"))
         .reset_index().sort_values(["referring_domains", "best_domain_rank"], ascending=False))
    sugg, score = [], []
    for u in g["url_to"]:
        q = url_path(u)
        # never suggest the dead URL itself (it may still be listed in the sitemap)
        cands = {k: v for k, v in live_paths.items() if k.rstrip("/") != u.rstrip("/")}
        hit = process.extractOne(q, cands, scorer=fuzz.token_set_ratio) if q and cands else None
        if hit and hit[1] >= min_score:          # hit = (matched path words, score, matched URL)
            sugg.append(hit[2]); score.append(round(hit[1]))
        else:
            sugg.append(None); score.append(round(hit[1]) if hit else None)
    g["in_sitemap"] = g["url_to"].map(lambda u: any(k.rstrip("/") == u.rstrip("/") for k in live_paths))
    g["suggested_redirect"], g["match_score"] = sugg, score
    return g


def reclamation_actions(reclaim: pd.DataFrame) -> pd.DataFrame:
    """Add a plain-English next step to each dead target URL."""
    out = reclaim.copy()

    def action(r):
        now = r.get("status_now")
        if pd.notna(now) and int(now) < 400:
            return ("already redirects today: nothing to do" if r.get("redirected_now")
                    else "loads today (fixed since DataForSEO's crawl): nothing to do")
        if r.get("in_sitemap"):
            return "still listed in your sitemap: check whether it loads before redirecting"
        if r.get("suggested_redirect"):
            return "add a 301 to suggested_redirect (check it is the right page first)"
        return "no close match: pick a redirect target by hand, or ask the linking site to update"
    out["action"] = [action(r) for _, r in out.iterrows()]
    return out


def share_table(s: pd.Series, name: str, weights: pd.Series | None = None) -> pd.DataFrame:
    """Counts (or summed weights) and share for one categorical column."""
    if weights is None:
        t = s.fillna("(none)").value_counts()
    else:
        t = weights.groupby(s.fillna("(none)")).sum().sort_values(ascending=False)
    return pd.DataFrame({name: t.index, "count": t.values, "share": (t.values / t.values.sum()).round(3)})


AUDIT_COLS = ["bucket", "decided_by", "why", "domain_from", "main_domain", "url_from", "page_from_title",
              "anchor", "anchor_type", "url_to", "dofollow", "semantic_location", "location_group",
              "domain_from_rank", "domain_rank", "backlink_spam_score", "spam_band", "domain_spam_score",
              "tld", "spam_prone_tld", "relevance", "review_hint", "owned", "first_seen", "link_age_days",
              "group_count", "domain_backlinks", "rule_bucket", "rule_reason", "llm_verdict",
              "llm_reason", "llm_confidence", "is_lost", "is_broken", "url_to_status_code"]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export(tables: dict[str, pd.DataFrame], out_dir: str | Path = "output", xlsx_name: str | None = None) -> list[Path]:
    """Write every table to CSV, plus (optionally) one Excel workbook with a tab
    per table that you can import straight into Google Sheets."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in tables.items():
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    if xlsx_name:
        p = out_dir / xlsx_name
        with pd.ExcelWriter(p) as xl:
            for name, df in tables.items():
                df.to_excel(xl, sheet_name=name[:31], index=False)
        written.append(p)
    return written
