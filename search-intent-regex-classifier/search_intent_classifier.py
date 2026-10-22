"""Rule-based (regex) search intent classifier for keyword research exports.

A 2026 refresh of the logic behind Lazarina Stoy's free Search Intent Keyword
Classifier Data Studio template (2021). It reads a Semrush / Ahrefs / GSC
keyword export, labels every keyword with one or more intents, flags "easy"
and "money" keywords, and prints the matching Data Studio and Google Sheets
formulas so you can reuse the same dictionaries in a dashboard.

Usage:
    python search_intent_classifier.py keywords.csv --brands "amazon,salesforce,hubspot"
    python search_intent_classifier.py --demo
"""
from __future__ import annotations

import argparse
import re
import sys

import pandas as pd

# --- 1. Intent dictionaries --------------------------------------------------
# The 2021 template's lists, cleaned up: duplicates removed ("which" was listed
# twice), "cheap" kept in commercial only (it was in two buckets), and a few
# terms added that the tools now treat as strong signals. Customise per niche:
# transactional intent in SaaS ("demo", "free trial") is not ecommerce ("buy").
INTENT_TERMS: dict[str, list[str]] = {
    "informational": [
        "how", "why", "what", "does", "which", "when", "who", "guide", "tutorial",
        "learn", "examples?", "resources?", "ideas", "tips", "meaning", "definition",
    ],
    "commercial": [
        "best", "top", "vs", "versus", "reviews?", "cheap", "comparison", "compare",
        "alternatives?",
    ],
    "transactional": [
        "buy", "price", "prices", "pricing", "expensive", "recommendations?",
        "recommended", "near me", "firm", "coupons?", "order", "purchase",
        "discount", "deal", "free trial", "demo",
    ],
}
# Navigational has no generic list: it is your brand, products and competitors.
DEFAULT_BRANDS = ["amazon", "salesforce", "hubspot", "azure", "zendesk"]

EASY_KD_MAX = 65      # "Easy Keywords": keyword difficulty below 65
MONEY_CPC_MIN = 0.01  # "Money Keywords": CPC (USD) of 0.01 or more


def build_pattern(terms: list[str]) -> re.Pattern:
    """Whole-word, case-insensitive alternation (the 2021 filters were plain
    'contains', so 'top' also matched 'laptop' and 'how' matched 'showroom')."""
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.IGNORECASE)


def classify(keyword: str, patterns: dict[str, re.Pattern]) -> list[str]:
    hits = [intent for intent, pat in patterns.items() if pat.search(str(keyword))]
    return hits or ["unclassified"]


def find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None


def run(df: pd.DataFrame, brands: list[str]) -> pd.DataFrame:
    patterns = {i: build_pattern(t) for i, t in INTENT_TERMS.items()}
    if brands:
        patterns["navigational"] = build_pattern([re.escape(b) for b in brands])

    kw = find_col(df, "keyword", "query", "top queries", "keywords")
    if kw is None:
        raise SystemExit("No Keyword / Query column found.")
    kd = find_col(df, "keyword difficulty", "kd", "difficulty")
    cpc = find_col(df, "cpc (usd)", "cpc")

    out = df.copy()
    labels = out[kw].map(lambda k: classify(k, patterns))
    out["intents"] = labels.map(", ".join)
    out["primary_intent"] = labels.map(lambda l: l[0])
    out["n_intents"] = labels.map(lambda l: 0 if l == ["unclassified"] else len(l))
    if kd:
        out["easy_keyword"] = pd.to_numeric(out[kd], errors="coerce") < EASY_KD_MAX
    if cpc:
        out["money_keyword"] = pd.to_numeric(out[cpc], errors="coerce") >= MONEY_CPC_MIN
    return out


def data_studio_formula(brands: list[str]) -> str:
    """A single calculated field for Data Studio (Looker Studio) using
    REGEXP_MATCH. Order matters: the first matching WHEN wins."""
    order = ["navigational", "transactional", "commercial", "informational"]
    terms = dict(INTENT_TERMS, navigational=[re.escape(b) for b in brands])
    lines = ["CASE"]
    for intent in order:
        if terms.get(intent):
            alt = "|".join(terms[intent])
            # (^|[^a-z0-9]) ... ([^a-z0-9]|$) acts as a word boundary without
            # backslashes, which avoids escaping differences in Data Studio.
            lines.append(f"  WHEN REGEXP_MATCH(LOWER(Keyword), \"(^|.*[^a-z0-9])({alt})([^a-z0-9].*|$)\") THEN \"{intent.title()}\"")
    lines += ["  ELSE \"Unclassified\"", "END"]
    return "\n".join(lines)


def sheets_formula(brands: list[str], cell: str = "A2") -> str:
    order = ["navigational", "transactional", "commercial", "informational"]
    terms = dict(INTENT_TERMS, navigational=[re.escape(b) for b in brands])
    parts = [f'REGEXMATCH(LOWER({cell}), "\\b({"|".join(terms[i])})\\b"), "{i.title()}"'
             for i in order if terms.get(i)]
    return "=IFS(" + ", ".join(parts) + ', TRUE, "Unclassified")'


DEMO = pd.DataFrame({
    "Keyword": [
        "how do ai chatbots work", "best chatbot for customer service",
        "hubspot chatbot builder", "chatbot pricing", "salesforce chatbot",
        "chatbot vs live chat", "buy chatbot software", "chatbot examples python",
        "chatbot benefits", "laptop chatbot app", "chatbot use cases",
        "zendesk chatbot reviews", "rasa chatbot tutorial", "chatbot near me",
    ],
    "Volume": [90, 480, 90, 1300, 720, 170, 30, 70, 260, 10, 390, 50, 70, 10],
    "Keyword Difficulty": [36, 71, 53, 48, 40, 33, 59, 45, 44, 12, 50, 38, 29, 5],
    "CPC (USD)": [0, 12.4, 6.1, 18.2, 4.3, 7.9, 22.0, 0, 3.5, 0, 5.2, 9.0, 0, 0],
})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("csv", nargs="?", help="Keyword export (CSV)")
    p.add_argument("--brands", default=",".join(DEFAULT_BRANDS),
                   help="Comma-separated brand/product/competitor names for navigational intent")
    p.add_argument("--demo", action="store_true", help="Run on a built-in sample")
    p.add_argument("--out", default="keywords_with_intent.csv")
    a = p.parse_args(argv)
    brands = [b.strip().lower() for b in a.brands.split(",") if b.strip()]
    df = DEMO if a.demo or not a.csv else pd.read_csv(a.csv)
    res = run(df, brands)
    res.to_csv(a.out, index=False)
    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(res.to_string(index=False))
        print("\nIntent split (a keyword can count in more than one):")
        print(res["intents"].str.split(", ").explode().value_counts().to_string())
    print("\nData Studio calculated field:\n" + data_studio_formula(brands))
    print("\nGoogle Sheets formula (keyword in A2):\n" + sheets_formula(brands))
    print(f"\nSaved {a.out}")


if __name__ == "__main__":
    main()
