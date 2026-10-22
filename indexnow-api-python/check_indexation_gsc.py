#!/usr/bin/env python3
"""
Check whether URLs are indexed in Google with the Search Console URL Inspection API.

This replaces the old "site:" Apps Script check from the 2022 version of the tutorial.
Scraping Google results breaks your Google Sheet as soon as Google serves a CAPTCHA,
and it's against Google's terms. The URL Inspection API gives you Google's own answer.

Quota (Oct 2026): 2,000 inspections per day and 600 per minute per Search Console property.
So inspect a sample, or spread big lists over several days (the script resumes).

Setup
  1. In Google Cloud, enable the "Google Search Console API" and create a service account.
     Download its JSON key.
  2. In Search Console > Settings > Users and permissions, add the service account's
     email address as a (restricted) user on the property.
  3. Run:
     python check_indexation_gsc.py --property sc-domain:example.com \
         --credentials service-account.json --urls-file indexnow_submissions.csv

  --property is "sc-domain:example.com" for a domain property, or the exact URL prefix
  ("https://www.example.com/") for a URL-prefix property.

Output: gsc_inspection.csv (url, verdict, coverage_state, indexing_state, last_crawl_time,
google_canonical, inspected_at). Re-running skips URLs already in the output file.

Requirements: google-api-python-client, google-auth (see requirements.txt).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
import time

from indexnow_submit import urls_from_file   # same file formats as the submitter

FIELDS = ["url", "verdict", "coverage_state", "indexing_state", "last_crawl_time",
          "google_canonical", "inspected_at"]


def build_service(credentials_path: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def inspect(service, site_url: str, url: str) -> dict:
    body = {"inspectionUrl": url, "siteUrl": site_url}
    res = service.urlInspection().index().inspect(body=body).execute()
    idx = res.get("inspectionResult", {}).get("indexStatusResult", {})
    return {
        "url": url,
        "verdict": idx.get("verdict", ""),                 # PASS / NEUTRAL / FAIL
        "coverage_state": idx.get("coverageState", ""),    # e.g. "Submitted and indexed"
        "indexing_state": idx.get("indexingState", ""),
        "last_crawl_time": idx.get("lastCrawlTime", ""),
        "google_canonical": idx.get("googleCanonical", ""),
        "inspected_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--property", required=True, help="sc-domain:example.com or https://www.example.com/")
    ap.add_argument("--credentials", required=True, help="service account JSON key")
    ap.add_argument("--urls-file", required=True, help=".txt/.csv/.json/.jsonl (e.g. the IndexNow log)")
    ap.add_argument("--out", default="gsc_inspection.csv")
    ap.add_argument("--max", type=int, default=2000, help="stop after N inspections (daily quota)")
    ap.add_argument("--pause", type=float, default=0.2, help="seconds between calls (keeps you under 600/min)")
    args = ap.parse_args(argv)

    urls = list(dict.fromkeys(urls_from_file(args.urls_file)))
    done = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            done = {row["url"] for row in csv.DictReader(f)}
    todo = [u for u in urls if u not in done][: args.max]
    print(f"{len(urls)} URLs, {len(done)} already inspected, inspecting {len(todo)} now.")
    if not todo:
        return 0

    service = build_service(args.credentials)
    new_file = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for i, url in enumerate(todo, 1):
            try:
                row = inspect(service, args.property, url)
            except Exception as exc:                       # quota, permissions, bad URL
                msg = str(exc)
                print(f"Stopped at {url}: {msg[:200]}")
                if "quota" in msg.lower() or "429" in msg:
                    print("Daily quota reached. Run again tomorrow; finished URLs are saved.")
                return 1
            w.writerow(row)
            f.flush()
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} inspected")
            time.sleep(args.pause)
    print(f"Done. Results in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
