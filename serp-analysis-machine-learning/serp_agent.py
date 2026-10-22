"""Agentic SERP analysis: Claude decides which of your analysis functions to call.

The scripted pipeline (run_pipeline.py) runs the same steps every week. This
agent is for the open question on top: "what changed for these keywords, and
what should we do about it?" It gets read-only tools over your snapshot store,
plus (optionally) one paid tool for a live SERP pull, capped by --max-live.

  python serp_agent.py --data-dir sample_data --my-domain example.com
  python serp_agent.py --data-dir data --live --max-live 3 --question "Why did we lose the AI Overview citation?"

Needs ANTHROPIC_API_KEY (and DataForSEO keys for --live). Uses the Anthropic
Python SDK's beta tool runner, which handles the tool-call loop.
"""
from __future__ import annotations

import argparse
import json

import anthropic
from anthropic import beta_tool

import serp_automation as sa

MODEL = "claude-opus-5-5"
STATE = {"data_dir": "sample_data", "live": False, "max_live": 0, "live_used": 0, "client": None}


def _snap():
    return sa.load_snapshots(STATE["data_dir"])


@beta_tool
def list_tracked_keywords() -> str:
    """List the tracked keywords and the snapshot dates available for each."""
    org = _snap()["organic"]
    return json.dumps({k: sorted(g["date"].unique().tolist()) for k, g in org.groupby("keyword")})


@beta_tool
def ranking_history(keyword: str) -> str:
    """Top-10 organic domains for a keyword at every snapshot date.

    Args:
        keyword: A tracked keyword, exactly as listed by list_tracked_keywords.
    """
    org = _snap()["organic"]
    g = org[org["keyword"] == keyword].sort_values(["date", "rank_group"])
    return json.dumps({d: x[["rank_group", "domain", "title"]].to_dict("records") for d, x in g.groupby("date")})


@beta_tool
def share_of_search(keyword: str) -> str:
    """Click-weighted share of the top 10 per domain and date, plus the biggest movers.

    Args:
        keyword: A tracked keyword.
    """
    org = _snap()["organic"]
    sos = sa.share_of_search(org[org["keyword"] == keyword])
    return json.dumps({"share": sos.round(3).to_dict(orient="index"),
                       "movers": sa.biggest_movers(sos).to_dict("records"),
                       "note": "CTR weights are an assumption (sa.CTR_CURVE)."})


@beta_tool
def ai_citations(keyword: str) -> str:
    """Which URLs Google's AI Overview / AI Mode cited per date, and how many also rank top 10.

    Args:
        keyword: A tracked keyword.
    """
    s = _snap()
    cit = s["citations"][s["citations"]["keyword"] == keyword]
    if cit.empty:
        return "No AI citations stored for this keyword."
    return json.dumps({"overlap_with_organic": sa.citation_overlap(cit, s["organic"]).to_dict("records"),
                       "cited": cit[["date", "surface", "citation_order", "domain", "title"]].to_dict("records")})


@beta_tool
def serp_features(keyword: str) -> str:
    """SERP features present (AI Overview, People Also Ask, video...) per date.

    Args:
        keyword: A tracked keyword.
    """
    f = _snap()["features"]
    return sa.feature_matrix(f[f["keyword"] == keyword]).to_json(orient="records")


@beta_tool
def fetch_live_serp(keyword: str) -> str:
    """PAID: pull today's live Google SERP (with AI Overview) for one keyword and store it.
    Only call this when the stored snapshots cannot answer the question.

    Args:
        keyword: The keyword to pull.
    """
    if not STATE["live"]:
        return "Live pulls are switched off for this run. Work from the stored snapshots."
    if STATE["live_used"] >= STATE["max_live"]:
        return f"Live-pull budget used up ({STATE['max_live']}). Work from what you have."
    STATE["client"] = STATE["client"] or sa.DataForSEO(max_spend_usd=0.05)
    sa.save_snapshot(sa.parse_serp(STATE["client"].organic(keyword)), STATE["data_dir"])
    STATE["live_used"] += 1
    return f"Stored today's SERP for {keyword!r}. Re-run the other tools to see it."


SYSTEM = """You are an SEO analyst working from stored SERP snapshots.
Use the tools to check facts before stating them; never guess a ranking or a citation.
Keep in mind: one keyword is an anecdote, CTR weights are assumptions, and snapshots
from different sources (historical database vs live pull) can differ for reasons
other than real ranking changes. Say so where it matters.
Finish with a short brief: what changed, what it likely means, 3 concrete next actions."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="sample_data")
    ap.add_argument("--my-domain", default="example.com")
    ap.add_argument("--question", default="What changed in the SERPs and AI answers we track, and what should we do next?")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-live", type=int, default=2)
    ap.add_argument("--max-turns", type=int, default=8, help="hard cap on model calls")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high"])
    args = ap.parse_args()
    STATE.update(data_dir=args.data_dir, live=args.live, max_live=args.max_live)

    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": args.effort},
        cache_control={"type": "ephemeral"},   # tools + history are re-sent every turn
        max_iterations=args.max_turns,
        tools=[list_tracked_keywords, ranking_history, share_of_search, ai_citations,
               serp_features, fetch_live_serp],
        messages=[{"role": "user", "content": f"My site: {args.my_domain}. {args.question}"}],
    )
    final = None
    for message in runner:                      # one iteration per model call
        sa.log_usage(message, "agent")
        calls = [b.name for b in message.content if b.type == "tool_use"]
        if calls:
            print(f"[turn {len(sa.LLM_USAGE)}] tools: {', '.join(calls)}")
        final = message
    print()
    print("\n".join(b.text for b in final.content if b.type == "text"))
    if final.stop_reason == "tool_use":
        print(f"\n(Stopped at the --max-turns cap of {args.max_turns} before the agent finished.)")
    cost = sum(r["usd"] for r in sa.LLM_USAGE)
    print(f"\n{len(sa.LLM_USAGE)} model calls, est. ${cost:.3f} (prices in sa.LLM_PRICES)")


if __name__ == "__main__":
    main()
