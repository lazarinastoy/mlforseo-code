#!/usr/bin/env python3
"""
IndexNow bulk submitter (MLforSEO, refreshed October 2026).

Submit new, updated or deleted URLs to every IndexNow search engine in one go.
One submission is shared with all participating engines (Bing, Yandex, Seznam.cz,
Naver, Yep, plus the Internet Archive and Amazonbot). Google does not take part.

What it does
  1. Collects URLs from a sitemap (index, .xml or .xml.gz), a .txt/.csv file,
     or a .json/.jsonl export (e.g. a crawler or log-analyser export such as Oncrawl).
  2. Optionally keeps only URLs changed since a date (sitemap <lastmod>).
  3. Drops duplicates and anything that isn't on your host (that's what causes a 422).
  4. Checks your key file is live and contains the key (that's what causes a 403).
  5. Posts the URLs in batches of up to 10,000, waits between batches, retries
     politely on 429, and stops if a batch fails, so you don't burn through the list.
  6. Writes a CSV log (url, batch, status, submitted_at) you can load into Google
     Sheets and Data Studio to track indexation.

Examples
  # make a key and the key file to upload to your site root
  python indexnow_submit.py generate-key

  # dry run: see what would be sent, send nothing
  python indexnow_submit.py submit --host www.example.com --key YOURKEY \
      --sitemap https://www.example.com/sitemap.xml --since 2026-10-01 --dry-run

  # submit a crawler export (JSON lines with a "url" field)
  python indexnow_submit.py submit --host www.example.com --key YOURKEY \
      --urls-file not_indexed.jsonl

Requirements: Python 3.9+, requests.
Docs: https://www.indexnow.org/documentation
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import json
import os
import random
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

import requests

# The shared endpoint forwards to every participating engine. You can also post to
# one engine directly; the URLs are shared with the others either way.
ENDPOINTS = {
    "indexnow": "https://api.indexnow.org/indexnow",
    "bing": "https://www.bing.com/indexnow",
    "yandex": "https://yandex.com/indexnow",
    "seznam": "https://search.seznam.cz/indexnow",
    "naver": "https://searchadvisor.naver.com/indexnow",
    "yep": "https://indexnow.yep.com/indexnow",
}

MAX_URLS_PER_REQUEST = 10_000           # protocol limit per POST
KEY_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,128}$")
USER_AGENT = "MLforSEO-IndexNow/2.0 (+https://www.mlforseo.com/)"

RESPONSES = {
    200: "OK: URLs received",
    202: "Accepted: URLs received, key validation pending",
    400: "Bad request: invalid format",
    403: "Forbidden: key not valid (key file not found, or key not in the file)",
    422: "Unprocessable: URLs don't belong to the host, or key doesn't match the protocol schema",
    429: "Too many requests: slow down (potential spam)",
}


# ---------------------------------------------------------------- keys
def generate_key(out_dir: str = ".") -> str:
    """Create a 32-character hex key and the {key}.txt file to host at your site root."""
    key = uuid.uuid4().hex
    path = Path(out_dir) / f"{key}.txt"
    path.write_text(key, encoding="utf-8")
    print(f"Key: {key}")
    print(f"Key file written: {path}")
    print(f"Upload it so it is reachable at https://<your-host>/{key}.txt")
    return key


def check_key_file(host: str, key: str, key_location: Optional[str] = None,
                   timeout: int = 20) -> bool:
    """Fetch the key file the way a search engine would and confirm it holds the key."""
    if not KEY_PATTERN.match(key):
        print("Key must be 8-128 characters: a-z, A-Z, 0-9 and dashes only.")
        return False
    url = key_location or f"https://{host}/{key}.txt"
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    except requests.RequestException as exc:
        print(f"Couldn't fetch the key file at {url}: {exc}")
        return False
    if r.status_code != 200:
        print(f"Key file at {url} returned HTTP {r.status_code}. Search engines will answer 403.")
        return False
    if r.text.strip().lstrip("﻿") != key:
        print(f"Key file at {url} is live but doesn't contain exactly the key.")
        return False
    print(f"Key file OK: {url}")
    return True


# ---------------------------------------------------------------- collecting URLs
def _fetch(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    data = r.content
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def _parse_date(value: str) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def urls_from_sitemap(sitemap_url: str, since: Optional[dt.date] = None,
                      _seen: Optional[set] = None) -> list[str]:
    """Read a sitemap or sitemap index (recursively). Filter by <lastmod> if `since` is set.

    URLs without a <lastmod> are kept when filtering, because we can't tell if they changed.
    """
    _seen = _seen if _seen is not None else set()
    if sitemap_url in _seen:
        return []
    _seen.add(sitemap_url)
    root = ET.fromstring(_fetch(sitemap_url))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []
    if root.tag.endswith("sitemapindex"):
        for sm in root.findall("sm:sitemap", ns):
            loc = sm.findtext("sm:loc", default="", namespaces=ns).strip()
            if loc:
                urls += urls_from_sitemap(loc, since, _seen)
        return urls
    for u in root.findall("sm:url", ns):
        loc = u.findtext("sm:loc", default="", namespaces=ns).strip()
        lastmod = _parse_date(u.findtext("sm:lastmod", default="", namespaces=ns))
        if loc and (since is None or lastmod is None or lastmod >= since):
            urls.append(loc)
    return urls


def urls_from_file(path: str, url_field: str = "url") -> list[str]:
    """Read URLs from .txt (one per line), .csv (a column called url/URL/Address/loc),
    .json (a list of strings or objects) or .jsonl (one object or string per line)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    suffix = p.suffix.lower()

    def from_obj(obj) -> Optional[str]:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            for k in (url_field, "url", "URL", "Url", "loc", "Address", "address"):
                if k in obj and obj[k]:
                    return str(obj[k])
        return None

    if suffix == ".jsonl":
        items = [json.loads(line) for line in text.splitlines() if line.strip()]
        return [u for u in map(from_obj, items) if u]
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict):            # e.g. {"urlList": [...]} or {"urls": [...]}
            data = data.get("urlList") or data.get("urls") or list(data.values())[0]
        return [u for u in map(from_obj, data) if u]
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        return [u for u in map(from_obj, reader) if u]
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def clean_urls(urls: Iterable[str], host: str) -> tuple[list[str], list[str]]:
    """De-duplicate (keeping order) and split into URLs on `host` and everything else."""
    keep, rejected, seen = [], [], set()
    for u in urls:
        u = u.strip()
        if not u or u in seen:
            continue
        seen.add(u)
        parsed = urlparse(u)
        if parsed.scheme in ("http", "https") and parsed.netloc.lower() == host.lower():
            keep.append(u)
        else:
            rejected.append(u)
    return keep, rejected


def batches(items: list[str], size: int = MAX_URLS_PER_REQUEST):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ---------------------------------------------------------------- submitting
def submit_batch(urls: list[str], host: str, key: str, key_location: Optional[str] = None,
                 endpoint: str = ENDPOINTS["indexnow"], max_retries: int = 4,
                 timeout: int = 60) -> int:
    """POST one batch as JSON. Retries 429 and 5xx with exponential backoff.
    Returns the final HTTP status code (0 if the request never got an answer)."""
    payload = {"host": host, "key": key, "urlList": urls}
    if key_location:
        payload["keyLocation"] = key_location
    headers = {"Content-Type": "application/json; charset=utf-8", "User-Agent": USER_AGENT}
    status = 0
    for attempt in range(max_retries + 1):
        try:
            # json= (not data=) so the body is real JSON
            r = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            status = r.status_code
        except requests.RequestException as exc:
            print(f"  request error: {exc}")
            status = 0
        if status in (200, 202):
            return status
        if status in (429, 0) or status >= 500:
            if attempt < max_retries:
                wait = 30 * (2 ** attempt) + random.uniform(0, 5)
                print(f"  HTTP {status}: waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait)
                continue
        return status          # 400, 403, 422: retrying won't help
    return status


def write_log(log_path: str, urls: list[str], batch_no: int, status: int) -> None:
    new = not os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["url", "batch", "status", "submitted_at"])
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        for u in urls:
            w.writerow([u, batch_no, status, now])


def run_submit(args: argparse.Namespace) -> int:
    host = args.host.lower().strip().strip("/")
    host = urlparse(host).netloc or host          # accept "https://www.example.com" too
    endpoint = ENDPOINTS.get(args.engine, args.engine)
    since = _parse_date(args.since) if args.since else None

    urls: list[str] = []
    if args.sitemap:
        for sm in args.sitemap:
            found = urls_from_sitemap(sm, since)
            print(f"Sitemap {sm}: {len(found)} URLs" + (f" changed since {since}" if since else ""))
            urls += found
    if args.urls_file:
        found = urls_from_file(args.urls_file, args.url_field)
        print(f"File {args.urls_file}: {len(found)} URLs")
        urls += found
    if args.url:
        urls += args.url

    urls, rejected = clean_urls(urls, host)
    if rejected:
        print(f"Skipped {len(rejected)} URLs that aren't on {host} (they would cause a 422), e.g. {rejected[:3]}")
    if not urls:
        print("No URLs to submit.")
        return 1
    if args.limit:
        urls = urls[: args.limit]
    n_batches = (len(urls) - 1) // args.batch_size + 1
    print(f"Ready: {len(urls)} URLs on {host} in {n_batches} batch(es) -> {endpoint}")

    if args.dry_run:
        for u in urls[:10]:
            print("  ", u)
        if len(urls) > 10:
            print(f"   ... and {len(urls) - 10} more")
        print("Dry run: nothing was sent.")
        return 0

    if not args.skip_key_check and not check_key_file(host, args.key, args.key_location):
        print("Fix the key file first (or pass --skip-key-check if you know what you're doing).")
        return 2

    for i, batch in enumerate(batches(urls, args.batch_size), start=1):
        status = submit_batch(batch, host, args.key, args.key_location, endpoint)
        print(f"Batch {i}/{n_batches}: {len(batch)} URLs -> HTTP {status} ({RESPONSES.get(status, 'unexpected')})")
        write_log(args.log, batch, i, status)
        if status not in (200, 202):
            print("Stopping here so you can fix the problem. Already-sent batches are in the log.")
            return 3
        if i < n_batches:
            time.sleep(args.pause)
    print(f"Done. Log: {args.log}")
    return 0


# ---------------------------------------------------------------- CLI
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Submit URLs to IndexNow in bulk.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate-key", help="create a key and its key file")
    g.add_argument("--out-dir", default=".")

    c = sub.add_parser("check-key", help="check the key file is live and correct")
    c.add_argument("--host", required=True)
    c.add_argument("--key", default=os.environ.get("INDEXNOW_KEY"))
    c.add_argument("--key-location")

    s = sub.add_parser("submit", help="submit URLs")
    s.add_argument("--host", required=True, help="your host, e.g. www.example.com")
    s.add_argument("--key", default=os.environ.get("INDEXNOW_KEY"),
                   help="your IndexNow key (or set INDEXNOW_KEY)")
    s.add_argument("--key-location", help="full URL of the key file, if not at the root")
    s.add_argument("--sitemap", action="append", help="sitemap or sitemap index URL (repeatable)")
    s.add_argument("--urls-file", help=".txt, .csv, .json or .jsonl file of URLs")
    s.add_argument("--url-field", default="url", help="field holding the URL in CSV/JSON files")
    s.add_argument("--url", action="append", help="a single URL (repeatable)")
    s.add_argument("--since", help="only sitemap URLs with <lastmod> on/after YYYY-MM-DD")
    s.add_argument("--engine", default="indexnow",
                   help=f"one of {', '.join(ENDPOINTS)} or a full endpoint URL")
    s.add_argument("--batch-size", type=int, default=MAX_URLS_PER_REQUEST)
    s.add_argument("--pause", type=float, default=10.0, help="seconds between batches")
    s.add_argument("--limit", type=int, help="only send the first N URLs (for testing)")
    s.add_argument("--log", default="indexnow_submissions.csv")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--skip-key-check", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "generate-key":
        generate_key(args.out_dir)
        return 0
    if not args.key:
        ap.error("--key is required (or set the INDEXNOW_KEY environment variable)")
    if args.cmd == "check-key":
        return 0 if check_key_file(args.host, args.key, args.key_location) else 2
    args.batch_size = max(1, min(args.batch_size, MAX_URLS_PER_REQUEST))
    return run_submit(args)


if __name__ == "__main__":
    sys.exit(main())
