"""Check the logic of every formula in formulas.py.

Google Sheets' REGEXMATCH / REGEXEXTRACT use Google's RE2 engine. The patterns
here only use features that RE2 and Python's `re` share ((?i), \\b, groups,
alternation, character classes, anchors), so testing them with `re` is a fair
proxy. If `google-re2` is installed (`pip install google-re2`), the tests run
on RE2 itself.

It also:
  * checks every formula string for balanced parentheses and quotes, and
  * re-runs the 2024 versions of the formulas to show the bugs they had.

Run:  python test_formulas.py
"""
import re as _re
try:
    import re2 as re  # the same engine Google Sheets uses
    ENGINE = "RE2 (google-re2)"
except ImportError:
    re = _re
    ENGINE = "Python re (RE2-compatible subset)"

import formulas as F

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL {name}: got {got!r}, want {want!r}")


def m(rx, text):
    return re.search(rx, text) is not None


# ---------- 1. syntax sanity: balanced parens / quotes outside string literals
def balanced(formula):
    depth, in_str = 0, False
    for ch in formula:
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            depth += ch == "("
            depth -= ch == ")"
            if depth < 0:
                return False
    return depth == 0 and not in_str


for f in F.FORMULAS:
    check(f"syntax {f['id']}", balanced(f["formula"]), True)

# ---------- 2. keyword intent, whole-word + case-insensitive
INFO, COMM, TRANS = F.wb(F.INFORMATIONAL), F.wb(F.COMMERCIAL), F.wb(F.TRANSACTIONAL)
NAV = F.wb(F.NAV_WORDS) + "|" + F.NAV_DOMAINS
LOCAL = F.wb(F.US_STATES + "|" + F.UK_CITIES)

cases = {
    # keyword: (informational, commercial, transactional)
    "How to make cold brew": (True, False, False),
    "cold brew show near me": (False, False, True),         # 'show' must NOT trigger 'how'
    "whole bean coffee": (False, False, False),             # 'whole' must NOT trigger 'who'
    "laptop stand": (False, False, False),                  # 'laptop' must NOT trigger 'top'
    "best laptop stand": (False, True, False),
    "notion alternatives": (False, True, False),
    "notion alternative": (False, True, False),
    "buy ergonomic chair": (False, False, True),
    "office supplies": (False, True, False),                # suppli\w*
    "always on vpn": (False, False, False),                 # 'always' must NOT trigger 'ways'
    "what is seo": (True, False, False),
}
for kw, (i, c, t) in cases.items():
    check(f"info  '{kw}'", m(INFO, kw), i)
    check(f"comm  '{kw}'", m(COMM, kw), c)
    check(f"trans '{kw}'", m(TRANS, kw), t)

for kw, want in {"plumber Texas": True, "texas instruments calculator": True,
                 "remaining balance": False, "london fog latte": True,
                 "derbyshire": False}.items():
    check(f"local '{kw}'", m(LOCAL, kw), want)

for kw, want in {"facebook login": True, "amazon.co.uk": True, "www bbc": False,
                 "www.bbc.com": True, "website builder": True, "organic search": False}.items():
    check(f"nav '{kw}'", m(NAV, kw), want)


# first-match intent (IFS order: info, trans, comm, local, nav)
def first_intent(kw):
    for label, rx in [("Informational", INFO), ("Transactional", TRANS),
                      ("Commercial", COMM), ("Localised", LOCAL), ("Navigational", NAV)]:
        if m(rx, kw):
            return label
    return "Unclassified"


check("ifs 'best crm software'", first_intent("best crm software"), "Commercial")
check("ifs 'crm pricing'", first_intent("crm pricing"), "Transactional")
check("ifs 'hubspot login'", first_intent("hubspot login"), "Navigational")
check("ifs 'dentist Ohio'", first_intent("dentist Ohio"), "Localised")
check("ifs 'xyz'", first_intent("xyz"), "Unclassified")


# ---------- 3. SERP features -> labels (TEXTJOIN skips empties)
def labels(pairs, text, empty):
    out = [label for label, rx in pairs if m(rx, text)]
    return ", ".join(out) if out else empty


ahrefs = "Sitelinks,Shopping results,Thumbnail,People also ask,Image pack"
semrush = "Site links, People also ask, AI overview"
check("serp intent ahrefs", labels(F.SERP_INTENT, ahrefs, "No SERP feature signal"),
      "Informational Intent, Navigational Intent, Transactional Intent, Engagement/Entertainment Intent")
check("serp intent semrush", labels(F.SERP_INTENT, semrush, "No SERP feature signal"),
      "Informational Intent, Navigational Intent")
check("serp content semrush", labels(F.SERP_CONTENT, semrush, "No features"),
      "AI features, Informational Features, Navigational Features")
check("serp empty", labels(F.SERP_INTENT, "", "No SERP feature signal"), "No SERP feature signal")


# the 2024 version used JOIN, which keeps empty strings
def join_2024(pairs, text):
    return ", ".join(label if m(rx, text) else "" for label, rx in pairs)


old = join_2024(F.SERP_INTENT, "People also ask")
check("2024 JOIN leaves stray commas", old.startswith("Informational Intent, , "), True)


# ---------- 4. URL section, first match wins
def section(url):
    for label, rx in F.URL_SECTIONS:
        if m(rx, url):
            return label
    return "Unclassified"


for url, want in {
    "https://www.bbc.com/news/world-europe-68376700": "News",
    "https://www.bbc.com/blog/world-europe-68255490": "Blog Posts",
    "https://example.com/vintage-cars/": "Unclassified",       # 'tag' inside 'vintage'
    "https://example.com/tag/seo/": "Tag Pages",
    "https://example.com/services/seo-audit/": "Services Pages",
    "https://example.com/blog/page/2/": "Blog Posts",
    "https://example.com/category/page/3": "Paginated",
    "https://example.com/about-us/": "Branded Pages",
}.items():
    check(f"section {url}", section(url), want)

# 2024 version: plain substring 'tag'
check("2024 'tag' substring bug", m("tag", "https://example.com/vintage-cars/"), True)


# ---------- 5. language
def lang(url):
    mm = re.search(F.LANG_REGEX, url.lower())
    code = mm.group(1)[:2] if mm else ""
    return dict(F.LANGS).get(code, "English")


for url, want in {"https://site.com/es/precios/": "Spanish", "https://site.com/fr": "French",
                  "https://site.com/de-at/preise/": "German", "https://site.com/blog/": "English",
                  "https://site.com/": "English", "https://site.com/ES/x": "Spanish"}.items():
    check(f"lang {url}", lang(url), want)


# ---------- 6. rank buckets
def bucket(pos):
    if not isinstance(pos, (int, float)) or pos < 1:
        return "Not ranked"
    for t, label in F.RANK_BUCKETS:
        if pos <= t:
            return label
    return "Not ranked"


def bucket_2024(a):
    rng = [(1, 3), (4, 10), (11, 20), (21, 50), (51, 100)]
    for (lo, hi), (_, label) in zip(rng, F.RANK_BUCKETS):
        if isinstance(a, (int, float)) and lo <= a <= hi:
            return label
    return "Not ranked"


for pos, want in {1: F.RANK_BUCKETS[0][1], 3: F.RANK_BUCKETS[0][1], 3.4: F.RANK_BUCKETS[1][1],
                  10.6: F.RANK_BUCKETS[2][1], 20: F.RANK_BUCKETS[2][1], 99.5: F.RANK_BUCKETS[4][1],
                  101: "Not ranked", 0: "Not ranked", "": "Not ranked"}.items():
    check(f"bucket {pos!r}", bucket(pos), want)
check("2024 bucket gap bug (3.4 -> Not ranked)", bucket_2024(3.4), "Not ranked")


# ---------- 7. brand from URL
def brand(url):
    host = re.search(F.HOST_REGEX, url.lower()).group(1)
    mm = re.search(F.BRAND_REGEX, host)
    return mm.group(1) if mm else host


def brand_2024(url):
    s = re.sub("https?://", "", url)
    s = re.sub(r"^www\.", "", s)
    return re.search(r"([^\.]+)", s).group(1).strip()


for url, want in {"https://www.bbc.com/news/x": "bbc", "https://www.bbc.co.uk/news": "bbc",
                  "https://blog.hubspot.com/marketing": "hubspot", "https://news.bbc.co.uk/": "bbc",
                  "https://maps.google.com/": "google", "https://www.amazon.com.au/x": "amazon",
                  "mlforseo.com/resources-library/": "mlforseo", "https://shop.example.io/": "example"}.items():
    check(f"brand {url}", brand(url), want)
check("2024 subdomain bug (blog.hubspot.com -> 'blog')", brand_2024("https://blog.hubspot.com/x"), "blog")

print(f"\nEngine: {ENGINE}\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
