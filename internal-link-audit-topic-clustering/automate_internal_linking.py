#!/usr/bin/env python3
"""
Automate internal linking with AI: a scriptable companion to the MLforSEO guide
"7 ways to automate internal linking with AI" (Lazarina Stoy, October 2026).

Subcommands (run `python automate_internal_linking.py <command> -h` for options):

  orphans   Orphan and weak-page detection: crawl vs XML sitemap (vs a Search Console export).
  suggest   Embedding-based link suggestions placed at passage level, with anchor text
            chosen extractively or by an LLM, and every anchor checked by guardrails.
  apply     Insert APPROVED suggestions into WordPress posts (dry run by default).
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
    "add or invent words. 2 to 7 words. It must describe what the target page is about, so a reader knows "
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


def llm_anchor(client, model, passage, target_title, target_summary):
    """Ask Claude for an anchor. Structured output keeps the reply parseable; the guardrails still check it."""
    response = client.beta.messages.create(
        model=model,
        max_tokens=1024,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",            # if the model declines, the API retries on a fallback model
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": LLM_SCHEMA}},
        system=LLM_SYSTEM,
        messages=[{"role": "user", "content":
                   f"<passage>\n{passage}\n</passage>\n<target_page>\nTitle: {target_title}\n"
                   f"Summary: {target_summary}\n</target_page>"}],
    )
    if response.stop_reason == "refusal":
        return {"anchor": "", "confidence": 0, "reason": "model declined"}
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    return json.loads(text)


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
        dupes.add(int(b))
        print(f"Possible duplicates, skipping the second: {pages.at[int(a), 'url']} | {pages.at[int(b), 'url']}",
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
    for i, j, s in candidates:
        src, dst = pages.at[i, "url"], pages.at[j, "url"]
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
                out = {"anchor": "", "reason": f"LLM error: {type(e).__name__}"}
            ok, reasons = guard.check(out.get("anchor", ""), passage, chunk_id, src, dst, anchors_to.get(dst, ()))
            if ok:
                anchor, method = out["anchor"], "llm"
            else:
                rejected = f"LLM anchor '{out.get('anchor', '')}' rejected: {'; '.join(reasons) or out.get('reason', '')}"
        if not anchor:
            continue
        guard.accept(anchor, chunk_id, src, dst)
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
    print(f"Saved {args.out}. Fill the 'approve' column (yes/no) before running `apply`.")


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
    p.add_argument("--out", default="link_suggestions.csv")
    p.set_defaults(func=cmd_suggest)

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
