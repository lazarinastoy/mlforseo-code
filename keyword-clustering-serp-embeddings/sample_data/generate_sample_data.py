"""
Generate the SYNTHETIC sample data used by keyword_clustering.ipynb.

Everything this script writes is made up:
  * the keywords are realistic home-coffee searches, but the volumes are
    invented (rounded to the buckets keyword tools use);
  * the "SERP" URLs are generated from fictional domains ending in .example,
    so they cannot be mistaken for real rankings.

How the fake SERPs are built (so you know what the notebook should find):
  * every keyword belongs to one "SERP group" (keywords Google would plausibly
    answer with the same pages, e.g. 'cold brew recipe' + 'cold brew ratio');
  * each group has its own pool of ranking URLs, each topic has a few hub
    URLs that rank across the topic, and a handful of big generic pages
    show up anywhere;
  * a keyword's top 10 = mostly URLs from its group pool + 1-3 topic hub URLs
    + the occasional generic page, shuffled by a seeded random generator.
  * a few keywords get no SERP data at all, to show how the hybrid method
    falls back to embeddings.

Run:  python generate_sample_data.py   (writes keywords.csv and serp_top10.csv)
"""
import csv
import hashlib
import random
from pathlib import Path

random.seed(42)
HERE = Path(__file__).parent

# topic -> {serp_group: [keywords]}  (first keyword in each group is the head term)
TOPICS = {
    "espresso-machines": {
        "best-espresso-machine": [
            "best espresso machine", "best espresso machine for home", "best espresso machine under 500",
            "best home espresso machine 2026", "top rated espresso machines", "best budget espresso machine",
            "best espresso machine for beginners", "espresso machine reviews",
        ],
        "how-espresso-machines-work": [
            "how does an espresso machine work", "how to use an espresso machine", "espresso machine parts explained",
            "what is a portafilter", "single boiler vs dual boiler", "what is a heat exchanger espresso machine",
            "espresso machine pressure bars explained",
        ],
        "buy-espresso-machine": [
            "espresso machine sale", "buy espresso machine", "espresso machine deals", "refurbished espresso machine",
            "cheap espresso machine", "espresso machine black friday",
        ],
        "espresso-troubleshooting": [
            "espresso tastes sour", "espresso tastes bitter", "why is my espresso watery", "espresso channeling",
            "espresso shot running too fast", "espresso machine not pumping water",
        ],
    },
    "grinders": {
        "best-grinder": [
            "best coffee grinder", "best burr grinder", "best espresso grinder", "best coffee grinder for pour over",
            "best manual coffee grinder", "best budget burr grinder", "coffee grinder reviews",
        ],
        "burr-vs-blade": [
            "burr vs blade grinder", "conical vs flat burr", "what is a burr grinder", "are blade grinders bad",
            "stepped vs stepless grinder",
        ],
        "grind-size": [
            "coffee grind size chart", "grind size for french press", "grind size for espresso",
            "grind size for pour over", "how fine to grind coffee for moka pot", "how to dial in espresso grind",
            "grind size for cold brew",
        ],
        "grinder-maintenance": [
            "how to clean a coffee grinder", "grinder retention", "how to calibrate burr grinder",
            "coffee grinder cleaning tablets",
        ],
    },
    "cold-brew": {
        "cold-brew-recipe": [
            "cold brew recipe", "how to make cold brew at home", "cold brew ratio", "cold brew coffee to water ratio",
            "how long to steep cold brew", "cold brew concentrate recipe", "easy cold brew recipe",
        ],
        "cold-brew-makers": [
            "best cold brew maker", "cold brew coffee maker", "cold brew pitcher", "best cold brew system",
            "toddy cold brew system review", "mason jar cold brew kit",
        ],
        "cold-brew-vs-iced": [
            "cold brew vs iced coffee", "does cold brew have more caffeine", "is cold brew less acidic",
            "cold brew vs nitro", "how long does cold brew last in the fridge",
        ],
    },
    "pour-over": {
        "pour-over-method": [
            "how to make pour over coffee", "pour over coffee ratio", "pour over technique", "v60 recipe",
            "chemex recipe", "pour over bloom time", "best pour over recipe",
        ],
        "pour-over-gear": [
            "best pour over coffee maker", "v60 vs chemex", "best gooseneck kettle", "pour over coffee kit",
            "best coffee scale for pour over", "kalita wave vs v60",
        ],
        "pour-over-vs-other": [
            "pour over vs french press", "pour over vs drip coffee", "is pour over better than drip",
        ],
    },
    "coffee-beans": {
        "best-beans": [
            "best coffee beans", "best coffee beans for espresso", "best whole bean coffee",
            "best coffee beans for cold brew", "best coffee subscription", "best coffee beans for french press",
        ],
        "roast-levels": [
            "light vs dark roast", "what is medium roast coffee", "does dark roast have more caffeine",
            "light roast vs dark roast caffeine", "espresso roast vs dark roast", "what is a blonde roast",
        ],
        "origins-and-process": [
            "arabica vs robusta", "what is single origin coffee", "ethiopian coffee flavor profile",
            "colombian coffee vs brazilian coffee", "washed vs natural process coffee",
            "what does honey processed coffee mean",
        ],
        "bean-storage": [
            "how to store coffee beans", "do coffee beans go bad", "should you freeze coffee beans",
            "how long do coffee beans last after roasting", "best coffee canister",
        ],
    },
    "milk-and-latte-art": {
        "latte-art": [
            "how to do latte art", "latte art for beginners", "how to pour a latte art heart",
            "latte art rosetta tutorial", "latte art tulip", "why can't i do latte art",
        ],
        "steaming-milk": [
            "how to steam milk for latte", "how to froth milk without a frother", "microfoam vs macrofoam",
            "best milk for latte art", "best oat milk for frothing", "milk temperature for latte",
        ],
        "milk-frothers": [
            "best milk frother", "handheld milk frother", "electric milk frother", "nespresso aeroccino review",
            "best milk frother for oat milk",
        ],
        "drink-definitions": [
            "latte vs cappuccino", "flat white vs latte", "what is a cortado", "what is a macchiato",
            "cappuccino vs macchiato", "what is a gibraltar coffee",
        ],
    },
    "cleaning-and-water": {
        "descaling": [
            "how to descale espresso machine", "how to descale a coffee maker", "descaling solution vs vinegar",
            "how often to descale espresso machine", "best descaler for espresso machine",
            "descale with citric acid",
        ],
        "backflushing": [
            "how to backflush espresso machine", "how to clean espresso machine group head",
            "how to clean portafilter", "espresso machine cleaning tablets", "how to clean a steam wand",
        ],
        "coffee-water": [
            "best water for espresso", "water hardness for coffee", "does water quality affect coffee taste",
            "third wave water review", "how to make coffee water at home",
        ],
    },
    "caffeine-and-decaf": {
        "caffeine-content": [
            "how much caffeine in espresso", "how much caffeine in a cup of coffee",
            "caffeine in cold brew vs regular coffee", "how much caffeine is too much", "caffeine in decaf coffee",
        ],
        "decaf-process": [
            "how is decaf coffee made", "swiss water process decaf", "is decaf coffee bad for you",
            "co2 decaf process", "does decaf coffee have caffeine",
        ],
        "best-decaf": [
            "best decaf coffee", "best decaf coffee beans", "best decaf espresso", "best decaf coffee pods",
        ],
    },
}

# Fictional domains (all .example, so nobody mistakes these for real rankings)
REVIEW_SITES = ["brewgearlab", "homebaristahq", "thecoffeebench", "cupandcrema", "grindreport", "kitchenkitreviews"]
GUIDE_SITES = ["brewschool", "coffeefundamentals", "roastnotes", "slowpourjournal", "baristabasics", "thebeanblog"]
SHOP_SITES = ["espressoshop", "cafeoutlet", "brewdepot", "homecoffeestore"]
FORUM_SITES = ["coffeeforum", "baristachat"]


def generic_urls(kw):
    """Big generic pages: one encyclopedia page that ranks everywhere, plus a video,
    a marketplace search and a forum thread that are specific to the keyword
    (on real SERPs these differ per query, so they shouldn't create overlap)."""
    slug = kw.replace(" ", "-").replace("'", "")
    vid = hashlib.md5(kw.encode()).hexdigest()[:11]
    return ["https://en.encyclo.example/wiki/Coffee", f"https://videotube.example/watch?v={vid}",
            f"https://bigmarket.example/s?k={kw.replace(' ', '+')}", f"https://coffeeforum.example/t/{slug}"]

# Keywords whose real-world SERPs tend to blend two groups. About 40% of their
# top 10 is drawn from the second group, which makes the clustering less tidy
# (as real SERPs are).
BRIDGES = {
    "best coffee beans for cold brew": "cold-brew-recipe",
    "best coffee beans for espresso": "best-espresso-machine",
    "grind size for cold brew": "cold-brew-recipe",
    "grind size for espresso": "espresso-troubleshooting",
    "how to dial in espresso grind": "espresso-troubleshooting",
    "best espresso grinder": "best-espresso-machine",
    "does cold brew have more caffeine": "caffeine-content",
    "caffeine in decaf coffee": "decaf-process",
    "best milk for latte art": "latte-art",
    "espresso machine cleaning tablets": "descaling",
    "best coffee grinder for pour over": "pour-over-gear",
    "best decaf espresso": "best-beans",
    "pour over vs french press": "pour-over-method",
    "how to clean a steam wand": "steaming-milk",
}

# A few head terms get hand-set (still invented) volumes so the biggest
# clusters look like a real coffee niche; everything else is random.
HEAD_VOLUMES = {
    "best espresso machine": 18100, "latte vs cappuccino": 12100, "best coffee beans": 9900,
    "best coffee grinder": 9900, "cold brew recipe": 8100, "best milk frother": 6600,
    "how much caffeine in espresso": 6600, "how to make pour over coffee": 3600,
    "how to descale espresso machine": 2900, "best decaf coffee": 2400, "best water for espresso": 880,
}

VOLUME_BUCKETS = [10, 20, 30, 40, 50, 70, 90, 110, 140, 170, 210, 260, 320, 390, 480, 590, 720, 880, 1000,
                  1300, 1600, 1900, 2400, 2900, 3600, 4400, 5400, 6600, 8100, 9900, 12100, 14800, 18100]


def bucket(v):
    return min(VOLUME_BUCKETS, key=lambda b: abs(b - v))


def sites_for(group):
    if group.startswith("best") or "makers" in group or "frothers" in group or "gear" in group:
        return REVIEW_SITES + SHOP_SITES[:2]
    if group.startswith("buy"):
        return SHOP_SITES + REVIEW_SITES[:2]
    if "troubleshooting" in group or "maintenance" in group:
        return GUIDE_SITES + FORUM_SITES
    return GUIDE_SITES + REVIEW_SITES[:2]


def make_pool(group, n):
    sites = sites_for(group)
    pool = []
    for i in range(n):
        site = sites[i % len(sites)]
        suffix = "" if i < len(sites) else f"-{i // len(sites) + 1}"
        pool.append(f"https://www.{site}.example/{group}{suffix}/")
    return pool


POOLS = {group: make_pool(group, 13) for groups in TOPICS.values() for group in groups}

keyword_rows, serp_rows = [], []
for topic, groups in TOPICS.items():
    hub_pool = [f"https://www.{s}.example/{topic}-guide/" for s in GUIDE_SITES[:3] + REVIEW_SITES[:3]]
    for group, keywords in groups.items():
        pool = POOLS[group]
        for i, kw in enumerate(keywords):
            # head term gets the most volume; the rest tail off (all invented)
            base = random.lognormvariate(5.2, 0.8) * (5 if i == 0 else 1)
            keyword_rows.append({"keyword": kw, "volume": HEAD_VOLUMES.get(kw, bucket(base))})

            # ~6% of keywords have no SERP export (shows the hybrid fallback)
            if random.random() < 0.06 and i > 0:
                continue
            n_group = random.choice([4, 5, 6, 7, 7, 8])                  # long tail = less stable SERPs
            n_hub = random.choice([1, 2, 2, 3])
            urls = random.sample(pool[:9], k=n_group)                    # core pages for the group
            if kw in BRIDGES:                                            # blended SERP
                urls = urls[:3] + random.sample(POOLS[BRIDGES[kw]][:9], k=4)
            urls += [u for u in random.sample(hub_pool, k=n_hub) if u not in urls]  # topic hubs
            while len(urls) < 10:
                extra = random.choice(generic_urls(kw) + pool[9:])       # generic pages + deeper group pages
                if extra not in urls:
                    urls.append(extra)
            urls = urls[:10]
            random.shuffle(urls)
            for rank, url in enumerate(urls, start=1):
                serp_rows.append({"keyword": kw, "rank": rank, "url": url})

with open(HERE / "keywords.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["keyword", "volume"])
    w.writeheader()
    w.writerows(keyword_rows)

with open(HERE / "serp_top10.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["keyword", "rank", "url"])
    w.writeheader()
    w.writerows(serp_rows)

print(f"{len(keyword_rows)} keywords, {len({r['keyword'] for r in serp_rows})} with SERP data, "
      f"{len(serp_rows)} SERP rows")
