"""
dataforseo_serp.py: a small, readable DataForSEO SERP API client for SEOs.

Part of the MLforSEO free resource library (Lazarina Stoy, MLforSEO, MIT licence).
https://github.com/lazarinastoy/mlforseo-code

What it does
  * Authenticates with your DataForSEO API login + password (HTTP Basic auth).
  * Pulls Google organic SERPs in two ways:
      - Live Advanced: one keyword per call, results in seconds, highest price.
      - Standard (task_post + task_get/advanced): up to 100 keywords per POST,
        results in a few minutes, cheaper.
  * Logs the cost DataForSEO reports for every call and stops at a spend cap.
  * Flattens the JSON into tidy tables: organic results, SERP features,
    People Also Ask questions, AI Overview citations and related searches.

Docs used (DataForSEO v3, checked 24 Oct 2026):
  https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/
  https://docs.dataforseo.com/v3/serp/google/organic/task_post/
  https://docs.dataforseo.com/v3/serp/google/organic/task_get/advanced/

Never paste your password into this file. Read it at runtime (see get_credentials).
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

API = "https://api.dataforseo.com/v3"

# Prices in USD per call, from the DataForSEO docs and pricing page in October 2026.
# They change: check https://dataforseo.com/pricing/serp/google-organic-serp-api.
# They are only used for the up-front ESTIMATE. The spend log uses the real `cost`
# value that DataForSEO returns with every response.
PRICES = {
    "live": 0.002,                # Live Advanced, per SERP page of up to 10 results
    "standard": 0.0006,           # Standard queue, normal priority (priority=1)
    "standard_high": 0.0012,      # Standard queue, high priority (priority=2)
    "async_aio_live": 0.002,      # load_async_ai_overview surcharge, Live (refunded if no async AIO)
    "async_aio_standard": 0.0006, # load_async_ai_overview surcharge, Standard (refunded if no async AIO)
    "paa_click": 0.00015,         # per People Also Ask click (people_also_ask_click_depth)
}

# Task status codes that mean "not ready yet" when you call task_get.
PENDING_CODES = {40601, 40602}   # "Task Handed", "Task In Queue"


# ---------------------------------------------------------------------------
# Credentials: read at runtime, never stored in the notebook or the repo
# ---------------------------------------------------------------------------
def get_credentials() -> tuple[str, str]:
    """Return (login, password) for the DataForSEO API.

    Order: Colab secrets (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD), then
    environment variables with the same names, then a hidden prompt.
    Your API login and password are on https://app.dataforseo.com/api-access
    (the API password is NOT your dashboard password).
    """
    login = password = None
    try:  # Google Colab: the key icon in the left sidebar
        from google.colab import userdata  # type: ignore
        login = userdata.get("DATAFORSEO_LOGIN")
        password = userdata.get("DATAFORSEO_PASSWORD")
    except Exception:
        pass
    login = login or os.environ.get("DATAFORSEO_LOGIN")
    password = password or os.environ.get("DATAFORSEO_PASSWORD")
    if not (login and password):
        from getpass import getpass
        login = login or input("DataForSEO API login (email): ").strip()
        password = password or getpass("DataForSEO API password: ").strip()
    return login, password


# ---------------------------------------------------------------------------
# Keyword hygiene and the cost estimate
# ---------------------------------------------------------------------------
def clean_keywords(keywords) -> list[str]:
    """Lower-case, trim, collapse spaces and drop duplicates and blanks,
    so you never pay twice for the same SERP."""
    seen, out = set(), []
    for kw in keywords:
        k = re.sub(r"\s+", " ", str(kw)).strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def estimate_cost(n_keywords: int, mode: str = "live", depth: int = 10,
                  load_async_ai_overview: bool = True, paa_clicks: int = 0,
                  priority: int = 1) -> dict:
    """Worst-case estimate in USD before you spend anything.

    Assumes every keyword is charged the AI Overview surcharge (in reality it is
    refunded when there is no asynchronous AI Overview) and every PAA click happens.
    """
    pages = max(1, -(-depth // 10))          # depth 10 = 1 page, 20 = 2 pages ...
    if mode == "live":
        base, aio = PRICES["live"], PRICES["async_aio_live"]
    else:
        base = PRICES["standard_high"] if priority == 2 else PRICES["standard"]
        aio = PRICES["async_aio_standard"]
    per_kw = base * pages + (aio if load_async_ai_overview else 0) + PRICES["paa_click"] * paa_clicks
    return {"mode": mode, "keywords": n_keywords, "pages_per_keyword": pages,
            "usd_per_keyword_max": round(per_kw, 5), "usd_total_max": round(per_kw * n_keywords, 4)}


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------
class DataForSEOClient:
    """Minimal DataForSEO SERP client with a spend cap and a cost log.

    client = DataForSEOClient(*get_credentials(), max_spend_usd=0.10)
    results = client.collect(["what is entity seo"], mode="live")
    client.cost_log  # one row per API call with the cost DataForSEO reported
    """

    def __init__(self, login: str, password: str, max_spend_usd: float = 0.10,
                 pause_seconds: float = 0.5, timeout: int = 120):
        self.session = requests.Session()
        self.session.auth = (login, password)          # HTTP Basic auth
        self.max_spend_usd = max_spend_usd             # hard stop for runaway loops
        self.pause_seconds = pause_seconds             # polite gap between live calls
        self.timeout = timeout
        self.spent = 0.0
        self.cost_log: list[dict] = []

    # -- low level ----------------------------------------------------------
    def _request(self, method: str, path: str, payload=None, label: str = "",
                 expected_cost: float = 0.0, retries: int = 3) -> dict:
        """One HTTP call with retries on rate limits / server errors, cost logging
        and the spend cap. Paid calls (POST) are refused if their worst-case cost
        would take the run over the cap. task_get calls are free."""
        charged = method == "POST"
        if charged and self.spent + expected_cost > self.max_spend_usd + 1e-9:
            raise RuntimeError(f"Spend cap: ${self.spent:.4f} spent, the next call could cost up to "
                               f"${expected_cost:.4f} and the cap is ${self.max_spend_usd}. "
                               "Raise MAX_SPEND_USD if you meant to spend more.")
        for attempt in range(retries):
            r = self.session.request(method, f"{API}{path}", json=payload, timeout=self.timeout)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)           # back off: 2s, 4s ...
                continue
            if r.status_code >= 400:                   # show DataForSEO's own message, not a bare HTTP error
                try:
                    msg = r.json().get("status_message") or r.reason
                except ValueError:
                    msg = r.reason
                hint = (" Check DATAFORSEO_LOGIN (your account email) and DATAFORSEO_PASSWORD: it must be the "
                        "API password from https://app.dataforseo.com/api-access, not your dashboard password."
                        if r.status_code == 401 else "")
                raise RuntimeError(f"DataForSEO HTTP {r.status_code}: {msg}{hint}")
            data = r.json()
            if data.get("status_code") != 20000:       # account-level problems (auth, balance)
                raise RuntimeError(f"DataForSEO {data.get('status_code')}: {data.get('status_message')}")
            cost = float(data.get("cost") or 0) if charged else 0.0
            self.spent += cost
            if charged:  # task_get polls are free, so they stay out of the log
                self.cost_log.append({"endpoint": "/".join(path.split("/")[-2:]), "label": label, "cost_usd": cost,
                                      "spent_so_far_usd": round(self.spent, 5)})
            return data
        raise RuntimeError("Request failed after retries")

    @staticmethod
    def _task_payload(keyword, location_code, language_code, device, depth,
                      load_async_ai_overview, paa_clicks, priority=None) -> dict:
        task = {"keyword": keyword, "location_code": location_code, "language_code": language_code,
                "device": device, "depth": depth, "load_async_ai_overview": load_async_ai_overview}
        if paa_clicks:
            task["people_also_ask_click_depth"] = paa_clicks   # 1-4
        if priority:
            task["priority"] = priority
        return task

    # -- Live Advanced: one keyword per call, results straight away ----------
    def live_advanced(self, keyword: str, location_code: int = 2840, language_code: str = "en",
                      device: str = "desktop", depth: int = 10, load_async_ai_overview: bool = True,
                      paa_clicks: int = 0) -> dict:
        """POST /v3/serp/google/organic/live/advanced. Returns the raw API response."""
        task = self._task_payload(keyword, location_code, language_code, device, depth,
                                  load_async_ai_overview, paa_clicks)
        worst = estimate_cost(1, "live", depth, load_async_ai_overview, paa_clicks)["usd_total_max"]
        return self._request("POST", "/serp/google/organic/live/advanced", [task], label=keyword,
                             expected_cost=worst)

    # -- Standard: post tasks now, fetch results when ready ------------------
    def task_post(self, keywords: list[str], location_code: int = 2840, language_code: str = "en",
                  device: str = "desktop", depth: int = 10, load_async_ai_overview: bool = True,
                  paa_clicks: int = 0, priority: int = 1) -> dict[str, str]:
        """POST /v3/serp/google/organic/task_post in batches of 100.
        Returns {task_id: keyword}."""
        ids = {}
        for i in range(0, len(keywords), 100):
            batch = keywords[i:i + 100]
            payload = [self._task_payload(k, location_code, language_code, device, depth,
                                          load_async_ai_overview, paa_clicks, priority) for k in batch]
            worst = estimate_cost(len(batch), "standard", depth, load_async_ai_overview,
                                  paa_clicks, priority)["usd_total_max"]
            data = self._request("POST", "/serp/google/organic/task_post", payload,
                                 label=f"{len(batch)} tasks", expected_cost=worst)
            for t in data["tasks"]:
                if t["status_code"] == 20100:          # "Task Created."
                    ids[t["id"]] = t["data"]["keyword"]
                else:
                    print(f"  ! not queued: {t['data'].get('keyword')} -> {t['status_message']}")
        return ids

    def task_get(self, task_id: str) -> dict:
        """GET /v3/serp/google/organic/task_get/advanced/{id} (free)."""
        return self._request("GET", f"/serp/google/organic/task_get/advanced/{task_id}", label=task_id)

    def wait_for_tasks(self, ids: dict[str, str], poll_seconds: int = 15, timeout_seconds: int = 900) -> list[dict]:
        """Poll each queued task until it is ready. Normal priority usually takes
        a few minutes. Returns a list of raw responses."""
        pending, done, start = dict(ids), [], time.time()
        while pending and time.time() - start < timeout_seconds:
            for task_id in list(pending):
                data = self.task_get(task_id)
                code = data["tasks"][0]["status_code"]
                if code == 20000:
                    done.append(data)
                    pending.pop(task_id)
                elif code not in PENDING_CODES:
                    print(f"  ! {pending.pop(task_id)}: {data['tasks'][0]['status_message']}")
            if pending:
                print(f"  {len(done)} ready, {len(pending)} still in the queue... checking again in {poll_seconds}s")
                time.sleep(poll_seconds)
        if pending:
            print(f"  ! Timed out with {len(pending)} tasks pending. Their IDs: {list(pending)}. "
                  "You can fetch them later with client.task_get(id) at no cost.")
        return done

    # -- one call for the notebook -------------------------------------------
    def collect(self, keywords: list[str], mode: str = "live", **params) -> list[dict]:
        """Collect SERPs for a keyword list. mode="live" or "standard".
        Returns a list of raw API responses (one per keyword)."""
        if mode == "live":
            out = []
            for i, kw in enumerate(keywords, 1):
                out.append(self.live_advanced(kw, **params))
                print(f"  [{i}/{len(keywords)}] {kw}: ${self.cost_log[-1]['cost_usd']:.4f}")
                time.sleep(self.pause_seconds)
            return out
        priority = params.pop("priority", 1)
        ids = self.task_post(keywords, priority=priority, **params)
        print(f"  queued {len(ids)} tasks; waiting for results (task_get is free)")
        return self.wait_for_tasks(ids)


class SampleClient:
    """Stands in for DataForSEOClient when USE_SAMPLE = True. It reads saved real
    API responses from sample_data/<keyword-slug>.json, so the notebook runs
    end to end without a key and without spending anything."""

    def __init__(self, sample_dir: str | Path = "sample_data"):
        self.sample_dir = Path(sample_dir)
        self.spent = 0.0
        self.cost_log: list[dict] = []

    def available_keywords(self) -> list[str]:
        out = []
        for p in sorted(self.sample_dir.glob("*.json")):
            try:
                out.append(json.loads(p.read_text())["tasks"][0]["data"]["keyword"])
            except (KeyError, IndexError, json.JSONDecodeError):
                continue
        return out

    def collect(self, keywords: list[str], mode: str = "live", **params) -> list[dict]:
        out = []
        for kw in keywords:
            p = self.sample_dir / f"{slugify(kw)}.json"
            if not p.exists():
                print(f"  (no sample saved for '{kw}', skipped)")
                continue
            data = json.loads(p.read_text())
            # what the call cost when it was collected (it costs nothing to replay)
            self.cost_log.append({"endpoint": "sample replay", "label": kw,
                                  "cost_usd": float(data.get("cost") or 0), "spent_so_far_usd": 0.0})
            out.append(data)
        return out


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Flattening: raw JSON -> tidy tables
# ---------------------------------------------------------------------------
def bare_domain(domain: str | None) -> str:
    """'www.example.co.uk' -> 'example.co.uk' so www and non-www count as one site."""
    d = (domain or "").lower().strip()
    return d[4:] if d.startswith("www.") else d


def results_from_responses(responses: list[dict]) -> list[dict]:
    """Pull the `result` objects out of raw API responses (Live or task_get)."""
    out = []
    for data in responses:
        for task in data.get("tasks") or []:
            if task.get("status_code") == 20000:
                out.extend(task.get("result") or [])
    return out


def ai_overview_references(ai_item: dict) -> list[dict]:
    """All unique cited URLs in one ai_overview item, in the order they appear.

    DataForSEO puts references in two places: on each ai_overview_element
    (the sources behind that paragraph) and on the ai_overview item itself
    (the source cards shown beside the answer). We read both and keep each URL once.
    """
    out, seen = [], set()
    for element in ai_item.get("items") or []:
        for r in element.get("references") or []:
            if r.get("url") and r["url"] not in seen:
                seen.add(r["url"])
                out.append({**r, "element_title": element.get("title") or ""})
    for r in ai_item.get("references") or []:
        if r.get("url") and r["url"] not in seen:
            seen.add(r["url"])
            out.append({**r, "element_title": "(source panel)"})
    return out


def flatten(responses: list[dict]) -> dict[str, pd.DataFrame]:
    """Turn raw responses into five tidy DataFrames:
    organic, serp_features, paa, ai_overview_citations, related_searches."""
    organic, features, paa, citations, related = [], [], [], [], []
    for res in results_from_responses(responses):
        kw = res.get("keyword", "")
        day = (res.get("datetime") or str(date.today()))[:10]
        base = {"date": day, "keyword": kw, "location_code": res.get("location_code"),
                "language_code": res.get("language_code")}
        for it in res.get("items") or []:
            t = it.get("type")
            features.append({**base, "item_type": t, "rank_group": it.get("rank_group"),
                             "rank_absolute": it.get("rank_absolute")})
            if t == "organic":
                organic.append({**base, "rank_group": it.get("rank_group"),
                                "rank_absolute": it.get("rank_absolute"),
                                "domain": bare_domain(it.get("domain")), "url": it.get("url"),
                                "title": it.get("title"), "description": it.get("description"),
                                "is_video": it.get("is_video"), "is_featured_snippet": it.get("is_featured_snippet")})
            elif t == "people_also_ask":
                for n, q in enumerate(it.get("items") or [], 1):
                    paa.append({**base, "paa_position": n, "question": q.get("title"),
                                "seed_question": q.get("seed_question")})
            elif t == "ai_overview":
                for n, r in enumerate(ai_overview_references(it), 1):
                    citations.append({**base, "citation_order": n, "domain": bare_domain(r.get("domain")),
                                      "url": r.get("url"), "title": r.get("title"),
                                      "source": r.get("source"), "aio_section": r.get("element_title")})
            elif t == "related_searches":
                for n, q in enumerate(it.get("items") or [], 1):
                    related.append({**base, "position": n, "related_search": q})
    return {"organic": pd.DataFrame(organic), "serp_features": pd.DataFrame(features),
            "paa": pd.DataFrame(paa), "ai_overview_citations": pd.DataFrame(citations),
            "related_searches": pd.DataFrame(related)}


def feature_matrix(serp_features: pd.DataFrame) -> pd.DataFrame:
    """Keyword x SERP feature table: 1 if the feature is on the SERP, else 0."""
    if serp_features.empty:
        return pd.DataFrame()
    m = pd.crosstab(serp_features["keyword"], serp_features["item_type"]).clip(upper=1)
    return m[m.sum().sort_values(ascending=False).index]


def export(tables: dict[str, pd.DataFrame], out_dir: str | Path = "output", xlsx_name: str | None = None) -> list[Path]:
    """Write every table to CSV, plus (optionally) one Excel workbook with a tab
    per table that you can import straight into Google Sheets."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in tables.items():
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    if xlsx_name:
        p = out_dir / xlsx_name
        with pd.ExcelWriter(p) as xl:
            for name, df in tables.items():
                df.to_excel(xl, sheet_name=name[:31], index=False)
        written.append(p)
    return written
