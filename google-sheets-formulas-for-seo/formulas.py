"""Single source of truth for the Google Sheets formulas in this folder.

`python build.py` writes formulas.csv and FORMULAS.md from this file, and
`python test_formulas.py` checks the regex logic of every formula against
sample keywords, SERP feature strings, URLs and positions.

Cell conventions (same as the MLforSEO post):
  C2 = keyword, J2 = SERP features (from a Semrush or Ahrefs export),
  A2 = URL (or the ranking position, for the rank-bucket formula).
"""

# --- keyword lists (Lazarina's original lists; `*` typos fixed, see README) ---

INFORMATIONAL = (
    "how|why|does|which|when|who|guide|tutorial|learn|examples|resource|ideas|tips|"
    "difference between|strategies|ways|example|directory|news|basics|concepts|troubleshoot|"
    "resolve|risks|beginners|upgrade|improve|optimize|case study|best practices|templates|"
    "pros and cons|analysis|articles|audit|benefits|blogs|build|calculate|campaign|choose|"
    "common questions|consider|cost|create|definition|definitive guide|earn|easy steps|"
    "essential|events|explainer video|factors|find|fix|grow|hacks|how to|ideal|importance of|"
    "increase|infographic|information|meaning|measure|metrics|mistakes|myths|opportunities|"
    "popular|practices|questions|remove|set up|shortcuts|stats|strategy|study|successful|"
    "tactics|techniques|terms|things to know|time|trends|tricks|types|updates|well explained|"
    "tutorials|framework|checklist|process|plan|test|glossary|sample|survey|exercises|report|"
    "certification|webinar|calendar|quiz|directories|to do list|design basics|what|where"
)

COMMERCIAL = (
    "best|top|vs|versus|review|reviews|compare|comparison|ratings|recommendation|buyer's guide|"
    "alternatives?|features?|benefits?|cost-effective|affordable|premium|quality|deal|offers|"
    "savings|discount|value|choice|selection|rankings|user ratings|testimonials|feedback|pros|"
    "cons|evaluation|assessment|analysis|benchmark|brand|models|versions|upgrade|update|launch|"
    "new|latest|innovative|technology|solutions|providers|vendors|suppliers|applications|"
    "software|platform|systems|tools|equipment|machinery|accessories|devices|gadgets|"
    "electronics|appliances|products|materials|suppli\\w*|kit|package|bundle"
)

TRANSACTIONAL = (
    "buy|purchase|order|price|quote|for sale|sale|deal|offers|discount|coupon|promo code|voucher|"
    "bargain|cost|pricing|cheap|affordable|expensive|premium|near me|online|e-commerce|"
    "shopping cart|checkout|shop|store|retailer|dealer|supplier|marketplace|auction|bid|buy now|"
    "pay|payment|finance|leasing|rent|rental|subscribe|subscription|free trial|book|reserve|"
    "enquire|inquiry|estimate|cost calculator|shipping|delivery|available|in stock|out of stock|"
    "pre-order|backorder|special offer|limited time offer|flash sale|clearance|wholesale|"
    "bulk buy|group buy|membership|reward|loyalty|gift card|cashback|trade-in|renew|"
    "secure checkout"
)

US_STATES = (
    "Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|"
    "Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|"
    "Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|"
    "New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|"
    "Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|"
    "West Virginia|Wisconsin|Wyoming"
)

UK_CITIES = (
    "London|Edinburgh|Manchester|Birmingham|Glasgow|Liverpool|Bristol|Newcastle|Leeds|Belfast|"
    "Cardiff|Sheffield|Nottingham|Leicester|Southampton|Brighton|Plymouth|Stoke-on-Trent|"
    "Wolverhampton|Derby"
)

NAV_WORDS = "login|log in|sign in|homepage|website|facebook|youtube|gmail|instagram|twitter|wikipedia"
NAV_DOMAINS = "www\\.|\\.(com|org|net|edu|gov|co\\.uk|uk)\\b"


def wb(words):
    """Case-insensitive, whole-word regex for REGEXMATCH (RE2 supports (?i) and \\b)."""
    return "(?i)\\b(" + words + ")\\b"


# SERP feature groups (Semrush writes "Site links", Ahrefs writes "Sitelinks")
SERP_INTENT = [
    ("Informational Intent", "(?i)Featured snippet|People also ask|Instant answer|Knowledge panel|Carousel|Thumbnail|Video preview|AI overview"),
    ("Navigational Intent", "(?i)Site ?links|Knowledge Graph"),
    ("Transactional Intent", "(?i)Local pack|Shopping ads|Local teaser pack|Shopping results|Popular products"),
    ("Commercial Intent", "(?i)Top ads|Bottom ads|AdWords top|AdWords bottom"),
    ("Engagement/Entertainment Intent", "(?i)Reviews|Video|Top stories|Images|Twitter|Featured video|Image pack|Discussions and forums"),
]

SERP_CONTENT = [
    ("Videos", "(?i)Video|Featured video"),
    ("Images", "(?i)Images|Image pack|Thumbnail"),
    ("Ads", "(?i)Top ads|Bottom ads|AdWords top|AdWords bottom|Shopping ads"),
    ("AI features", "(?i)AI overview|AI Mode|AI summary"),
    ("Informational Features", "(?i)Featured snippet|People also ask|Instant answer|Knowledge panel|Carousel|Video preview"),
    ("Navigational Features", "(?i)Site ?links|Knowledge Graph"),
    ("Local Features", "(?i)Local pack|Local teaser pack|Shopping results"),
    ("Social/News Features", "(?i)Reviews|Top stories|Twitter|Discussions and forums"),
]

URL_SECTIONS = [
    ("Blog Posts", "/blog/"),
    ("White papers", "/white-papers/"),
    ("News", "/news/"),
    ("Case studies", "/case-studies/"),
    ("Insights", "/insights/"),
    ("Branded Pages", "/(careers|about-us|contact|job-opportunities|clients|reviews|our-work|our-team|join-team)(/|$)"),
    ("Services Pages", "/(services?|expertise|hospitality-travel-tourism|economic-development|energy|higher-education|technology|financial-services)(/|$)"),
    ("Tag Pages", "/tag/"),
    ("Paginated", "/page/[0-9]+"),
]

LANG_REGEX = "^https?://[^/]+/([a-z]{2}(?:-[a-z]{2})?)(?:/|$)"
LANGS = [("es", "Spanish"), ("fr", "French"), ("de", "German"), ("it", "Italian")]

HOST_REGEX = "^(?:https?://)?(?:www\\.)?([^/:?#]+)"
BRAND_REGEX = "([^.]+)\\.(?:(?:co|com|org|net|gov|ac|edu)\\.[a-z]{2}|[a-z]{2,})$"

RANK_BUCKETS = [
    (3, "Money Keywords - Protect (1-3)"),
    (10, "High-Potential Keywords - Move to top (4-10)"),
    (20, "Striking Distance Keywords - Prioritise improvements (11-20)"),
    (50, "Need Improvements (21-50)"),
    (100, "Low Ranked - Heavy content edits needed (51-100)"),
]


def _if_list(pairs, ref):
    return ",\n  ".join(f'IF(REGEXMATCH({ref}, "{rx}"), "{label}", )' for label, rx in pairs)


def _textjoin_labels(pairs, ref, empty_label):
    return (
        f"=LET(labels, TEXTJOIN(\", \", TRUE,\n  {_if_list(pairs, ref)}),\n"
        f"  IF(labels=\"\", \"{empty_label}\", labels))"
    )


FORMULAS = [
    {
        "id": "informational",
        "title": "Label keywords for informational search intent",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(INFORMATIONAL)}"), "Informational Intent", "Other")',
    },
    {
        "id": "commercial",
        "title": "Label keywords for commercial search intent",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(COMMERCIAL)}"), "Commercial Intent", "Other")',
    },
    {
        "id": "transactional",
        "title": "Label keywords for transactional search intent",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(TRANSACTIONAL)}"), "Transactional Intent", "Other")',
    },
    {
        "id": "local_us",
        "title": "Label keywords for localised intent (US states)",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(US_STATES)}"), "Localised Intent - US", "Other")',
    },
    {
        "id": "local_uk",
        "title": "Label keywords for localised intent (UK cities)",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(UK_CITIES)}"), "Localised Intent - UK", "Other")',
    },
    {
        "id": "local_uk_range",
        "title": "Localised intent from a full list of cities kept in another tab",
        "input": "C2 = keyword; Cities!A2:A = one city per row",
        "formula": '=IF(REGEXMATCH(C2, "(?i)\\b(" & TEXTJOIN("|", TRUE, Cities!A2:A) & ")\\b"), "Localised Intent - UK", "Other")',
    },
    {
        "id": "navigational",
        "title": "Label keywords for navigational intent",
        "input": "C2 = keyword",
        "formula": f'=IF(REGEXMATCH(C2, "{wb(NAV_WORDS)}|{NAV_DOMAINS}"), "Navigational Intent", "Other")',
    },
    {
        "id": "intent_first_match",
        "title": "One intent label per keyword (first match wins)",
        "input": "C2 = keyword",
        "formula": (
            "=IFNA(IFS(\n"
            f'  REGEXMATCH(C2, "{wb(INFORMATIONAL)}"), "Informational",\n'
            f'  REGEXMATCH(C2, "{wb(TRANSACTIONAL)}"), "Transactional",\n'
            f'  REGEXMATCH(C2, "{wb(COMMERCIAL)}"), "Commercial",\n'
            f'  REGEXMATCH(C2, "{wb(US_STATES + "|" + UK_CITIES)}"), "Localised",\n'
            f'  REGEXMATCH(C2, "{wb(NAV_WORDS)}|{NAV_DOMAINS}"), "Navigational"\n'
            '), "Unclassified")'
        ),
    },
    {
        "id": "intent_rules_table",
        "title": "Every matching intent label, from a rules tab (whole column, BYROW + LAMBDA)",
        "input": "C2:C = keywords; Rules!A2:A = label, Rules!B2:B = pipe-separated words",
        "formula": (
            "=BYROW(C2:C, LAMBDA(kw, IF(kw=\"\", ,\n"
            "  IFERROR(TEXTJOIN(\", \", TRUE,\n"
            "    FILTER(Rules!A2:A, Rules!B2:B<>\"\", REGEXMATCH(kw, \"(?i)\\b(\" & Rules!B2:B & \")\\b\"))),\n"
            "  \"Unclassified\"))))"
        ),
    },
    {
        "id": "serp_intent",
        "title": "SERP features as search intent signals (all matching labels)",
        "input": "J2 = SERP features",
        "formula": _textjoin_labels(SERP_INTENT, "J2", "No SERP feature signal"),
    },
    {
        "id": "branded",
        "title": "Split keywords into own brand, competitor brand and non-branded",
        "input": "C2 = keyword",
        "formula": (
            "=IFS(\n"
            '  REGEXMATCH(C2, "(?i){brand name}|{brand variations and misspellings}"), "Branded - own",\n'
            '  REGEXMATCH(C2, "(?i){competitor brand names and variations}"), "Branded - competitor",\n'
            '  TRUE, "Non-branded")'
        ),
    },
    {
        "id": "serp_content",
        "title": "Content types Google is featuring, from SERP features",
        "input": "J2 = SERP features",
        "formula": _textjoin_labels(SERP_CONTENT, "J2", "No features"),
    },
    {
        "id": "url_section",
        "title": "Classify pages per site section from the URL",
        "input": "A2 = URL",
        "formula": (
            "=IFS(\n  "
            + ",\n  ".join(f'REGEXMATCH(A2, "{rx}"), "{label}"' for label, rx in URL_SECTIONS)
            + ',\n  TRUE, "Unclassified")'
        ),
    },
    {
        "id": "url_section_table",
        "title": "Site sections from a rules tab (first match wins, XLOOKUP)",
        "input": "A2 = URL; Sections!A2:A20 = label, Sections!B2:B20 = regex",
        "formula": '=XLOOKUP(TRUE, ARRAYFORMULA(REGEXMATCH(A2, Sections!B2:B20)), Sections!A2:A20, "Unclassified")',
    },
    {
        "id": "url_language",
        "title": "Label URLs by language subfolder",
        "input": "A2 = URL",
        "formula": (
            f'=LET(code, IFERROR(REGEXEXTRACT(LOWER(A2), "{LANG_REGEX}"), ""),\n'
            "  SWITCH(LEFT(code, 2), "
            + ", ".join(f'"{c}", "{n}"' for c, n in LANGS)
            + ', "English"))'
        ),
    },
    {
        "id": "rank_buckets",
        "title": "Classify rankings into opportunity buckets (handles decimal positions)",
        "input": "A2 = position (rank tracker or Search Console average position)",
        "formula": (
            "=IFS(\n"
            '  NOT(ISNUMBER(A2)), "Not ranked",\n'
            '  A2 < 1, "Not ranked",\n'
            + "".join(f'  A2 <= {t}, "{label}",\n' for t, label in RANK_BUCKETS)
            + '  TRUE, "Not ranked")'
        ),
    },
    {
        "id": "brand_from_url",
        "title": "Extract the brand (registrable domain name) from a URL",
        "input": "A2 = URL",
        "formula": (
            f'=LET(host, REGEXEXTRACT(LOWER(A2), "{HOST_REGEX}"),\n'
            f'  IFERROR(REGEXEXTRACT(host, "{BRAND_REGEX}"), host))'
        ),
    },
    {
        "id": "brand_from_url_2024",
        "title": "Brand from URL, the 2024 version (kept for comparison)",
        "input": "A2 = URL",
        "formula": '=TRIM(REGEXEXTRACT(REGEXREPLACE(REGEXREPLACE(A2, "https?://", ""), "^www\\.", ""), "([^\\.]+)"))',
    },
    {
        "id": "whole_column",
        "title": "Any single-cell formula above, for the whole column (MAP + LAMBDA)",
        "input": "C2:C = keywords",
        "formula": (
            '=MAP(C2:C, LAMBDA(kw, IF(kw="", , IF(REGEXMATCH(kw, "(?i)\\b(how|why|guide|tutorial)\\b"), "Informational Intent", "Other"))))'
        ),
    },
]
