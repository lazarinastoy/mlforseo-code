"""Practical 5.5 — turn the audit into an internal link plan, and into link rules.

Inputs (all from earlier practicals)
  entity_mentions.csv        url, entity, type, salience, ...           (Entity Extractor)
  page_entity_profiles.csv   url, dominant_entity, ...                   (Entity Extractor)
  naming_table.csv           canonical, variants (a|b|c), owner_url       (Practical 3.3; owner_url optional)
  all_inlinks.csv            Screaming Frog > Bulk Export > Links > All Inlinks
Outputs
  link_plan.csv   from_url, to_url, entity, anchor, from_salience, to_is_orphan, priority
  link_rules.csv  keyword, url, max_per_page — the shape most auto-linking plugins import

    python link_map.py --min-salience 0.02 --per-page 3
No API calls: this step is arithmetic. Claude comes in afterwards, on the sentences.
"""
import argparse, csv
from collections import defaultdict


def norm(u):
    return u.split("#")[0].split("?")[0].rstrip("/").lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-salience", type=float, default=0.02)
    ap.add_argument("--per-page", type=int, default=3, help="new links proposed per source page")
    ap.add_argument("--exclude", default="/tag/,/category/,/author/,/page/",
                    help="URL fragments that never give or receive a planned link (archives, pagination)")
    a = ap.parse_args()
    skip = [x for x in a.exclude.split(",") if x]
    ok = lambda u: not any(x in u + "/" for x in skip)

    names = {}      # any surface form -> canonical
    owner = {}      # canonical -> the page that should receive links for it
    for r in csv.DictReader(open("naming_table.csv", encoding="utf-8")):
        c = r["canonical"].strip()
        for v in [c] + [x for x in r.get("variants", "").split("|") if x.strip()]:
            names[v.strip().lower()] = c
        if r.get("owner_url"):
            owner[c] = norm(r["owner_url"])

    # The owner of an entity, if the table does not name one: the page where it is dominant
    # with the highest salience. One owner per entity — that is the hub pattern from 5.5.
    best = {}
    for r in csv.DictReader(open("page_entity_profiles.csv", encoding="utf-8")):
        c = names.get((r.get("dominant_entity") or "").lower())
        s = float(r.get("dominant_salience") or 0)
        if c and c not in owner and ok(norm(r["url"])) and s > best.get(c, ("", -1))[1]:
            best[c] = (norm(r["url"]), s)
    picked = {c for c in best if c not in owner}   # suggestions, not decisions: check these
    for c, (u, _) in best.items():
        owner.setdefault(c, u)

    linked, inbound = set(), defaultdict(int)
    for r in csv.DictReader(open("all_inlinks.csv", encoding="utf-8")):
        if r.get("Type", "Hyperlink") != "Hyperlink":
            continue
        s, d = norm(r["Source"]), norm(r["Destination"])
        linked.add((s, d))
        if r.get("Link Position", "Content") == "Content":
            inbound[d] += 1

    plan = defaultdict(list)
    for r in csv.DictReader(open("entity_mentions.csv", encoding="utf-8")):
        c = names.get(r["entity"].strip().lower())
        sal = float(r.get("salience") or 0)
        if not c or c not in owner or sal < a.min_salience:
            continue
        src, dst = norm(r["url"]), owner[c]
        if src == dst or (src, dst) in linked or not ok(src):   # no self-links; subtract what exists
            continue
        plan[src].append((dst, c, sal))

    rows = []
    for src, cands in plan.items():
        seen = set()
        for dst, c, sal in sorted(cands, key=lambda x: (inbound[x[0]] > 0, -x[2])):
            if dst in seen:
                continue
            seen.add(dst)
            rows.append([src, dst, c, c, round(sal, 4), inbound[dst] == 0])
            if len(seen) >= a.per_page:
                break
    # Orphan targets first, then the most salient mentions.
    rows.sort(key=lambda r: (not r[5], -r[4]))
    with open("link_plan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from_url", "to_url", "entity", "anchor", "from_salience", "to_is_orphan", "priority"])
        for i, r in enumerate(rows, 1):
            w.writerow(r + [(i - 1) // 20 + 1])          # rounds of twenty
    with open("link_rules.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["keyword", "url", "max_per_page", "owner_source"])
        for c, u in sorted(owner.items()):
            w.writerow([c, u, 1, "auto - check" if c in picked else "naming table"])
    print(f"{len(rows)} proposed links on {len(plan)} pages -> link_plan.csv (rounds of 20)")
    print(f"{len(owner)} entity -> page rules -> link_rules.csv ({len(picked)} owners picked automatically: check them)")


if __name__ == "__main__":
    main()
