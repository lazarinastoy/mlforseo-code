#!/usr/bin/env python3
"""Build the generic training set for the ensemble (Notebook 4's method in the tool).

Two parts, both made from patterns, not from anyone's search data:

1. notebook4  Notebook 4's own generator, copied verbatim (same topics, templates and random seed),
              so its 270 synthetic and 144 human queries are reproduced exactly.
2. extension  The same idea over 32 more topics in other verticals, with more template variety per
              patent query type, human queries that are questions or comparisons too (people type
              "x vs y" and "how to ..." as well), typos, and mixed capitalisation on both sides so
              the model cannot learn "capital letters = synthetic". No pet or dog topics, so the
              course's dog-harness test set stays out of domain.

    python3 generate_training_set.py --out out/generic.csv

Columns: query, label (1 = synthetic, 0 = user), source, group (topic, used for grouped CV).
"""
import argparse
import csv
import random

# --------------------------------------------------------------------------------------------
# 1. Notebook 4 generator, verbatim
# --------------------------------------------------------------------------------------------
random.seed(42)

TOPICS = [
    ("CRM software", "Salesforce", "HubSpot"),
    ("project management tools", "Asana", "Monday.com"),
    ("cloud hosting", "AWS", "Google Cloud"),
    ("email marketing", "Mailchimp", "ConvertKit"),
    ("payment gateway", "Stripe", "PayPal"),
    ("website builder", "WordPress", "Squarespace"),
    ("video conferencing", "Zoom", "Microsoft Teams"),
    ("accounting software", "QuickBooks", "Xero"),
    ("e-commerce platform", "Shopify", "WooCommerce"),
    ("cybersecurity solution", "CrowdStrike", "Palo Alto Networks"),
    ("HR software", "Workday", "BambooHR"),
    ("data analytics tool", "Tableau", "Power BI"),
    ("VPN service", "NordVPN", "ExpressVPN"),
    ("laptop", "MacBook Pro", "Dell XPS"),
    ("electric vehicle", "Tesla Model Y", "Hyundai Ioniq 5"),
]

AUDIENCES = ["small businesses", "enterprise companies", "startups", "freelancers",
             "remote teams", "agencies", "nonprofits", "educational institutions"]


def generate_synthetic_queries():
    """Generate synthetic fan-out queries following the 8 patent types."""
    queries = []
    for topic, brand_a, brand_b in TOPICS:
        audience = random.choice(AUDIENCES)

        # Type 1: Equivalent
        queries.append(f"best {topic} solutions available today")
        queries.append(f"top rated {topic} options to consider")

        # Type 2: Follow-up
        queries.append(f"how to choose the right {topic} for your needs")
        queries.append(f"what to look for when evaluating {topic}")
        queries.append(f"how to migrate from {brand_a} to {brand_b}")

        # Type 3: Generalization
        queries.append(f"complete guide to {topic} for businesses")
        queries.append(f"overview of different types of {topic}")

        # Type 4: Canonicalization
        queries.append(f"{topic} comparison and buying guide 2025")

        # Type 5: Comparative
        queries.append(f"{brand_a} vs {brand_b} features and pricing comparison")
        queries.append(f"comparison of {brand_a} and {brand_b} for {audience}")
        queries.append(f"which is better {brand_a} or {brand_b} for {audience}")

        # Type 6: Implicit
        queries.append(f"average cost of {topic} for {audience}")
        queries.append(f"customer satisfaction ratings for popular {topic}")
        queries.append(f"security and compliance features in {topic}")
        queries.append(f"common integration challenges with {topic}")

        # Type 7: Specialization
        queries.append(f"best {topic} for {audience} with limited budget")
        queries.append(f"affordable {topic} designed specifically for {audience}")
        queries.append(f"{topic} with advanced features for {audience}")

    return queries


def generate_human_queries():
    """Generate realistic human-typed queries."""
    queries = []

    # Navigational
    navs = ["amazon", "gmail", "youtube", "facebook", "reddit", "netflix",
            "spotify", "twitter", "linkedin", "github", "stackoverflow",
            "pinterest", "tiktok", "whatsapp web", "google docs",
            "outlook login", "zoom download", "slack", "notion", "figma"]
    queries.extend(navs)

    # Short informational
    for topic, _, _ in TOPICS:
        queries.append(topic.split()[0])  # Single word
        queries.append(topic)  # Just the topic
        queries.append(f"{topic} pricing")
        queries.append(f"{topic} free")
        queries.append(f"best {topic}")
        queries.append(f"{topic} review")

    # Typo/messy queries
    messy = [
        "crm softwre", "projct managment tool", "cheep hosting",
        "email mrketing", "paymnt processing", "websit builder",
        "how fix zoom audio", "laptop overheating fix", "wifi problem",
        "delete facebook account", "unsub from email", "forgot passwrd",
        "slow internet fix", "phone not charging", "screen flickerng",
        "best phone under 500", "cheap flights europe", "job openings near me",
        "resume template free", "how loose weight", "meal prep ideas",
        "gym near me cheap", "free vpn download", "tax calculator 2025",
    ]
    queries.extend(messy)

    # Conversational AI prompts (long human queries)
    conversational = [
        "can you explain how CRM systems work for someone new to sales",
        "help me decide between Shopify and WooCommerce for my small bakery",
        "what should i know before switching from gmail to outlook",
        "im looking for a cheap laptop for college nothing fancy just needs to run word and chrome",
        "tell me about electric cars are they actually worth it in 2025",
        "i need help writing a business plan for a food truck",
        "whats the deal with cloud computing i keep hearing about it",
        "my boss wants me to learn python where do i start",
        "planning a wedding on a budget any tips",
        "how do i get my website to show up on google",
    ]
    queries.extend(conversational)

    return queries


NB4_SYNTHETIC = generate_synthetic_queries()
NB4_HUMAN = generate_human_queries()


def nb4_topic_of(query):
    """Group label for grouped cross-validation."""
    low = query.lower()
    for topic, a, b in TOPICS:
        if topic.lower() in low or a.lower() in low or b.lower() in low:
            return "nb4:" + topic
    return "nb4:other"


# --------------------------------------------------------------------------------------------
# 2. Extension (not in the notebook): more topics, more templates per patent type, more human forms
# --------------------------------------------------------------------------------------------
EXT_TOPICS = [
    # topic, the topic with an article, brand/product A, brand/product B, a typical use, a typical problem
    ("running shoes", "a pair of running shoes", "Nike Pegasus", "Brooks Ghost", "marathon training", "heel pain"),
    ("espresso machine", "an espresso machine", "Breville Barista Express", "De'Longhi Dedica", "making lattes at home", "leaking water"),
    ("robot vacuum", "a robot vacuum", "Roomba j7", "Roborock S8", "homes with carpets", "getting stuck"),
    ("mattress", "a mattress", "Casper", "Purple", "back pain", "sagging"),
    ("air fryer", "an air fryer", "Ninja", "Cosori", "cooking for one", "smoking"),
    ("travel insurance", "travel insurance", "Allianz", "World Nomads", "backpacking in Asia", "claims being denied"),
    ("credit card", "a credit card", "Chase Sapphire", "Amex Gold", "earning travel points", "high interest"),
    ("language learning app", "a language learning app", "Duolingo", "Babbel", "learning Spanish", "losing motivation"),
    ("meal kit", "a meal kit", "HelloFresh", "Blue Apron", "busy weeknights", "too much packaging"),
    ("standing desk", "a standing desk", "Uplift", "Flexispot", "a home office", "wobbling"),
    ("noise cancelling headphones", "noise cancelling headphones", "Sony WH-1000XM5", "Bose QuietComfort", "long flights", "ear pain"),
    ("electric toothbrush", "an electric toothbrush", "Oral-B", "Philips Sonicare", "sensitive gums", "battery dying"),
    ("home security camera", "a home security camera", "Ring", "Arlo", "apartments", "false alerts"),
    ("password manager", "a password manager", "1Password", "Bitwarden", "families", "sync errors"),
    ("online course platform", "an online course platform", "Coursera", "Udemy", "career changers", "low completion rates"),
    ("road bike", "a road bike", "Trek", "Specialized", "commuting", "flat tyres"),
    ("smart watch", "a smart watch", "Apple Watch", "Garmin Fenix", "tracking runs", "short battery life"),
    ("web hosting", "web hosting", "Bluehost", "SiteGround", "small blogs", "slow load times"),
    ("SEO tool", "an SEO tool", "Ahrefs", "Semrush", "keyword research", "data accuracy"),
    ("note taking app", "a note taking app", "Notion", "Evernote", "students", "slow sync"),
    ("car insurance", "car insurance", "Geico", "Progressive", "new drivers", "premium increases"),
    ("baby stroller", "a baby stroller", "UPPAbaby Vista", "Bugaboo Fox", "city living", "heavy folding"),
    ("hiking boots", "a pair of hiking boots", "Salomon", "Merrell", "wet trails", "blisters"),
    ("coffee grinder", "a coffee grinder", "Baratza Encore", "Fellow Ode", "pour over coffee", "uneven grind"),
    ("dishwasher", "a dishwasher", "Bosch", "Miele", "large families", "dishes not drying"),
    ("e-reader", "an e-reader", "Kindle Paperwhite", "Kobo Clara", "reading at night", "screen glare"),
    ("gaming laptop", "a gaming laptop", "ASUS ROG", "Razer Blade", "streaming games", "overheating"),
    ("yoga mat", "a yoga mat", "Manduka", "Lululemon", "hot yoga", "slipping"),
    ("camping tent", "a camping tent", "REI Half Dome", "Big Agnes Copper Spur", "backpacking trips", "condensation"),
    ("savings account", "a savings account", "Ally", "Marcus", "an emergency fund", "falling rates"),
    ("wireless router", "a wireless router", "Eero", "TP-Link Deco", "large houses", "dropped connections"),
    ("skincare serum", "a skincare serum", "The Ordinary", "La Roche-Posay", "dry skin", "breakouts"),
]
EXT_AUDIENCES = ["beginners", "families", "students", "small apartments", "seniors", "frequent travellers",
                 "professionals", "people on a budget", "remote workers", "first-time buyers"]
EXT_FEATURES = ["long battery life", "a long warranty", "easy setup", "good customer support", "low running costs"]


def r_year(rnd):
    return rnd.choice(["2024", "2025", "2026"])


def r_price(rnd):
    return rnd.choice(["50", "100", "150", "200", "300", "500", "1000"])


def synthetic_ext(rnd, topic, art, a, b, use, problem):
    aud = rnd.choice(EXT_AUDIENCES)
    aud2 = rnd.choice(EXT_AUDIENCES)
    feat = rnd.choice(EXT_FEATURES)
    y, p = r_year(rnd), r_price(rnd)
    by_type = {
        "equivalent": [f"top rated {topic} options to consider", f"most recommended {topic} right now",
                       f"highest rated {topic} according to reviews", f"well reviewed {topic} worth buying"],
        "follow_up": [f"how to set up {art} for the first time", f"what to do after buying {art}",
                      f"how long does {art} last with regular use", f"how to clean and maintain {art}",
                      f"how to get the most out of {a}", f"what accessories do you need for {art}"],
        "generalization": [f"different types of {topic} explained", f"what is {art} and how does it work",
                           f"{topic} basics for {aud}", f"everything you need to know about {topic}"],
        "canonicalization": [f"{topic} buying guide {y}", f"{a} specifications and key features",
                             f"{topic} definition and main features", f"{a} {topic} full review {y}"],
        "comparative": [f"{a} vs {b} which is better for {aud}", f"{a} or {b} for {use} which should I choose",
                        f"how does {a} compare to {b} for {use}", f"differences between {a} and {b} for {aud2}",
                        f"{a} compared to {b} pros and cons", f"is {a} better than {b} for {use}"],
        "implicit": [f"is {art} worth the money for {aud}", f"common problems with {a} and how to fix them",
                     f"how much does {art} cost in {y}", f"{a} warranty and customer support experiences",
                     f"hidden costs of {topic} most people overlook", f"what do owners say about {problem} on the {a}"],
        "specialization": [f"best {topic} for {aud} under {p} dollars", f"best {topic} for {use} in {y}",
                           f"{topic} for {aud} with {feat}", f"most durable {topic} for {use}",
                           f"best {topic} for {aud} that avoids {problem}"],
    }
    out = []
    for qtype, qs in by_type.items():
        for q in rnd.sample(qs, k=min(len(qs), 3)):
            out.append((q, qtype))
    return out


def typo(rnd, word):
    if len(word) < 5 or not word.isalpha():
        return word
    i = rnd.randrange(1, len(word) - 1)
    op = rnd.choice(["drop", "swap", "double"])
    if op == "drop":
        return word[:i] + word[i + 1:]
    if op == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    return word[:i] + word[i] + word[i:]


def human_ext(rnd, topic, art, a, b, use, problem):
    t = topic.lower()
    al, bl = a.lower(), b.lower()
    head = t.split()[-1]
    pool = [
        t, f"{t} reviews", f"best {t}", f"cheap {t}", f"{t} sale", f"{t} near me", f"{al}", f"{al} price",
        f"{al} {head}", f"{al} vs {bl}", f"{al} or {bl}", f"{t} {r_year(rnd)}", f"best {t} {r_year(rnd)}",
        f"{t} under {r_price(rnd)}", f"how to clean {t}", f"how to use {al}", f"{al} not working",
        f"{t} {problem}", f"{al} {problem}", f"{al} reddit", f"{al} manual",
        f"what is the best {t}", f"which {t} should i buy", f"how much is {art.lower()}", f"{t} for {use}",
        f"{al} discount code", f"{al} customer service", f"is {al} worth it", f"{t} black friday",
        f"{t} vs", f"second hand {t}",
    ]
    picks = rnd.sample(pool, k=14)
    out = [(q, "short") for q in picks]
    # typos
    for q in rnd.sample(picks, k=3):
        words = q.split()
        j = rnd.randrange(len(words))
        words[j] = typo(rnd, words[j])
        out.append((" ".join(words), "typo"))
    # conversational prompts people type into AI search (long, first person, no punctuation)
    convo = [
        f"having issues with {problem} on my {al} what should i do",
        f"is it worth getting {art.lower()} if i only need it for {use.lower()}",
        f"need {art.lower()} for my mum who is 70 any suggestions",
        f"thinking about buying {al} but not sure if its worth the money",
        f"what {t} would you recommend for someone who knows nothing about them",
        f"i have about {r_price(rnd)} to spend on {art.lower()} what are my options",
    ]
    for q in rnd.sample(convo, k=2):
        out.append((q, "conversational"))
    return out


def recase(rnd, q, label):
    """Mixed capitalisation on both sides, so capitals alone do not separate the classes."""
    r = rnd.random()
    if label == 1:
        return q.lower() if r < 0.5 else q              # half of synthetic lists are lower-cased by tools
    if r < 0.08:
        return q[:1].upper() + q[1:]                     # some people capitalise the first word
    if r < 0.14:
        return " ".join(w.capitalize() if w.isalpha() and len(w) > 3 else w for w in q.split())
    return q.lower()


def build():
    rows = []
    for q in NB4_SYNTHETIC:
        rows.append((q, 1, "notebook4", nb4_topic_of(q)))
    for q in NB4_HUMAN:
        rows.append((q, 0, "notebook4", nb4_topic_of(q)))
    rnd = random.Random(2026)
    for topic, art, a, b, use, problem in EXT_TOPICS:
        g = "ext:" + topic
        for q, _ in synthetic_ext(rnd, topic, art, a, b, use, problem):
            rows.append((recase(rnd, q, 1), 1, "extension", g))
        for q, _ in human_ext(rnd, topic, art, a, b, use, problem):
            rows.append((recase(rnd, q, 0), 0, "extension", g))
    seen, out = set(), []
    for r in rows:                                   # drop exact duplicates, keep the first
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/generic.csv")
    args = ap.parse_args()
    rows = build()
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "label", "source", "group"])
        w.writerows(rows)
    n1 = sum(r[1] for r in rows)
    nb4 = [r for r in rows if r[2] == "notebook4"]
    print(f"{len(rows)} queries ({n1} synthetic, {len(rows) - n1} user); notebook 4 part: {len(nb4)}"
          f" ({sum(r[1] for r in nb4)} synthetic) -> {args.out}")


if __name__ == "__main__":
    main()
