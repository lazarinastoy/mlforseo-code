"""Fuzzy Booster: score how well each page's title, meta description and h1 match its
top Search Console query, and optionally ask OpenAI for a better title.

Script version of fuzzy_booster.ipynb (MLforSEO tutorial "How to Automatically Optimize your
SEO Metadata with FuzzyWuzzy and OpenAI in Google Colab").

Examples
--------
# Try it on the bundled sample data, no API calls
python fuzzy_booster.py --sample --no-openai

# Your own property (OAuth "Desktop app" client JSON or a service-account key)
export OPENAI_API_KEY=...
python fuzzy_booster.py --site https://www.example.com/ --brand "example|exampel" \
    --credentials credentials.json --lang english
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import unicodedata
from collections import defaultdict
from urllib.parse import parse_qs, urlparse

import pandas as pd
from rapidfuzz import fuzz  # maintained replacement for FuzzyWuzzy: same token_set_ratio scorer

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_CSV = os.path.join(HERE, "sample_gsc_metadata.csv")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FuzzyBooster/2.0; +https://www.mlforseo.com/)"}

PROMPT_TEMPLATE = """Task: Generate a new title that meets the following criteria:
1. The title cannot be longer than 60 characters.
2. The title must include the specified query, represented in the template as '{query}'.
3. The title must be written in the specified language, represented in the template as '{lang}'.
4. No words should be repeated in the title.
5. Use the entities found in the given 'current title' '{title}' to construct the new title.
Please ensure that your title meets all of the criteria. Reply with the title only.
"""


# ---------------------------------------------------------------- Step 1: query parameters
def home_regex(site: str) -> str:
    """Regex that matches the home page of a URL-prefix or sc-domain: property."""
    if site.startswith("sc-domain:"):
        return r"^https?://(www\.)?" + re.escape(site.split(":", 1)[1]) + "/?$"
    return "^" + re.escape(site) + "$"


def build_request(site: str, branded_queries: str, months: int = 16, today: datetime.date | None = None) -> dict:
    from dateutil import relativedelta

    end_date = today or datetime.date.today()
    start_date = end_date - relativedelta.relativedelta(months=months)
    filters = [{"dimension": "page", "operator": "excludingRegex", "expression": home_regex(site)}]
    if branded_queries:
        filters.append({"dimension": "query", "operator": "excludingRegex", "expression": branded_queries})
    return {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "dimensions": ["page", "query"],
        "dimensionFilterGroups": [{"filters": filters}],
        "rowLimit": 25000,
    }


# ---------------------------------------------------------------- Step 2: Search Console
def get_credentials(path: str = "credentials.json", token_path: str = "token.json"):
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow

    with open(path) as f:
        if '"service_account"' in f.read():
            return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = Flow.from_client_secrets_file(path, scopes=SCOPES, redirect_uri="http://localhost")
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        print(f"Please verify your account at the following URL:\n{auth_url}")
        reply = input("Paste the full localhost URL you were sent to (or just the code): ").strip()
        code = parse_qs(urlparse(reply).query).get("code", [reply])[0]
        flow.fetch_token(code=code)
        creds = flow.credentials
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def rows_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Search Console rows -> one row per page with its most clicked query."""
    sc = defaultdict(list)
    for row in rows:
        sc["page"].append(row["keys"][0] or 0)
        sc["query"].append(row["keys"][1] or 0)
        sc["clicks"].append(row["clicks"] or 0)
        sc["ctr"].append(row["ctr"] or 0)
        sc["impressions"].append(row["impressions"] or 0)
        sc["position"].append(row["position"] or 0)
    df = pd.DataFrame(data=sc, columns=["page", "query", "clicks", "ctr", "impressions", "position"])
    if df.empty:
        return df
    df["clicks"] = df["clicks"].astype("int")
    df["ctr"] = df["ctr"] * 100
    df["impressions"] = df["impressions"].astype("int")
    df["position"] = df["position"].round(2)
    return top_query_per_page(df)


def top_query_per_page(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("clicks", ascending=False)
    return df.drop_duplicates(subset=["page"], keep="first")


def fetch_search_console(site: str, request: dict, credentials_path: str) -> pd.DataFrame:
    from googleapiclient.discovery import build

    service = build("searchconsole", "v1", credentials=get_credentials(credentials_path))
    print("Getting Google Search Console data...")
    response = service.searchanalytics().query(siteUrl=site, body=request).execute()
    return rows_to_dataframe(response.get("rows", []))


# ---------------------------------------------------------------- Step 3: scrape metadata
def parse_meta(html) -> tuple[str, str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title").get_text(strip=True) if soup.find("title") else "No title"
    description = soup.select_one('meta[name="description"]')
    meta = description.get("content", "").strip() if description else "No meta description"
    h1 = soup.find("h1").get_text(strip=True) if soup.find("h1") else "No h1"
    return title, meta, h1


def get_meta(url: str) -> tuple[str, str, str]:
    import chardet
    import requests

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        encoding = chardet.detect(response.content)["encoding"]
        page_content = response.content.decode(encoding, errors="replace") if encoding else response.content
        return parse_meta(page_content)
    except Exception as e:  # keep going on timeouts, blocks, bad HTML
        print(f"Could not fetch {url}: {e}")
        return "Error", "Error", "Error"


def add_metadata(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["title"], df["meta"], df["h1"] = zip(*df["page"].apply(get_meta))
    return df


# ---------------------------------------------------------------- Step 4: clean text
def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", errors="ignore").decode("utf-8")


def load_stopwords(lang: str) -> set[str]:
    import nltk

    nltk.download("stopwords", quiet=True)
    from nltk.corpus import stopwords

    words = set(stopwords.words(lang))
    return words | {strip_accents(w) for w in words}


def clean_text(text, stop_words: set[str]) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = strip_accents(text)
    return " ".join(word for word in text.split() if word not in stop_words)


# ---------------------------------------------------------------- Step 5: fuzzy similarity
def add_similarity(df: pd.DataFrame, stop_words: set[str]) -> pd.DataFrame:
    df = df.copy()
    for column in ["title", "meta", "h1", "query"]:
        df[column + "_clean"] = df[column].apply(lambda t: clean_text(t, stop_words))
    for col in ["title", "meta", "h1"]:
        df[f"{col}_similarity"] = [
            round(fuzz.token_set_ratio(q, v)) for q, v in zip(df["query_clean"], df[f"{col}_clean"])
        ]
    return df.drop(columns=[c for c in df.columns if c.endswith("_clean")])


# ---------------------------------------------------------------- Step 6: OpenAI titles
def get_openai_client():
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        try:  # Colab secret named OPENAI_API_KEY
            from google.colab import userdata

            os.environ["OPENAI_API_KEY"] = userdata.get("OPENAI_API_KEY")
        except ImportError:
            sys.exit("Set the OPENAI_API_KEY environment variable (or run with --no-openai).")
    return OpenAI()


def strip_quotes(title) -> str:
    title = str(title)
    if len(title) > 1 and title[0] in "\"'" and title[-1] == title[0]:
        return title[1:-1]
    return title


def generate_titles(df: pd.DataFrame, client, lang: str, threshold: int = 60,
                    model: str = "gpt-4o-mini", temperature: float = 0.0) -> pd.DataFrame:
    df = df.copy()
    df["new_title"] = ""
    for index, row in df[df["title_similarity"] <= threshold].iterrows():
        prompt = PROMPT_TEMPLATE.format(query=row["query"], lang=lang, title=row["title"])
        completion = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        df.at[index, "new_title"] = strip_quotes(completion.choices[0].message.content.strip())
    return df


# ---------------------------------------------------------------- CLI
def main(argv=None) -> pd.DataFrame:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sample", action="store_true", help="use sample_gsc_metadata.csv (skips Search Console and scraping)")
    p.add_argument("--site", help="https://www.example.com/ or sc-domain:example.com")
    p.add_argument("--brand", default="", help="regex of branded queries to exclude, e.g. 'acme|acme corp'")
    p.add_argument("--credentials", default="credentials.json")
    p.add_argument("--months", type=int, default=16)
    p.add_argument("--lang", default="spanish", help="NLTK stopwords language (default: spanish, as in the post)")
    p.add_argument("--threshold", type=int, default=60, help="generate titles at or below this title_similarity")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--no-openai", action="store_true", help="skip Step 6")
    p.add_argument("--out", default="fuzzy_booster.csv")
    args = p.parse_args(argv)

    if args.sample:
        df = top_query_per_page(pd.read_csv(SAMPLE_CSV))
    else:
        if not args.site:
            p.error("--site is required unless you use --sample")
        request = build_request(args.site, args.brand, args.months)
        df = add_metadata(fetch_search_console(args.site, request, args.credentials))

    df = add_similarity(df, load_stopwords(args.lang))
    if not args.no_openai:
        df = generate_titles(df, get_openai_client(), args.lang, args.threshold, args.model)
    df.to_csv(args.out, index=False)
    print(df.to_string(index=False, max_colwidth=50))
    print(f"\nSaved {len(df)} rows to {args.out}")
    return df


if __name__ == "__main__":
    main()
