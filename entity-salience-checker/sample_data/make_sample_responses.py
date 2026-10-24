"""
Build the SAMPLE Natural Language API v1 responses used when USE_SAMPLE = True.

These are NOT real API outputs. They are shaped exactly like a v1 documents:analyzeEntities
response (entities[] with name, type, metadata, salience and mentions[] with text.content,
text.beginOffset and type, plus language), so the notebook's code paths are exercised
without an API key. The salience values come from a simple stand-in formula below
(mention count, position in the text, proper vs common mention), normalised to sum to 1.
Google's real salience model is not public and will give different numbers.

Knowledge Graph MIDs and Wikipedia URLs are real: each MID was looked up from the entity's
Wikidata item (property P646, Freebase ID) on 24 October 2026. The pages and the sites
(Brewly, Coffee One, Daily Grind Notes) are fictional.

Run from this folder:  python make_sample_responses.py
Needs: trafilatura, lxml_html_clean, beautifulsoup4 (same as the notebook).
"""
import csv
import json
import pathlib
import re

import trafilatura
from bs4 import BeautifulSoup

HERE = pathlib.Path(__file__).parent
WIKI = "https://en.wikipedia.org/wiki/"

# surface forms (regex, case-insensitive) -> (entity name, type, metadata, mention type)
ENTITIES = [
    (r"French press(?:es)?", "French press", "CONSUMER_GOOD", {"mid": "/m/01p1qs", "wikipedia_url": WIKI + "French_press"}, "COMMON"),
    (r"cafeti[eè]re", "cafetière", "CONSUMER_GOOD", {}, "COMMON"),
    (r"plunger pot|press pot", "press pot", "OTHER", {}, "COMMON"),
    (r"Brewly Burr Grinder Pro", "Brewly Burr Grinder Pro", "CONSUMER_GOOD", {}, "PROPER"),
    (r"Brewly Classic", "Brewly Classic", "CONSUMER_GOOD", {}, "PROPER"),
    (r"Brewly", "Brewly", "ORGANIZATION", {}, "PROPER"),
    (r"Coffee One", "Coffee One", "ORGANIZATION", {}, "PROPER"),
    (r"Daily Grind Notes", "Daily Grind Notes", "ORGANIZATION", {}, "PROPER"),
    (r"cookies?", "cookies", "OTHER", {}, "COMMON"),
    (r"privacy policy|privacy", "privacy policy", "OTHER", {}, "COMMON"),
    (r"Bodum", "Bodum", "ORGANIZATION", {"mid": "/m/0cb7xp", "wikipedia_url": WIKI + "Bodum"}, "PROPER"),
    (r"newsletter(?: subscribers)?", "newsletter", "OTHER", {}, "COMMON"),
    (r"free shipping", "free shipping", "OTHER", {}, "COMMON"),
    (r"coffee beans?", "coffee beans", "CONSUMER_GOOD", {"mid": "/m/05bzrs", "wikipedia_url": WIKI + "Coffee_bean"}, "COMMON"),
    (r"burr grinders?", "burr grinder", "CONSUMER_GOOD", {}, "COMMON"),
    (r"blade grinders?", "blade grinders", "CONSUMER_GOOD", {}, "COMMON"),
    (r"grinder", "grinder", "CONSUMER_GOOD", {}, "COMMON"),
    (r"gooseneck kettle|kettle", "kettle", "CONSUMER_GOOD", {"mid": "/m/03s_tn", "wikipedia_url": WIKI + "Kettle"}, "COMMON"),
    (r"coffee", "coffee", "CONSUMER_GOOD", {"mid": "/m/02vqfm", "wikipedia_url": WIKI + "Coffee"}, "COMMON"),
    (r"water", "water", "OTHER", {"mid": "/m/0838f", "wikipedia_url": WIKI + "Water"}, "COMMON"),
    (r"baristas?", "baristas", "PERSON", {"mid": "/m/01f1n4", "wikipedia_url": WIKI + "Barista"}, "COMMON"),
    (r"\bUK\b", "UK", "LOCATION", {"mid": "/m/07ssc", "wikipedia_url": WIKI + "United_Kingdom"}, "PROPER"),
    (r"\bUS\b", "US", "LOCATION", {"mid": "/m/09c7w0", "wikipedia_url": WIKI + "United_States"}, "PROPER"),
    (r"mesh filter|mesh|metal filter|filters?", "filter", "OTHER", {}, "COMMON"),
    (r"plunger", "plunger", "OTHER", {}, "COMMON"),
    (r"grounds", "grounds", "OTHER", {}, "COMMON"),
    (r"grind(?: size)?", "grind", "OTHER", {}, "COMMON"),
    (r"ratio", "ratio", "OTHER", {}, "COMMON"),
    (r"brew time|steep", "brew time", "OTHER", {}, "COMMON"),
    (r"cups?", "cup", "OTHER", {}, "COMMON"),
    (r"oils", "oils", "OTHER", {}, "COMMON"),
    (r"team", "team", "PERSON", {}, "COMMON"),
    (r"customers", "customers", "PERSON", {}, "COMMON"),
    (r"brewers?", "brewers", "CONSUMER_GOOD", {}, "COMMON"),
    (r"kitchen", "kitchen", "LOCATION", {}, "COMMON"),
    (r"jug", "jug", "CONSUMER_GOOD", {}, "COMMON"),
    (r"timer", "timer", "CONSUMER_GOOD", {}, "COMMON"),
    (r"particles|dust", "particles", "OTHER", {}, "COMMON"),
    (r"sea salt", "sea salt", "OTHER", {}, "COMMON"),
    (r"compost", "compost", "OTHER", {}, "COMMON"),
    (r"orders?", "order", "OTHER", {}, "COMMON"),
]
# Numbers and prices: v1 returns these as NUMBER / PRICE entities with metadata and salience 0
NUMBERS = [(r"£30", "PRICE", lambda m: {"value": "30.000000", "currency": "GBP"}),
           (r"\b(\d+(?:\.\d+)?)(?= ?(?:grams|ml|minutes|-cup|-litre))", "NUMBER", lambda m: {"value": m.group(1)})]


def main_text(html):
    """Same settings as the notebook's extract_main_text()."""
    return trafilatura.extract(html, include_comments=False, include_tables=False,
                               favor_precision=True) or ""


def full_text(html):
    """Same as the notebook's extract_full_text(): every visible text node, nav and footer included."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines()]
    return "\n".join(ln for ln in lines if ln)


def build_response(text):
    taken = [False] * len(text)
    found = {}
    for pattern, name, etype, meta, mtype in ENTITIES:
        for m in re.finditer(pattern, text, flags=re.I):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            ent = found.setdefault(name, {"name": name, "type": etype, "metadata": dict(meta), "mentions": []})
            ent["mentions"].append({"text": {"content": m.group(0), "beginOffset": m.start()}, "type": mtype})

    # Stand-in salience: earlier and proper mentions count more, normalised to sum to 1
    scores = {}
    for name, ent in found.items():
        s = 0.0
        for men in ent["mentions"]:
            pos = men["text"]["beginOffset"] / max(len(text), 1)
            s += (1.6 if men["type"] == "PROPER" else 1.0) * (1.0 + 1.5 * (1 - pos))
        if ent["type"] in ("OTHER",) and not ent["metadata"]:
            s *= 0.6                      # generic nouns pull less weight
        scores[name] = s
    total = sum(scores.values())
    entities = []
    for name, ent in found.items():
        ent["mentions"].sort(key=lambda x: x["text"]["beginOffset"])
        ent["salience"] = round(scores[name] / total, 6)
        entities.append(ent)

    for pattern, etype, meta_fn in NUMBERS:
        for m in re.finditer(pattern, text):
            entities.append({"name": m.group(0), "type": etype, "metadata": meta_fn(m), "salience": 0,
                             "mentions": [{"text": {"content": m.group(0), "beginOffset": m.start()}, "type": "TYPE_UNKNOWN"}]})

    entities.sort(key=lambda e: e["salience"], reverse=True)    # v1 returns entities by salience
    for e in entities:                                         # v1 omits empty metadata as {}
        e["metadata"] = e["metadata"] or {}
    return {"entities": entities, "language": "en"}


if __name__ == "__main__":
    with open(HERE / "pages_SAMPLE.csv") as f:
        pages = list(csv.DictReader(f))
    for p in pages:
        html = (HERE / "html" / f"{p['sample_id']}.html").read_text(encoding="utf-8")
        for mode, text in (("main", main_text(html)), ("full", full_text(html))):
            resp = build_response(text)
            out = HERE / "responses" / f"{p['sample_id']}__{mode}.json"
            out.write_text(json.dumps(resp, indent=1, ensure_ascii=False), encoding="utf-8")
            top = ", ".join(f"{e['name']} {e['salience']:.3f}" for e in resp["entities"][:4])
            print(f"{out.name}: {len(text)} chars, {len(resp['entities'])} entities. Top: {top}")
