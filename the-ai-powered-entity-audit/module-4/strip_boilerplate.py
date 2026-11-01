"""Practical 4.4 — find and remove site chrome and boilerplate from a corpus, the same way for
every corpus in the comparison (Lesson 4.4: "Filter everything, with the same rules, and write
down what you filtered").

Two layers, because chrome survives at two levels:
  text     sentences and lines repeated across many pages of ONE site (cookie banners,
           newsletter boxes, author bios, "related posts", footers) — removed from the text
           before extraction, so they never become entities
  entities chrome entities ("view course", "interview prep"): removed automatically when they are
           button text, numbers, or occur inside the boilerplate lines; entities that are merely
           frequent are only flagged for review, because a focused site's core topics are frequent too

    python strip_boilerplate.py scan  wordlift/ marketermilk/ yoursite/      # writes review files
    #   ... read boilerplate_lines.csv and chrome_entities.csv; set decision to keep / remove ...
    python strip_boilerplate.py apply wordlift/ marketermilk/ yoursite/      # writes *_clean files

Each folder holds one site: internal_all.csv (Screaming Frog export with a Content column from
your custom extraction) and/or entity_mentions.csv (Entity Extractor export). Thresholds are a
starting point, not an answer — Lesson 2.3 had to come down from 40% to about 10% on its own site.
"""
import argparse, csv, pathlib, re, sys
from collections import defaultdict

csv.field_size_limit(sys.maxsize)
BUTTONS = re.compile(r"^(view|read|see|share|subscribe|sign up|log ?in|buy|purchase|download|get|try|start|"
                     r"join|book|contact|learn more|click|watch|enrol|register|add to|continue|explore|apply)\b", re.I)
NOISE = re.compile(r"cookie|privacy policy|all rights reserved|©|terms (of|and) (use|service)|newsletter|"
                   r"follow us|share (this|on)|related (posts|articles)|table of contents|written by|"
                   r"posted (in|on)|leave a (comment|reply)", re.I)


def norm(s):
    s = re.sub(r"\d+", "#", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^\w#' ]+", " ", s)).strip()


def units(text):
    """Lines first (navigation and boxes are line-shaped), then sentences inside long lines."""
    out = []
    for line in re.split(r"[\r\n]+", text or ""):
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line) if len(line) > 200 else [line]
        out += [p.strip() for p in parts if len(p.strip()) >= 12]
    return out


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def scan(folders, min_line_share, min_line_pages, entity_share):
    lines_out, ents_out = [], []
    for d in map(pathlib.Path, folders):
        site = d.name.rstrip("/")
        pages = [r for r in read(d / "internal_all.csv") if r.get("Content")] if (d / "internal_all.csv").exists() else []
        if pages:
            df, example = defaultdict(set), {}
            for r in pages:
                for u in set(units(r["Content"])):
                    k = norm(u)
                    if len(k) >= 10:
                        df[k].add(r["Address"]); example.setdefault(k, u)
            n = len(pages)
            for k, urls in df.items():
                share = len(urls) / n
                if len(urls) >= min_line_pages and (share >= min_line_share or NOISE.search(k)):
                    lines_out.append([site, example[k][:300], len(urls), round(share, 3),
                                      "noise pattern" if NOISE.search(k) else "repeated", "remove"])
            print(f"{site}: {n} pages, {sum(1 for x in lines_out if x[0] == site)} boilerplate lines")
        if (d / "entity_mentions.csv").exists():
            rows = read(d / "entity_mentions.csv")
            n = len({r["url"] for r in rows}) or 1
            pages_per = defaultdict(set)
            for r in rows:
                pages_per[(r.get("entity_norm") or r["entity"]).lower()].add(r["url"])
            chrome_text = " | ".join(norm(x[1]) for x in lines_out if x[0] == site)
            total = len(pages_per); strong = review = 0
            for e, urls in pages_per.items():
                share = len(urls) / n
                if len(urls) < 3:
                    continue
                ne = norm(e)
                if re.fullmatch(r"[#\W_]*", ne) or len(ne) <= 1:
                    why, dec = "number or symbol", "remove"
                elif BUTTONS.search(e):
                    why, dec = "button text", "remove"
                elif ne and len(ne) >= 4 and re.search(r"\b%s\b" % re.escape(ne), chrome_text):
                    why, dec = "also appears in boilerplate text", "review"
                elif share >= entity_share:
                    why, dec = "on %d%% of pages" % round(share * 100), "review"
                else:
                    continue
                strong += dec == "remove"; review += dec == "review"
                ents_out.append([site, e, len(urls), round(share, 3), why, dec])
            print(f"{site}: {total} distinct entities on {n} pages -> {strong} chrome to remove, "
                  f"{review} frequent entities to review (>= {entity_share:.0%} of pages)")
    with open("boilerplate_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["site", "text", "pages", "share", "why", "decision"])
        w.writerows(sorted(lines_out, key=lambda r: (r[0], -r[2])))
    with open("chrome_entities.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["site", "entity", "pages", "share", "why", "decision"])
        w.writerows(sorted(ents_out, key=lambda r: (r[0], -r[2])))
    print("Now read both files. 'remove' rows are strong chrome signals; 'review' rows are frequent entities that "
          "may be the site's real core topics — set each to remove or keep. apply only removes 'remove'. "
          "Keep both files: they are your record of what was filtered, for every corpus.")


def apply(folders):
    rm_lines, rm_ents = defaultdict(set), defaultdict(set)
    for r in read("boilerplate_lines.csv"):
        if r["decision"].strip().lower() == "remove":
            rm_lines[r["site"]].add(norm(r["text"]))
    for r in read("chrome_entities.csv"):
        if r["decision"].strip().lower() == "remove":
            rm_ents[r["site"]].add(r["entity"].lower())
    for d in map(pathlib.Path, folders):
        site = d.name.rstrip("/")
        if (d / "internal_all.csv").exists():
            rows = read(d / "internal_all.csv"); before = after = 0
            for r in rows:
                kept = [u for u in units(r.get("Content", "")) if norm(u) not in rm_lines[site]]
                before += len((r.get("Content") or "").split()); r["Content"] = "\n".join(kept)
                after += len(r["Content"].split())
            with open(d / "internal_all_clean.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
            print(f"{site}: text {before:,} -> {after:,} words ({1 - after / max(before, 1):.1%} boilerplate removed)")
        if (d / "entity_mentions.csv").exists():
            rows = read(d / "entity_mentions.csv")
            keep = [r for r in rows if (r.get("entity_norm") or r["entity"]).lower() not in rm_ents[site]]
            with open(d / "entity_mentions_clean.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(keep)
            print(f"{site}: entity rows {len(rows):,} -> {len(keep):,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scan", "apply"])
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--line-share", type=float, default=0.2, help="repeated on this share of a site's pages")
    ap.add_argument("--line-pages", type=int, default=3, help="and on at least this many pages")
    ap.add_argument("--entity-share", type=float, default=0.10, help="Lesson 2.3 chrome threshold")
    a = ap.parse_args()
    scan(a.folders, a.line_share, a.line_pages, a.entity_share) if a.mode == "scan" else apply(a.folders)
