"""Practical 5.3 — the five-check extraction audit on your own pages, then Claude rewrites
only the sections that fail, for a person to review.

    pip install anthropic beautifulsoup4 requests pydantic
    python extraction_check.py urls.txt --selector "div.entry-content"          # audit only, free
    python extraction_check.py urls.txt --selector "div.entry-content" --rewrite  # + drafts

The checks are heuristics (Lesson 5.3): a flag means "look at this", not "this is wrong".
  heading    H2/H3 that is generic ("Overview", "Conclusion") or two words or fewer
  backref    sequential-reader language ("as mentioned above", "see below")
  opener     a section whose first sentence starts with a bare pronoun (It / This / They …)
  unsourced  a sentence with a statistic and no source, study, year or "according to"
  oversized  a section over 400 words — more than one retrieval chunk
"""
import argparse, csv, re, sys
import requests
from bs4 import BeautifulSoup

GENERIC = {"introduction", "intro", "overview", "conclusion", "summary", "final thoughts", "key takeaways",
           "background", "a closer look", "why it matters", "next steps", "wrapping up", "getting started",
           "the bottom line", "in summary", "in conclusion", "the problem", "the solution", "how it works"}
BACKREF = re.compile(r"\b(as (?:we )?(?:noted|mentioned|discussed|explained|saw|shown|described)"
                     r"(?: (?:above|earlier|before|below|previously))?|see (?:above|below)"
                     r"|(?:mentioned|discussed|shown|noted|listed) (?:above|earlier|below)"
                     r"|in the (?:previous|next|following|last) section|the above (?:table|list|example))\b", re.I)
PRONOUN_OPEN = re.compile(r"^(It|This|These|They|That|Those|Its|Their)\b")
STAT = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x\b|times\b)|\b\d{1,3}(?:,\d{3})+\b")
SOURCE = re.compile(r"according to|source|study|survey|report|research|data from|\b(?:19|20)\d\d\b|found that", re.I)

REWRITE = """Rewrite one section of a web page so it can be retrieved and quoted on its own.

Heading: {heading}
Flags from the audit: {flags}
Section text:
<section>
{text}
</section>

Rules:
- Make the heading the question this section answers, in the reader's words.
- First sentence: the direct answer or definition, naming the subject in full (no "it", "this").
- One claim per paragraph. Keep every fact, number and source that is already there.
- Do NOT add facts, numbers, sources or examples. If a statistic has no source, keep it and
  add [SOURCE NEEDED] after it.
- Remove "as mentioned above"-style references; restate what they pointed at in a few words.
- If the section is over 400 words, split it into two sections, each with its own heading.
Return only the rewritten section in Markdown."""


def sections(html, selector):
    body = BeautifulSoup(html, "html.parser").select_one(selector)
    if not body:
        return []
    out, cur = [], None
    for el in body.find_all(["h2", "h3", "p", "li", "td"]):
        if el.name in ("h2", "h3"):
            cur = {"heading": el.get_text(" ", strip=True), "text": []}
            out.append(cur)
        elif cur is not None and el.get_text(strip=True):
            cur["text"].append(el.get_text(" ", strip=True))
    return out


def check(sec):
    text = " ".join(sec["text"])
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text else ""
    h = sec["heading"].strip().rstrip(":").lower()
    flags = []
    if h in GENERIC or len(h.split()) <= 2:
        flags.append("heading")
    if BACKREF.search(text):
        flags.append("backref")
    if PRONOUN_OPEN.match(first):
        flags.append("opener")
    if any(STAT.search(s) and not SOURCE.search(s) for s in re.split(r"(?<=[.!?])\s+", text)):
        flags.append("unsourced")
    if len(text.split()) > 400:
        flags.append("oversized")
    return flags, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls")
    ap.add_argument("--selector", default="div.entry-content")
    ap.add_argument("--rewrite", action="store_true")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    a = ap.parse_args()
    client = None
    if a.rewrite:
        import anthropic
        client = anthropic.Anthropic()
    rows = []
    for url in [u.strip() for u in open(a.urls) if u.strip()]:
        html = requests.get(url, timeout=30, headers={"User-Agent": "extraction-check"}).text
        secs = sections(html, a.selector)
        if not secs:
            print(f"! no sections under {a.selector}: {url}", file=sys.stderr)
        for s in secs:
            flags, text = check(s)
            draft = ""
            if flags and client:
                msg = client.messages.create(model=a.model, max_tokens=2048, messages=[{"role": "user",
                      "content": REWRITE.format(heading=s["heading"], flags=", ".join(flags), text=text)}])
                draft = next((b.text for b in msg.content if b.type == "text"), "")
            rows.append([url, s["heading"], len(text.split()), " ".join(flags), text, draft, ""])
    with open("extraction_audit.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "heading", "words", "flags", "original", "draft", "decision"])
        w.writerows(rows)
    failing = sum(1 for r in rows if r[3])
    print(f"{len(rows)} sections, {failing} flagged -> extraction_audit.csv")


if __name__ == "__main__":
    main()
