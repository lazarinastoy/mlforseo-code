"""
Generate the SYNTHETIC Search Console sample used by the notebook.

Nothing here is real data. "Brewly" (www.brewly.example) is a made-up coffee equipment
shop with a blog, and every number is simulated. The scenarios are written to cover the
cases the checker has to tell apart: true cannibalisation (two similar pages taking turns),
mixed-intent results (a product page and a guide both ranking), brand queries with
sitelinks, one clear winner with a weak second page, and URL variants (fragments,
tracking parameters, missing trailing slashes) that are really one page.

Run:  python make_sample_data.py   ->  writes gsc_sample_SYNTHETIC.csv
"""
import csv
import datetime as dt
import math
import random

random.seed(42)
SITE = "https://www.brewly.example"
START = dt.date(2026, 8, 1)
DAYS = 56

# Rough CTR by position (illustrative only, a typical-looking curve)
def ctr_at(pos):
    return max(0.004, 0.32 * math.exp(-0.32 * (pos - 1)))


def visibility(pos):
    """Share of the query's searches where a result at this position is seen (impression)."""
    if pos <= 10:
        return 1.0
    if pos <= 20:
        return 0.35
    return 0.08


def rotating(period, phase=0):
    """1 when this page 'leads' on day d, 0 when the other page leads."""
    return lambda d: 1 if ((d + phase) // period) % 2 == 0 else 0


# Each scenario: queries with daily search demand, and pages with a position function of the day.
# position(d) returns None when the page doesn't show that day.
def jitter(x, s=0.8):
    return max(1.0, random.gauss(x, s))


def scenario_rows():
    lead = rotating(6)
    lead_b = rotating(9, phase=3)
    scenarios = [
        # A. True cannibalisation: two similar blog posts take turns ranking
        (["french press vs pour over", "pour over vs french press"], [140, 60], {
            "/blog/french-press-vs-pour-over/": lambda d: jitter(6) if lead(d) else (jitter(14) if random.random() < 0.5 else None),
            "/blog/pour-over-coffee-guide/": lambda d: jitter(7) if not lead(d) else (jitter(15) if random.random() < 0.5 else None),
        }),
        # B. Recipe page vs guide, plus a jump-link fragment URL of the guide
        (["cold brew ratio", "cold brew coffee ratio"], [210, 70], {
            "/recipes/cold-brew/": lambda d: jitter(4) if lead_b(d) else jitter(9),
            "/blog/cold-brew-guide/": lambda d: jitter(5) if not lead_b(d) else (jitter(11) if random.random() < 0.6 else None),
            "/blog/cold-brew-guide/#ratio": lambda d: jitter(5) if (not lead_b(d) and random.random() < 0.4) else None,
        }),
        # C. Mixed intent: product page and an explainer both rank, every day, no rotation
        (["burr grinder"], [320], {
            "/products/burr-grinder-pro/": lambda d: jitter(8, 1.0),
            "/blog/what-is-a-burr-grinder/": lambda d: jitter(5, 0.7),
        }),
        # D. Three-way split: new list post, last year's list post, and the shop category
        (["best coffee grinder", "best coffee grinders"], [260, 120], {
            "/blog/best-coffee-grinders/": lambda d: jitter(7) if lead(d) else jitter(12),
            "/blog/best-burr-grinders-2025/": lambda d: jitter(8) if not lead(d) else (jitter(16) if random.random() < 0.5 else None),
            "/collections/grinders/": lambda d: jitter(18, 2) if random.random() < 0.7 else None,
        }),
        # E. Brand query with sitelinks: several pages, all near the top, every day
        (["brewly"], [180], {
            "/": lambda d: jitter(1.0, 0.1),
            "/shop/": lambda d: jitter(2.0, 0.3),
            "/about/": lambda d: jitter(2.6, 0.4),
            "/contact/": lambda d: jitter(3.0, 0.4),
        }),
        # F. Brand + product
        (["brewly grinder"], [45], {
            "/products/burr-grinder-pro/": lambda d: jitter(1.2, 0.2),
            "/": lambda d: jitter(2.5, 0.4),
        }),
        # G. One clear winner, weak second page
        (["how to descale an espresso machine", "how to descale espresso machine"], [150, 90], {
            "/blog/how-to-descale-an-espresso-machine/": lambda d: jitter(3, 0.5),
            "/blog/espresso-machine-maintenance/": lambda d: jitter(17, 2) if random.random() < 0.35 else None,
        }),
        # H. Two similar guides splitting a query fairly evenly, both shown most days
        (["espresso machine cleaning"], [130], {
            "/blog/espresso-machine-maintenance/": lambda d: jitter(5, 1.0),
            "/blog/how-to-descale-an-espresso-machine/": lambda d: jitter(7.5, 1.2) if random.random() < 0.85 else None,
        }),
        # I. Single page, with a tracking-parameter variant (should merge, not be flagged)
        (["aeropress recipe"], [190], {
            "/recipes/aeropress/": lambda d: jitter(3, 0.5),
            "/recipes/aeropress/?utm_source=newsletter": lambda d: jitter(3, 0.5) if random.random() < 0.2 else None,
        }),
        # J. Dominant page plus a deep, irrelevant ranking (below the impression-share floor)
        (["pour over ratio"], [160], {
            "/recipes/pour-over/": lambda d: jitter(3, 0.5),
            "/blog/pour-over-coffee-guide/": lambda d: jitter(38, 4) if random.random() < 0.25 else None,
        }),
        # K. Ordinary single-page queries (most of a real export looks like this)
        (["how to make cold brew"], [240], {"/blog/cold-brew-guide/": lambda d: jitter(4, 0.6)}),
        (["chemex vs v60"], [110], {
            "/blog/chemex-vs-v60/": lambda d: jitter(4, 0.6),
            "/blog/chemex-vs-v60": lambda d: jitter(4, 0.6) if random.random() < 0.15 else None,  # missing slash
        }),
        (["coffee to water ratio"], [300], {"/blog/coffee-to-water-ratio/": lambda d: jitter(6, 1.0)}),
        (["espresso grind size"], [120], {"/blog/espresso-grind-size/": lambda d: jitter(5, 0.8)}),
        (["brewly discount code"], [25], {"/promotions/": lambda d: jitter(1.5, 0.3)}),
        (["gooseneck kettle"], [200], {"/products/gooseneck-kettle/": lambda d: jitter(11, 1.5)}),
    ]
    rows = []
    for queries, demands, pages in scenarios:
        for query, demand in zip(queries, demands):
            for d in range(DAYS):
                day = START + dt.timedelta(days=d)
                weekday_factor = 0.8 if day.weekday() >= 5 else 1.05
                searches = max(1, int(random.gauss(demand * weekday_factor, demand * 0.12)))
                for path, pos_fn in pages.items():
                    pos = pos_fn(d)
                    if pos is None:
                        continue
                    impressions = sum(1 for _ in range(searches) if random.random() < visibility(pos))
                    if impressions == 0:
                        continue
                    clicks = sum(1 for _ in range(impressions) if random.random() < ctr_at(pos))
                    rows.append({
                        "date": day.isoformat(), "query": query, "page": SITE + path,
                        "clicks": clicks, "impressions": impressions,
                        "ctr": round(clicks / impressions, 4), "position": round(pos, 1),
                    })
    return rows


if __name__ == "__main__":
    rows = scenario_rows()
    rows.sort(key=lambda r: (r["date"], r["query"], r["page"]))
    with open("gsc_sample_SYNTHETIC.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows")
