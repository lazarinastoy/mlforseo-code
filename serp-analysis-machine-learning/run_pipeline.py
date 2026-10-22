"""Scripted SERP pipeline: collect -> store -> (classify) -> measure -> report.

Run it by hand, from cron, or from GitHub Actions (see github-actions-serp-tracker.yml).
Deterministic and cheap: the only paid calls are the SERP pulls (and the
optional LLM classification).

  python run_pipeline.py --keywords keywords.txt --data-dir data --ai-mode --my-domain mlforseo.com
  python run_pipeline.py --demo        # no keys: runs the analysis steps on sample_data/

Outputs in --data-dir: the snapshot CSVs, share_of_search.csv,
citation_overlap.csv, serp_clusters.csv, (serp_labels.csv) and report.md.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import serp_automation as sa


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", help="text file, one keyword per line")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--ai-mode", action="store_true", help="also pull Google AI Mode answers")
    ap.add_argument("--classify", action="store_true", help="LLM-label the latest SERPs (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--my-domain", default=None)
    ap.add_argument("--max-spend", type=float, default=0.50, help="USD cap for DataForSEO calls in this run")
    ap.add_argument("--demo", action="store_true", help="skip collection and use sample_data/")
    args = ap.parse_args()

    data_dir = Path("sample_data" if args.demo else args.data_dir)
    out_dir = Path(args.data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.demo:
        keywords = [k.strip() for k in open(args.keywords) if k.strip() and not k.startswith("#")]
        client = sa.DataForSEO(max_spend_usd=args.max_spend)
        sa.collect(keywords, client, data_dir, ai_mode=args.ai_mode)
        print(f"Collected {len(keywords)} keywords, DataForSEO spend this run: ${client.spent:.4f}")

    snap = sa.load_snapshots(data_dir)
    org = snap["organic"]

    sos = sa.share_of_search(org)
    sos.to_csv(out_dir / "share_of_search.csv")

    if not snap["citations"].empty:
        sa.citation_overlap(snap["citations"], org).to_csv(out_dir / "citation_overlap.csv", index=False)

    if org["keyword"].nunique() > 1:
        overlap = sa.serp_overlap(org)
        sa.cluster_by_overlap(overlap).to_csv(out_dir / "serp_clusters.csv", index=False)

    if args.classify and os.environ.get("ANTHROPIC_API_KEY"):
        sa.classify_latest(snap).to_csv(out_dir / "serp_labels.csv", index=False)

    report = sa.change_report(snap, my_domain=args.my_domain)
    (out_dir / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
