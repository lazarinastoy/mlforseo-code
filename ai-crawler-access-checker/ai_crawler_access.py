"""
AI Crawler Access Checker: robots.txt + llms.txt + bot rules
============================================================

Companion code for the MLforSEO post "Your robots.txt might be the silent
killer of your AI traffic". By Lazarina Stoy, MLforSEO. MIT licence.

What it does, for one or many domains:

1. Fetches robots.txt (or reads a saved copy for offline mode).
2. Evaluates allow / block for a maintained list of AI crawlers and control
   tokens (GPTBot, OAI-SearchBot, ClaudeBot, Google-Extended, ...) on sample
   URLs, using Protego, a robots.txt parser that follows Google's spec
   (longest-match wins, Allow wins ties, * and $ wildcards).
3. Checks /llms.txt and /llms-full.txt (presence and basic llmstxt.org format).
4. Flags common mistakes (blanket blocks, blocking search bots when you meant
   to block training, Google-Extended misunderstandings, typos, ...).
5. Optional live check: requests a URL with each crawler's user-agent string
   and records the status code. This only detects user-agent based blocking.

Every crawler below was checked against the vendor's own documentation
(links in AI_AGENTS) on 24 October 2026. Vendors add and rename crawlers,
so re-check the docs before relying on this list.

Usage from Python:

    from ai_crawler_access import audit_domains
    results = audit_domains(["www.mlforseo.com"], paths=["/", "/blog/"])

Usage from the command line:

    python ai_crawler_access.py www.mlforseo.com www.nytimes.com --out results/
    python ai_crawler_access.py --offline sample_data --out results/
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from protego import Protego

# ---------------------------------------------------------------------------
# 1. The crawler list
# ---------------------------------------------------------------------------
# category values:
#   "AI training"            collects data to train models
#   "AI search / answers"    indexes or fetches pages to show and cite in AI answers
#   "User-initiated fetch"   fetches a page because a person asked the assistant to
#   "Search engine"          classic search crawler (Google, Bing, Apple)
#   "Control token"          never crawls; only read in robots.txt to decide data use
#   "Other"                  link previews, site-owner requested crawls, etc.
#
# ua_string: the user-agent header used for the optional live check.
#   ua_source "vendor docs" = copied from the vendor page.
#   ua_source "approximation" = the vendor does not publish a full string, so we
#   build one around the documented token. None = control token, no live check.

DOCS = {
    "openai": "https://developers.openai.com/api/docs/bots",
    "anthropic": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
    "perplexity": "https://docs.perplexity.ai/guides/bots",
    "google_common": "https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers",
    "googlebot": "https://developers.google.com/search/docs/crawling-indexing/googlebot",
    "apple": "https://support.apple.com/en-us/119829",
    "bing": "https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0",
    "commoncrawl": "https://commoncrawl.org/ccbot",
    "meta": "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers/",
    "amazon": "https://developer.amazon.com/amazonbot",
    "mistral": "https://docs.mistral.ai/robots",
    "duckduckgo": "https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot",
}


def _approx_ua(token: str) -> str:
    return f"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; {token}/1.0)"


AI_AGENTS = [
    # --- OpenAI ---
    dict(token="GPTBot", vendor="OpenAI", category="AI training",
         controls="Crawls content that may be used to train OpenAI's generative AI foundation models.",
         honours_robots="yes", docs=DOCS["openai"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.4; +https://openai.com/gptbot"),
    dict(token="OAI-SearchBot", vendor="OpenAI", category="AI search / answers",
         controls="Surfaces websites in ChatGPT's search features. Block it and your pages can't appear as ChatGPT search results.",
         honours_robots="yes", docs=DOCS["openai"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot"),
    dict(token="ChatGPT-User", vendor="OpenAI", category="User-initiated fetch",
         controls="Visits a page when a ChatGPT or Custom GPT user asks it to.",
         honours_robots="may not apply (user-initiated)", docs=DOCS["openai"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    # --- Anthropic ---
    dict(token="ClaudeBot", vendor="Anthropic", category="AI training",
         controls="Collects public web content that may be used to train Anthropic's models.",
         honours_robots="yes", docs=DOCS["anthropic"], ua_source="approximation",
         ua_string=_approx_ua("ClaudeBot")),
    dict(token="Claude-SearchBot", vendor="Anthropic", category="AI search / answers",
         controls="Indexes pages to improve the quality of Claude's search results.",
         honours_robots="yes", docs=DOCS["anthropic"], ua_source="approximation",
         ua_string=_approx_ua("Claude-SearchBot")),
    dict(token="Claude-User", vendor="Anthropic", category="User-initiated fetch",
         controls="Fetches a page when a Claude user asks a question that needs it.",
         honours_robots="yes", docs=DOCS["anthropic"], ua_source="approximation",
         ua_string=_approx_ua("Claude-User")),
    # --- Perplexity ---
    dict(token="PerplexityBot", vendor="Perplexity", category="AI search / answers",
         controls="Surfaces and links websites in Perplexity search results. Perplexity says it is not used to crawl content for AI foundation models.",
         honours_robots="yes", docs=DOCS["perplexity"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    dict(token="Perplexity-User", vendor="Perplexity", category="User-initiated fetch",
         controls="Fetches a page when a Perplexity user asks a question.",
         honours_robots="generally ignores robots.txt (vendor docs)", docs=DOCS["perplexity"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)"),
    # --- Google ---
    dict(token="Googlebot", vendor="Google", category="Search engine",
         controls="Google Search, including AI Overviews and AI Mode. Blocking it removes you from Search, AI features included.",
         honours_robots="yes", docs=DOCS["googlebot"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    dict(token="Google-Extended", vendor="Google", category="Control token",
         controls="Whether content Google crawls may be used to train future Gemini models and for grounding in Gemini Apps and Vertex AI. Does NOT affect Google Search inclusion or ranking, so it does not control AI Overviews or AI Mode.",
         honours_robots="yes (token only, no separate crawler)", docs=DOCS["google_common"], ua_source=None, ua_string=None),
    dict(token="Google-CloudVertexBot", vendor="Google", category="Other",
         controls="Crawls requested by site owners for building Vertex AI Agents.",
         honours_robots="yes", docs=DOCS["google_common"], ua_source="approximation",
         ua_string=_approx_ua("Google-CloudVertexBot")),
    # --- Microsoft ---
    dict(token="Bingbot", vendor="Microsoft", category="Search engine",
         controls="Bing Search. Microsoft has no separate AI-search crawler token, so Bingbot access also matters for Copilot answers that draw on Bing.",
         honours_robots="yes", docs=DOCS["bing"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    # --- Apple ---
    dict(token="Applebot", vendor="Apple", category="Search engine",
         controls="Search in Spotlight, Siri and Safari. Apple says crawled data may also be used to train its foundation models unless you disallow Applebot-Extended.",
         honours_robots="yes", docs=DOCS["apple"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"),
    dict(token="Applebot-Extended", vendor="Apple", category="Control token",
         controls="Opt-out from Apple using Applebot-crawled data to train generative AI models. Does not crawl; pages stay in Apple search.",
         honours_robots="yes (token only, no separate crawler)", docs=DOCS["apple"], ua_source=None, ua_string=None),
    # --- Amazon ---
    dict(token="Amazonbot", vendor="Amazon", category="AI training",
         controls="Improves Amazon products and services; Amazon says the data may be used to train Amazon AI models.",
         honours_robots="yes", docs=DOCS["amazon"], ua_source="vendor docs (Chrome version filled in)",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1) Chrome/119.0.6045.214 Safari/537.36"),
    dict(token="Amzn-SearchBot", vendor="Amazon", category="AI search / answers",
         controls="Improves search experiences in Amazon products (for example Alexa and Rufus). Amazon says it does not crawl for generative AI training.",
         honours_robots="yes", docs=DOCS["amazon"], ua_source="vendor docs (Chrome version filled in)",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-SearchBot/0.1) Chrome/119.0.6045.214 Safari/537.36"),
    dict(token="Amzn-User", vendor="Amazon", category="User-initiated fetch",
         controls="Supports user actions, such as answering Alexa questions that need up-to-date information.",
         honours_robots="may not follow all directives (user-initiated)", docs=DOCS["amazon"], ua_source="vendor docs (Chrome version filled in)",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-User/0.1) Chrome/119.0.6045.214 Safari/537.36"),
    # --- Meta ---
    dict(token="Meta-ExternalAgent", vendor="Meta", category="AI training",
         controls="Crawls the web for use cases such as training AI models or improving products.",
         honours_robots="yes", docs=DOCS["meta"], ua_source="approximation",
         ua_string="meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    dict(token="Meta-WebIndexer", vendor="Meta", category="AI search / answers",
         controls="Improves Meta AI search result quality.",
         honours_robots="yes", docs=DOCS["meta"], ua_source="approximation",
         ua_string="meta-webindexer/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    dict(token="Meta-ExternalFetcher", vendor="Meta", category="User-initiated fetch",
         controls="Fetches individual links at a user's request.",
         honours_robots="may bypass robots.txt (vendor docs)", docs=DOCS["meta"], ua_source="approximation",
         ua_string="meta-externalfetcher/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    dict(token="facebookexternalhit", vendor="Meta", category="Other",
         controls="Builds link previews when a URL is shared in Meta's apps.",
         honours_robots="may bypass for security checks (vendor docs)", docs=DOCS["meta"], ua_source="vendor docs",
         ua_string="facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"),
    # --- Mistral ---
    dict(token="MistralAI-Training", vendor="Mistral AI", category="AI training",
         controls="Builds datasets to train Mistral's generative AI models.",
         honours_robots="yes", docs=DOCS["mistral"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-Training/1.0; +https://docs.mistral.ai/robots)"),
    dict(token="MistralAI-Index", vendor="Mistral AI", category="AI search / answers",
         controls="Indexes content for Mistral's search features. Mistral says it is not used for training.",
         honours_robots="yes", docs=DOCS["mistral"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-Index/1.0; +https://docs.mistral.ai/robots)"),
    dict(token="MistralAI-User", vendor="Mistral AI", category="User-initiated fetch",
         controls="Visits a page when a Mistral user asks it to.",
         honours_robots="see vendor docs", docs=DOCS["mistral"], ua_source="vendor docs",
         ua_string="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots)"),
    # --- DuckDuckGo ---
    dict(token="DuckAssistBot", vendor="DuckDuckGo", category="AI search / answers",
         controls="Fetches pages in real time for DuckDuckGo's AI-assisted answers. DuckDuckGo says the data is not used to train AI models.",
         honours_robots="yes", docs=DOCS["duckduckgo"], ua_source="vendor docs",
         ua_string="DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)"),
    # --- Dataset builders and others ---
    dict(token="CCBot", vendor="Common Crawl", category="AI training",
         controls="Builds the open Common Crawl dataset, which is widely used to train AI models.",
         honours_robots="yes", docs=DOCS["commoncrawl"], ua_source="vendor docs",
         ua_string="CCBot/2.0 (https://commoncrawl.org/faq/)"),
    dict(token="Bytespider", vendor="ByteDance", category="AI training",
         controls="ByteDance's crawler, widely reported to collect AI training data.",
         honours_robots="unverified: no official ByteDance documentation found", docs="", ua_source="approximation",
         ua_string="Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)"),
]

# Vendor pairs: (training agent, search agent). Used to spot "blocked search when
# you probably only meant to block training".
TRAINING_SEARCH_PAIRS = [
    ("GPTBot", "OAI-SearchBot"),
    ("ClaudeBot", "Claude-SearchBot"),
    ("Amazonbot", "Amzn-SearchBot"),
    ("MistralAI-Training", "MistralAI-Index"),
    ("Meta-ExternalAgent", "Meta-WebIndexer"),
]

# Tokens that show up in robots.txt files but are not in the vendor's current docs.
LEGACY_TOKENS = {
    "anthropic-ai": "Not in Anthropic's current crawler docs. Use ClaudeBot (training), Claude-SearchBot and Claude-User.",
    "claude-web": "Not in Anthropic's current crawler docs. Use ClaudeBot (training), Claude-SearchBot and Claude-User.",
}

USER_AGENT = "MLforSEO-AI-Crawler-Access-Checker/1.0 (+https://www.mlforseo.com)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
GOOGLE_ROBOTS_LIMIT = 500 * 1024  # Google ignores anything after 500 KiB
MAX_DOWNLOAD = 2 * 1024 * 1024    # never read more than 2 MB (some llms-full.txt files are 40 MB+)


def agents_table() -> pd.DataFrame:
    """The crawler list as a DataFrame (handy for the notebook and the export)."""
    return pd.DataFrame(AI_AGENTS)[
        ["vendor", "token", "category", "controls", "honours_robots", "ua_source", "docs"]
    ]


# ---------------------------------------------------------------------------
# 2. Fetching
# ---------------------------------------------------------------------------

@dataclass
class Fetched:
    url: str
    status: int | None = None
    final_url: str = ""
    content_type: str = ""
    text: str = ""
    size_bytes: int | None = None
    truncated: bool = False
    error: str = ""


def normalise_domain(domain: str) -> str:
    """'mlforseo.com/blog' -> 'https://mlforseo.com'. Keeps www if you typed it."""
    domain = domain.strip()
    if not re.match(r"^https?://", domain):
        domain = "https://" + domain
    p = urlparse(domain)
    return f"{p.scheme}://{p.netloc}"


def fetch(url: str, user_agent: str = USER_AGENT, timeout: int = 20) -> Fetched:
    """GET a URL, following redirects, reading at most MAX_DOWNLOAD bytes."""
    out = Fetched(url=url)
    try:
        with requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout,
                          stream=True, allow_redirects=True) as r:
            out.status = r.status_code
            out.final_url = r.url
            out.content_type = r.headers.get("Content-Type", "")
            body = b""
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) >= MAX_DOWNLOAD:
                    out.truncated = True
                    break
            # Decoded size. (Content-Length is the compressed size, so we don't use it.)
            out.size_bytes = len(body)
            out.text = body.decode(r.encoding or "utf-8", errors="replace")
    except requests.RequestException as e:
        out.error = type(e).__name__ + ": " + str(e)[:200]
    return out


def fetch_robots(origin: str) -> Fetched:
    """Fetch robots.txt. If the site refuses our honest UA (403), retry once as a browser."""
    f = fetch(origin + "/robots.txt")
    if f.status in (401, 403):
        retry = fetch(origin + "/robots.txt", user_agent=BROWSER_UA)
        if retry.status == 200:
            retry.error = "403 for the checker's user agent; fetched with a browser user agent instead"
            return retry
    return f


def load_offline(sample_dir: str | Path, host: str) -> dict:
    """Read saved files for offline mode: robots/<host>.txt and llms/<host>__llms.txt etc."""
    sample_dir = Path(sample_dir)
    out = {}
    for key, rel in [("robots", f"robots/{host}.txt"),
                     ("llms", f"llms/{host}__llms.txt"),
                     ("llms_full", f"llms/{host}__llms-full.txt")]:
        p = sample_dir / rel
        url = f"https://{host}/" + {"robots": "robots.txt", "llms": "llms.txt", "llms_full": "llms-full.txt"}[key]
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            ctype = "text/html" if txt.lstrip().lower().startswith(("<!doctype", "<html")) else "text/plain"
            out[key] = Fetched(url=url, status=200, final_url=url, content_type=ctype,
                               text=txt, size_bytes=len(txt.encode()))
        else:
            out[key] = Fetched(url=url, status=404, final_url=url, content_type="text/html")
    return out


# ---------------------------------------------------------------------------
# 3. robots.txt evaluation
# ---------------------------------------------------------------------------

UA_LINE = re.compile(r"^\s*user-agent\s*:\s*(.*?)\s*(#.*)?$", re.I)


def product_token(value: str) -> str:
    """The part of a user-agent value crawlers compare, like Google's parser:
    letters, '-' and '_' up to the first other character. 'meta-webindexer/1.1'
    -> 'meta-webindexer'. '*' stays '*'."""
    value = value.strip()
    if value.startswith("*"):
        return "*"
    m = re.match(r"[A-Za-z_-]+", value)
    return m.group(0) if m else value


def group_tokens(robots_txt: str) -> list[str]:
    """All user-agent values named in the file, in order, as written."""
    tokens = []
    for line in robots_txt.splitlines():
        m = UA_LINE.match(line)
        if m and m.group(1):
            tokens.append(m.group(1))
    return tokens


def _strict_text(robots_txt: str, token: str) -> str:
    """Rewrite the file so only groups whose user-agent EXACTLY equals `token`
    (case-insensitive) or '*' survive. RFC 9309 and Google's parser match the
    product token exactly; Protego is more generous and also matches prefixes
    such as 'User-agent: Claude' for ClaudeBot. Renaming the other groups keeps
    the file structure intact while removing that generosity."""
    lines = []
    for line in robots_txt.splitlines():
        m = UA_LINE.match(line)
        if m:
            value = product_token(m.group(1))
            if value != "*" and value.lower() != token.lower():
                line = "User-agent: zz-not-this-bot"
            else:
                line = f"User-agent: {value}"
        lines.append(line)
    return "\n".join(lines)


def can_fetch(robots_txt: str, token: str, url: str, strict: bool = True) -> bool:
    text = _strict_text(robots_txt, token) if strict else robots_txt
    return Protego.parse(text).can_fetch(url, token)


def matched_group(robots_txt: str, token: str) -> str:
    """Which group applies to this token under exact matching: the token itself, '*' or none."""
    toks = [product_token(t).lower() for t in group_tokens(robots_txt)]
    if token.lower() in toks:
        return token
    if "*" in toks:
        return "*"
    return "(none: everything allowed)"


def evaluate_robots(origin: str, robots: Fetched, paths: list[str]) -> pd.DataFrame:
    """One row per agent x path with the allow/block decision."""
    rows = []
    status = robots.status
    for a in AI_AGENTS:
        for path in paths:
            url = urljoin(origin + "/", path.lstrip("/"))
            row = dict(site=origin, token=a["token"], vendor=a["vendor"], category=a["category"],
                       path=path, url=url)
            if robots.error and status is None:
                row.update(decision="unknown", group="", basis=f"robots.txt not reachable ({robots.error})")
            elif status is not None and status >= 500 or status == 429:
                row.update(decision="blocked", group="",
                           basis=f"robots.txt returned {status}: Google treats this as a full disallow until it can fetch the file")
            elif status is not None and 400 <= status < 500:
                row.update(decision="allowed", group="",
                           basis=f"robots.txt returned {status}: crawlers treat this as no restrictions")
            else:
                strict = can_fetch(robots.text, a["token"], url, strict=True)
                lenient = can_fetch(robots.text, a["token"], url, strict=False)
                basis = "exact token match (RFC 9309 / Google)"
                if strict != lenient:
                    basis += (f"; a prefix-matching parser would say {'allowed' if lenient else 'blocked'} "
                              "(see the partial-token flag)")
                row.update(decision="allowed" if strict else "blocked",
                           group=matched_group(robots.text, a["token"]), basis=basis)
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. llms.txt checks (format from https://llmstxt.org/)
# ---------------------------------------------------------------------------

MD_LINK = re.compile(r"\[[^\]]+\]\((https?://|/)[^)]+\)")


def check_llms(f: Fetched, origin: str, kind: str) -> dict:
    """Presence and basic validity of llms.txt / llms-full.txt."""
    row = dict(site=origin, file=kind, url=f.url, status=f.status, final_url=f.final_url,
               content_type=f.content_type, size_bytes=f.size_bytes, present=False,
               valid_basic=False, h1_title="", has_summary=False, h2_sections=0,
               markdown_links=0, notes="")
    if f.error:
        row["notes"] = f.error
        return row
    if f.status != 200:
        row["notes"] = f"not found ({f.status})"
        return row
    body = f.text.lstrip("﻿")
    looks_html = body.lstrip().lower().startswith(("<!doctype", "<html")) or "text/html" in f.content_type.lower()
    redirected_home = urlparse(f.final_url).path in ("", "/")
    if looks_html or redirected_home:
        row["notes"] = ("returns 200 but serves an HTML page or redirects to the homepage, "
                        "so it is effectively missing (a 'soft 404')")
        return row
    row["present"] = True
    lines = [l for l in body.splitlines() if l.strip()]
    first = lines[0].strip() if lines else ""
    row["h1_title"] = first[2:].strip() if first.startswith("# ") else ""
    row["has_summary"] = any(l.lstrip().startswith(">") for l in lines[:10])
    row["h2_sections"] = sum(1 for l in lines if l.startswith("## "))
    row["markdown_links"] = len(MD_LINK.findall(body))
    notes = []
    if not row["h1_title"]:
        notes.append("first line should be an H1 ('# Site name'), the only required element")
    if kind == "llms.txt":
        if not row["has_summary"]:
            notes.append("no '> ' summary blockquote near the top (recommended)")
        if row["h2_sections"] == 0:
            notes.append("no '## ' sections with link lists")
        if row["markdown_links"] == 0:
            notes.append("no markdown links found")
    if f.truncated:
        notes.append(f"large file: only the first {MAX_DOWNLOAD // 1024 // 1024} MB were read")
    row["valid_basic"] = bool(row["h1_title"]) and (kind != "llms.txt" or row["markdown_links"] > 0)
    row["notes"] = "; ".join(notes) if notes else "looks well formed"
    return row


# ---------------------------------------------------------------------------
# 5. Common mistakes
# ---------------------------------------------------------------------------

def find_mistakes(origin: str, robots: Fetched, decisions: pd.DataFrame) -> list[dict]:
    """Rules of thumb that catch the most common robots.txt problems for AI visibility."""
    flags = []

    def flag(severity, issue, detail):
        flags.append(dict(site=origin, severity=severity, issue=issue, detail=detail))

    if robots.status is None:
        flag("high", "robots.txt unreachable", robots.error or "no response")
        return flags
    if robots.status >= 500 or robots.status == 429:
        flag("high", f"robots.txt returns {robots.status}",
             "Google stops crawling while robots.txt errors, then falls back to a cached copy. Fix the server response.")
        return flags
    if 400 <= robots.status < 500:
        flag("info", f"No robots.txt ({robots.status})",
             "Crawlers treat a missing robots.txt as 'everything allowed'. Fine if that is what you want.")
        return flags
    if robots.error:
        flag("medium", "robots.txt blocked for unknown user agents", robots.error +
             ". A firewall that blocks unknown bots from robots.txt may also block AI crawlers from the file.")

    text = robots.text
    if "text/html" in robots.content_type.lower() or text.lstrip().lower().startswith(("<!doctype", "<html")):
        flag("high", "robots.txt serves HTML",
             "The URL returns a web page instead of a plain-text robots.txt. Parsers will find no valid rules.")
    if robots.size_bytes and robots.size_bytes > GOOGLE_ROBOTS_LIMIT:
        flag("medium", "robots.txt over 500 KiB", "Google ignores everything after the first 500 KiB.")

    home = decisions[decisions["path"] == decisions["path"].iloc[0]].set_index("token")["decision"]

    def blocked(tok):
        return home.get(tok) == "blocked"

    # Blanket block for every bot without its own group
    if not can_fetch(text, "zz-any-other-bot", origin + "/", strict=True):
        allowed_named = [t for t in home.index if not blocked(t)]
        flag("high", "Blanket 'Disallow: /' for all bots",
             "The '*' group blocks the homepage for every crawler without its own group, AI search and "
             "user-initiated fetchers included. " + (f"Explicitly allowed: {', '.join(allowed_named)}."
                                                     if allowed_named else "No AI crawler is explicitly allowed."))

    if blocked("Googlebot"):
        flag("high", "Googlebot blocked",
             "This removes the page from Google Search, including AI Overviews and AI Mode. "
             "Google-Extended is the token for Gemini training and grounding, not Googlebot. "
             "Some large sites serve a different robots.txt to verified crawlers, so confirm in Search Console's robots.txt report.")

    if blocked("Google-Extended") and not blocked("Googlebot"):
        flag("info", "Google-Extended blocked (check the intent)",
             "This opts out of Gemini model training and grounding in Gemini Apps / Vertex AI. It does NOT remove "
             "you from Google Search, AI Overviews or AI Mode. To limit what AI features show from a page, Google "
             "points to nosnippet, data-nosnippet, max-snippet or noindex.")

    if blocked("Applebot") and not blocked("Applebot-Extended"):
        flag("medium", "Applebot blocked, Applebot-Extended allowed",
             "Blocking Applebot removes you from Siri, Spotlight and Safari search. To opt out of Apple's AI "
             "training only, allow Applebot and disallow Applebot-Extended.")

    for train, search in TRAINING_SEARCH_PAIRS:
        if blocked(train) and blocked(search):
            flag("medium", f"{search} blocked along with {train}",
                 f"{train} is the training crawler; {search} is the search crawler. If you only meant to opt out "
                 f"of training, allow {search} so your pages can still be found and cited.")
        elif blocked(search) and not blocked(train):
            flag("high", f"{search} blocked but {train} allowed",
                 "This is usually the wrong way round: the site can be used for training but can't be cited in search.")

    for tok in ["PerplexityBot", "DuckAssistBot"]:
        if blocked(tok):
            flag("medium", f"{tok} blocked", f"{tok} powers AI search answers that cite and link sources, not model training.")

    user_blocked = [t for t in home.index if blocked(t)
                    and next(a for a in AI_AGENTS if a["token"] == t)["category"] == "User-initiated fetch"]
    if user_blocked:
        flag("info", "User-initiated fetchers disallowed",
             f"{', '.join(user_blocked)}: some vendors say robots.txt may not apply to fetches a user asked for "
             "(OpenAI, Perplexity, Amazon, Meta). robots.txt is a request, not access control. Use your firewall/CDN if you must block.")

    # Typos, legacy tokens and partial tokens
    known = {a["token"].lower(): a["token"] for a in AI_AGENTS}
    squash = {re.sub(r"[^a-z0-9]", "", k): v for k, v in known.items()}
    for raw in sorted(set(group_tokens(text)), key=str.lower):
        low = product_token(raw).lower()
        if low != raw.strip().lower() and low in known:
            flag("info", f"Version or extra text in token '{raw}'",
                 f"Google's parser reads this as '{known[low]}', but simpler parsers may not. Use the bare token.")
        if low == "*" or low in known:
            continue
        if low in LEGACY_TOKENS:
            flag("low", f"Outdated token '{raw}'", LEGACY_TOKENS[low])
            continue
        sq = re.sub(r"[^a-z0-9]", "", low)
        close = [squash[sq]] if sq in squash else [known[c] for c in
                                                    difflib.get_close_matches(low, known.keys(), n=1, cutoff=0.93)]
        if close:
            flag("medium", f"Possible typo: '{raw}'",
                 f"Did you mean '{close[0]}'? Crawlers match the token exactly, so this group may be ignored.")
            continue
        prefix_of = [known[k] for k in known if k.startswith(low) and k != low]
        if prefix_of:
            flag("medium", f"Partial token '{raw}'",
                 f"Matches the start of {', '.join(prefix_of)}. RFC 9309 and Google match the full token, so these "
                 "crawlers may ignore this group. Name each crawler in full.")
    return flags


# ---------------------------------------------------------------------------
# 6. Optional live user-agent check
# ---------------------------------------------------------------------------

def live_ua_check(url: str, pause: float = 1.0) -> pd.DataFrame:
    """Request one URL with each crawler's user-agent string and record what comes back.

    Caveat: this only detects blocking based on the user-agent header. Most CDNs
    (Cloudflare, Akamai, Fastly) verify real crawlers by IP range or reverse DNS,
    so a spoofed request can be blocked as a fake bot even when the real crawler
    gets through, or let through when the real one is blocked. Treat it as a hint.
    """
    rows = []
    baseline = fetch(url, user_agent=BROWSER_UA)
    rows.append(dict(token="(browser baseline)", ua_source="", status=baseline.status,
                     final_url=baseline.final_url, bytes=baseline.size_bytes, error=baseline.error))
    for a in AI_AGENTS:
        if not a["ua_string"]:
            continue
        time.sleep(pause)
        f = fetch(url, user_agent=a["ua_string"])
        rows.append(dict(token=a["token"], ua_source=a["ua_source"], status=f.status,
                         final_url=f.final_url, bytes=f.size_bytes, error=f.error))
    df = pd.DataFrame(rows)
    df["differs_from_browser"] = df["status"] != baseline.status
    if baseline.status != 200:
        print(f"Warning: the normal browser request got {baseline.status or baseline.error}. The site's bot "
              "protection is probably blocking your IP or network (common from Colab and cloud servers), "
              "so the per-bot results below say little about what the real crawlers get.")
    return df


# ---------------------------------------------------------------------------
# 7. Put it together
# ---------------------------------------------------------------------------

@dataclass
class AuditResult:
    summary: pd.DataFrame
    decisions: pd.DataFrame
    llms: pd.DataFrame
    flags: pd.DataFrame
    robots_files: dict = field(default_factory=dict)


def audit_domains(domains: list[str], paths: list[str] | None = None,
                  offline_dir: str | Path | None = None, pause: float = 1.0) -> AuditResult:
    """Run the whole audit. `offline_dir` = folder with saved files (no network)."""
    paths = paths or ["/"]
    all_dec, all_llms, all_flags, summary, files = [], [], [], [], {}
    for d in domains:
        origin = normalise_domain(d)
        host = urlparse(origin).netloc
        if offline_dir:
            saved = load_offline(offline_dir, host)
            robots, llms, llms_full = saved["robots"], saved["llms"], saved["llms_full"]
        else:
            robots = fetch_robots(origin)
            llms = fetch(origin + "/llms.txt")
            llms_full = fetch(origin + "/llms-full.txt")
            time.sleep(pause)
        files[host] = robots.text
        dec = evaluate_robots(origin, robots, paths)
        flags = find_mistakes(origin, robots, dec)
        lrows = [check_llms(llms, origin, "llms.txt"), check_llms(llms_full, origin, "llms-full.txt")]
        home = dec[dec["path"] == paths[0]]
        by_cat = home.groupby("category")["decision"].apply(lambda s: f"{(s == 'blocked').sum()}/{len(s)} blocked")
        summary.append(dict(
            site=origin, robots_status=robots.status, robots_bytes=robots.size_bytes,
            agents_blocked_on_home=int((home["decision"] == "blocked").sum()), agents_checked=len(home),
            training_bots=by_cat.get("AI training", ""), search_answer_bots=by_cat.get("AI search / answers", ""),
            user_fetchers=by_cat.get("User-initiated fetch", ""),
            googlebot=home.set_index("token")["decision"].get("Googlebot", ""),
            google_extended=home.set_index("token")["decision"].get("Google-Extended", ""),
            llms_txt=lrows[0]["present"], llms_full_txt=lrows[1]["present"],
            high_flags=sum(f["severity"] == "high" for f in flags),
            all_flags=len(flags),
        ))
        all_dec.append(dec)
        all_llms.extend(lrows)
        all_flags.extend(flags)
    return AuditResult(
        summary=pd.DataFrame(summary),
        decisions=pd.concat(all_dec, ignore_index=True),
        llms=pd.DataFrame(all_llms),
        flags=pd.DataFrame(all_flags, columns=["site", "severity", "issue", "detail"]),
        robots_files=files,
    )


def access_matrix(decisions: pd.DataFrame, path: str | None = None) -> pd.DataFrame:
    """Sites as rows, crawlers as columns, for one path (default: the first path)."""
    path = path or decisions["path"].iloc[0]
    d = decisions[decisions["path"] == path]
    order = [a["token"] for a in AI_AGENTS]
    m = d.pivot(index="site", columns="token", values="decision")
    return m[[t for t in order if t in m.columns]]


def export(result: AuditResult, out_dir: str | Path = "results") -> list[Path]:
    """CSV files plus one Sheets-ready .xlsx workbook with a tab per table."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "summary": result.summary,
        "access_matrix": access_matrix(result.decisions).reset_index(),
        "decisions": result.decisions,
        "flags": result.flags,
        "llms_txt": result.llms,
        "crawler_list": agents_table(),
    }
    written = []
    for name, df in tables.items():
        p = out_dir / f"ai_crawler_{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    xlsx = out_dir / "ai_crawler_access_audit.xlsx"
    with pd.ExcelWriter(xlsx) as xw:
        for name, df in tables.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    written.append(xlsx)
    return written


def main():
    ap = argparse.ArgumentParser(description="Check AI crawler access in robots.txt and llms.txt.")
    ap.add_argument("domains", nargs="*", help="domains, e.g. www.mlforseo.com")
    ap.add_argument("--paths", default="/", help="comma-separated paths to test, e.g. /,/blog/,/wp-admin/")
    ap.add_argument("--offline", help="folder with saved robots/ and llms/ files (no network)")
    ap.add_argument("--live-ua", help="also request this URL with each crawler user agent")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    domains = args.domains
    if args.offline and not domains:
        domains = [p.stem for p in sorted(Path(args.offline, "robots").glob("*.txt"))]
    res = audit_domains(domains, paths=args.paths.split(","), offline_dir=args.offline)
    print(res.summary.to_string(index=False))
    print()
    print(res.flags.to_string(index=False))
    if args.live_ua:
        print(live_ua_check(args.live_ua).to_string(index=False))
    for p in export(res, args.out):
        print("wrote", p)


if __name__ == "__main__":
    main()
