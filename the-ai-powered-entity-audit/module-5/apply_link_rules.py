"""Practical 5.5: apply entity link rules to HTML, the way our Auto Links plugin does.

This is the plugin's engine rewritten in Python, so you can use the same rules anywhere: preview
what a rule set would do before you switch it on, run it at build time on a static or headless
site, or hand it to a developer as the specification for your CMS.

How it works (the same rules as the WordPress plugin):
  - The HTML is split into tags and text. Tags pass through byte for byte; only text is linked.
  - Text inside a, h1-h6, pre, code, kbd, samp, button, label, select, option, textarea, svg,
    math and nav is skipped, as is anything inside class="no-autolink" or data-no-autolink.
  - All keywords go into one pattern, longest first, so "MLforSEO Academy" wins over "MLforSEO".
  - Matches never start or end inside a word, URL or domain.
  - "max" caps links per rule per page (0 = every mention). A page never links to itself.
  - Disabled rules are ignored, so guessed owners stay switched off until someone checks them.

    python apply_link_rules.py --rules link_rules.json --html pages/          # preview: report only
    python apply_link_rules.py --rules link_rules.json --html pages/ --write  # write linked copies to linked/

Each .html file needs its own URL so self-links can be skipped: put it in pages.csv
(file,url), or name files after their slug (entity-seo.html -> https://<--site>/entity-seo/).
Outputs link_preview.csv: file, url, rule, keyword, target, sentence.
"""
import argparse, csv, html, json, pathlib, re

SKIP = {"a", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "kbd", "samp", "button", "label",
        "select", "option", "textarea", "svg", "math", "nav"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr"}
TOKEN = re.compile(r"(<!--.*?-->|<[^>]+>)", re.S)
TAG = re.compile(r"<\s*(/)?\s*([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>", re.S)


def norm(u):
    u = re.sub(r"^https?://", "", u.strip().lower())
    u = re.sub(r"^www\.", "", u)
    return u.split("#")[0].split("?")[0].rstrip("/")


def compile_rules(rules):
    """One alternation per case mode, longest keyword first, mapped back to its rule."""
    live = [r for r in rules if r.get("enabled", True) and r.get("keywords") and r.get("url")]
    out = []
    for cs in (True, False):
        kw = {}
        for r in live:
            if bool(r.get("case_sensitive")) == cs:
                for k in r["keywords"]:
                    kw.setdefault(k if cs else k.lower(), r)
        if not kw:
            continue
        alts = sorted(kw, key=len, reverse=True)
        # multi-word keywords also match across non-breaking spaces
        body = "|".join(re.escape(k).replace(r"\ ", r"(?:\s|&nbsp;| )+") for k in alts)
        pat = re.compile(r"(?<![\w/.@-])(" + body + r")(?![\w-]|\.\w)", 0 if cs else re.I)
        out.append((pat, kw, cs))
    return out


def link_page(doc, page_url, compiled, rules_by_id):
    used = {rid: 0 for rid in rules_by_id}
    self_url = norm(page_url)
    stack, found, parts = [], [], TOKEN.split(doc)
    for i, part in enumerate(parts):
        if i % 2 == 1:                                  # a tag or comment: track the skip stack
            m = TAG.match(part)
            if m and not part.startswith("<!--"):
                closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
                if closing:
                    if any(t.lstrip("!") == name for t in stack):
                        while stack and stack.pop().lstrip("!") != name:
                            pass
                elif name not in VOID and not attrs.rstrip().endswith("/"):
                    skip = name in SKIP or "no-autolink" in attrs
                    stack.append(("!" if skip else "") + name)
            continue
        if any(t.startswith("!") for t in stack) or not part.strip():
            continue

        # Collect matches from both case modes on the original text, then keep the earliest,
        # longest, non-overlapping ones, so a link is never placed inside another link.
        cands = []
        for pat, kw, cs in compiled:
            for m in pat.finditer(part):
                key = re.sub(r"(?:\s|&nbsp;|\u00a0)+", " ", m.group(1) if cs else m.group(1).lower())
                r = kw.get(key)
                if r and norm(r["url"]) != self_url:
                    cands.append((m.start(1), m.end(1), r))
        cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
        text = html.unescape(re.sub(r"\s+", " ", part)).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        out, pos = [], 0
        for start, end, r in cands:
            cap = int(r.get("max", 1))
            if start < pos or (cap and used[r["id"]] >= cap):
                continue
            used[r["id"]] += 1
            word = part[start:end]
            plain = html.unescape(word).replace("\u00a0", " ")
            sent = next((x for x in sentences if plain.lower() in x.lower()), text)
            found.append((r["id"], plain, r["url"], sent[:200]))
            rel = {"affiliate": ' rel="sponsored nofollow noopener" target="_blank"',
                   "external": ' rel="noopener" target="_blank"'}.get(r.get("type"), "")
            out += [part[pos:start], f'<a href="{html.escape(r["url"], quote=True)}"{rel}>{word}</a>']
            pos = end
        part = "".join(out) + part[pos:]
        parts[i] = part
    return "".join(parts), found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="link_rules.json")
    ap.add_argument("--html", required=True, help="an .html file or a folder of them")
    ap.add_argument("--pages", default="pages.csv", help="file,url map (optional)")
    ap.add_argument("--site", default="https://www.example.com", help="used when pages.csv has no row")
    ap.add_argument("--write", action="store_true", help="write linked copies to linked/")
    a = ap.parse_args()

    rules = json.load(open(a.rules, encoding="utf-8"))
    for r in rules:
        if r.get("url", "").startswith("/"):
            r["url"] = a.site.rstrip("/") + r["url"]
    by_id = {r["id"]: r for r in rules}
    compiled = compile_rules(rules)
    urls = {}
    if pathlib.Path(a.pages).exists():
        urls = {r["file"]: r["url"] for r in csv.DictReader(open(a.pages, encoding="utf-8"))}

    src = pathlib.Path(a.html)
    files = sorted(src.glob("*.html")) if src.is_dir() else [src]
    out_dir = pathlib.Path("linked")
    rows = []
    for f in files:
        url = urls.get(f.name) or f"{a.site.rstrip('/')}/{f.stem}/"
        new, found = link_page(f.read_text(encoding="utf-8"), url, compiled, by_id)
        rows += [[f.name, url, *x[:3], x[3]] for x in found]
        if a.write:
            out_dir.mkdir(exist_ok=True)
            (out_dir / f.name).write_text(new, encoding="utf-8")
    with open("link_preview.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "url", "rule", "keyword", "target", "sentence"])
        w.writerows(rows)
    off = sum(1 for r in rules if not r.get("enabled", True))
    print(f"{len(rows)} links on {len({r[0] for r in rows})} of {len(files)} pages "
          f"from {len(rules) - off} enabled rules ({off} disabled) -> link_preview.csv"
          + (f"; linked copies in {out_dir}/" if a.write else " (preview only: add --write)"))


if __name__ == "__main__":
    main()
