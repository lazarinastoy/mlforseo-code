#!/usr/bin/env python3
"""
Automate internal linking with AI: a scriptable companion to the MLforSEO guide
"10 ways to automate internal linking with AI" (Lazarina Stoy, October 2026).

Subcommands (run `python automate_internal_linking.py <command> -h` for options):

  orphans   Orphan and weak-page detection: crawl vs XML sitemap (vs a Search Console export).
  suggest   Embedding-based link suggestions placed at passage level, with anchor text
            chosen extractively or by an LLM, and every anchor checked by guardrails.
  queries   Link opportunities from Search Console: pages ranking in striking distance for a
            query, linked from other pages that already use that query's words.
  linkcheck Broken, redirected and non-canonical internal links, with the URL to point to instead.
  related   Embedding-based "related posts" lists for a widget or static block (plus the vectors).
  apply     Insert APPROVED suggestions (or href fixes from linkcheck) into WordPress posts
            (dry run by default).
  measure   Before/after impact of the links you added, against a control group of pages
            you didn't touch (difference in differences on a Search Console export).

Input: either the public WordPress REST API of a site (`--site https://example.com`, posts only,
in-content links only) or Screaming Frog exports (`--sf-pages`, `--sf-inlinks`).

Nothing is ever published without a human: `suggest` writes a CSV with an empty `approve`
column, and `apply` only touches rows you marked yes, only with `--write`.
"""
from __future__ import annotations

import argparse
import difflib
import html as htmllib
import json
import os
import re
import sys
import time
from urllib.parse import urlparse, urlunparse
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (MLforSEO internal linking automation)"}

GENERIC_ANCHORS = {
    "click here", "read more", "here", "this", "learn more", "more", "this article", "this post",
    "link", "find out more", "continue reading", "this guide", "see more", "this page", "website",
}
STOP = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for", "with", "by", "at", "from",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these", "those", "as",
    "if", "so", "than", "then", "you", "your", "we", "our", "i", "my", "they", "their", "can", "will",
    "how", "what", "which", "who", "why", "when", "where", "not", "no", "do", "does", "did", "into",
    "about", "also", "just", "more", "most", "such", "all", "any", "each", "other", "some", "very",
    "has", "have", "had", "there", "here", "up", "out", "over", "use", "using", "used",
}
# words that make a span read like part of a sentence rather than a description of a page
NOT_INSIDE_ANCHOR = {"is", "are", "was", "were", "be", "been", "you", "your", "we", "i", "they", "it", "not",
                     "how", "why", "what", "when", "meant", "means", "can", "will", "should", "would", "did"}


# --------------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------------
def normalise_url(u: str) -> str:
    p = urlparse(str(u).strip())
    path = p.path or "/"
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return urlunparse((p.scheme or "https", p.netloc.lower(), path, "", "", ""))


def load_wordpress(site: str):
    """Published posts from the WP REST API, kept as paragraphs, plus their in-content internal links."""
    from bs4 import BeautifulSoup

    site = site.rstrip("/")
    posts, page = [], 1
    while True:
        r = requests.get(f"{site}/wp-json/wp/v2/posts",
                         params={"per_page": 100, "page": page, "_fields": "id,link,title,content"},
                         headers=UA, timeout=60)
        if r.status_code != 200 or not r.json():
            break
        posts += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    host = urlparse(site).netloc.lower()
    pages, links = [], []
    for p in posts:
        url = normalise_url(p["link"])
        soup = BeautifulSoup(p["content"]["rendered"], "html.parser")
        for tag in soup(["script", "style", "pre", "code", "noscript"]):
            tag.decompose()
        paras = []
        for el in soup.find_all(["p", "li"]):
            if el.find_parent(["li"]) is not None and el.name == "p":
                continue
            text = el.get_text(" ", strip=True)
            if len(text.split()) < 8:
                continue
            linked = []
            for a in el.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/"):
                    href = site + href
                if urlparse(href).netloc.lower() == host:
                    linked.append(normalise_url(href))
            paras.append({"text": text, "links_to": linked})
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = site + href
            if urlparse(href).netloc.lower() != host:
                continue
            links.append({"Source": url, "Destination": normalise_url(href), "raw_destination": href,
                          "Anchor": a.get_text(" ", strip=True), "Link Position": "Content",
                          "Follow": "false" if "nofollow" in (a.get("rel") or []) else "true"})
        pages.append({"url": url, "post_id": p["id"], "title": htmllib.unescape(p["title"]["rendered"]),
                      "content": soup.get_text(" ", strip=True), "paragraphs": paras})
    return pd.DataFrame(pages), pd.DataFrame(links)


def load_screaming_frog(pages_csv, content_col, inlinks_csv, title_col="Title 1"):
    pages = pd.read_csv(pages_csv).rename(columns={"Address": "url", content_col: "content"})
    pages["title"] = pages[title_col] if title_col in pages.columns else ""
    pages["url"] = pages["url"].map(normalise_url)
    pages["paragraphs"] = None          # SF extraction text has no paragraph breaks: we use sentence windows
    links = pd.read_csv(inlinks_csv, low_memory=False)
    if "Type" in links.columns:
        links = links[links["Type"].astype(str).str.lower().eq("hyperlink")]
    for col in ["Anchor", "Follow", "Link Position", "Status Code"]:
        if col not in links.columns:
            links[col] = None
    links["raw_destination"] = links["Destination"].astype(str)
    links["Source"] = links["Source"].map(normalise_url)
    links["Destination"] = links["Destination"].map(normalise_url)
    return pages, links


def load(args):
    if args.sf_pages:
        pages, links = load_screaming_frog(args.sf_pages, args.sf_content_col, args.sf_inlinks)
    else:
        pages, links = load_wordpress(args.site)
    pages["content"] = pages["content"].fillna("").astype(str)
    pages["title"] = pages["title"].fillna("").astype(str)
    pages = pages[pages["content"].str.split().str.len() >= 50].drop_duplicates("url").reset_index(drop=True)
    links["Anchor"] = links["Anchor"].fillna("").astype(str)
    print(f"Loaded {len(pages)} pages and {len(links)} internal links", file=sys.stderr)
    return pages, links


# --------------------------------------------------------------------------------------------
# 1. Orphans
# --------------------------------------------------------------------------------------------
def sitemap_urls(url: str, seen=None) -> set:
    """All <loc> URLs from a sitemap or sitemap index (follows nested sitemaps)."""
    seen = seen or set()
    if url in seen:
        return set()
    seen.add(url)
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    out = set()
    for sm in root.findall("s:sitemap/s:loc", ns):
        out |= sitemap_urls(sm.text.strip(), seen)
    for loc in root.findall("s:url/s:loc", ns):
        out.add(normalise_url(loc.text))
    return out


def cmd_orphans(args):
    pages, links = load(args)
    crawled = set(pages["url"])
    linked = links[links["Source"].isin(crawled)]
    inlinks = linked.groupby("Destination")["Source"].nunique()
    content = linked[linked["Link Position"].astype(str).str.lower().eq("content")]
    content_in = content.groupby("Destination")["Source"].nunique()

    known = set(crawled)
    sources = {u: {"crawl"} for u in crawled}
    if args.sitemap:
        sm = sitemap_urls(args.sitemap)
        if args.sitemap_filter:
            sm = {u for u in sm if re.search(args.sitemap_filter, u)}
        for u in sm:
            sources.setdefault(u, set()).add("sitemap")
        known |= sm
    if args.gsc_pages:
        g = pd.read_csv(args.gsc_pages)
        col = next(c for c in g.columns if c.lower() in ("page", "top pages", "url", "address", "landing page"))
        for u in g[col].dropna().map(normalise_url):
            sources.setdefault(u, set()).add("search console")
            known.add(u)

    rows = []
    wp = not args.sf_pages          # the WP REST API only sees post bodies, not menus or footers
    orphan_label = ("no in-content links from any other post (WP API: menus, footers and archives not seen)"
                    if wp else "orphan: no internal links from any crawled page")
    for u in sorted(known):
        n_in, n_ctx = int(inlinks.get(u, 0)), int(content_in.get(u, 0))
        if args.sitemap and "crawl" in sources.get(u, set()) and "sitemap" not in sources[u]:
            rows.append({"url": u, "status": "crawled but missing from the XML sitemap", "unique_inlinks": n_in,
                         "content_inlinks": n_ctx, "found_in": "crawl"})
        if n_in == 0:
            status = orphan_label
        elif n_ctx == 0:
            status = "no contextual inlinks (only navigation, footer or related-post links)"
        elif n_ctx == 1:
            status = "weak: one contextual inlink"
        else:
            continue
        rows.append({"url": u, "status": status, "unique_inlinks": n_in, "content_inlinks": n_ctx,
                     "found_in": ", ".join(sorted(sources.get(u, {"crawl"})))})
    out = pd.DataFrame(rows)
    if "Crawl Depth" in pages.columns:
        deep = pages[pd.to_numeric(pages["Crawl Depth"], errors="coerce") > args.max_depth]
        out = pd.concat([out, pd.DataFrame({"url": deep["url"], "status": f"deep: more than {args.max_depth} clicks from the start URL",
                                            "found_in": "crawl"})])
    out.to_csv(args.out, index=False)
    print(out["status"].value_counts().to_string() if len(out) else "No orphan or weak pages found.")
    print(f"Saved {args.out}")


# --------------------------------------------------------------------------------------------
# 2. Suggestions: page similarity -> best passage -> anchor -> guardrails
# --------------------------------------------------------------------------------------------
def chunks_for(row, window=60):
    """Paragraphs when we have them, otherwise ~60-word sentence windows."""
    if isinstance(row.get("paragraphs"), list) and row["paragraphs"]:
        return [(p["text"], set(p["links_to"])) for p in row["paragraphs"]]
    sents = re.split(r"(?<=[.!?])\s+", row["content"])
    out, buf = [], []
    for s in sents:
        buf.append(s)
        if len(" ".join(buf).split()) >= window:
            out.append((" ".join(buf), set()))
            buf = []
    if buf and len(" ".join(buf).split()) >= 8:
        out.append((" ".join(buf), set()))
    return out


def ngrams(text, nmin=2, nmax=6):
    """Candidate anchors: word spans that don't start or end with a stop word, kept verbatim."""
    toks = list(re.finditer(r"[A-Za-z0-9][A-Za-z0-9\-’']*", text))
    out = set()
    for n in range(nmin, nmax + 1):
        for i in range(len(toks) - n + 1):
            span = toks[i:i + n]
            first, last = span[0].group(0).lower(), span[-1].group(0).lower()
            if first in STOP or last in STOP or last.endswith(("'s", "’s")):
                continue
            between = text[span[0].start():span[-1].end()]
            if re.search(r"[.,;:!?()\[\]\"“”<>=/|]", between):      # don't cross punctuation or markup debris
                continue
            if any(t.group(0).lower() in NOT_INSIDE_ANCHOR for t in span):
                continue
            out.add(between)
    return sorted(out)


class Guardrails:
    """Every anchor, extractive or LLM-generated, passes these checks or is rejected with a reason."""

    def __init__(self, brand_terms, max_links_per_source=3, max_same_anchor_per_target=2,
                 min_words=2, max_words=7):
        self.brand = [b.lower() for b in brand_terms]
        self.max_links_per_source = max_links_per_source
        self.max_same_anchor = max_same_anchor_per_target
        self.min_words, self.max_words = min_words, max_words
        self.per_source, self.anchor_use, self.used_chunks = {}, {}, set()
        self.source_anchors = {}

    def check(self, anchor, chunk_text, chunk_id, source, target, existing_anchors_to_target=()):
        reasons = []
        a = (anchor or "").strip()
        al = a.lower()
        if not a:
            return False, ["no anchor"]
        if not re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", chunk_text, flags=re.IGNORECASE):
            reasons.append("not found verbatim in the passage (the model rewrote or invented text)")
        n = len(a.split())
        if n < self.min_words or n > self.max_words:
            reasons.append(f"{n} words (allowed {self.min_words}-{self.max_words})")
        if al in GENERIC_ANCHORS:
            reasons.append("generic anchor")
        if any(al == b for b in self.brand):
            reasons.append("brand-only anchor")
        words = re.findall(r"[a-z0-9]+", al)
        if words and (words[0] in STOP or words[-1] in STOP):
            reasons.append("starts or ends with a stop word")
        if self.per_source.get(source, 0) >= self.max_links_per_source:
            reasons.append(f"source already has {self.max_links_per_source} new links in this batch")
        if chunk_id in self.used_chunks:
            reasons.append("passage already gets a new link (don't chain links)")
        uses = self.anchor_use.get((target, al), 0) + sum(1 for e in existing_anchors_to_target if e.lower() == al)
        if uses >= self.max_same_anchor:
            reasons.append("same anchor already used for this target (keep anchors varied)")
        if self.source_anchors.get((source, al), target) != target:
            reasons.append("same anchor already points to a different page from this source")
        return (not reasons), reasons

    def accept(self, anchor, chunk_id, source, target):
        al = anchor.lower().strip()
        self.per_source[source] = self.per_source.get(source, 0) + 1
        self.anchor_use[(target, al)] = self.anchor_use.get((target, al), 0) + 1
        self.used_chunks.add(chunk_id)
        self.source_anchors[(source, al)] = target


LLM_SYSTEM = (
    "You choose internal link anchor text for an SEO team. You will get one passage from a source page "
    "and a description of a target page. Pick the span of the passage that would make the best anchor "
    "text for a link to the target page.\n"
    "Rules: copy the span exactly as it appears in the passage, character for character; never rewrite, "
    "add or invent words. 2 to 7 words; don't start or end the span with an article, preposition or "
    "conjunction (a, the, of, for, and...). It must describe what the target page is about, so a reader knows "
    "where the link goes. No generic phrases (click here, read more, this article) and no brand name on its own. "
    "If no span in the passage is a natural, honest anchor for this target, return an empty anchor."
)
LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "anchor": {"type": "string", "description": "exact span copied from the passage, or empty"},
        "confidence": {"type": "number", "description": "0 to 1"},
        "reason": {"type": "string", "description": "one short sentence"},
    },
    "required": ["anchor", "confidence", "reason"],
    "additionalProperties": False,
}


# Models that accept the `effort` setting and the server-side refusal fallback (Haiku 4.5 accepts neither)
EFFORT_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
                 "claude-sonnet-5-5", "claude-sonnet-5", "claude-sonnet-4-6", "claude-fable-5", "claude-fable-5-1")
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1")


def llm_anchor(client, model, passage, target_title, target_summary):
    """Ask Claude for an anchor. Structured output keeps the reply parseable; the guardrails still check it."""
    output_config = {"format": {"type": "json_schema", "schema": LLM_SCHEMA}}
    extra = {}
    if model in EFFORT_MODELS:
        output_config["effort"] = "low"     # a short extraction task: low effort is plenty and keeps it cheap
    if model in FALLBACK_MODELS:
        extra = {"betas": ["server-side-fallback-2026-07-01"],
                 "fallbacks": "default"}    # if the model declines, the API retries on a fallback model
    response = client.beta.messages.create(
        model=model,
        max_tokens=1024,
        output_config=output_config,
        **extra,
        system=LLM_SYSTEM,
        messages=[{"role": "user", "content":
                   f"<passage>\n{passage}\n</passage>\n<target_page>\nTitle: {target_title}\n"
                   f"Summary: {target_summary}\n</target_page>"}],
    )
    u = response.usage
    usage = {"input": u.input_tokens or 0, "output": u.output_tokens or 0, "model": response.model}
    if response.stop_reason == "refusal":
        return {"anchor": "", "confidence": 0, "reason": "model declined", "_usage": usage}
    if response.stop_reason == "max_tokens":
        return {"anchor": "", "confidence": 0, "reason": "hit max_tokens before answering", "_usage": usage}
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    out = json.loads(text)
    out["_usage"] = usage
    return out


# USD per million tokens (input, output); used only to print an estimate of what the run cost
PRICES = {"claude-opus-5-5": (4, 20), "claude-opus-5": (5, 25), "claude-sonnet-5-5": (2, 10),
          "claude-sonnet-5": (2, 10), "claude-haiku-4-5": (1, 5), "claude-fable-5-1": (10, 50)}


def match_passage_span(anchor, passage):
    """Models sometimes "tidy" typography: a straight apostrophe for the passage's curly one, or a hyphen
    for a dash. If the anchor matches the passage once quotes, dashes and spacing are ignored, return the
    passage's own characters (so `apply` can find it). Words are never changed; anything else is left for
    the verbatim guardrail to reject."""
    if not anchor or anchor.lower() in passage.lower():
        return anchor
    pattern = ""
    for ch in anchor:
        if ch in "'’‘`":
            pattern += "['’‘`]"
        elif ch in '"“”':
            pattern += '["“”]'
        elif ch in "-–—":
            pattern += "[-–—]"
        elif ch.isspace():
            pattern += r"\s+"
        else:
            pattern += re.escape(ch)
    m = re.search(r"(?<![\w])" + pattern + r"(?![\w])", passage, flags=re.IGNORECASE)
    return m.group(0) if m else anchor


def page_canonical(url):
    """The rel=canonical a page declares (None if it can't be fetched or has none)."""
    try:
        r = requests.get(url, headers=UA, timeout=20)
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', r.text, flags=re.IGNORECASE)
        h = m and re.search(r'href=["\']([^"\']+)', m.group(0))
        return normalise_url(h.group(1)) if h else None
    except requests.RequestException:
        return None


def pick_canonical(pages, a, b, inl):
    """Of two near-duplicate pages, which one should links point to?
    1. the one the other declares as its canonical; 2. no '-2'-style slug suffix; 3. more inlinks."""
    ua, ub = pages.at[a, "url"], pages.at[b, "url"]
    if page_canonical(ub) == normalise_url(ua):
        return a, b
    if page_canonical(ua) == normalise_url(ub):
        return b, a
    suffix = re.compile(r"-\d+/?$")
    if bool(suffix.search(ua)) != bool(suffix.search(ub)):
        return (b, a) if suffix.search(ua) else (a, b)
    return (a, b) if int(inl.get(ua, 0)) >= int(inl.get(ub, 0)) else (b, a)


def cmd_suggest(args):
    from sentence_transformers import SentenceTransformer

    pages, links = load(args)
    model = SentenceTransformer(args.model)
    t0 = time.time()
    page_text = (pages["title"] + ". " + pages["content"].str.split().str[:args.max_words].str.join(" ")).tolist()
    emb = model.encode(page_text, batch_size=16, normalize_embeddings=True)
    sim = emb @ emb.T
    upper = sim[np.triu_indices(len(sim), 1)]
    threshold = float(np.percentile(upper, args.percentile))
    print(f"Embedded {len(pages)} pages in {time.time() - t0:.0f}s; pair threshold p{args.percentile} = {threshold:.3f}",
          file=sys.stderr)

    # passages for every page, embedded once
    chunk_rows = []
    for i, row in pages.iterrows():
        for k, (text, linked) in enumerate(chunks_for(row)):
            chunk_rows.append({"page": i, "k": k, "text": text, "links_to": linked})
    chunk_emb = model.encode([c["text"] for c in chunk_rows], batch_size=32, normalize_embeddings=True)
    by_page = {}
    for idx, c in enumerate(chunk_rows):
        by_page.setdefault(c["page"], []).append(idx)
    print(f"Embedded {len(chunk_rows)} passages", file=sys.stderr)

    existing = set(zip(links["Source"], links["Destination"]))
    anchors_to = links.groupby("Destination")["Anchor"].apply(list).to_dict()
    inl = links[links["Source"].isin(set(pages["url"]))].groupby("Destination")["Source"].nunique()

    client = None
    if args.llm:
        import anthropic
        client = anthropic.Anthropic()

    guard = Guardrails(args.brand, args.max_links_per_source, args.max_same_anchor)
    # near-duplicate pages (>= --duplicate) are a consolidation job, not a linking job: keep one of each
    dupes = set()
    for a, b in zip(*np.where(np.triu(sim, 1) >= args.duplicate)):
        keep, drop = pick_canonical(pages, int(a), int(b), inl)
        dupes.add(drop)
        print(f"Possible duplicates, keeping {pages.at[keep, 'url']} | skipping {pages.at[drop, 'url']}",
              file=sys.stderr)

    candidates = []
    for i in range(len(pages)):
        if i in dupes:
            continue
        for j in np.argsort(-sim[i]):
            if j == i or j in dupes or sim[i, j] < threshold or sim[i, j] >= args.duplicate:
                continue
            if (pages.at[i, "url"], pages.at[j, "url"]) in existing:
                continue
            candidates.append((i, int(j), float(sim[i, j])))
    # targets with few inlinks first, then similarity: the pages that need links most get first pick
    candidates.sort(key=lambda c: (min(int(inl.get(pages.at[c[1], "url"], 0)), 5), -c[2]))

    rows, llm_calls = [], 0
    llm_tokens = {"input": 0, "output": 0}
    llm_log = []
    llm_stats = {"accepted": 0, "declined": 0, "rejected": 0, "errors": 0}
    cost = 0.0
    per_target = {}
    for i, j, s in candidates:
        src, dst = pages.at[i, "url"], pages.at[j, "url"]
        if per_target.get(dst, 0) >= args.max_per_target:
            continue
        ids = [c for c in by_page.get(i, []) if dst not in chunk_rows[c]["links_to"]]
        if not ids:
            continue
        scores = chunk_emb[ids] @ emb[j]
        best = ids[int(np.argmax(scores))]
        passage = chunk_rows[best]["text"]
        chunk_id = (i, chunk_rows[best]["k"])

        # extractive anchor: candidate spans ranked by similarity to the target title
        cands = ngrams(passage)
        title_words = set(re.findall(r"[a-z0-9]+", pages.at[j, "title"].lower())) - STOP
        cands = [c for c in cands if set(re.findall(r"[a-z0-9]+", c.lower())) & title_words] or cands
        extractive, ex_score = "", 0.0
        if cands:
            ce = model.encode(cands[:200], normalize_embeddings=True)
            ce_scores = ce @ model.encode([pages.at[j, "title"]], normalize_embeddings=True)[0]
            order = np.argsort(-ce_scores)
            for o in order[:10]:
                if ce_scores[o] < args.min_anchor_score:
                    break
                ok, _ = guard.check(cands[o], passage, chunk_id, src, dst, anchors_to.get(dst, ()))
                if ok:
                    extractive, ex_score = cands[o], float(ce_scores[o])
                    break

        anchor, method, rejected = extractive, "extractive (embedding-ranked span)", ""
        if client is not None and llm_calls < args.llm_limit:
            llm_calls += 1
            summary = " ".join(pages.at[j, "content"].split()[:60])
            try:
                out = llm_anchor(client, args.llm_model, passage, pages.at[j, "title"], summary)
            except Exception as e:                     # network or API error: keep the extractive anchor
                out = {"anchor": "", "reason": f"LLM error: {type(e).__name__}: {str(e)[:120]}"}
                llm_stats["errors"] += 1
            usage = out.pop("_usage", None)
            if usage:
                llm_tokens["input"] += usage["input"]
                llm_tokens["output"] += usage["output"]
                pin, pout = PRICES.get(usage["model"], PRICES.get(args.llm_model, (0, 0)))
                cost += (usage["input"] * pin + usage["output"] * pout) / 1e6
            llm_anchor_text = (out.get("anchor") or "").strip()
            # deterministic repair: drop a leading article ("A semantic keyword universe" -> "semantic
            # keyword universe"). The result is still a verbatim span of the passage, so nothing is invented.
            llm_anchor_text = re.sub(r"^(?:a|an|the)\s+", "", llm_anchor_text, flags=re.IGNORECASE)
            llm_anchor_text = match_passage_span(llm_anchor_text, passage)
            conf = out.get("confidence")
            if not llm_anchor_text:                    # the model said no natural anchor exists (allowed)
                if not out.get("reason", "").startswith("LLM error"):
                    llm_stats["declined"] += 1
                rejected = f"LLM gave no anchor: {out.get('reason', '')}"
            else:
                ok, reasons = guard.check(llm_anchor_text, passage, chunk_id, src, dst, anchors_to.get(dst, ()))
                if isinstance(conf, (int, float)) and conf < args.llm_min_confidence:
                    ok = False
                    reasons = reasons + [f"model's own confidence {conf:.2f} < {args.llm_min_confidence}"]
                if ok:
                    anchor, method = llm_anchor_text, "llm"
                    llm_stats["accepted"] += 1
                else:
                    llm_stats["rejected"] += 1
                    rejected = f"LLM anchor '{llm_anchor_text}' rejected: {'; '.join(reasons)}"
            llm_log.append({"source_url": src, "target_url": dst, "llm_anchor": llm_anchor_text,
                            "confidence": out.get("confidence", ""), "reason": out.get("reason", ""),
                            "outcome": "accepted" if method == "llm" else (rejected or ""),
                            "extractive_anchor": extractive, "passage": passage[:600]})
        if not anchor:
            continue
        guard.accept(anchor, chunk_id, src, dst)
        per_target[dst] = per_target.get(dst, 0) + 1
        rows.append({
            "approve": "", "source_url": src, "source_title": pages.at[i, "title"],
            "target_url": dst, "target_title": pages.at[j, "title"],
            "page_similarity": round(s, 3), "passage_similarity": round(float(np.max(scores)), 3),
            "target_unique_inlinks": int(inl.get(dst, 0)), "anchor": anchor, "anchor_method": method,
            "anchor_score": round(ex_score, 3) if method.startswith("extractive") else "",
            "llm_rejected": rejected, "passage": passage[:600],
            "source_post_id": pages.at[i, "post_id"] if "post_id" in pages.columns else "",
        })
    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"{len(candidates)} unlinked similar pairs -> {len(out)} suggestions that passed the guardrails "
          f"({out['source_url'].nunique() if len(out) else 0} source pages). LLM calls: {llm_calls}.")
    if llm_calls:
        print(f"LLM anchors: {llm_stats['accepted']} passed the guardrails, {llm_stats['rejected']} rejected, "
              f"{llm_stats['declined']} 'no natural anchor', {llm_stats['errors']} errors. "
              f"Tokens: {llm_tokens['input']:,} in / {llm_tokens['output']:,} out, about ${cost:.3f}.")
        log_path = os.path.splitext(args.out)[0] + "_llm_log.csv"
        pd.DataFrame(llm_log).to_csv(log_path, index=False)
        print(f"Every LLM answer (accepted or not) is in {log_path}.")
    print(f"Saved {args.out}. Fill the 'approve' column (yes/no) before running `apply`.")


# --------------------------------------------------------------------------------------------
# 2b. Search Console queries: link the page Google already ranks, with the words people search
# --------------------------------------------------------------------------------------------
def read_gsc_queries(path):
    """A page + query export (Search Console API, Search Analytics for Sheets, BigQuery bulk export)."""
    g = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in g.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        sys.exit(f"{path}: need a column named one of {names}")

    g = g.rename(columns={pick("page", "url", "landing page", "address"): "page", pick("query", "queries", "top queries"): "query",
                          pick("impressions"): "impressions", pick("position", "average position", "avg. position"): "position"})
    g["clicks"] = g[cols["clicks"]] if "clicks" in cols else 0
    g["page"] = g["page"].map(normalise_url)
    g["query"] = g["query"].astype(str).str.strip()
    return g[["page", "query", "clicks", "impressions", "position"]]


def cmd_queries(args):
    pages, links = load(args)
    g = read_gsc_queries(args.gsc_queries)
    g = g[(g["impressions"] >= args.min_impressions) & g["position"].between(args.min_position, args.max_position)]
    # a query that several of your pages rank for is a cannibalisation question first: send links to the
    # page that does best for it, and flag the rest
    g = g.sort_values(["query", "position", "clicks"], ascending=[True, True, False])
    ranking_pages = g.groupby("query")["page"].nunique()
    g = g.drop_duplicates("query", keep="first")
    n_words = g["query"].str.split().str.len()
    g = g[(n_words >= 2) & (n_words <= 7)]
    print(f"{len(g)} striking-distance queries (positions {args.min_position:g}-{args.max_position:g}, "
          f">= {args.min_impressions} impressions)", file=sys.stderr)

    existing = set(zip(links["Source"], links["Destination"]))
    anchors_to = links.groupby("Destination")["Anchor"].apply(list).to_dict()
    known = set(pages["url"])
    guard = Guardrails(args.brand, args.max_links_per_source, args.max_same_anchor)
    chunks = {i: chunks_for(row) for i, row in pages.iterrows()}
    rows = []
    # biggest opportunities first: lots of impressions, ranking just off the top spots
    for _, q in g.sort_values("impressions", ascending=False).iterrows():
        target = q["page"]
        if target not in known and not args.allow_unknown_targets:
            continue
        pat = re.compile(r"(?<![\w])" + re.escape(q["query"]) + r"(?![\w])", flags=re.IGNORECASE)
        found = 0
        for i, row in pages.iterrows():
            src = row["url"]
            if src == target or (src, target) in existing:
                continue
            for k, (text, linked) in enumerate(chunks[i]):
                m = pat.search(text)
                if not m or target in linked:
                    continue
                anchor = m.group(0)                       # the source page's own words, not the query's casing
                ok, reasons = guard.check(anchor, text, (i, k), src, target, anchors_to.get(target, ()))
                if not ok:
                    continue
                guard.accept(anchor, (i, k), src, target)
                found += 1
                rows.append({
                    "approve": "", "source_url": src, "source_title": row["title"], "target_url": target,
                    "query": q["query"], "impressions": int(q["impressions"]), "clicks": int(q["clicks"]),
                    "position": round(float(q["position"]), 1), "pages_ranking_for_query": int(ranking_pages[q["query"]]),
                    "anchor": anchor, "anchor_method": "search console query", "passage": text[:600],
                    "source_post_id": row["post_id"] if "post_id" in pages.columns else "",
                })
                break                                     # one paragraph per source page is enough
            if found >= args.max_sources_per_query:
                break
    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"{len(out)} suggestions for {out['target_url'].nunique() if len(out) else 0} target pages "
          f"from {out['query'].nunique() if len(out) else 0} queries. Saved {args.out}; review, then `apply`.")
    if len(out) and (out["pages_ranking_for_query"] > 1).any():
        print("Some queries rank with more than one of your pages (see pages_ranking_for_query): "
              "check for cannibalisation before you add links.")


# --------------------------------------------------------------------------------------------
# 2c. Link health: broken, redirected and non-canonical internal links
# --------------------------------------------------------------------------------------------
def fetch_status(url, timeout=20):
    """First-hop status, final URL and status after redirects, number of hops, and the final page's canonical."""
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return {"first_status": "error", "final_url": "", "final_status": type(e).__name__, "hops": 0, "canonical": ""}
    canonical = ""
    if r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', r.text, flags=re.IGNORECASE)
        h = m and re.search(r'href=["\']([^"\']+)', m.group(0))
        canonical = normalise_url(h.group(1)) if h else ""
    first = r.history[0].status_code if r.history else r.status_code
    return {"first_status": first, "final_url": normalise_url(r.url), "final_status": r.status_code,
            "hops": len(r.history), "canonical": canonical}


def cmd_linkcheck(args):
    pages, links = load(args)
    links = links.copy()
    links["href"] = links["raw_destination"].astype(str).str.split("#").str[0]
    links = links[links["href"].str.startswith("http")]
    hrefs = links["href"].drop_duplicates().tolist()[:args.max_urls]
    print(f"Checking {len(hrefs)} unique internal link targets", file=sys.stderr)
    status = {}
    for n, h in enumerate(hrefs, 1):
        status[h] = fetch_status(h)
        time.sleep(args.delay)                            # be polite to your own server
        if n % 50 == 0:
            print(f"  {n}/{len(hrefs)}", file=sys.stderr)
    rows = []
    for _, l in links[links["href"].isin(status)].iterrows():
        s = status[l["href"]]
        issue, fix = "", ""
        if s["first_status"] == "error" or (isinstance(s["final_status"], int) and s["final_status"] >= 400):
            issue = f"broken ({s['final_status']})"
            fix = ""                                     # needs a human: pick a replacement (try `suggest`)
        elif s["hops"] > 1:
            issue, fix = f"redirect chain ({s['hops']} hops)", s["final_url"]
        elif s["hops"] == 1:
            issue, fix = f"redirect ({s['first_status']})", s["final_url"]
        elif s["canonical"] and s["canonical"] != normalise_url(l["href"]):
            issue, fix = "points to a non-canonical URL", s["canonical"]
        if not issue:
            continue
        rows.append({"approve": "", "source_url": l["Source"], "anchor": l["Anchor"], "old_href": l["raw_destination"],
                     "issue": issue, "fix_href": fix, "final_status": s["final_status"],
                     "link_position": l.get("Link Position", "")})
    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(out["issue"].str.replace(r" \(.*", "", regex=True).value_counts().to_string() if len(out)
          else "No broken, redirected or non-canonical internal links found.")
    print(f"Saved {args.out}. Rows with a fix_href can go through `apply` (it swaps the href); "
          "broken links need a replacement chosen by a person.")


# --------------------------------------------------------------------------------------------
# 2d. Related posts: embedding-based "read next" lists for a widget or a static block
# --------------------------------------------------------------------------------------------
def cmd_related(args):
    from sentence_transformers import SentenceTransformer

    pages, links = load(args)
    model = SentenceTransformer(args.model)
    text = (pages["title"] + ". " + pages["content"].str.split().str[:args.max_words].str.join(" ")).tolist()
    emb = model.encode(text, batch_size=16, normalize_embeddings=True)
    sim = emb @ emb.T
    np.fill_diagonal(sim, -1)
    inl = links[links["Source"].isin(set(pages["url"]))].groupby("Destination")["Source"].nunique()
    rows, out_json = [], {}
    for i in range(len(pages)):
        picks = []
        for j in np.argsort(-sim[i]):
            if sim[i, j] >= args.duplicate:              # a near-copy isn't "related", it's a consolidation job
                continue
            if any(sim[j, p] >= args.diversity for p in picks):   # don't show three versions of one topic
                continue
            picks.append(int(j))
            if len(picks) == args.k:
                break
        out_json[pages.at[i, "url"]] = [pages.at[j, "url"] for j in picks]
        for rank, j in enumerate(picks, 1):
            rows.append({"url": pages.at[i, "url"], "rank": rank, "related_url": pages.at[j, "url"],
                         "related_title": pages.at[j, "title"], "similarity": round(float(sim[i, j]), 3),
                         "related_unique_inlinks": int(inl.get(pages.at[j, "url"], 0))})
    pd.DataFrame(rows).to_csv(args.out, index=False)
    with open(os.path.splitext(args.out)[0] + ".json", "w") as f:
        json.dump(out_json, f, indent=1)
    np.save(os.path.splitext(args.out)[0] + "_embeddings.npy", emb)
    print(f"{len(pages)} pages x {args.k} related posts. Saved {args.out}, a JSON map for your template, "
          f"and the embeddings (load them into a vector database if you want live lookups).")


# --------------------------------------------------------------------------------------------
# 3. Apply approved links to WordPress (dry run unless --write)
# --------------------------------------------------------------------------------------------
def insert_link(html: str, anchor: str, href: str):
    """Link the first plain-text occurrence of `anchor` inside a <p> or <li>, never inside an
    existing link, heading, code or button. Returns (new_html, inserted?)."""
    if href in html:
        return html, False                                    # already linked somewhere on the page
    block_re = re.compile(r"<(p|li)(\s[^>]*)?>.*?</\1>", flags=re.S | re.I)
    pat = re.compile(r"(?<![\w])" + re.escape(anchor) + r"(?![\w])", flags=re.I)
    for m in block_re.finditer(html):
        block = m.group(0)
        parts = re.split(r"(<[^>]+>)", block)
        depth = 0                                             # inside <a>, <code>, <button>?
        for k, part in enumerate(parts):
            if part.startswith("<"):
                tag = re.match(r"</?\s*([a-zA-Z0-9]+)", part)
                if tag and tag.group(1).lower() in ("a", "code", "button"):
                    depth += -1 if part.startswith("</") else 1
                continue
            if depth == 0:
                hit = pat.search(part)
                if hit:
                    parts[k] = part[:hit.start()] + f'<a href="{href}">{hit.group(0)}</a>' + part[hit.end():]
                    new_block = "".join(parts)
                    return html[:m.start()] + new_block + html[m.end():], True
    return html, False


def replace_href(html: str, old: str, new: str):
    """Point existing links at `new` instead of `old` (redirected or non-canonical URLs). Anchors are untouched."""
    pat = re.compile(r'(href=)(["\'])' + re.escape(old) + r'(#[^"\']*)?\2')
    out, n = pat.subn(lambda m: f"{m.group(1)}{m.group(2)}{new}{m.group(3) or ''}{m.group(2)}", html)
    return out, n > 0


def cmd_apply(args):
    df = pd.read_csv(args.suggestions).fillna("")
    df = df[df["approve"].astype(str).str.strip().str.lower().isin(["y", "yes", "1", "true", "x"])]
    if df.empty:
        print("No approved rows. Put 'yes' in the approve column for the links you want.")
        return
    user, pwd = os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD")
    if not (user and pwd):
        sys.exit("Set WP_USER and WP_APP_PASSWORD (a WordPress application password) to read raw post content.")
    site = args.site.rstrip("/")
    auth = (user, pwd)
    log = []
    for src, group in df.groupby("source_url"):
        slug = urlparse(src).path.rstrip("/").rsplit("/", 1)[-1]
        r = requests.get(f"{site}/wp-json/wp/v2/posts", params={"slug": slug, "context": "edit", "status": "any"},
                         auth=auth, headers=UA, timeout=60)
        r.raise_for_status()
        if not r.json():
            log.append({"source_url": src, "result": "post not found"})
            continue
        post = r.json()[0]
        before = after = post["content"]["raw"]
        for _, row in group.iterrows():
            if row.get("fix_href"):                       # a row from `linkcheck`: swap the href, keep the anchor
                after, ok = replace_href(after, row["old_href"], row["fix_href"])
                log.append({"source_url": src, "target_url": row["fix_href"], "anchor": row["anchor"],
                            "result": "href updated" if ok else "skipped (old href not found)"})
                continue
            if "target_url" not in row or not row["target_url"]:
                continue
            after, ok = insert_link(after, row["anchor"], row["target_url"])
            log.append({"source_url": src, "target_url": row["target_url"], "anchor": row["anchor"],
                        "result": "inserted" if ok else "skipped (anchor not found as plain text, or already linked)"})
        if after == before:
            continue
        diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        print(f"\n=== {src} (post {post['id']}) ===\n" + "\n".join(list(diff)[2:]))
        if args.write:
            u = requests.post(f"{site}/wp-json/wp/v2/posts/{post['id']}", json={"content": after},
                              auth=auth, headers=UA, timeout=60)
            u.raise_for_status()
            print(f"Saved post {post['id']} (WordPress keeps a revision, so you can roll back).")
    pd.DataFrame(log).to_csv(args.log, index=False)
    print(f"\n{'Wrote changes' if args.write else 'Dry run only, nothing saved'}. Log: {args.log}")


# --------------------------------------------------------------------------------------------
# 4. Measurement: difference in differences against untouched pages
# --------------------------------------------------------------------------------------------
def cmd_measure(args):
    gsc = pd.read_csv(args.gsc_daily)
    cols = {c.lower(): c for c in gsc.columns}
    gsc = gsc.rename(columns={cols.get("date", "date"): "date", cols.get("page", "page"): "page",
                              cols.get("clicks", "clicks"): "clicks", cols.get("impressions", "impressions"): "impressions"})
    gsc["date"] = pd.to_datetime(gsc["date"])
    gsc["page"] = gsc["page"].map(normalise_url)
    changes = pd.read_csv(args.changes)
    changes["url"] = changes["url"].map(normalise_url)
    change_date = pd.to_datetime(args.change_date) if args.change_date else pd.to_datetime(changes["change_date"]).min()
    test = set(changes["url"])
    pre = (gsc["date"] < change_date) & (gsc["date"] >= change_date - pd.Timedelta(days=args.days))
    post = (gsc["date"] >= change_date + pd.Timedelta(days=args.lag)) & \
           (gsc["date"] < change_date + pd.Timedelta(days=args.lag + args.days))
    gsc["group"] = np.where(gsc["page"].isin(test), "test (links added)", "control (untouched)")
    if args.control_pattern:
        gsc = gsc[gsc["group"].str.startswith("test") | gsc["page"].str.contains(args.control_pattern, regex=True)]
    rows = []
    for metric in ("clicks", "impressions"):
        for g in ("test (links added)", "control (untouched)"):
            d = gsc[gsc["group"] == g]
            b = d[pre.loc[d.index]].groupby("date")[metric].sum().mean()
            a = d[post.loc[d.index]].groupby("date")[metric].sum().mean()
            rows.append({"metric": metric, "group": g, "pages": d["page"].nunique(),
                         "daily_before": round(b, 1), "daily_after": round(a, 1),
                         "change_pct": round((a / b - 1) * 100, 1) if b else np.nan})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    for metric in ("clicks", "impressions"):
        t = out[(out.metric == metric) & out.group.str.startswith("test")]["change_pct"].iloc[0]
        c = out[(out.metric == metric) & out.group.str.startswith("control")]["change_pct"].iloc[0]
        print(f"{metric}: test {t:+.1f}% vs control {c:+.1f}% -> difference in differences {t - c:+.1f} points")
    print("This is a sanity check, not proof: seasonality, other releases and small samples all move these numbers. "
          "For a real answer, split similar pages into test and control BEFORE you add links.")
    out.to_csv(args.out, index=False)


# --------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_source(p):
        p.add_argument("--site", default="https://www.mlforseo.com", help="WordPress site (public REST API)")
        p.add_argument("--sf-pages", help="Screaming Frog custom extraction export (Address + content column)")
        p.add_argument("--sf-content-col", default="Content 1")
        p.add_argument("--sf-inlinks", help="Screaming Frog Bulk Export > Links > All Inlinks")

    p = sub.add_parser("orphans", help="orphan and weak-page detection")
    add_source(p)
    p.add_argument("--sitemap", help="XML sitemap or sitemap index URL")
    p.add_argument("--sitemap-filter", help="regex to keep only some sitemap URLs (e.g. post URLs)")
    p.add_argument("--gsc-pages", help="Search Console Pages export (CSV)")
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--out", default="orphan_report.csv")
    p.set_defaults(func=cmd_orphans)

    p = sub.add_parser("suggest", help="embedding link suggestions + anchors + guardrails")
    add_source(p)
    p.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    p.add_argument("--max-words", type=int, default=350)
    p.add_argument("--percentile", type=float, default=90)
    p.add_argument("--duplicate", type=float, default=0.95)
    p.add_argument("--brand", nargs="*", default=["mlforseo", "ml for seo", "lazarina", "lazarina stoy"])
    p.add_argument("--max-links-per-source", type=int, default=3)
    p.add_argument("--max-same-anchor", type=int, default=2)
    p.add_argument("--min-anchor-score", type=float, default=0.6,
                   help="extractive anchors must be at least this similar to the target title")
    p.add_argument("--llm", action="store_true", help="ask Claude for the anchor (needs ANTHROPIC_API_KEY)")
    p.add_argument("--llm-model", default="claude-opus-5-5")
    p.add_argument("--llm-limit", type=int, default=50, help="max LLM calls per run (cost cap)")
    p.add_argument("--llm-min-confidence", type=float, default=0.5,
                   help="reject LLM anchors the model itself rates below this")
    p.add_argument("--max-per-target", type=int, default=3,
                   help="max new links to one target page per batch (stops one page soaking up every link)")
    p.add_argument("--out", default="link_suggestions.csv")
    p.set_defaults(func=cmd_suggest)

    p = sub.add_parser("queries", help="link opportunities from Search Console page + query data")
    add_source(p)
    p.add_argument("--gsc-queries", required=True, help="CSV with page, query, clicks, impressions, position")
    p.add_argument("--min-impressions", type=int, default=50)
    p.add_argument("--min-position", type=float, default=4)
    p.add_argument("--max-position", type=float, default=20)
    p.add_argument("--max-sources-per-query", type=int, default=3)
    p.add_argument("--allow-unknown-targets", action="store_true", help="keep targets that aren't in the crawl")
    p.add_argument("--brand", nargs="*", default=["mlforseo", "ml for seo", "lazarina", "lazarina stoy"])
    p.add_argument("--max-links-per-source", type=int, default=3)
    p.add_argument("--max-same-anchor", type=int, default=2)
    p.add_argument("--out", default="query_link_suggestions.csv")
    p.set_defaults(func=cmd_queries)

    p = sub.add_parser("linkcheck", help="broken, redirected and non-canonical internal links")
    add_source(p)
    p.add_argument("--max-urls", type=int, default=2000)
    p.add_argument("--delay", type=float, default=0.2, help="seconds between requests")
    p.add_argument("--out", default="link_health.csv")
    p.set_defaults(func=cmd_linkcheck)

    p = sub.add_parser("related", help="embedding-based related posts (for a widget or static block)")
    add_source(p)
    p.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    p.add_argument("--max-words", type=int, default=350)
    p.add_argument("--k", type=int, default=4)
    p.add_argument("--duplicate", type=float, default=0.95)
    p.add_argument("--diversity", type=float, default=0.92,
                   help="skip a candidate this similar to one already picked")
    p.add_argument("--out", default="related_posts.csv")
    p.set_defaults(func=cmd_related)

    p = sub.add_parser("apply", help="insert approved links into WordPress (dry run unless --write)")
    p.add_argument("--site", required=True)
    p.add_argument("--suggestions", default="link_suggestions.csv")
    p.add_argument("--write", action="store_true")
    p.add_argument("--log", default="apply_log.csv")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("measure", help="difference in differences on a Search Console daily export")
    p.add_argument("--gsc-daily", required=True, help="CSV with date, page, clicks, impressions")
    p.add_argument("--changes", required=True, help="CSV with url (pages that got new links) and change_date")
    p.add_argument("--change-date")
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--lag", type=int, default=7, help="days to skip after the change (recrawl time)")
    p.add_argument("--control-pattern", help="regex limiting the control group to comparable pages")
    p.add_argument("--out", default="impact_summary.csv")
    p.set_defaults(func=cmd_measure)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
