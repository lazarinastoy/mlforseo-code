"""Practical 5.2 — draft entity-first meta descriptions with Claude, for a person to review.

Input
  page_entity_profiles.csv  from the Entity Extractor (Practical 2.3)
  pages.csv                 url, title, meta_description, main_content  (your crawl export)
Output
  review.csv                one row per page: old and new side by side, checks, an empty
                            "decision" column for approve / edit / reject

    pip install anthropic pydantic
    export ANTHROPIC_API_KEY=...        # never paste the key into the script
    python meta_descriptions.py --limit 5     # try five pages first, read them, then run the rest
"""
import argparse, csv, re
import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5-5"   # Lesson 2.5: Haiku 4.5 is the cheaper tier once your checks pass
SITE_VOICE = "Plain, specific British English. No hype, no exclamation marks."


class Draft(BaseModel):
    meta_description: str
    entity_in_first_ten_words: bool
    needs_review: bool
    reason: str


PROMPT = """You write meta descriptions for {site}.

Page title: {title}
Current meta description: {old}
Intended entity (what this page is about): {entity}

Page text:
<page>
{text}
</page>

Write one meta description that:
- names "{entity}" within its first ten words, in exactly that form
- says what this page covers, in the site's own voice: {voice}
- is 120-155 characters
- makes no claim, number or promise that is not in the page text above

If the page text does not support a good description, set needs_review to true and say why."""


def checks(new, entity, text):
    """The checks a person should not have to do by eye."""
    out = []
    if not 120 <= len(new) <= 155:
        out.append(f"length {len(new)}")
    if entity.lower() not in " ".join(new.split()[:10]).lower():
        out.append("entity not in first ten words")
    for n in re.findall(r"\d[\d,.%]*", new):
        if n.rstrip(".,") not in text:
            out.append(f"number {n} not on the page")
    return "; ".join(out) or "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default="page_entity_profiles.csv")
    ap.add_argument("--pages", default="pages.csv")
    ap.add_argument("--site", default="our site")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    pages = {r["url"]: r for r in csv.DictReader(open(a.pages, encoding="utf-8"))}
    todo = []
    for r in csv.DictReader(open(a.profiles, encoding="utf-8")):
        page = pages.get(r["url"])
        entity = (r.get("intended_entity") or "").strip()
        # Only pages whose subject is already right and missing from the meta description.
        # A MISMATCH page needs the Lesson 5.2 content fix first, not a new snippet.
        if page and entity and r.get("intent_match", "").upper() != "MISMATCH" \
                and str(r.get("dominant_in_meta", "")).lower() in ("false", "0", "no"):
            todo.append((r["url"], entity, page))
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} pages to draft")

    client = anthropic.Anthropic()
    with open("review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "entity", "old", "new", "chars", "checks", "needs_review", "reason", "decision"])
        for url, entity, page in todo:
            text = page["main_content"][:12000]
            resp = client.messages.parse(
                model=MODEL, max_tokens=1024,
                messages=[{"role": "user", "content": PROMPT.format(
                    site=a.site, title=page["title"], old=page["meta_description"],
                    entity=entity, text=text, voice=SITE_VOICE)}],
                output_format=Draft,
            )
            d = resp.parsed_output
            w.writerow([url, entity, page["meta_description"], d.meta_description, len(d.meta_description),
                        checks(d.meta_description, entity, text), d.needs_review, d.reason, ""])
            print("drafted", url)
    print("Open review.csv. Approve, edit or reject every row before importing anything.")


if __name__ == "__main__":
    main()
