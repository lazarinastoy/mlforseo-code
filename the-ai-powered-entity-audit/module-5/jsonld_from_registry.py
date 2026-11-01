"""Practical 5.6 — Claude drafts each page's JSON-LD from your entity registry; code checks
graph integrity and evidence; a person runs the validators and approves.

    pip install anthropic pydantic
    python jsonld_from_registry.py --registry registry.json --pages pages.csv --limit 3
pages.csv: url, title, page_type (article | course | profile | page …), main_content
Writes jsonld/<slug>.json and jsonld_review.csv. Nothing is deployed from here.
"""
import argparse, csv, json, pathlib, re
import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5-5"


class Claim(BaseModel):
    claim: str          # e.g. "author is Jane Doe"
    evidence: str       # the exact sentence on the page, or "registry", "title" or "url"


class Draft(BaseModel):
    jsonld: str         # the JSON-LD document as a JSON string, with an @graph array
    claims: list[Claim]


PROMPT = """You write schema.org JSON-LD for one web page.

Entity registry (the only source of identity — these entities already exist):
<registry>
{registry}
</registry>

Page: {url}
Title: {title}
Page type: {page_type}
Visible text:
<page>
{text}
</page>

Write one JSON-LD document with "@context": "https://schema.org" and an "@graph" array that
describes THIS page (a WebPage or a more specific type, with its own "@id" of "{url}#webpage").
Rules:
- Refer to registry entities by "@id" only, e.g. {{"@id": "https://…/#organization"}}.
  Never copy their properties into this page, never invent a new @id for them.
- One "@type" per node. No "sameAs" that is not already in the registry.
- Only facts visible in the page text above or present in the registry. No ratings, reviews,
  prices, dates or authors the page does not show.
- Use "about" for the page's main subject when the registry has it.
Then list every claim you made and the exact sentence from the visible text that supports it.
If a claim comes from the registry, the evidence is "registry"; from the page title, "title";
from the URL, "url"."""


def refs(node, out):
    """Every {"@id": x} reference inside a node (not the node's own @id)."""
    if isinstance(node, dict):
        if set(node) == {"@id"}:
            out.add(node["@id"])
        for k, v in node.items():
            if k != "@id":
                refs(v, out)
    elif isinstance(node, list):
        for v in node:
            refs(v, out)
    return out


def integrity(doc, registry, text):
    """Layer 2 — graph integrity — plus the 'true representation' evidence check."""
    reg = {e["@id"]: e for e in registry}
    problems = []
    graph = doc.get("@graph", [])
    ids = {n.get("@id") for n in graph if isinstance(n, dict)}
    for n in graph:
        t = n.get("@type")
        if isinstance(t, list) and len(t) > 1:
            problems.append(f"two types on one node: {t}")
        if n.get("@id") in reg and len(n) > 2:
            problems.append(f"re-declares registry entity {n['@id']}")
        for s in n.get("sameAs", []) if isinstance(n.get("sameAs"), list) else [n.get("sameAs")] if n.get("sameAs") else []:
            if not any(s in (e.get("sameAs") or []) for e in registry):
                problems.append(f"new sameAs not in registry: {s}")
    for r in refs(graph, set()):
        if r not in ids and r not in reg:
            problems.append(f"@id reference resolves to nothing: {r}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--pages", default="pages.csv")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    registry = json.load(open(a.registry, encoding="utf-8"))["entities"]
    pages = list(csv.DictReader(open(a.pages, encoding="utf-8")))[: a.limit or None]
    out = pathlib.Path("jsonld"); out.mkdir(exist_ok=True)
    client = anthropic.Anthropic()
    with open("jsonld_review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "file", "nodes", "integrity", "unsupported_claims", "decision"])
        for p in pages:
            text = p["main_content"][:12000]
            resp = client.messages.parse(
                model=MODEL, max_tokens=4096,
                messages=[{"role": "user", "content": PROMPT.format(
                    registry=json.dumps(registry, indent=1), url=p["url"], title=p["title"],
                    page_type=p.get("page_type", "page"), text=text)}],
                output_format=Draft,
            )
            d = resp.parsed_output
            try:
                doc = json.loads(d.jsonld)
            except json.JSONDecodeError as e:
                w.writerow([p["url"], "", 0, f"not valid JSON: {e}", "", ""]); continue
            problems = integrity(doc, registry, text)
            meta_ok = {"registry", "title", "url"}
            unsupported = [c.claim for c in d.claims
                           if c.evidence.strip().lower() not in meta_ok
                           and " ".join(c.evidence.split()) not in " ".join(text.split())
                           and c.evidence.strip() not in (p["title"], p["url"])]
            slug = re.sub(r"[^a-z0-9]+", "-", p["url"].lower()).strip("-")[-80:]
            (out / f"{slug}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False))
            w.writerow([p["url"], f"jsonld/{slug}.json", len(doc.get("@graph", [])),
                        "; ".join(problems) or "ok", "; ".join(unsupported) or "ok", ""])
            print("drafted", p["url"], "-", "ok" if not problems and not unsupported else "CHECK")
    print("Next: paste one file per page type into validator.schema.org and the Rich Results Test.")


if __name__ == "__main__":
    main()
