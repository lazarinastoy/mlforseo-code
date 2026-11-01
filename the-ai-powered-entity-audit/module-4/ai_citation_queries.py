"""Practical 4.3 — AI-citation analysis with the configuration Lesson 4.3 calls for, priced before
it runs, with a sample you read before you trust any aggregate.

    python ai_citation_queries.py plan topics.txt --domain yoursite.com --known "entity seo"
    #   read plan.csv: every task, why it exists, and the estimated cost — nothing has run yet
    export DATAFORSEO_LOGIN=...  DATAFORSEO_PASSWORD=...     # API Access page, not your account login
    python ai_citation_queries.py run
    #   fill the on_topic column in samples.csv (yes / no) for every row
    python ai_citation_queries.py report --brand "Your Brand"

topics.txt: one topic per line, the way a person would type it into an AI assistant.

The rules this script enforces (all from Lesson 4.3, calibrated on 31 October 2026):
  one topic per call            multi-keyword targets combine as AND, not OR — "a, b" is not two topics
  search_scope = ["question"]   the topic must be in the user's question. With the default scope,
                                "entity seo" returned 33,160 mentions led by Instagram and Facebook;
                                with question scope, 85 mentions led by Neil Patel, Schema App,
                                Search Engine Land and InLinks
  match_type = word_match       the default; partial_match is the looser one, not the tighter
  sample before aggregate       a search/live sample is pulled for every topic and must be read
  a known query                 one topic whose answer you already know, to calibrate the instrument
  date and method on everything ChatGPT data is US English only; Google = AI Overviews
"""
import argparse, base64, csv, datetime as dt, json, os, pathlib, re, sys, urllib.request
from collections import Counter

API = "https://api.dataforseo.com/v3/ai_optimization/llm_mentions"
TASK_COST, ROW_COST = 0.10, 0.001        # dataforseo.com/pricing/ai-optimization/llm-mentions, Oct 2026
GENERIC = {"entity", "entities", "semantic", "machine learning", "ai", "data", "content", "schema",
           "graph", "search", "marketing", "seo", "analytics", "automation"}


def clean_topic(raw):
    """Format one topic the way the lesson says, or explain why it cannot be used."""
    t = re.sub(r"\s+", " ", re.sub(r"[\"“”'’?!.:;]+", " ", raw.strip().lower())).strip()
    if not t:
        return None, "empty"
    if len(t) > 250:
        return None, "longer than 250 characters"
    if re.search(r",|\s/\s|\s&\s|\s\+\s|\band\b.*\band\b", t) or ("," in raw):
        return None, "looks like several topics in one line — split it: one topic per call"
    if t in GENERIC or len(t.split()) == 1:
        return t, "warning: one generic word — homonyms likely (add a qualifier, e.g. 'entity seo')"
    return t, ""


def plan(a):
    topics, notes = [], []
    for line in open(a.topics, encoding="utf-8"):
        t, why = clean_topic(line)
        if t is None:
            if why != "empty":
                notes.append([line.strip(), "SKIPPED", why])
            continue
        if t not in topics:
            topics.append(t)
            notes.append([line.strip(), t, why])
    known = clean_topic(a.known)[0] if a.known else None
    if known and known not in topics:
        topics.append(known)
    platforms = ["google"] + (["chat_gpt"] if a.location_code == 2840 and a.language_code == "en" else [])
    base = {"location_code": a.location_code, "language_code": a.language_code}
    tasks = []
    for p in platforms:
        if a.domain:
            tasks.append(dict(endpoint="search", why="scoped: answers that cite your domain",
                              rows=a.sample, body=dict(base, platform=p, limit=a.sample, tag=f"scoped|{p}|{a.domain}",
                              target=[{"domain": a.domain.replace("https://", "").replace("www.", "").strip("/"),
                                       "search_scope": ["sources"]}])))
        for t in topics:
            kind = "known" if t == known else "topic"
            tgt = [{"keyword": t, "search_scope": ["question"], "match_type": "word_match"}]
            tasks.append(dict(endpoint="search", why=f"{kind}: sample to read before trusting the aggregate",
                              rows=a.sample, body=dict(base, platform=p, limit=a.sample, target=tgt,
                              order_by=["ai_search_volume,desc"], tag=f"sample|{p}|{t}")))
            tasks.append(dict(endpoint="top_domains", why=f"{kind}: who is cited for this topic",
                              rows=10, body=dict(base, platform=p, target=tgt, links_scope="sources",
                              items_list_limit=10, internal_list_limit=1, tag=f"top|{p}|{t}")))
    cost = sum(TASK_COST + ROW_COST * t["rows"] for t in tasks)
    json.dump({"created": dt.date.today().isoformat(), "known": known, "domain": a.domain, "tasks": tasks},
              open("plan.json", "w"), indent=1)
    with open("plan.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["endpoint", "platform", "target", "why", "max_cost_usd"])
        for t in tasks:
            tg = t["body"]["target"][0]
            w.writerow([t["endpoint"], t["body"]["platform"], tg.get("keyword") or tg.get("domain"), t["why"],
                        round(TASK_COST + ROW_COST * t["rows"], 3)])
    with open("topic_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["as_written", "as_queried", "note"]); w.writerows(notes)
    print(f"{len(topics)} topics x {len(platforms)} platform(s) -> {len(tasks)} tasks, at most ${cost:.2f}")
    print("Read topic_check.csv and plan.csv. Nothing has been sent yet.")


def call(endpoint, body):
    login, pw = os.environ.get("DATAFORSEO_LOGIN"), os.environ.get("DATAFORSEO_PASSWORD")
    if not (login and pw):
        sys.exit("Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD (from app.dataforseo.com/api-access).")
    req = urllib.request.Request(f"{API}/{endpoint}/live", data=json.dumps([body]).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization":
                                          "Basic " + base64.b64encode(f"{login}:{pw}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def mentions(item):
    return sum(x.get("mentions") or 0 for x in item.get("platform") or [])


def run(a):
    p = json.load(open("plan.json")); raw = pathlib.Path("raw"); raw.mkdir(exist_ok=True)
    spent, samples, tops, along = 0.0, [], [], Counter()
    for i, t in enumerate(p["tasks"]):
        d = call(t["endpoint"], t["body"]); spent += d.get("cost") or 0
        (raw / f"{i:03d}.json").write_text(json.dumps(d, indent=1))
        task = (d.get("tasks") or [{}])[0]
        if task.get("status_code") != 20000:
            print("!", t["body"]["tag"], task.get("status_message")); continue
        res = (task.get("result") or [{}])[0] or {}
        kind, plat, target = t["body"]["tag"].split("|", 2)
        if t["endpoint"] == "search":
            for it in res.get("items") or []:
                srcs = [s.get("domain") for s in it.get("sources") or [] if s.get("domain")]
                if kind == "scoped":
                    along.update(s for s in set(srcs) if p["domain"] not in s)
                else:
                    samples.append([target, plat, it.get("question"), it.get("ai_search_volume"),
                                    re.sub(r"\s+", " ", it.get("answer") or "")[:400], "; ".join(srcs[:8]), ""])
            if kind == "sample":
                print(f"{target} [{plat}]: {res.get('total_count')} matching questions")
        else:
            for rank, it in enumerate(res.get("items") or [], 1):
                tops.append([target, plat, rank, it.get("key"), mentions(it),
                             "known" if target == p.get("known") else "topic", "unverified"])
        print(f"  {t['body']['tag']}  running total ${spent:.2f}")
    with open("samples.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["topic", "platform", "question", "ai_search_volume", "answer_excerpt",
                                       "sources", "on_topic"]); w.writerows(samples)
    with open("top_domains.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["topic", "platform", "rank", "domain", "mentions", "kind", "status"])
        w.writerows(tops)
    with open("cited_alongside.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["domain", "answers_citing_both"]); w.writerows(along.most_common(50))
    json.dump({"run_date": dt.date.today().isoformat(), "cost_usd": round(spent, 3)}, open("run.json", "w"))
    print(f"Done: ${spent:.2f}. Now mark on_topic (yes/no) for every row of samples.csv, then run report.")


def report(a):
    p, r = json.load(open("plan.json")), json.load(open("run.json"))
    s = list(csv.DictReader(open("samples.csv", encoding="utf-8")))
    tops = list(csv.DictReader(open("top_domains.csv", encoding="utf-8")))
    along = list(csv.DictReader(open("cited_alongside.csv", encoding="utf-8")))
    unread = sum(1 for x in s if x["on_topic"].strip().lower() not in ("yes", "no"))
    if unread:
        sys.exit(f"{unread} sample rows have no on_topic answer. Read them first — that is the check.")
    prec = {}
    for x in s:
        k = (x["topic"], x["platform"]); prec.setdefault(k, []).append(x["on_topic"].strip().lower() == "yes")
    L = [f"# AI visibility — {a.brand}", "",
         f"*Data: DataForSEO LLM Mentions, run {r['run_date']}. Cost ${r['cost_usd']:.2f}. "
         f"Location {p['tasks'][0]['body']['location_code']}, language {p['tasks'][0]['body']['language_code']}. "
         "Google = AI Overviews; ChatGPT data is US English only.*", "",
         "## 1. Cited alongside us (scoped — reliable)", "",
         "| Domain | Answers citing both |", "|---|---:|"]
    L += [f"| {x['domain']} | {x['answers_citing_both']} |" for x in along[:10]] or ["| — | — |"]
    L += ["", "## 2. Who is cited for each topic (topic-level)", "",
          "Each topic is labelled by the sample check: **verified** when at least 80% of the sampled "
          "questions were genuinely about the topic, **indicative** below that. Indicative rows are "
          "not used for decisions.", ""]
    for (topic, plat), flags in prec.items():
        share = sum(flags) / len(flags)
        status = "verified" if share >= 0.8 else "indicative"
        doms = [f"{x['domain']} ({x['mentions']})" for x in tops if x["topic"] == topic and x["platform"] == plat][:8]
        L += [f"**{topic}** · {plat} · {status} ({sum(flags)}/{len(flags)} sampled questions on topic)  ",
              ", ".join(doms) or "no domains returned", ""]
    L += ["## 3. Calibration", ""]
    if p.get("known"):
        L += [f"Known query: **{p['known']}**. Write here whether the returned domains match the competitive "
              "set you expected, and what that says about trusting the other topics.", ""]
    else:
        L += ["**No calibration query was run.** Treat every topic-level result as indicative until you re-run "
              "with `--known` set to a topic whose cited sites you can name.", ""]
    L += ["## 4. Method", "",
          "One topic per call; topic required in the user's question (`search_scope: question`); "
          "`match_type: word_match`; sources counted from cited links (`links_scope: sources`); a sample of "
          "answers read for every topic before its aggregate was used.", ""]
    pathlib.Path("report.md").write_text("\n".join(L), encoding="utf-8")
    print("report.md written — a draft. Add the findings and recommendations by hand.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan"); pl.add_argument("topics"); pl.add_argument("--domain", default="")
    pl.add_argument("--known", default=""); pl.add_argument("--location-code", type=int, default=2840)
    pl.add_argument("--language-code", default="en"); pl.add_argument("--sample", type=int, default=20)
    sub.add_parser("run")
    rp = sub.add_parser("report"); rp.add_argument("--brand", default="our brand")
    a = ap.parse_args()
    {"plan": plan, "run": run, "report": report}[a.cmd](a)
