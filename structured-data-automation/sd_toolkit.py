#!/usr/bin/env python3
"""
Structured data automation toolkit (MLforSEO, October 2026).

Three jobs, one file:

  1. AUDIT     crawl a list of URLs, extract the structured data already on each page
               (JSON-LD, Microdata, RDFa), and flag structured data OPPORTUNITIES with a
               rule-based page classifier.
  2. GENERATE  build JSON-LD from a data source (a CSV, or a SQL database) instead of
               typing it into a generator page by page. Output is one connected @graph per
               page (Organization, WebSite, WebPage, BreadcrumbList, Article/Product/Event...).
  3. VALIDATE  check JSON-LD against (a) the live schema.org vocabulary (unknown types,
               unknown or misplaced properties), (b) Google's required and recommended
               properties for the rich results that still exist in 2026, and (c) the page's
               visible text, because markup that doesn't match the page is a policy problem.

Usage
  python sd_toolkit.py audit    --urls urls.txt --out audit.csv
  python sd_toolkit.py generate --csv example_data/articles.csv --site example_data/site.json --out-dir jsonld/
  python sd_toolkit.py generate --sqlite example_data/demo.db --query "SELECT * FROM products" --site example_data/site.json --out-dir jsonld/
  python sd_toolkit.py validate --file jsonld/some-page.json
  python sd_toolkit.py validate --url https://www.example.com/page/

Requirements: Python 3.9+, requests, beautifulsoup4, lxml, extruct, pandas.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; MLforSEO-StructuredData/1.0; +https://www.mlforseo.com/)"
VOCAB_URL = "https://schema.org/version/latest/schemaorg-current-https.jsonld"
VOCAB_CACHE = Path(__file__).with_name(".schemaorg-current-https.jsonld")

# --------------------------------------------------------------------------------------
# Google rich result status, checked against Google Search Central on 22 Oct 2026.
# "supported" = there is still a Google Search feature that uses this markup.
# Markup that Google no longer uses is still valid schema.org, and other systems
# (Bing, AI assistants, knowledge graphs) can still read it. It just won't earn a
# rich result in Google.
# --------------------------------------------------------------------------------------
GOOGLE_STATUS = {
    "Article":          ("supported", "Article / BlogPosting / NewsArticle: better title, image and date display"),
    "BreadcrumbList":   ("supported", "Breadcrumb trail in results"),
    "Product":          ("supported", "Product snippets and merchant listings"),
    "Event":            ("supported", "Event experience"),
    "JobPosting":       ("supported", "Job search experience"),
    "VideoObject":      ("supported", "Video results, key moments"),
    "Recipe":           ("supported", "Recipe rich results and carousels"),
    "Course":           ("supported", "Course list (carousel). Course info was retired in 2025"),
    "Organization":     ("supported", "Logo and knowledge panel details"),
    "LocalBusiness":    ("supported", "Business details"),
    "ProfilePage":      ("supported", "Profile pages (forums, author pages)"),
    "DiscussionForumPosting": ("supported", "Discussions and forums"),
    "QAPage":           ("supported", "Q&A, for pages where users answer one question"),
    "Review":           ("supported", "Review snippets (on supported item types only)"),
    "SoftwareApplication": ("supported", "Software app"),
    "Dataset":          ("other", "Used by Dataset Search only, not Google Search (clarified Nov 2025)"),
    "FAQPage":          ("retired", "FAQ rich results stopped showing on 7 May 2026 (limited to gov/health sites since Aug 2023)"),
    "HowTo":            ("retired", "How-to rich results removed in 2023"),
    "VehicleListing":   ("retired", "Retired in 2025 (Search Console support removed Sept 2025)"),
    "EstimatedSalary":  ("retired", "Retired in 2025"),
    "LearningVideo":    ("retired", "Retired in 2025"),
    "SpecialAnnouncement": ("retired", "Retired 31 July 2025"),
    "ClaimReview":      ("retired", "Being phased out of Google Search since 2025; still used by Fact Check Explorer"),
    "Quiz":             ("retired", "Practice problems: documentation removed Jan 2026"),
    "WebSite":          ("supported", "Site names (the sitelinks search box was removed in Nov 2024)"),
}

# Google's required (R) and recommended (r) properties for the features above.
# "a|b" = either. Only the top-level node is checked; nested checks are noted inline.
GOOGLE_PROPS = {
    "Article":        {"R": [], "r": ["headline", "image", "datePublished", "dateModified", "author"]},
    "BreadcrumbList": {"R": ["itemListElement"], "r": []},
    "Product":        {"R": ["name", "offers|review|aggregateRating"], "r": ["image", "description", "brand", "sku"]},
    "Offer":          {"R": ["price|priceSpecification"], "r": ["priceCurrency", "availability", "url"]},
    "Event":          {"R": ["name", "startDate", "location"], "r": ["description", "endDate", "eventStatus", "image", "offers", "organizer", "performer"]},
    "JobPosting":     {"R": ["title", "description", "datePosted", "hiringOrganization", "jobLocation|applicantLocationRequirements"], "r": ["validThrough", "employmentType", "baseSalary", "identifier"]},
    "VideoObject":    {"R": ["name", "thumbnailUrl", "uploadDate"], "r": ["description", "duration", "contentUrl", "embedUrl"]},
    "Recipe":         {"R": ["name", "image"], "r": ["author", "datePublished", "description", "recipeIngredient", "recipeInstructions", "totalTime"]},
    "Course":         {"R": ["name", "description"], "r": ["provider"]},
    "Organization":   {"R": [], "r": ["name", "url", "logo", "sameAs", "address", "contactPoint"]},
    "LocalBusiness":  {"R": ["name", "address"], "r": ["telephone", "openingHoursSpecification", "geo", "url"]},
    "ProfilePage":    {"R": ["mainEntity"], "r": ["dateCreated", "dateModified"]},
}
ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle", "Report", "ScholarlyArticle"}
ORG_TYPES = {"Organization", "Corporation", "EducationalOrganization", "NGO", "OnlineBusiness", "OnlineStore"}


# ======================================================================================
# helpers
# ======================================================================================
def fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.text


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def types_of(node: dict) -> list[str]:
    out = []
    for t in as_list(node.get("@type")):
        t = str(t)
        for prefix in ("https://schema.org/", "http://schema.org/", "schema:"):
            if t.startswith(prefix):
                t = t[len(prefix):]
        out.append(t)
    return out


def iter_nodes(data) -> Iterable[dict]:
    """Yield every typed node in a JSON-LD blob (handles @graph, lists and nesting)."""
    if isinstance(data, list):
        for item in data:
            yield from iter_nodes(item)
    elif isinstance(data, dict):
        if "@type" in data:
            yield data
        for k, v in data.items():
            if k != "@context" and isinstance(v, (dict, list)):
                yield from iter_nodes(v)


def top_level_nodes(data) -> list[dict]:
    """The nodes a reader would call 'the markup on this page' (top level or @graph members)."""
    out = []
    for item in as_list(data):
        if isinstance(item, dict) and "@graph" in item:
            out += [n for n in as_list(item["@graph"]) if isinstance(n, dict)]
        elif isinstance(item, dict):
            out.append(item)
    return out


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


# ======================================================================================
# 1. AUDIT: extract what's there + detect opportunities
# ======================================================================================
def extract_existing(html: str, url: str) -> dict:
    """Return {'json-ld': [...], 'microdata': [...], 'rdfa': [...]} using extruct."""
    import extruct
    return extruct.extract(html, base_url=url, syntaxes=["json-ld", "microdata", "rdfa"],
                           uniform=True, errors="ignore")


def existing_types(extracted: dict) -> list[str]:
    found = []
    for syntax in ("json-ld", "microdata", "rdfa"):
        for node in iter_nodes(extracted.get(syntax, [])):
            found += types_of(node)
    return sorted(set(t for t in found if t and not t.startswith("http")))


QUESTION_RE = re.compile(r"\?\s*$")
PRICE_RE = re.compile(r"(?:[$€£¥]\s?\d[\d.,]*|\d[\d.,]*\s?(?:EUR|USD|GBP|лв))", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4}|"
                     r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},?\s\d{4}|\d{4}-\d{2}-\d{2})\b")


def detect_opportunities(html: str, url: str) -> list[dict]:
    """Rule-based page classifier. Each rule looks for signals in the URL, the HTML
    structure and the text, and suggests a schema.org type. Deliberately simple and
    explainable: every suggestion says which signal fired."""
    soup = BeautifulSoup(html, "lxml")
    text = visible_text(html).lower()
    path = urlparse(url).path.lower()
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h2", "h3", "h4"])]
    og_type = (soup.find("meta", property="og:type") or {}).get("content", "").lower()
    out: list[dict] = []

    def add(t: str, signal: str):
        status, note = GOOGLE_STATUS.get(t, ("n/a", ""))
        out.append({"type": t, "signal": signal, "google": status, "note": note})

    # Article / BlogPosting
    depth = len([p for p in path.split("/") if p])
    if og_type == "article" or (depth >= 1 and og_type != "website" and
                                (soup.find("article") or soup.find("time", attrs={"datetime": True}))):
        add("Article", f"og:type={og_type or '-'}, <article>/<time> present")

    # Breadcrumbs: nested URL path, or a breadcrumb nav already on the page
    if depth >= 2 or soup.select_one('[class*="breadcrumb"], nav[aria-label*="readcrumb"]'):
        add("BreadcrumbList", f"URL depth {depth} / breadcrumb element")

    # FAQ-style content: question headings, or an FAQ section
    q_heads = [h for h in headings if QUESTION_RE.search(h)]
    faq_section = any(re.search(r"\b(faq|frequently asked)", h, re.I) for h in headings) or soup.find("details")
    if len(q_heads) >= 3 or faq_section:
        add("FAQPage", f"{len(q_heads)} question headings" + (", FAQ section" if faq_section else ""))

    # How-to content: step headings or a "how to" title with an ordered list
    title = (soup.title.get_text() if soup.title else "").lower()
    step_heads = [h for h in headings if re.match(r"^\(?(step\s*)?\d+[).:]", h.strip(), re.I)]
    if len(step_heads) >= 3 or ("how to" in title and soup.find("ol")):
        add("HowTo", f"{len(step_heads)} numbered step headings / 'how to' title")

    # Product: a price plus a buy signal
    if PRICE_RE.search(text) and re.search(r"add to (cart|basket)|buy now|in stock|out of stock|checkout", text):
        add("Product", "price + buy/stock wording")

    # Course: course wording plus lessons/modules or enrol
    if re.search(r"\bcourse\b", text) and re.search(r"\b(enrol|enroll|lessons?|modules?|curriculum)\b", text) \
            and re.search(r"/(course|courses|product|training)/", path):
        add("Course", "course wording + /course/ URL")

    # Event: a date plus event wording
    if DATE_RE.search(text) and re.search(r"\b(tickets?|register now|venue|doors open|agenda|livestream)\b", text):
        add("Event", "date + ticket/venue/register wording")

    # Job posting
    if re.search(r"\b(apply now|job description|responsibilities|requirements)\b", text) and \
            re.search(r"/(jobs?|careers?|vacanc)", path):
        add("JobPosting", "job wording + /jobs/ URL")

    # Video
    if soup.find("video") or soup.find("iframe", src=re.compile(r"youtube\.com|youtube-nocookie\.com|vimeo\.com|wistia")):
        add("VideoObject", "<video> or YouTube/Vimeo embed")

    # Recipe
    if "ingredients" in text and re.search(r"\b(method|instructions|directions)\b", text):
        add("Recipe", "ingredients + method wording")

    # Organization / LocalBusiness on home, about and contact pages
    if depth == 0 or re.search(r"/(about|contact)", path):
        has_address = bool(re.search(r"\b(street|st\.|road|rd\.|avenue|ulitsa|ul\.)\b", text)) and \
            bool(re.search(r"\+?\d[\d\s()-]{7,}", text))
        add("LocalBusiness" if has_address else "Organization",
            "home/about/contact page" + (" with address + phone" if has_address else ""))

    # Author / profile pages
    if re.search(r"/(author|people|team|profile)/", path):
        add("ProfilePage", "author/profile URL")

    # Reviews and ratings
    if re.search(r"\b\d(\.\d)?\s?(out of|/)\s?5\b|\bstars?\b.*\breview", text):
        add("Review", "rating wording ('4.5 out of 5')")

    return out


def audit_url(url: str) -> dict:
    """One row per URL: what's there, what's missing, what's broken."""
    row = {"url": url, "existing_types": "", "opportunities": "", "missing_supported": "",
           "missing_retired": "", "validation_errors": 0, "validation_warnings": 0, "error": ""}
    try:
        html = fetch(url)
    except Exception as exc:
        row["error"] = str(exc)[:200]
        return row
    extracted = extract_existing(html, url)
    have = existing_types(extracted)
    opps = detect_opportunities(html, url)
    row["existing_types"] = ", ".join(have)
    row["opportunities"] = "; ".join(f"{o['type']} ({o['signal']})" for o in opps)

    def covered(t: str) -> bool:
        if t == "Article":
            return bool(ARTICLE_TYPES & set(have))
        if t == "Organization":
            return bool((ORG_TYPES | {"LocalBusiness"}) & set(have))
        return t in have

    missing = [o for o in opps if not covered(o["type"])]
    row["missing_supported"] = ", ".join(o["type"] for o in missing if o["google"] == "supported")
    row["missing_retired"] = ", ".join(o["type"] for o in missing if o["google"] == "retired")
    issues = validate_jsonld(extracted.get("json-ld", []), page_text=visible_text(html))
    row["validation_errors"] = sum(1 for i in issues if i["level"] == "error")
    row["validation_warnings"] = sum(1 for i in issues if i["level"] == "warning")
    row["issues"] = " | ".join(f"[{i['level']}] {i['where']}: {i['msg']}" for i in issues[:12])
    return row


# ======================================================================================
# 2. GENERATE: JSON-LD from data
# ======================================================================================
def _clean(d: dict) -> dict:
    """Drop empty values so the markup only states what we actually know."""
    out = {}
    for k, v in d.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, float) and v != v:      # NaN from pandas
            continue
        out[k] = v
    return out


def breadcrumb_from_url(url: str, names: Optional[dict] = None, home_name: str = "Home",
                        current_name: Optional[str] = None) -> dict:
    """Build a BreadcrumbList from the URL path. `names` maps path segments to labels;
    `current_name` (usually the page title) labels the last crumb."""
    names = names or {}
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}/"
    parts = [s for s in p.path.split("/") if s]
    items = [{"@type": "ListItem", "position": 1, "name": home_name, "item": base}]
    acc = base
    for i, seg in enumerate(parts, start=2):
        acc = urljoin(acc, seg + "/")
        label = names.get(seg) or seg.replace("-", " ").replace("_", " ").capitalize()
        if i == len(parts) + 1 and current_name:
            label = current_name
        item = {"@type": "ListItem", "position": i, "name": label}
        if i < len(parts) + 1:                   # the current page doesn't need "item"
            item["item"] = acc
        items.append(item)
    return {"@type": "BreadcrumbList", "@id": url.rstrip("/") + "/#breadcrumb", "itemListElement": items}


def site_nodes(site: dict) -> list[dict]:
    """Organization + WebSite nodes, shared by every page via @id."""
    org_id = site["url"].rstrip("/") + "/#organization"
    org = _clean({
        "@type": site.get("org_type", "Organization"), "@id": org_id,
        "name": site["name"], "url": site["url"],
        "logo": {"@type": "ImageObject", "url": site["logo"]} if site.get("logo") else None,
        "sameAs": site.get("sameAs"),
    })
    web = _clean({"@type": "WebSite", "@id": site["url"].rstrip("/") + "/#website",
                  "name": site["name"], "url": site["url"], "publisher": {"@id": org_id},
                  "inLanguage": site.get("language")})
    return [org, web]


def page_graph(record: dict, site: dict) -> dict:
    """Turn one data row into a connected JSON-LD @graph.

    `record["type"]` picks the main entity: Article/BlogPosting, Product, Event or Course.
    Columns are named after schema.org properties so the mapping stays obvious.
    """
    url = record["url"]
    org_id = site["url"].rstrip("/") + "/#organization"
    page_id = url.rstrip("/") + "/#webpage"
    main_id = url.rstrip("/") + "/#main"
    t = record.get("type", "Article")
    graph = site_nodes(site)
    crumbs = breadcrumb_from_url(url, site.get("breadcrumb_names"),
                                 current_name=record.get("title") or record.get("name"))
    graph.append(crumbs)
    graph.append(_clean({"@type": "WebPage", "@id": page_id, "url": url, "name": record.get("title") or record.get("name"),
                         "isPartOf": {"@id": site["url"].rstrip("/") + "/#website"},
                         "breadcrumb": {"@id": crumbs["@id"]}, "mainEntity": {"@id": main_id}}))

    if t in ARTICLE_TYPES:
        author = None
        if record.get("author_name"):
            author = _clean({"@type": "Person", "@id": record.get("author_url", "").rstrip("/") + "/#person" if record.get("author_url") else None,
                             "name": record["author_name"], "url": record.get("author_url")})
        main = {"@type": t, "headline": record.get("title"), "description": record.get("description"),
                "image": record.get("image"), "datePublished": record.get("datePublished"),
                "dateModified": record.get("dateModified"), "author": author, "publisher": {"@id": org_id}}
    elif t == "Product":
        offer = _clean({"@type": "Offer", "price": record.get("price"), "priceCurrency": record.get("priceCurrency"),
                        "availability": f"https://schema.org/{record['availability']}" if record.get("availability") else None,
                        "url": url})
        main = {"@type": "Product", "name": record.get("name"), "description": record.get("description"),
                "image": record.get("image"), "sku": record.get("sku"),
                "brand": {"@type": "Brand", "name": record["brand"]} if record.get("brand") else None,
                "offers": offer if offer.get("price") not in (None, "") else None}
    elif t == "Event":
        location = None
        if record.get("location_name") or record.get("location_address"):
            location = _clean({"@type": "Place", "name": record.get("location_name"),
                               "address": record.get("location_address")})
        elif record.get("online_url"):
            location = {"@type": "VirtualLocation", "url": record["online_url"]}
        main = {"@type": "Event", "name": record.get("name"), "description": record.get("description"),
                "startDate": record.get("startDate"), "endDate": record.get("endDate"),
                "eventStatus": "https://schema.org/EventScheduled",
                "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode" if record.get("online_url") and not record.get("location_address")
                else "https://schema.org/OfflineEventAttendanceMode",
                "location": location, "image": record.get("image"), "organizer": {"@id": org_id}}
    elif t == "Course":
        main = {"@type": "Course", "name": record.get("name"), "description": record.get("description"),
                "provider": {"@id": org_id}, "url": url}
    else:
        raise ValueError(f"No template for type {t!r}. Add one to page_graph().")

    main = _clean({**main, "@id": main_id, "mainEntityOfPage": {"@id": page_id}})
    graph.append(main)
    return {"@context": "https://schema.org", "@graph": graph}


def to_script_tag(jsonld: dict) -> str:
    """Ready-to-paste <script> tag. '</' is escaped so text can't close the tag early."""
    body = json.dumps(jsonld, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>'


def records_from_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()} for row in csv.DictReader(f)]


def records_from_sqlite(db_path: str, query: str) -> list[dict]:
    """Any SQL database works the same way: connect, query, map columns to properties.
    (For PostgreSQL swap sqlite3 for psycopg; for MySQL, PyMySQL.)"""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(query).fetchall()]
    finally:
        con.close()


def slugify(url: str) -> str:
    s = urlparse(url).path.strip("/").replace("/", "__") or "home"
    return re.sub(r"[^a-zA-Z0-9_-]", "-", s)


# ======================================================================================
# 3. VALIDATE
# ======================================================================================
@lru_cache(maxsize=1)
def load_vocab() -> dict:
    """Download (once) and index the current schema.org vocabulary."""
    if not VOCAB_CACHE.exists():
        r = requests.get(VOCAB_URL, timeout=60, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        VOCAB_CACHE.write_bytes(r.content)
    graph = json.loads(VOCAB_CACHE.read_text(encoding="utf-8"))["@graph"]

    def ids(v):
        return [x["@id"].replace("schema:", "") for x in as_list(v) if isinstance(x, dict) and "@id" in x]

    classes, props, enum_members = {}, {}, set()
    for n in graph:
        nid = n["@id"].replace("schema:", "")
        ntype = as_list(n.get("@type"))
        if "rdfs:Class" in ntype:
            classes[nid] = ids(n.get("rdfs:subClassOf"))
        if "rdf:Property" in ntype:
            props[nid] = {"domain": ids(n.get("schema:domainIncludes")),
                          "superseded": bool(n.get("schema:supersededBy"))}
        if any(isinstance(t, str) and t.startswith("schema:") for t in ntype) and "rdfs:Class" not in ntype:
            enum_members.add(nid)            # e.g. InStock is typed schema:ItemAvailability

    @lru_cache(maxsize=None)
    def ancestors(c: str) -> frozenset:
        seen, stack = set(), [c]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack += classes.get(x, [])
        return frozenset(seen)

    return {"classes": classes, "props": props, "enum": enum_members, "ancestors": ancestors}


def _has(node: dict, spec: str) -> bool:
    return any(node.get(p) not in (None, "", [], {}) for p in spec.split("|"))


def validate_node(node: dict, where: str, vocab: dict, page_text: Optional[str]) -> list[dict]:
    issues = []
    nt = types_of(node)
    # (a) schema.org vocabulary
    for t in nt:
        if t not in vocab["classes"]:
            issues.append({"level": "error", "where": where, "msg": f"@type '{t}' is not a schema.org type"})
    known = [t for t in nt if t in vocab["classes"]]
    allowed_domains = set()
    for t in known:
        allowed_domains |= vocab["ancestors"](t)
    for prop, val in node.items():
        if prop.startswith("@"):
            continue
        if prop.endswith("-input") or prop.endswith("-output"):
            # schema.org Action annotations (e.g. SearchAction "query-input"): valid, not vocabulary terms
            continue
        p = vocab["props"].get(prop)
        if p is None:
            issues.append({"level": "error", "where": where, "msg": f"'{prop}' is not a schema.org property"})
            continue
        if p["superseded"]:
            issues.append({"level": "warning", "where": where, "msg": f"'{prop}' is superseded in schema.org"})
        if known and p["domain"] and not (set(p["domain"]) & allowed_domains):
            issues.append({"level": "warning", "where": where,
                           "msg": f"'{prop}' isn't expected on {'/'.join(known)} (expected on {', '.join(p['domain'][:4])})"})

    # (b) Google features
    if "SearchAction" in nt:
        issues.append({"level": "info", "where": where, "msg": "SearchAction: the sitelinks search box was removed in Nov 2024, so Google ignores it (harmless)"})
    for t in nt:
        key = "Article" if t in ARTICLE_TYPES else ("Organization" if t in ORG_TYPES else t)
        status = GOOGLE_STATUS.get(key)
        if status and status[0] == "retired":
            issues.append({"level": "info", "where": where, "msg": f"{t}: no Google rich result any more ({status[1]}). Fine to keep if it matches the page."})
        spec = GOOGLE_PROPS.get(key)
        if spec:
            for req in spec["R"]:
                if not _has(node, req):
                    issues.append({"level": "error", "where": where, "msg": f"Google requires '{req}' on {t}"})
            for rec in spec["r"]:
                if not _has(node, rec):
                    issues.append({"level": "warning", "where": where, "msg": f"Google recommends '{rec}' on {t}"})
        if t == "BreadcrumbList":
            for i, li in enumerate(as_list(node.get("itemListElement")), 1):
                if isinstance(li, dict):
                    for req in ("position", "name"):
                        if req not in li and not (req == "name" and isinstance(li.get("item"), dict) and li["item"].get("name")):
                            issues.append({"level": "error", "where": f"{where}.itemListElement[{i}]", "msg": f"ListItem needs '{req}'"})

    # (c) does the markup match the page?
    if page_text:
        low = page_text.lower()
        for prop in ("headline", "name"):
            v = node.get(prop)
            if isinstance(v, str) and len(v) > 3 and set(nt) - {"ListItem", "WebSite", "Organization", "Brand", "Person",
                                                                "ImageObject", "WebPage", "Place", "Offer"}:
                if v.lower()[:60] not in low:
                    issues.append({"level": "warning", "where": where, "msg": f"{prop} '{v[:60]}' isn't in the visible text"})
        price = node.get("price")
        if price not in (None, "") and str(price) not in page_text:
            issues.append({"level": "warning", "where": where, "msg": f"price {price} isn't in the visible text"})
    return issues


def validate_jsonld(data, page_text: Optional[str] = None) -> list[dict]:
    """Validate every node in a JSON-LD blob (dict, list, or a list of blobs from extruct)."""
    vocab = load_vocab()
    issues = []
    for i, blob in enumerate(as_list(data)):
        if isinstance(blob, dict) and blob.get("@context") and "schema.org" not in json.dumps(blob.get("@context")):
            issues.append({"level": "warning", "where": f"block{i}", "msg": "@context isn't schema.org"})
        counts = Counter()
        for node in iter_nodes(blob):
            t = "+".join(types_of(node)) or "?"
            counts[t] += 1
            issues += validate_node(node, f"block{i}.{t}#{counts[t]}", vocab, page_text)
    return issues


def validate_text(raw: str) -> list[dict]:
    """Step zero: is it even valid JSON?"""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [{"level": "error", "where": f"line {exc.lineno} col {exc.colno}", "msg": f"Invalid JSON: {exc.msg}"}]
    return validate_jsonld(data)


# ======================================================================================
# CLI
# ======================================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Structured data automation: audit, generate, validate.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="audit existing markup and find opportunities")
    a.add_argument("--urls", required=True, help="text file, one URL per line")
    a.add_argument("--out", default="structured_data_audit.csv")

    g = sub.add_parser("generate", help="generate JSON-LD from a CSV or a SQL query")
    g.add_argument("--csv")
    g.add_argument("--sqlite")
    g.add_argument("--query", default="SELECT * FROM pages")
    g.add_argument("--site", required=True, help="site.json with name, url, logo, sameAs")
    g.add_argument("--out-dir", default="jsonld")

    v = sub.add_parser("validate", help="validate a JSON-LD file or the markup on a live URL")
    v.add_argument("--file")
    v.add_argument("--url")

    args = ap.parse_args(argv)

    if args.cmd == "audit":
        urls = [u.strip() for u in Path(args.urls).read_text().splitlines() if u.strip() and not u.startswith("#")]
        rows = []
        for u in urls:
            print("auditing", u)
            rows.append(audit_url(u))
        fields = ["url", "existing_types", "opportunities", "missing_supported", "missing_retired",
                  "validation_errors", "validation_warnings", "issues", "error"]
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {args.out}")
        return 0

    if args.cmd == "generate":
        site = json.loads(Path(args.site).read_text(encoding="utf-8"))
        if args.csv:
            records = records_from_csv(args.csv)
        elif args.sqlite:
            records = records_from_sqlite(args.sqlite, args.query)
        else:
            ap.error("pass --csv or --sqlite")
        os.makedirs(args.out_dir, exist_ok=True)
        total_errors = 0
        for rec in records:
            jsonld = page_graph(rec, site)
            issues = [i for i in validate_jsonld(jsonld) if i["level"] == "error"]
            total_errors += len(issues)
            name = slugify(rec["url"])
            Path(args.out_dir, f"{name}.json").write_text(json.dumps(jsonld, ensure_ascii=False, indent=2), encoding="utf-8")
            Path(args.out_dir, f"{name}.html").write_text(to_script_tag(jsonld), encoding="utf-8")
            flag = "OK" if not issues else f"{len(issues)} error(s): " + "; ".join(i["msg"] for i in issues)
            print(f"{rec['url']}: {flag}")
        print(f"Generated {len(records)} page graphs in {args.out_dir}/ ({total_errors} errors)")
        return 1 if total_errors else 0

    if args.cmd == "validate":
        if args.file:
            issues = validate_text(Path(args.file).read_text(encoding="utf-8"))
        elif args.url:
            html = fetch(args.url)
            issues = validate_jsonld(extract_existing(html, args.url).get("json-ld", []), page_text=visible_text(html))
        else:
            ap.error("pass --file or --url")
        for i in issues:
            print(f"[{i['level']:7}] {i['where']}: {i['msg']}")
        errors = sum(1 for i in issues if i["level"] == "error")
        print(f"{errors} error(s), {sum(1 for i in issues if i['level'] == 'warning')} warning(s)")
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
