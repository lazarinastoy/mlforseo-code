"""Practical 5.6: check a whole site's structured data the way our deploys do.

Two checks, run on live URLs, on any CMS:

  1. Smoke test (what our GitHub Action runs after every deploy):
     every URL must have exactly ONE application/ld+json block, it must parse,
     and it must contain an @graph. Two blocks means two emitters that will disagree.
  2. Entity census (the check that found our duplicate people):
     across the whole site, every Person and Organization name should map to exactly
     one @id. Two @ids for one name means machines see two different things.
  Plus graph integrity per page: every {"@id": ...} reference must resolve to a node on
  the page, or to an id you list as external (a sister site that owns that entity).

    python graph_check.py --sitemap https://www.example.com/sitemap_index.xml --limit 200
    python graph_check.py --urls urls.txt
    python graph_check.py --urls urls.txt --expect-class my-schema --external https://me.com/

Outputs graph_check.csv (one row per URL) and census.csv, and exits 1 if any URL fails
the smoke test, so you can run it in CI after a deploy.
No API calls and no keys; it only fetches your public pages.
"""
import argparse, csv, json, re, sys, time, urllib.request
from collections import defaultdict
from xml.etree import ElementTree

UA = "Mozilla/5.0 (compatible; entity-audit-graph-check/1.0)"
BLOCK = re.compile(r'<script([^>]*type=["\']application/ld\+json["\'][^>]*)>(.*?)</script>', re.S | re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def sitemap_urls(url, limit):
    out, todo = [], [url]
    while todo and len(out) < limit:
        root = ElementTree.fromstring(get(todo.pop(0)).encode())
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        todo += [e.text.strip() for e in root.findall("s:sitemap/s:loc", ns)]
        out += [e.text.strip() for e in root.findall("s:url/s:loc", ns)]
    return out[:limit]


def nodes(data):
    """Every dict node in a JSON-LD document, @graph or not."""
    stack, out = [data], []
    while stack:
        x = stack.pop()
        if isinstance(x, list):
            stack += x
        elif isinstance(x, dict):
            out.append(x)
            stack += list(x.values())
    return out


def types(n):
    t = n.get("@type", [])
    return t if isinstance(t, list) else [t]


def check(url, html, expect_class, external):
    blocks = BLOCK.findall(html)
    row = {"url": url, "blocks": len(blocks), "parses": "", "graph": "", "class": "",
           "unresolved": "", "multi_type": "", "result": "ok"}
    found, problems = [], []
    if len(blocks) != 1:
        problems.append(f"{len(blocks)} ld+json blocks")
    for attrs, body in blocks:
        try:
            data = json.loads(body)
        except ValueError:
            row["parses"] = "no"
            problems.append("a block does not parse")
            continue
        row["parses"] = "yes"
        row["graph"] = "yes" if isinstance(data, dict) and "@graph" in data else "no"
        if expect_class:
            row["class"] = "yes" if expect_class in attrs else "no"
        found += nodes(data)
    if row["graph"] == "no":
        problems.append("no @graph")
    if row["class"] == "no":
        problems.append(f"block is not from {expect_class}")
    declared = {n["@id"] for n in found if "@id" in n and len(n) > 1}
    refs = {n["@id"] for n in found if set(n) == {"@id"}}
    missing = sorted(r for r in refs - declared if not any(r.startswith(e) for e in external))
    row["unresolved"] = " | ".join(missing)
    row["multi_type"] = " | ".join(f'{n.get("@id", n.get("name", "?"))}: {"+".join(types(n))}'
                                   for n in found if len(types(n)) > 1)
    if problems:
        row["result"] = "FAIL: " + "; ".join(problems)
    elif missing or row["multi_type"]:
        row["result"] = "check"
    return row, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitemap")
    ap.add_argument("--urls", help="a text file, one URL per line")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--expect-class", default="", help="class your own ld+json script carries")
    ap.add_argument("--external", default="", help="comma-separated id prefixes owned by other sites")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    a = ap.parse_args()
    if not (a.sitemap or a.urls):
        ap.error("give --sitemap or --urls")
    urls = sitemap_urls(a.sitemap, a.limit) if a.sitemap else \
        [l.strip() for l in open(a.urls, encoding="utf-8") if l.strip()][:a.limit]
    external = [x for x in a.external.split(",") if x]

    rows, census = [], defaultdict(lambda: defaultdict(set))   # name -> @id -> urls
    for i, u in enumerate(urls, 1):
        try:
            row, found = check(u, get(u), a.expect_class, external)
        except Exception as e:                                     # keep going, report it
            row, found = {"url": u, "result": f"FAIL: fetch error {e}"}, []
        rows.append(row)
        for n in found:
            if n.get("name") and n.get("@id") and set(types(n)) & {"Person", "Organization"}:
                census[str(n["name"]).strip()][n["@id"]].add(u)
        print(f"  {i}/{len(urls)} {row['result'][:40]:40} {u}")
        time.sleep(a.delay)

    cols = ["url", "blocks", "parses", "graph", "class", "unresolved", "multi_type", "result"]
    with open("graph_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open("census.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "ids", "id", "pages", "example"])
        for name, ids in sorted(census.items(), key=lambda x: -len(x[1])):
            for i, us in ids.items():
                w.writerow([name, len(ids), i, len(us), sorted(us)[0]])

    fails = [r for r in rows if r["result"].startswith("FAIL")]
    dupes = [n for n, ids in census.items() if len(ids) > 1]
    print(f"\n{len(rows)} URLs: {len(rows) - len(fails)} pass the smoke test, {len(fails)} fail -> graph_check.csv")
    print(f"census: {len(census)} people and organisations, {len(dupes)} with more than one @id -> census.csv")
    for n in dupes[:10]:
        print(f"  two or more @ids for {n!r}: {', '.join(census[n])}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
