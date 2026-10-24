#!/usr/bin/env python3
"""Write the synthetic sample exports in sample_data/ (a fictional running shoe shop, stride-example.com).

The files copy the real export formats so prepare_exports.py and the workbook are tested on realistic input:
  gsc_pages_current.csv / gsc_pages_previous.csv  Search Console > Performance > Pages > Export (CSV): Top pages, Clicks, Impressions, CTR, Position
  ga4_landing_pages.csv                            GA4 > Reports > Engagement > Landing page > Share > Download CSV (with the # comment lines)
  internal_html.csv                                Screaming Frog SEO Spider > Internal > HTML > Export (full column set)
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "sample_data"
SITE = "https://www.stride-example.com"

# Screaming Frog SEO Spider internal export header (v20+ with near-duplicate and semantic similarity columns).
SF_HEADER = ["Address", "Content Type", "Status Code", "Status", "Indexability", "Indexability Status", "Title 1", "Title 1 Length",
             "Title 1 Pixel Width", "Meta Description 1", "Meta Description 1 Length", "Meta Description 1 Pixel Width",
             "Meta Keywords 1", "Meta Keywords 1 Length", "H1-1", "H1-1 Length", "H1-2", "H1-2 Length", "H2-1", "H2-1 Length",
             "H2-2", "H2-2 Length", "Meta Robots 1", "X-Robots-Tag 1", "Meta Refresh 1", "Canonical Link Element 1",
             'rel="next" 1', 'rel="prev" 1', 'HTTP rel="next" 1', 'HTTP rel="prev" 1', "amphtml Link Element", "Size (Bytes)",
             "Transferred (Bytes)", "Total Transferred (Bytes)", "CO2 (mg)", "Carbon Rating", "Word Count", "Sentence Count",
             "Average Words Per Sentence", "Flesch Reading Ease Score", "Readability", "Text Ratio", "Crawl Depth", "Folder Depth",
             "Link Score", "Inlinks", "Unique Inlinks", "Unique JS Inlinks", "% of Total", "Outlinks", "Unique Outlinks",
             "Unique JS Outlinks", "External Outlinks", "Unique External Outlinks", "Unique External JS Outlinks",
             "Closest Near Duplicate Match", "No. Near Duplicates", "Spelling Errors", "Grammar Errors", "Hash", "Response Time",
             "Last Modified", "Redirect URL", "Redirect Type", "Cookies", "Language", "HTTP Version", "Mobile Alternate Link",
             "Closest Semantically Similar Address", "Semantic Similarity Score", "No. Semantically Similar",
             "Semantic Relevance Score", "URL Encoded Address", "Crawl Timestamp"]

# path, status, indexability status ("" = Indexable), words, unique inlinks, near-dup match, sem match, sem score, title,
# GSC now (clicks, impressions, position), GSC previous clicks, GA4 (sessions, avg engagement s, key events)
PAGES = [
    ("/", 200, "", 850, 120, "", "", None, "Stride & Co: running shoes and gait analysis", (1240, 30200, 3.1), 1180, (2610, 48.2, 61)),
    ("/trail-running-shoes/", 200, "", 610, 85, "", "", None, "Trail running shoes", (905, 41000, 6.2), 880, (1450, 41.0, 37)),
    ("/road-running-shoes/", 200, "", 560, 80, "", "", None, "Road running shoes", (640, 12100, 3.4), 610, (980, 39.5, 30)),
    ("/blog/best-trail-running-shoes/", 200, "", 2300, 22, "", "", None, "The best trail running shoes", (210, 9800, 7.9), 520, (300, 71.3, 4)),
    ("/blog/trail-running-for-beginners/", 200, "", 1650, 12, "", "", None, "Trail running for beginners", (45, 3900, 11.3), 50, (70, 66.0, 0)),
    ("/blog/wide-feet-guide/", 200, "", 1400, 18, "", "", None, "Running shoes for wide feet: a fitting guide", (160, 5200, 2.8), 150, (210, 83.1, 3)),
    ("/wide-fit-running-shoes/", 200, "", 520, 64, "", "", None, "Wide fit running shoes", (380, 8100, 3.9), 360, (520, 37.2, 19)),
    ("/blog/hoka-vs-brooks/", 200, "", 1900, 15, "/blog/hoka-vs-brooks-2023/", "", None, "Hoka vs Brooks", (120, 4100, 3.5), 115, (160, 75.4, 2)),
    ("/blog/hoka-vs-brooks-2023/", 200, "", 1750, 3, "/blog/hoka-vs-brooks/", "", None, "Hoka vs Brooks (2023)", (8, 900, 24.0), 30, (11, 51.0, 0)),
    ("/blog/best-marathon-shoes-2022/", 200, "", 900, 4, "", "/marathon-running-shoes/", 0.93, "Best marathon shoes 2022", (4, 600, 28.4), 12, (6, 22.0, 0)),
    ("/marathon-running-shoes/", 200, "", 640, 70, "", "/blog/best-marathon-shoes-2022/", 0.93, "Marathon running shoes", (300, 9400, 3.6), 290, (430, 36.0, 21)),
    ("/blog/running-shoe-sizing-chart/", 200, "", 220, 9, "", "", None, "Running shoe sizing chart", (30, 2600, 8.0), 28, (44, 58.0, 1)),
    ("/blog/london-store-opening-2019/", 200, "", 180, 2, "", "", None, "Our London store is open", (0, 15, 41.0), 0, (3, 12.0, 0)),
    ("/blog/staff-picks-may-2020/", 200, "", 240, 2, "", "", None, "Staff picks: May 2020", (0, 40, 37.5), 1, (2, 9.0, 0)),
    ("/tag/shoes/", 200, "noindex", 90, 30, "", "", None, "Shoes archive", (0, 0, None), 0, (1, 4.0, 0)),
    ("/old-sale/", 301, "Redirected", 0, 6, "", "", None, "", (0, 0, None), 0, (0, 0, 0)),
    ("/blog/how-to-lace-running-shoes/", 404, "Client Error", 0, 5, "", "", None, "", (25, 1300, 9.1), 60, (20, 5.0, 0)),
    ("/blog/cushioning-explained/", 404, "Client Error", 0, 1, "", "", None, "", (0, 0, None), 0, (0, 0, 0)),
    ("/services/gait-analysis/", 200, "", 780, 55, "", "", None, "Free gait analysis", (90, 2400, 3.0), 85, (240, 62.0, 40)),
    ("/blog/replace-running-shoes/", 200, "", 1550, 16, "", "", None, "How often should you replace running shoes?", (450, 11200, 2.9), 470, (520, 88.0, 6)),
    ("/stores/london/", 200, "", 420, 40, "", "", None, "Stride & Co London", (150, 3100, 2.2), 140, (330, 44.0, 25)),
    ("/blog/running-glossary/", 200, "Canonicalised", 2600, 7, "", "", None, "Running glossary", (12, 700, 14.0), 10, (18, 70.0, 0)),
    ("/blog/winter-running-tips/", 200, "", 1100, 6, "", "", None, "Winter running tips", (6, 150, 18.2), 7, (15, 95.0, 1)),
    ("/blog/parkrun-guide/", 200, "", 1250, 11, "", "", None, "A beginner's guide to parkrun", (70, 2200, 4.8), 140, (95, 80.0, 1)),
]
GSC_ONLY = [("/blog/orphan-race-calendar/", (35, 1400, 6.5), 30)]   # gets clicks but the crawler never found it


def sf_row(p):
    path, status, ix_status, words, inl, near, sem, score, title, *_ = p
    row = {h: "" for h in SF_HEADER}
    url = SITE + path
    row.update({
        "Address": url, "Content Type": "text/html; charset=UTF-8", "Status Code": status,
        "Status": {200: "OK", 301: "Moved Permanently", 404: "Not Found"}[status],
        "Indexability": "Indexable" if not ix_status else "Non-Indexable", "Indexability Status": ix_status,
        "Title 1": title, "Title 1 Length": len(title) if title else 0, "Word Count": words, "Unique Inlinks": inl,
        "Inlinks": inl * 2, "Crawl Depth": 1 if path.count("/") <= 2 else 2, "Folder Depth": path.strip("/").count("/") + (1 if path != "/" else 0),
        "Closest Near Duplicate Match": SITE + near if near else "", "No. Near Duplicates": 1 if near else 0,
        "Closest Semantically Similar Address": SITE + sem if sem else "", "Semantic Similarity Score": score if score else "",
        "No. Semantically Similar": 1 if sem else 0, "Meta Robots 1": "noindex, follow" if ix_status == "noindex" else "",
        "Canonical Link Element 1": SITE + "/glossary/" if ix_status == "Canonicalised" else (url if status == 200 else ""),
        "Redirect URL": SITE + "/sale/" if status == 301 else "", "Redirect Type": "HTTP Redirect" if status == 301 else "",
        "Language": "en-GB", "HTTP Version": "1.1", "URL Encoded Address": url, "Crawl Timestamp": "2026-10-20 09:14:03",
    })
    return row


def main():
    OUT.mkdir(exist_ok=True)
    with open(OUT / "internal_html.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SF_HEADER, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for p in PAGES:
            w.writerow(sf_row(p))

    def gsc(name, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Top pages", "Clicks", "Impressions", "CTR", "Position"])
            for url, c, i, pos in rows:
                w.writerow([url, c, i, f"{(c / i * 100 if i else 0):.2f}%", "" if pos is None else pos])

    cur = [(SITE + p[0], *p[9]) for p in PAGES if p[9][1] > 0] + [(SITE + p, *g) for p, g, _ in GSC_ONLY]
    gsc("gsc_pages_current.csv", sorted(cur, key=lambda r: -r[1]))
    prev = []
    for p in PAGES:
        if p[10] > 0:
            imp = max(p[9][1], p[10] * 25)
            prev.append((SITE + p[0], p[10], imp, p[9][2] or 9.0))
    prev += [(SITE + p, c, c * 40, 7.0) for p, _, c in GSC_ONLY]
    gsc("gsc_pages_previous.csv", sorted(prev, key=lambda r: -r[1]))

    with open(OUT / "ga4_landing_pages.csv", "w", newline="", encoding="utf-8") as f:
        f.write("# ----------------------------------------\n# Landing page\n# Account: Stride & Co (sample)\n# Property: stride-example.com\n"
                "# ----------------------------------------\n#\n# Start date: 20260720\n# End date: 20261019\n")
        w = csv.writer(f)
        w.writerow(["Landing page + query string", "Sessions", "Active users", "New users", "Average engagement time per session",
                    "Key events", "Total revenue"])
        for p in PAGES:
            s, eng, ke = p[11]
            if s == 0:
                continue
            if p[0] == "/trail-running-shoes/":   # the same page with a tracking parameter, as GA4 reports it
                w.writerow([p[0], s - 120, int((s - 120) * 0.8), int((s - 120) * 0.6), eng, ke - 3, 0])
                w.writerow([p[0] + "?utm_source=newsletter&utm_medium=email", 120, 101, 30, eng, 3, 0])
            else:
                w.writerow([p[0], s, int(s * 0.8), int(s * 0.6), eng, ke, 0])
        w.writerow(["(not set)", 40, 38, 30, 3.2, 0, 0])
    print("sample exports written to", OUT)


if __name__ == "__main__":
    main()
