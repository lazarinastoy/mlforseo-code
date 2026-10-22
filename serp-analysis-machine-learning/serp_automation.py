"""Automated SERP analysis: collection, AI classification, gaps, AI citations,
share of search over time, SERP-overlap clustering, People Also Ask mining,
volatility alerts and brand monitoring in LLM answers.

Companion code for the MLforSEO guide "10 ways to automate SERP analysis with AI"
by Lazarina Stoy. Every function works on plain pandas DataFrames, so you can
use the pieces on their own, from the scripted pipeline (run_pipeline.py) or
as tools for an agent (serp_agent.py).

Tables used throughout (one row each):
  organic    date, keyword, rank_group, rank_absolute, domain, url, title, description
  features   date, keyword, item_type, rank_absolute
  citations  date, keyword, surface (ai_overview | ai_mode | chat_gpt | perplexity ...),
             citation_order, domain, url, title
  questions  date, keyword, position, question, seed_question   (People Also Ask)

Keys, all optional, read from environment variables:
  DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD   live collection
  ANTHROPIC_API_KEY                        LLM classification and the agent
  GOOGLE_NL_API_KEY                        Google Cloud Natural Language entities
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import date as _date
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------
# Assumptions you should edit
# --------------------------------------------------------------------------
# Click-through rate by organic position (rank_group). This is an ASSUMPTION
# used to weight share of search. Replace it with your own Search Console CTR
# curve, or a study you trust, and say which one you used.
CTR_CURVE = {1: 0.28, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
             6: 0.04, 7: 0.03, 8: 0.025, 9: 0.02, 10: 0.018}

LLM_MODEL = "claude-opus-5-5"   # any model with structured outputs works
# USD per million tokens (input, output), October 2026. Check
# https://www.anthropic.com/pricing before relying on it.
LLM_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0),
              "claude-haiku-4-5": (1.0, 5.0)}
LLM_USAGE: list[dict] = []      # one row per API call, so you can see what a run cost


def log_usage(resp, label: str = "") -> dict:
    """Record the tokens (and the estimated cost) of one Messages API response."""
    u = resp.usage
    pin, pout = LLM_PRICES.get(resp.model, LLM_PRICES[LLM_MODEL])
    inp = (u.input_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0) * 1.25 \
        + (getattr(u, "cache_read_input_tokens", 0) or 0) * 0.1
    row = dict(label=label, model=resp.model, input_tokens=u.input_tokens,
               output_tokens=u.output_tokens, usd=round((inp * pin + u.output_tokens * pout) / 1e6, 5))
    LLM_USAGE.append(row)
    return row

SNAPSHOT_FILES = {"organic": "serp_snapshots.csv",
                  "features": "serp_features.csv",
                  "citations": "ai_citations.csv",
                  "questions": "paa_questions.csv"}
KEYS = {"organic": ["date", "keyword", "url"],
        "features": ["date", "keyword", "item_type", "rank_absolute"],
        "citations": ["date", "keyword", "surface", "url"],
        "questions": ["date", "keyword", "question"]}


# --------------------------------------------------------------------------
# 1. Collection: SERP API + snapshots you can schedule
# --------------------------------------------------------------------------
class DataForSEO:
    """Minimal DataForSEO client for the three endpoints used here.

    Live SERP endpoints take ONE task per request (the API enforces it).
    Prices change; check https://dataforseo.com/pricing before a big run.
    """

    BASE = "https://api.dataforseo.com/v3"

    def __init__(self, login: str | None = None, password: str | None = None,
                 max_spend_usd: float = 0.50):
        self.auth = (login or os.environ["DATAFORSEO_LOGIN"],
                     password or os.environ["DATAFORSEO_PASSWORD"])
        self.max_spend_usd = max_spend_usd   # a hard stop for runaway loops
        self.spent = 0.0

    def _post(self, path: str, task: dict, retries: int = 3) -> dict:
        if self.spent >= self.max_spend_usd:
            raise RuntimeError(f"Spend cap reached (${self.spent:.3f}). Raise max_spend_usd.")
        for attempt in range(retries):
            r = requests.post(f"{self.BASE}{path}", auth=self.auth, json=[task], timeout=120)
            if r.status_code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            self.spent += float(data.get("cost") or 0)
            t = data["tasks"][0]
            if t["status_code"] != 20000:
                raise RuntimeError(f"{path}: {t['status_code']} {t['status_message']}")
            return t["result"][0]
        raise RuntimeError("unreachable")

    def organic(self, keyword: str, location_code: int = 2840, language_code: str = "en",
                device: str = "desktop", depth: int = 10, ai_overview: bool = True,
                paa_clicks: int = 0) -> dict:
        """Google organic SERP, advanced (all SERP features). `ai_overview=True`
        asks DataForSEO to load asynchronous AI Overviews (a small surcharge, refunded
        when there is none). `paa_clicks` (1-4) expands People Also Ask for more
        questions, at $0.00015 per click."""
        task = {"keyword": keyword, "location_code": location_code, "language_code": language_code,
                "device": device, "depth": depth, "load_async_ai_overview": ai_overview}
        if paa_clicks:
            task["people_also_ask_click_depth"] = paa_clicks
        return self._post("/serp/google/organic/live/advanced", task)

    def ai_mode(self, keyword: str, location_code: int = 2840, language_code: str = "en",
                device: str = "desktop") -> dict:
        """Google AI Mode answer with its references."""
        return self._post("/serp/google/ai_mode/live/advanced", {
            "keyword": keyword, "location_code": location_code,
            "language_code": language_code, "device": device})

    def historical(self, keyword: str, date_from: str, location_code: int = 2840,
                   language_code: str = "en") -> list[dict]:
        """Monthly historical SERP snapshots (DataForSEO Labs), up to 365 days back.
        Useful to backfill a tracker on day one."""
        res = self._post("/dataforseo_labs/google/historical_serps/live", {
            "keyword": keyword, "location_code": location_code,
            "language_code": language_code, "date_from": date_from})
        return res.get("items") or []

    def llm_response(self, prompt: str, platform: str = "chat_gpt", model: str = "gpt-4.1-mini",
                     web_search: bool = False, max_output_tokens: int = 600) -> dict:
        """One answer from an LLM (DataForSEO AI Optimization API). platform is
        "chat_gpt", "perplexity" (model "sonar"; always searches the web), "gemini"
        or "claude". The cost is a small base fee plus the provider's token price."""
        task = {"user_prompt": prompt, "model_name": model, "max_output_tokens": max_output_tokens}
        if web_search and platform == "chat_gpt":
            task["web_search"] = True
        res = self._post(f"/ai_optimization/{platform}/llm_responses/live", task)
        res["platform"], res["user_prompt"] = platform, prompt
        return res


def _references(ai_item: dict) -> list[dict]:
    """All unique references in an ai_overview item (element-level first, in order)."""
    out, seen = [], set()
    blocks = [e.get("references") or [] for e in (ai_item.get("items") or [])]
    blocks.append(ai_item.get("references") or [])
    for refs in blocks:
        for r in refs:
            u = r.get("url")
            if u and u not in seen:
                seen.add(u)
                out.append(r)
    return out


def parse_serp(result: dict, surface: str = "organic", snapshot_date: str | None = None) -> dict:
    """Turn one DataForSEO result (organic advanced, AI Mode, or one historical
    snapshot) into the three tidy tables."""
    d = snapshot_date or (result.get("datetime") or str(_date.today()))[:10]
    kw = result.get("keyword", "")
    organic, features, citations, questions = [], [], [], []
    for it in result.get("items") or []:
        t = it.get("type")
        if surface == "organic":
            features.append(dict(date=d, keyword=kw, item_type=t, rank_absolute=it.get("rank_absolute")))
        if t == "organic":
            organic.append(dict(date=d, keyword=kw, rank_group=it.get("rank_group"),
                                rank_absolute=it.get("rank_absolute"), domain=it.get("domain"),
                                url=it.get("url"), title=it.get("title") or "",
                                description=clean_snippet(it.get("description") or "")))
        elif t == "ai_overview":
            surf = "ai_mode" if surface == "ai_mode" else "ai_overview"
            for i, r in enumerate(_references(it), 1):
                citations.append(dict(date=d, keyword=kw, surface=surf, citation_order=i,
                                      domain=r.get("domain") or "", url=r["url"],
                                      title=r.get("title") or ""))
        elif t == "people_also_ask":
            for q in it.get("items") or []:
                if q.get("title"):
                    questions.append(dict(date=d, keyword=kw, position=len(questions) + 1,
                                          question=q["title"], seed_question=q.get("seed_question") or ""))
    return {"organic": pd.DataFrame(organic), "features": pd.DataFrame(features),
            "citations": pd.DataFrame(citations), "questions": pd.DataFrame(questions)}


def clean_snippet(text: str) -> str:
    """Strip the leading date ("Jun 10, 2025 — ") and trailing "Read more"."""
    text = re.sub(r"^[A-Z][a-z]{2} \d{1,2}, \d{4} — ", "", text.strip())
    return re.sub(r"\s*Read more$", "", text).strip()


def save_snapshot(tables: dict, data_dir: str | Path) -> None:
    """Append tables to the CSV store, de-duplicated, so a cron job can run daily."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        if df is None or df.empty:
            continue
        path = data_dir / SNAPSHOT_FILES[name]
        if path.exists():
            df = pd.concat([pd.read_csv(path), df], ignore_index=True)
        df.drop_duplicates(subset=KEYS[name], keep="last").to_csv(path, index=False)


def load_snapshots(data_dir: str | Path) -> dict:
    data_dir = Path(data_dir)
    out = {}
    for name, f in SNAPSHOT_FILES.items():
        p = data_dir / f
        out[name] = pd.read_csv(p) if p.exists() else pd.DataFrame()
    return out


def collect(keywords: list[str], client: DataForSEO, data_dir: str | Path,
            ai_mode: bool = False, paa_clicks: int = 0) -> dict:
    """One scheduled run: pull every keyword, parse, append to the store."""
    for kw in keywords:
        save_snapshot(parse_serp(client.organic(kw, paa_clicks=paa_clicks)), data_dir)
        if ai_mode:
            save_snapshot(parse_serp(client.ai_mode(kw), surface="ai_mode"), data_dir)
    return load_snapshots(data_dir)


# --------------------------------------------------------------------------
# 2. LLM structured-output classification of results and SERPs
# --------------------------------------------------------------------------
PAGE_TYPES = ["guide or tutorial", "definition or glossary", "free tool", "product or pricing page",
              "listicle or comparison", "forum or community", "video", "news", "course", "other"]
INTENTS = ["informational", "commercial", "transactional", "navigational"]
SERP_FORMATS = ["read", "do (use a tool)", "compare", "buy", "watch", "discuss", "mixed"]

CLASSIFY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["results", "dominant_intent", "dominant_format", "reasoning"],
    "properties": {
        "results": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["rank", "page_type", "intent"],
            "properties": {"rank": {"type": "integer"},
                           "page_type": {"type": "string", "enum": PAGE_TYPES},
                           "intent": {"type": "string", "enum": INTENTS}}}},
        "dominant_intent": {"type": "string", "enum": INTENTS},
        "dominant_format": {"type": "string", "enum": SERP_FORMATS},
        "reasoning": {"type": "string"}}}


def serp_prompt(keyword: str, organic: pd.DataFrame, features: pd.DataFrame) -> str:
    o = organic.assign(description=organic.get("description", "")).fillna({"description": ""})
    rows = "\n".join(f"{int(r.rank_group)}. {r.domain} | {r.title} | {r.description}"
                     for r in o.sort_values("rank_group").itertuples())
    feats = (", ".join(sorted(set(features["item_type"])))
             if features is not None and not features.empty else "unknown")
    return (f"Keyword: {keyword}\nSERP features present: {feats}\n\nOrganic results "
            f"(rank. domain | title | snippet):\n{rows}\n\nLabel every result's page type and "
            "intent from the allowed values only. Then give the SERP's dominant intent and "
            "dominant format (what the searcher mostly wants to do), with one sentence of reasoning.")


def classify_serp(keyword: str, organic: pd.DataFrame, features: pd.DataFrame,
                  client=None, model: str = LLM_MODEL) -> dict:
    """One call per SERP. The JSON schema puts your label lists in enums, so the
    model can only answer from them."""
    import anthropic
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
        messages=[{"role": "user", "content": serp_prompt(keyword, organic, features)}])
    log_usage(resp, f"classify: {keyword}")
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Model declined to classify {keyword!r}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"Ran out of tokens classifying {keyword!r}; raise max_tokens")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def classify_latest(snap: dict, client=None, model: str = LLM_MODEL) -> pd.DataFrame:
    """Classify the latest SERP for every keyword; returns one row per result."""
    org, feat = snap["organic"], snap["features"]
    out = []
    for kw, g in org.groupby("keyword"):
        latest = g["date"].max()
        o = g[g["date"] == latest]
        f = feat[(feat["keyword"] == kw) & (feat["date"] == latest)] if not feat.empty else feat
        lab = classify_serp(kw, o, f, client=client, model=model)
        by_rank = {r["rank"]: r for r in lab["results"]}
        for r in o.itertuples():
            l = by_rank.get(int(r.rank_group), {})
            out.append(dict(date=latest, keyword=kw, rank_group=r.rank_group, domain=r.domain,
                            page_type=l.get("page_type"), intent=l.get("intent"),
                            serp_intent=lab["dominant_intent"], serp_format=lab["dominant_format"]))
    return pd.DataFrame(out)


def feature_matrix(features: pd.DataFrame) -> pd.DataFrame:
    """Which SERP features appeared, per keyword and date (1/0). No AI needed:
    the SERP API already types every element."""
    if features.empty:
        return features
    m = (features.assign(v=1).pivot_table(index=["keyword", "date"], columns="item_type",
                                          values="v", aggfunc="max", fill_value=0))
    return m.reset_index()


# --------------------------------------------------------------------------
# 3. Entity and n-gram gap analysis
# --------------------------------------------------------------------------
def ngram_gap(serp_docs: list[str], my_doc: str, ngram_range=(1, 3), min_share: float = 0.25,
              stop_words="english") -> pd.DataFrame:
    """N-grams used by at least `min_share` of the ranking documents, flagged by
    whether your page uses them. Document frequency, not raw counts, so one
    repetitive page can't dominate."""
    from sklearn.feature_extraction.text import CountVectorizer
    vec = CountVectorizer(ngram_range=ngram_range, stop_words=stop_words, binary=True,
                          token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]+\b")
    X = vec.fit_transform([d.lower() for d in serp_docs])
    share = pd.Series(X.mean(axis=0).A1, index=vec.get_feature_names_out())
    share = share[share >= min_share].sort_values(ascending=False)
    mine = my_doc.lower()
    df = pd.DataFrame({"ngram": share.index, "serp_doc_share": share.values.round(2)})
    df["in_my_page"] = [bool(re.search(rf"\b{re.escape(g)}\b", mine)) for g in df["ngram"]]
    # drop n-grams fully contained in a longer n-gram with the same share
    keep = []
    for g, s in zip(df["ngram"], df["serp_doc_share"]):
        if not any(g != h and f" {g} " in f" {h} " and abs(s - t) < 1e-9
                   for h, t in zip(df["ngram"], df["serp_doc_share"])):
            keep.append(g)
    return df[df["ngram"].isin(keep)].reset_index(drop=True)


def entities_spacy(texts: list[str], nlp=None) -> list[set]:
    """Free fallback: spaCy NER + noun chunks. Fine for a first look; misses
    and mislabels more than a knowledge-graph-backed API."""
    import spacy
    nlp = nlp or spacy.load("en_core_web_sm")
    out = []
    for doc in nlp.pipe(texts):
        ents = {e.text.lower().strip() for e in doc.ents
                if e.label_ not in ("DATE", "TIME", "CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY")}
        ents |= {c.text.lower().strip() for c in doc.noun_chunks if len(c.text.split()) > 1
                 and c.root.pos_ in ("NOUN", "PROPN")}
        cleaned = set()
        for e in ents:
            e = re.sub(r"^[^a-z0-9]+|[^a-z0-9)]+$", "", e)          # stray dashes, quotes, commas
            e = re.sub(r"^(the|a|an|your|our|this|any) ", "", e)
            if 2 < len(e) and len(e.split()) <= 4:
                cleaned.add(e)
        out.append(cleaned)
    return out


def entities_google(texts: list[str], api_key: str | None = None) -> list[set]:
    """Google Cloud Natural Language v1 analyzeEntities (v1 keeps salience and
    Wikipedia URLs). First 5,000 units/month free per feature."""
    key = api_key or os.environ["GOOGLE_NL_API_KEY"]
    url = f"https://language.googleapis.com/v1/documents:analyzeEntities?key={key}"
    out = []
    for t in texts:
        r = requests.post(url, json={"document": {"type": "PLAIN_TEXT", "content": t},
                                     "encodingType": "UTF8"}, timeout=60)
        r.raise_for_status()
        out.append({e["name"].lower() for e in r.json().get("entities", [])})
    return out


def entity_gap(serp_docs: list[str], my_doc: str, extractor=entities_spacy,
               min_docs: int = 2) -> pd.DataFrame:
    """Entities mentioned by >= `min_docs` ranking documents but not by your page."""
    sets = extractor(serp_docs + [my_doc])
    serp_sets, mine = sets[:-1], sets[-1]
    c = Counter(e for s in serp_sets for e in s)
    rows = [dict(entity=e, serp_docs=n, serp_doc_share=round(n / len(serp_sets), 2),
                 in_my_page=(e in mine or e in my_doc.lower()))
            for e, n in c.most_common() if n >= min_docs]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 4. AI Overview and AI Mode citation tracking
# --------------------------------------------------------------------------
def citation_overlap(citations: pd.DataFrame, organic: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Per keyword, date and surface: how many URLs were cited, and how many of
    them also rank in the organic top `top_n` that day (by URL and by domain)."""
    rows = []
    for (kw, d, surf), g in citations.groupby(["keyword", "date", "surface"]):
        o = organic[(organic["keyword"] == kw) & (organic["date"] == d) & (organic["rank_group"] <= top_n)]
        if o.empty:  # AI Mode pulled on its own: compare with the closest organic snapshot
            dates = organic.loc[organic["keyword"] == kw, "date"]
            if dates.empty:
                continue
            o = organic[(organic["keyword"] == kw) & (organic["date"] == dates.max())]
        urls = set(o["url"].str.rstrip("/"))
        doms = set(o["domain"].str.replace("www.", "", regex=False))
        cu = g["url"].str.rstrip("/")
        cd = g["domain"].str.replace("www.", "", regex=False)
        rows.append(dict(keyword=kw, date=d, surface=surf, cited_urls=cu.nunique(),
                         cited_domains=cd.nunique(),
                         cited_urls_ranking_top10=int(cu.isin(urls).sum()),
                         cited_domains_ranking_top10=int(cd[~cd.duplicated()].isin(doms).sum())))
    return pd.DataFrame(rows)


def citation_presence(citations: pd.DataFrame, keyword: str, surface: str = "ai_overview") -> pd.DataFrame:
    """Domain x date grid of AI citations (1 = cited) for one keyword."""
    c = citations[(citations["keyword"] == keyword) & (citations["surface"] == surface)].copy()
    c["domain"] = c["domain"].str.replace("www.", "", regex=False)
    m = c.assign(v=1).pivot_table(index="domain", columns="date", values="v", aggfunc="max", fill_value=0)
    return m.loc[m.sum(axis=1).sort_values(ascending=False).index]


def my_citation_rate(citations: pd.DataFrame, my_domain: str) -> pd.DataFrame:
    """Share of tracked AI answers (keyword x date x surface) that cite your domain."""
    c = citations.assign(mine=citations["domain"].str.contains(my_domain, regex=False))
    per = c.groupby(["keyword", "date", "surface"])["mine"].any().reset_index()
    return per.groupby(["date", "surface"])["mine"].mean().rename("citation_rate").reset_index()


# --------------------------------------------------------------------------
# 5. Share of search over time
# --------------------------------------------------------------------------
def share_of_search(organic: pd.DataFrame, by: str = "domain", weight: str = "ctr",
                    top_n: int = 10) -> pd.DataFrame:
    """Share of the tracked top-`top_n` per date. weight='slots' counts ranking
    positions; weight='ctr' weights each slot by CTR_CURVE (an assumption).
    Returns date x `by` with shares that sum to 1 per date."""
    o = organic[organic["rank_group"] <= top_n].copy()
    o["domain"] = o["domain"].str.replace("www.", "", regex=False)
    o["w"] = 1.0 if weight == "slots" else o["rank_group"].map(CTR_CURVE).fillna(0.01)
    p = o.pivot_table(index="date", columns=by, values="w", aggfunc="sum", fill_value=0)
    return p.div(p.sum(axis=1), axis=0).sort_index()


def biggest_movers(sos: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Change in share between the first and last snapshot."""
    delta = (sos.iloc[-1] - sos.iloc[0]).sort_values()
    out = pd.concat([delta.head(n), delta.tail(n)]).drop_duplicates()
    return out.rename("share_change").round(3).reset_index()


# --------------------------------------------------------------------------
# 6. Clustering keywords by SERP overlap
# --------------------------------------------------------------------------
def serp_overlap(organic: pd.DataFrame, top_n: int = 10, snapshot: str = "latest") -> pd.DataFrame:
    """Keyword x keyword count of shared ranking URLs in the top `top_n`."""
    o = organic[organic["rank_group"] <= top_n]
    if snapshot == "latest":
        o = o[o["date"] == o.groupby("keyword")["date"].transform("max")]
    sets = {k: set(g["url"].str.rstrip("/")) for k, g in o.groupby("keyword")}
    kws = sorted(sets)
    return pd.DataFrame([[len(sets[a] & sets[b]) for b in kws] for a in kws], index=kws, columns=kws)


def cluster_by_overlap(overlap: pd.DataFrame, min_shared: int = 3) -> pd.DataFrame:
    """Hard clustering: keywords that share >= `min_shared` URLs are linked;
    each connected group is one cluster (one page should target it). Average-
    linkage hierarchical clustering gives a softer view; see dendrogram_data()."""
    kws = list(overlap.index)
    parent = {k: k for k in kws}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for a in kws:
        for b in kws:
            if a < b and overlap.loc[a, b] >= min_shared:
                parent[find(a)] = find(b)
    roots = {k: find(k) for k in kws}
    ids = {r: i + 1 for i, r in enumerate(dict.fromkeys(roots.values()))}
    return pd.DataFrame({"keyword": kws, "cluster": [ids[roots[k]] for k in kws]}).sort_values(["cluster", "keyword"])


def dendrogram_data(overlap: pd.DataFrame, top_n: int = 10):
    """Linkage matrix (average linkage on 1 - shared/top_n) for scipy's dendrogram."""
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform
    dist = 1 - overlap / top_n
    for k in dist.index:
        dist.loc[k, k] = 0
    return linkage(squareform(dist.clip(lower=0).values, checks=False), method="average")


# --------------------------------------------------------------------------
# 7. A plain-text change report (what the scheduled pipeline emails or posts)
# --------------------------------------------------------------------------
def change_report(snap: dict, my_domain: str | None = None) -> str:
    org, feat, cit = snap["organic"], snap["features"], snap["citations"]
    lines = [f"# SERP change report ({org['date'].max()})", ""]
    for kw, g in org.groupby("keyword"):
        dates = sorted(g["date"].unique())
        lines.append(f"## {kw}")
        if len(dates) >= 2:
            prev, last = dates[-2], dates[-1]
            a = set(g.loc[g["date"] == prev, "domain"])
            b = set(g.loc[g["date"] == last, "domain"])
            lines.append(f"- Since {prev}: {len(b - a)} new domains in the top 10 "
                         f"({', '.join(sorted(b - a)) or 'none'}); dropped out: {', '.join(sorted(a - b)) or 'none'}.")
            v = serp_volatility(g).iloc[-1]
            flag = " ALERT" if v["volatility"] >= ALERT_THRESHOLD else ""
            lines.append(f"- Volatility {v['volatility']:.2f} (0 = unchanged, 1 = a whole new top 10).{flag}")
        if not feat.empty:
            f = feat[(feat["keyword"] == kw) & (feat["date"] == dates[-1])]
            lines.append(f"- SERP features now: {', '.join(sorted(set(f['item_type'])))}.")
        if not cit.empty:
            ov = citation_overlap(cit[cit["keyword"] == kw], org)
            for r in ov[ov["date"] == ov["date"].max()].itertuples():
                lines.append(f"- {r.surface}: {r.cited_urls} cited URLs, {r.cited_urls_ranking_top10} of them "
                             f"in the organic top 10.")
            if my_domain:
                mine = cit[(cit["keyword"] == kw) & cit["domain"].str.contains(my_domain, regex=False)]
                lines.append(f"- {my_domain} cited: {'yes' if not mine.empty else 'no'} (latest answers).")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 8. People Also Ask mining and clustering
# --------------------------------------------------------------------------
QUESTION_USES = ["section in the main page", "FAQ entry", "separate page", "off-topic (skip)"]
QUESTION_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["themes"],
    "properties": {"themes": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["theme", "questions", "use"],
        "properties": {"theme": {"type": "string"},
                       "questions": {"type": "array", "items": {"type": "string"}},
                       "use": {"type": "string", "enum": QUESTION_USES}}}}}}


def question_table(questions: pd.DataFrame) -> pd.DataFrame:
    """De-duplicated PAA questions: in how many keyword (x market) SERPs and
    snapshots each appeared. Questions that recur across SERPs are the core of the topic."""
    q = questions.assign(q_norm=questions["question"].str.lower().str.strip(" ?"))
    q["source"] = q["keyword"] + (" | " + q["market"].astype(str) if "market" in q else "")
    out = (q.groupby("q_norm").agg(question=("question", "first"), sources=("source", "nunique"),
                                   seen=("date", "count"), best_position=("position", "min"))
           .sort_values(["sources", "seen", "best_position"], ascending=[False, False, True]))
    return out.reset_index(drop=True)


def cluster_questions(questions: list[str], topic: str, client=None, model: str = LLM_MODEL) -> dict:
    """Group questions into themes and say how a page about `topic` should use
    each theme. One structured-output call; the enum stops invented 'uses'."""
    import anthropic
    client = client or anthropic.Anthropic()
    prompt = (f"Topic of the page: {topic}\n\nPeople Also Ask questions collected from Google:\n"
              + "\n".join(f"- {q}" for q in questions)
              + "\n\nGroup questions that ask the same thing or closely related things into themes "
              "(use every question exactly once, copied verbatim). For each theme, choose how a page "
              "about the topic should use it. Mark questions that drifted away from the topic as off-topic.")
    resp = client.messages.create(
        model=model, max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": QUESTION_SCHEMA}},
        messages=[{"role": "user", "content": prompt}])
    log_usage(resp, f"questions: {topic}")
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Question clustering stopped early: {resp.stop_reason}")
    out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    placed = {q for t in out["themes"] for q in t["questions"]}
    out["unplaced"] = [q for q in questions if q not in placed]   # check, don't assume
    return out


# --------------------------------------------------------------------------
# 9. Volatility scores and alerts
# --------------------------------------------------------------------------
ALERT_THRESHOLD = 0.5   # tune on your own history: alert on what's unusual for YOUR keywords


def serp_volatility(organic: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Per keyword and consecutive pair of snapshots: how much the top `top_n`
    changed. url_turnover = 1 - Jaccard similarity of the URL sets.
    volatility = total position change, where a URL that entered or left counts as
    moving to position top_n + 1, divided by the change if every URL had been
    replaced. 0 = identical, 1 = a whole new top 10; moves near the top weigh more."""
    rows = []
    o = organic[organic["rank_group"] <= top_n]
    for kw, g in o.groupby("keyword"):
        dates = sorted(g["date"].unique())
        for prev, cur in zip(dates, dates[1:]):
            a = dict(zip(g.loc[g["date"] == prev, "url"].str.rstrip("/"), g.loc[g["date"] == prev, "rank_group"]))
            b = dict(zip(g.loc[g["date"] == cur, "url"].str.rstrip("/"), g.loc[g["date"] == cur, "rank_group"]))
            urls = set(a) | set(b)
            moves = sum(abs(a.get(u, top_n + 1) - b.get(u, top_n + 1)) for u in urls)
            worst = sum(top_n + 1 - r for r in a.values()) + sum(top_n + 1 - r for r in b.values())
            rows.append(dict(keyword=kw, date_from=prev, date_to=cur,
                             url_turnover=round(1 - len(set(a) & set(b)) / len(urls), 2),
                             volatility=round(moves / worst, 2) if worst else 0.0,
                             entered=len(set(b) - set(a)), left=len(set(a) - set(b))))
    return pd.DataFrame(rows)


def volatility_alerts(vol: pd.DataFrame, threshold: float = ALERT_THRESHOLD) -> pd.DataFrame:
    """The keyword/date pairs worth a human look."""
    return vol[vol["volatility"] >= threshold].sort_values("volatility", ascending=False)


def compare_markets(organic: pd.DataFrame, keyword: str, market_col: str = "market",
                    top_n: int = 10) -> pd.DataFrame:
    """Same keyword, different markets (or devices): shared URLs and domains in
    the top `top_n`, for every pair of markets. Add a `market` column when you
    store each pull (e.g. "US", "UK", "US-mobile")."""
    o = organic[(organic["keyword"] == keyword) & (organic["rank_group"] <= top_n)]
    sets = {m: (set(g["url"].str.rstrip("/")), set(g["domain"].str.replace("www.", "", regex=False)))
            for m, g in o.groupby(market_col)}
    ms = sorted(sets)
    return pd.DataFrame([dict(market_a=a, market_b=b, shared_urls=len(sets[a][0] & sets[b][0]),
                              shared_domains=len(sets[a][1] & sets[b][1]),
                              url_jaccard=round(len(sets[a][0] & sets[b][0]) / len(sets[a][0] | sets[b][0]), 2))
                         for i, a in enumerate(ms) for b in ms[i + 1:]])


# --------------------------------------------------------------------------
# 10. Brand mentions and citations in LLM answers (ChatGPT, Perplexity ...)
# --------------------------------------------------------------------------
def parse_llm_answer(result: dict, snapshot_date: str | None = None) -> dict:
    """One DataForSEO LLM-responses result -> an answers row and citations rows
    (same citations table as AI Overviews, with surface = the platform)."""
    d = snapshot_date or (result.get("datetime") or str(_date.today()))[:10]
    platform, prompt = result.get("platform", "llm"), result.get("user_prompt", "")
    text, cites = [], []
    for item in result.get("items") or []:
        for sec in item.get("sections") or []:
            text.append(sec.get("text") or "")
            for a in sec.get("annotations") or []:
                if a.get("url") and a["url"] not in {c["url"] for c in cites}:
                    cites.append(dict(date=d, keyword=prompt, surface=platform, citation_order=len(cites) + 1,
                                      domain=re.sub(r"^https?://([^/]+).*", r"\1", a["url"]),
                                      url=a["url"], title=a.get("title") or ""))
    answer = dict(date=d, platform=platform, model=result.get("model_name"), prompt=prompt,
                  web_search=result.get("web_search"), text="\n".join(text))
    return {"answers": pd.DataFrame([answer]), "citations": pd.DataFrame(cites)}


def brand_mentions(answers: pd.DataFrame, brands: dict[str, str]) -> pd.DataFrame:
    """Which brands each answer mentions, and where (1 = mentioned first).
    `brands` maps a display name to a regex, e.g. {"Semrush": r"sem ?rush"}."""
    rows = []
    for r in answers.itertuples():
        hits = {b: m.start() for b, pat in brands.items() if (m := re.search(pat, r.text, re.I))}
        order = {b: i + 1 for i, b in enumerate(sorted(hits, key=hits.get))}
        rows.append({"date": r.date, "platform": r.platform, "prompt": r.prompt,
                     **{b: order.get(b, 0) for b in brands}})
    return pd.DataFrame(rows)
