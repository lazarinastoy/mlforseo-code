#!/usr/bin/env python3
"""
Blog architecture audit
=======================

Companion script for the MLforSEO guide "Blog and site architecture for SEO and
conversions in the AI search era" by Lazarina Stoy.

It answers five questions about a blog (or a whole site):

1. Click depth   - how many clicks from the homepage does each page sit?
2. URL depth vs click depth - do your folders say "shallow" while your links say "deep" (or vice versa)?
3. Orphans       - which URLs are in the XML sitemap but are never linked internally?
4. Category balance - which sections are bloated, and which are thin?
5. Hub coverage  - does each hub/category page actually link to the posts that live under it?

Two ways to feed it:

  A) A sitemap (it crawls the internal links itself, politely):
       python blog_architecture_audit.py --sitemap https://www.example.com/sitemap_index.xml

  B) A Screaming Frog crawl export (no crawling needed):
       python blog_architecture_audit.py --sf-internal internal_html.csv \
           --sf-inlinks all_inlinks.csv --sitemap https://www.example.com/sitemap.xml

     internal_html.csv = Internal tab > filter HTML > Export
     all_inlinks.csv   = Bulk Export > Links > All Inlinks (optional, enables hub coverage)
     --sitemap is optional in this mode; add it to find orphans.

Outputs (in --out, default ./audit_output):
  pages.csv         one row per URL: url depth, click depth, inlinks, section, flags
  sections.csv      category balance per section
  hubs.csv          hub coverage per hub page
  orphans.csv       sitemap URLs with no internal inlinks / never reached
  summary.md        the human-readable report (also printed to the console)
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from xml.etree import ElementTree as ET

import pandas as pd
import requests
from bs4 import BeautifulSoup

UA = "MLforSEO-blog-architecture-audit/1.0 (+https://github.com/lazarinastoy/mlforseo-code)"
SKIP_EXT = re.compile(r"\.(jpe?g|png|gif|webp|svg|avif|pdf|zip|mp4|mp3|webm|css|js|xml|txt|ico|woff2?)$", re.I)
# URLs a crawler should not follow for an architecture audit (admin, feeds, search, share links)
SKIP_PATH = re.compile(r"/(wp-admin|wp-json|wp-login|feed|xmlrpc\.php|cart|checkout|my-account)(/|$)|[?&](s|replytocom|share)=", re.I)
# Typical archive patterns, used for the "archive hygiene" counts
ARCHIVE_PATTERNS = {
    "pagination": re.compile(r"/page/\d+/?$|[?&](page|paged)=\d+", re.I),
    "tag": re.compile(r"/tag/", re.I),
    "author": re.compile(r"/author/", re.I),
    "date_archive": re.compile(r"/\d{4}/(\d{2}/)?$"),
    "parameter": re.compile(r"\?"),
}


# --------------------------------------------------------------------------- helpers
def norm(url: str) -> str:
    """Normalise a URL for comparison: drop fragment, force trailing slash on paths without an extension."""
    url, _ = urldefrag(url.strip())
    p = urlparse(url)
    path = p.path or "/"
    if not path.endswith("/") and not re.search(r"\.[a-z0-9]{2,5}$", path, re.I):
        path += "/"
    netloc = p.netloc.lower()
    q = f"?{p.query}" if p.query else ""
    return f"{p.scheme.lower()}://{netloc}{path}{q}"


def url_depth(url: str) -> int:
    """Number of folders in the path: / = 0, /blog/ = 1, /blog/post/ = 2."""
    return len([s for s in urlparse(url).path.split("/") if s])


def section_of(url: str, level: int) -> str:
    """The section a URL belongs to = its first `level` path segments (the parent folder by default)."""
    segs = [s for s in urlparse(url).path.split("/") if s]
    if not segs:
        return "(home)"
    if level <= 0:  # parent folder
        segs = segs[:-1]
    else:
        segs = segs[:level] if len(segs) > level else segs[:-1]
    return "/" + "/".join(segs) + ("/" if segs else "")


def get(session: requests.Session, url: str, timeout: int = 20):
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True)
        return r
    except requests.RequestException as e:
        print(f"  ! {url}: {e}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- sitemap
def read_sitemap(session: requests.Session, url: str, seen: set | None = None) -> list[str]:
    """Read a sitemap or sitemap index (recursively, .gz supported). Returns page URLs."""
    seen = set() if seen is None else seen
    if url in seen:
        return []
    seen.add(url)
    r = get(session, url)
    if r is None or r.status_code != 200:
        print(f"  ! could not read sitemap {url}", file=sys.stderr)
        return []
    content = r.content
    if url.endswith(".gz"):
        try:
            content = gzip.decompress(content)
        except OSError:
            pass
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        print(f"  ! not valid XML: {url}", file=sys.stderr)
        return []
    tag = root.tag.split("}")[-1]
    # only the <loc> directly inside each <url>/<sitemap> entry (skips <image:loc>, <video:loc>, ...)
    locs = [child.text.strip() for entry in root for child in entry
            if child.tag.split("}")[-1] == "loc" and not child.tag.startswith("{http://www.google.com/schemas/sitemap-image")
            and child.text]
    if tag == "sitemapindex":
        out = []
        for child in locs:
            out += read_sitemap(session, child, seen)
        return out
    return locs


# --------------------------------------------------------------------------- crawler
def crawl(session, start: str, host: str, max_pages: int, delay: float, extra_seeds=()):
    """Breadth-first crawl from the homepage, following <a href> links on the same host.

    Returns (click_depth: dict url->depth, edges: list of (source, target, anchor, in_nav), status: dict).
    Pages only reachable from `extra_seeds` (sitemap URLs never found via links) are fetched
    afterwards so their outlinks count, but they keep depth = None (= not reachable by clicking).
    """
    depth = {start: 0}
    status, edges = {}, []
    queue = deque([start])
    fetched = 0

    def fetch(url):
        nonlocal fetched
        r = get(session, url)
        fetched += 1
        if r is None:
            status[url] = "error"
            return []
        status[url] = r.status_code
        final = norm(r.url)
        if final != url:
            status[url] = f"{r.status_code} -> {final}"
        if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        nav_links = set()
        for nav in soup.select("nav, header, footer, [role=navigation]"):
            for a in nav.find_all("a", href=True):
                nav_links.add(id(a))
        out = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            tgt = norm(urljoin(final, href))
            p = urlparse(tgt)
            if p.netloc.lower().removeprefix("www.") != host or SKIP_EXT.search(p.path) or SKIP_PATH.search(tgt):
                continue
            if "nofollow" in (a.get("rel") or []):
                continue
            anchor = " ".join(a.get_text(" ", strip=True).split())[:120]
            out.append((url, tgt, anchor, id(a) in nav_links))
        return out

    while queue and fetched < max_pages:
        url = queue.popleft()
        links = fetch(url)
        edges += links
        for _, tgt, _, _ in links:
            if tgt not in depth:
                depth[tgt] = depth[url] + 1
                queue.append(tgt)
        time.sleep(delay)
        if fetched % 25 == 0:
            print(f"  crawled {fetched} pages, {len(depth)} discovered, queue {len(queue)}")

    # fetch unreached sitemap URLs so their outlinks are known (they stay depth=None)
    for url in extra_seeds:
        if url not in status and fetched < max_pages:
            edges += fetch(url)
            time.sleep(delay)
    return depth, edges, status


# --------------------------------------------------------------------------- Screaming Frog
def load_sf(internal_csv: str, inlinks_csv: str | None):
    df = pd.read_csv(internal_csv, low_memory=False)
    cols = {c.lower(): c for c in df.columns}
    need = ["address", "crawl depth"]
    for n in need:
        if n not in cols:
            sys.exit(f"Screaming Frog export is missing the '{n}' column. Export the Internal tab (HTML filter).")
    if "status code" in cols:
        df = df[df[cols["status code"]] == 200]
    if "indexability" in cols:
        df = df[df[cols["indexability"]].astype(str).str.lower() == "indexable"]
    depth = {norm(u): (int(d) if pd.notna(d) else None) for u, d in zip(df[cols["address"]], df[cols["crawl depth"]])}
    status = {u: 200 for u in depth}
    edges = []
    if inlinks_csv:
        il = pd.read_csv(inlinks_csv, low_memory=False)
        ic = {c.lower(): c for c in il.columns}
        if "type" in ic:
            il = il[il[ic["type"]].astype(str).str.lower().isin(["hyperlink", "ahref"])]
        if "follow" in ic:
            il = il[il[ic["follow"]].astype(str).str.lower() != "false"]
        pos = ic.get("link position")
        anc = ic.get("anchor") or ic.get("anchor text")
        for _, row in il.iterrows():
            in_nav = str(row[pos]).lower() in ("navigation", "header", "footer") if pos else False
            edges.append((norm(row[ic["source"]]), norm(row[ic["destination"]]), str(row[anc]) if anc else "", in_nav))
    return depth, edges, status


# --------------------------------------------------------------------------- analysis
def analyse(depth, edges, status, sitemap_urls, home, section_level, post_pattern, hub_pattern, max_click_depth):
    sitemap = {norm(u) for u in sitemap_urls}
    ok_pages = {u for u, s in status.items() if s == 200}
    universe = (ok_pages | sitemap) - {u for u, s in status.items() if s not in (200, None) and u not in sitemap}

    # inlinks (unique source pages, excluding self links); split contextual vs navigation
    inl, inl_ctx = defaultdict(set), defaultdict(set)
    outl = defaultdict(set)
    for s, t, _, nav in edges:
        if s == t:
            continue
        inl[t].add(s)
        outl[s].add(t)
        if not nav:
            inl_ctx[t].add(s)

    post_re = re.compile(post_pattern) if post_pattern else None
    rows = []
    for u in sorted(universe):
        d = depth.get(u)
        ud = url_depth(u)
        archive = next((k for k, rx in ARCHIVE_PATTERNS.items() if rx.search(u)), "")
        rows.append({
            "url": u,
            "in_sitemap": u in sitemap,
            "status": status.get(u, "not crawled"),
            "url_depth": ud,
            "click_depth": d,
            "depth_gap": (d - ud) if d is not None else None,
            "unique_inlinks": len(inl.get(u, ())),
            "contextual_inlinks": len(inl_ctx.get(u, ())),
            "outlinks": len(outl.get(u, ())),
            "section": section_of(u, section_level),
            "archive_type": archive,
            "is_post": bool(post_re.search(u)) if post_re else (ud >= 2 and not archive),
        })
    pages = pd.DataFrame(rows)

    # hubs: explicit pattern, else any URL that is the parent folder of 2+ other URLs
    by_parent = defaultdict(list)
    for u in pages["url"]:
        segs = [s for s in urlparse(u).path.split("/") if s]
        if segs:
            parent = norm(f"{urlparse(u).scheme}://{urlparse(u).netloc}/" + "/".join(segs[:-1]))
            by_parent[parent].append(u)
    if hub_pattern:
        hub_re = re.compile(hub_pattern)
        hubs = [u for u in pages["url"] if hub_re.search(u)]
    else:
        hubs = [p for p, kids in by_parent.items() if len(kids) >= 2 and p != norm(home) and p in set(pages["url"])]
    hub_rows = []
    for h in hubs:
        kids = [k for k in by_parent.get(h, []) if not ARCHIVE_PATTERNS["pagination"].search(k)]
        if not kids:
            continue
        # a hub "covers" a child if the hub OR one of its paginated pages links to it
        hub_family = {h} | {u for u in outl if u.startswith(h) and ARCHIVE_PATTERNS["pagination"].search(u)}
        linked = {k for k in kids if any(k in outl.get(src, ()) for src in hub_family)}
        hub_rows.append({
            "hub": h,
            "hub_click_depth": depth.get(h),
            "children_in_folder": len(kids),
            "children_linked_from_hub": len(linked),
            "coverage_pct": round(100 * len(linked) / len(kids), 1),
            "unlinked_examples": " | ".join(sorted(set(kids) - linked)[:5]),
        })
    hubs_df = pd.DataFrame(hub_rows).sort_values("coverage_pct") if hub_rows else pd.DataFrame(
        columns=["hub", "hub_click_depth", "children_in_folder", "children_linked_from_hub", "coverage_pct", "unlinked_examples"])

    # category balance (posts only)
    posts = pages[pages["is_post"]]
    sec = posts.groupby("section").agg(
        posts=("url", "count"),
        median_click_depth=("click_depth", "median"),
        max_click_depth=("click_depth", "max"),
        median_contextual_inlinks=("contextual_inlinks", "median"),
        orphans=("unique_inlinks", lambda s: int((s == 0).sum())),
    ).reset_index().sort_values("posts", ascending=False)
    total = max(int(sec["posts"].sum()), 1)
    sec["share_pct"] = (100 * sec["posts"] / total).round(1)
    sec["flag"] = sec.apply(lambda r: "thin (<3 posts)" if r.posts < 3 else ("dominant (>40%)" if r.share_pct > 40 else ""), axis=1)

    # orphans: sitemap URLs nobody links to, or never reached from the homepage
    pages["orphan"] = pages["in_sitemap"] & (pages["unique_inlinks"] == 0)
    pages["unreachable"] = pages["in_sitemap"] & pages["click_depth"].isna()
    pages["too_deep"] = pages["click_depth"].fillna(-1) > max_click_depth
    pages["not_in_sitemap"] = (~pages["in_sitemap"]) & (pages["status"] == 200) & (pages["archive_type"] == "") & bool(sitemap)
    return pages, sec, hubs_df


def report(pages, sec, hubs, max_click_depth, site) -> str:
    L = []
    P = pages[pages["status"] == 200]
    posts = P[P["is_post"]]
    L.append(f"# Blog architecture audit: {site}\n")
    L.append(f"- Pages analysed (HTTP 200): **{len(P)}**; of which posts/leaf pages: **{len(posts)}**")
    L.append(f"- In XML sitemap: **{int(pages['in_sitemap'].sum())}**\n")

    L.append("## 1. Click depth")
    cd = P["click_depth"].dropna().astype(int).value_counts().sort_index()
    for d, n in cd.items():
        L.append(f"- depth {d}: {n} pages")
    deep = P[P["too_deep"]]
    L.append(f"\n**{len(deep)} pages are more than {max_click_depth} clicks from the homepage.**")
    for u in deep.sort_values("click_depth", ascending=False)["url"].head(10):
        L.append(f"  - {u}")

    L.append("\n## 2. URL depth vs click depth")
    both = P.dropna(subset=["click_depth"])
    if len(both):
        corr = both["url_depth"].corr(both["click_depth"])
        L.append(f"- Median URL depth (folders): {both['url_depth'].median():g}; median click depth: {both['click_depth'].median():g}")
        L.append(f"- Correlation between the two: {corr:.2f} (folders and links {'tell a similar story' if corr > 0.5 else 'tell different stories'})")
        hidden = both[(both["depth_gap"] >= 2)]
        L.append(f"- **{len(hidden)} pages look shallow in the URL but are buried in the links** (click depth at least 2 more than folder depth).")
        for u in hidden.sort_values("depth_gap", ascending=False)["url"].head(8):
            L.append(f"  - {u}")
        L.append("- Reminder: Google has said click depth from the homepage matters more than how many folders a URL has. Fix links before you touch URLs.")

    L.append("\n## 3. Orphans and sitemap gaps")
    orph = pages[pages["orphan"]]
    unr = pages[pages["unreachable"] & ~pages["orphan"]]
    L.append(f"- **{len(orph)} sitemap URLs have no internal links pointing to them** (true orphans).")
    for u in orph["url"].head(10):
        L.append(f"  - {u}")
    L.append(f"- {len(unr)} more sitemap URLs are linked only from other unreachable pages (no click path from the homepage).")
    nis = pages[pages["not_in_sitemap"]]
    if len(nis):
        L.append(f"- {len(nis)} crawlable, non-archive pages are missing from the sitemap.")
    weak = posts[(posts["contextual_inlinks"] <= 1) & ~posts["orphan"]]
    L.append(f"- {len(weak)} posts have at most one contextual (in-content, non-navigation) internal link.")

    L.append("\n## 4. Category balance (posts per section)")
    if len(sec):
        L.append(sec[["section", "posts", "share_pct", "median_click_depth", "median_contextual_inlinks", "orphans", "flag"]]
                 .to_markdown(index=False) if _has_tabulate() else sec.to_string(index=False))

    L.append("\n## 5. Hub coverage (does each hub link to the posts under it?)")
    if len(hubs):
        L.append(hubs[["hub", "hub_click_depth", "children_in_folder", "children_linked_from_hub", "coverage_pct"]]
                 .to_markdown(index=False) if _has_tabulate() else hubs.to_string(index=False))
        low = hubs[hubs["coverage_pct"] < 80]
        L.append(f"\n**{len(low)} hubs link to fewer than 80% of their children.** See hubs.csv for unlinked examples.")
    else:
        L.append("No hubs found (pass --hub-pattern to name them).")

    L.append("\n## Archive hygiene")
    arch = P["archive_type"].value_counts()
    for k, n in arch.items():
        if k:
            L.append(f"- {k}: {n} crawlable URLs")
    if not arch.drop("", errors="ignore").sum():
        L.append("- No tag, author, date, pagination or parameter URLs were found in the crawl.")
    return "\n".join(L)


def _has_tabulate():
    try:
        import tabulate  # noqa: F401
        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sitemap", help="Sitemap or sitemap index URL")
    ap.add_argument("--home", help="Homepage URL to start the crawl (default: the sitemap's host root)")
    ap.add_argument("--sf-internal", help="Screaming Frog Internal (HTML) export CSV")
    ap.add_argument("--sf-inlinks", help="Screaming Frog Bulk Export > All Inlinks CSV (optional)")
    ap.add_argument("--max-pages", type=int, default=1500, help="Crawl limit (default 1500)")
    ap.add_argument("--delay", type=float, default=0.5, help="Seconds between requests (default 0.5)")
    ap.add_argument("--max-click-depth", type=int, default=3, help="Flag pages deeper than this (default 3)")
    ap.add_argument("--section-level", type=int, default=0,
                    help="Section = first N path segments; 0 = the parent folder (default)")
    ap.add_argument("--post-pattern", help="Regex that identifies posts, e.g. '/blog/[^/]+/$'")
    ap.add_argument("--hub-pattern", help="Regex that identifies hub/category pages, e.g. '/category/'")
    ap.add_argument("--out", default="audit_output", help="Output folder")
    a = ap.parse_args()

    if not a.sitemap and not a.sf_internal:
        ap.error("give --sitemap, --sf-internal, or both")

    s = requests.Session()
    s.headers["User-Agent"] = UA
    sitemap_urls = []
    if a.sitemap:
        print(f"Reading sitemap {a.sitemap}")
        sitemap_urls = read_sitemap(s, a.sitemap)
        print(f"  {len(sitemap_urls)} URLs in sitemap")

    base = a.home or (f"{urlparse(a.sitemap).scheme}://{urlparse(a.sitemap).netloc}/" if a.sitemap else None)
    if a.sf_internal:
        depth, edges, status = load_sf(a.sf_internal, a.sf_inlinks)
        base = base or min(depth, key=lambda u: depth[u] if depth[u] is not None else 99)
        for u in sitemap_urls:
            status.setdefault(norm(u), None)
    else:
        home = norm(base)
        host = urlparse(home).netloc.lower().removeprefix("www.")
        print(f"Crawling from {home} (max {a.max_pages} pages, {a.delay}s delay)")
        depth, edges, status = crawl(s, home, host, a.max_pages, a.delay, [norm(u) for u in sitemap_urls])

    pages, sec, hubs = analyse(depth, edges, status, sitemap_urls, base, a.section_level,
                               a.post_pattern, a.hub_pattern, a.max_click_depth)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pages.to_csv(out / "pages.csv", index=False)
    sec.to_csv(out / "sections.csv", index=False)
    hubs.to_csv(out / "hubs.csv", index=False)
    pages[pages["orphan"] | pages["unreachable"]].to_csv(out / "orphans.csv", index=False)
    md = report(pages, sec, hubs, a.max_click_depth, urlparse(base).netloc)
    (out / "summary.md").write_text(md)
    print("\n" + md)
    print(f"\nFiles written to {out.resolve()}")


if __name__ == "__main__":
    main()
