"""
aio_tracker.py: AI Overview presence, cited domains and your citation share.

Part of the MLforSEO free resource library (Lazarina Stoy, MLforSEO, MIT licence).
Works on the tidy tables from dataforseo_serp.flatten() (a copy of the helper from
../dataforseo-serp-collection/ ships in this folder so it runs on its own).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from dataforseo_serp import bare_domain

BRAND_PURPLE = "#8448ef"   # your domain
NEUTRAL = "#b9b4c4"        # everyone else


def is_domain(domain: str, target: str) -> bool:
    """True if `domain` is `target` or one of its subdomains
    (blog.example.com matches example.com). www. is ignored."""
    d, t = bare_domain(domain), bare_domain(target)
    return bool(t) and (d == t or d.endswith("." + t))


def aio_presence(tables: dict[str, pd.DataFrame], my_domain: str) -> pd.DataFrame:
    """One row per keyword: is there an AI Overview, how many URLs and domains
    it cites, whether you are cited (and where), and your organic rank."""
    feats, cites, org = tables["serp_features"], tables["ai_overview_citations"], tables["organic"]
    rows = []
    for kw in feats["keyword"].unique():
        has_aio = bool((feats.query("keyword == @kw")["item_type"] == "ai_overview").any())
        c = cites[cites["keyword"] == kw] if not cites.empty else cites
        mine_c = c[c["domain"].apply(lambda d: is_domain(d, my_domain))] if not c.empty else c
        o = org[org["keyword"] == kw] if not org.empty else org
        mine_o = o[o["domain"].apply(lambda d: is_domain(d, my_domain))] if not o.empty else o
        rows.append({
            "keyword": kw,
            "has_ai_overview": has_aio,
            "cited_urls": len(c),
            "cited_domains": c["domain"].nunique() if not c.empty else 0,
            "you_cited": not mine_c.empty,
            "your_first_citation_position": int(mine_c["citation_order"].min()) if not mine_c.empty else None,
            "your_cited_urls": " | ".join(mine_c["url"]) if not mine_c.empty else "",
            "your_organic_rank": int(mine_o["rank_group"].min()) if not mine_o.empty else None,
            "top_cited_domains": ", ".join(c["domain"].drop_duplicates().head(3)) if not c.empty else "",
        })
    out = pd.DataFrame(rows)
    for col in ("your_first_citation_position", "your_organic_rank"):   # 1 not 1.0; blank, not NaN
        if col in out:
            out[col] = out[col].astype("Int64")
    return out


def citation_share(citations: pd.DataFrame, my_domain: str, n_aio_keywords: int) -> pd.DataFrame:
    """Share of all AI Overview citations by domain.

    citations       = cited URLs from that domain, across all keywords
                      (your subdomains are rolled up into your domain's row)
    share_of_citations = citations / all citations in the set
    keywords_cited_in  = AI Overviews that cite the domain at least once
    keyword_coverage   = keywords_cited_in / keywords with an AI Overview
    """
    if citations.empty:
        return pd.DataFrame(columns=["domain", "citations", "share_of_citations",
                                     "keywords_cited_in", "keyword_coverage", "is_you"])
    # Count your subdomains (help.example.com, blog.example.com) under your domain,
    # so this table agrees with aio_presence(), which already treats them as you.
    me = bare_domain(my_domain)
    citations = citations.assign(domain=citations["domain"].apply(
        lambda d: me if is_domain(d, my_domain) else d))
    g = (citations.groupby("domain")
         .agg(citations=("url", "size"), keywords_cited_in=("keyword", "nunique"))
         .reset_index())
    g["share_of_citations"] = (g["citations"] / g["citations"].sum()).round(3)
    g["keyword_coverage"] = (g["keywords_cited_in"] / max(n_aio_keywords, 1)).round(3)
    g["is_you"] = g["domain"].apply(lambda d: is_domain(d, my_domain))
    g = g.sort_values(["citations", "keywords_cited_in", "domain"], ascending=[False, False, True])
    return g[["domain", "citations", "share_of_citations", "keywords_cited_in",
              "keyword_coverage", "is_you"]].reset_index(drop=True)


def citation_gaps(presence: pd.DataFrame, citations: pd.DataFrame,
                  competitors: list[str] | None = None) -> pd.DataFrame:
    """Keywords with an AI Overview that doesn't cite you. If you give a
    competitor list, only gaps where at least one of them IS cited are kept."""
    gaps = presence[presence["has_ai_overview"] & ~presence["you_cited"]].copy()
    rows = []
    for _, r in gaps.iterrows():
        doms = citations.loc[citations["keyword"] == r["keyword"], "domain"].drop_duplicates().tolist()
        if competitors:
            doms = [d for d in doms if any(is_domain(d, c) for c in competitors)]
            if not doms:
                continue
        rows.append({"keyword": r["keyword"], "cited_instead": ", ".join(doms),
                     "your_organic_rank": r["your_organic_rank"]})
    return pd.DataFrame(rows, columns=["keyword", "cited_instead", "your_organic_rank"])


def cited_vs_ranking(tables: dict[str, pd.DataFrame], top_n: int = 10) -> pd.DataFrame:
    """Per keyword: domains both cited and ranking in the organic top N, cited
    without ranking, and ranking without being cited."""
    cites, org = tables["ai_overview_citations"], tables["organic"]
    rows = []
    for kw in cites["keyword"].unique() if not cites.empty else []:
        cited = set(cites.loc[cites["keyword"] == kw, "domain"])
        ranking = set(org.loc[(org["keyword"] == kw) & (org["rank_group"] <= top_n), "domain"])
        rows.append({"keyword": kw,
                     "cited_and_ranking": ", ".join(sorted(cited & ranking)),
                     "cited_not_ranking": ", ".join(sorted(cited - ranking)),
                     "ranking_not_cited": ", ".join(sorted(ranking - cited)),
                     "overlap_pct": round(100 * len(cited & ranking) / len(cited), 1) if cited else None})
    return pd.DataFrame(rows)


def plot_share(share: pd.DataFrame, top_n: int = 12, title: str = "Share of AI Overview citations",
               path: str | Path | None = None):
    """Horizontal bar chart of the top domains; your domain in MLforSEO purple."""
    import matplotlib.pyplot as plt

    top = share.head(top_n)
    if not top["is_you"].any() and share["is_you"].any():   # always show yourself
        top = pd.concat([top.iloc[:-1], share[share["is_you"]].head(1)])
    top = top.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(top) + 1.2))
    colors = [BRAND_PURPLE if me else NEUTRAL for me in top["is_you"]]
    ax.barh(top["domain"], top["share_of_citations"] * 100, color=colors, height=0.6)
    for y, (v, n) in enumerate(zip(top["share_of_citations"], top["citations"])):
        ax.text(v * 100 + 0.3, y, f"{v:.0%}  ({n})", va="center", fontsize=9, color="#3d3650")
    ax.set_xlabel("% of all cited URLs (count in brackets)")
    ax.set_title(title, loc="left", fontsize=12, color="#1A0B32")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, color="#ece9f2")
    ax.set_axisbelow(True)
    ax.set_xlim(0, top["share_of_citations"].max() * 100 * 1.25)
    fig.tight_layout()
    if path:
        fig.savefig(path, dpi=150)
    return fig


def append_history(presence: pd.DataFrame, history_csv: str | Path, run_date: str | None = None) -> pd.DataFrame:
    """Add today's presence table to a running history file so you can see
    AI Overview presence and your citations change week by week."""
    p = Path(history_csv)
    today = presence.assign(run_date=run_date or str(date.today()))
    if p.exists():
        today = pd.concat([pd.read_csv(p), today], ignore_index=True)
        today = today.drop_duplicates(subset=["run_date", "keyword"], keep="last")
        for col in ("your_first_citation_position", "your_organic_rank"):   # CSV reads them back as floats
            if col in today:
                today[col] = pd.to_numeric(today[col], errors="coerce").astype("Int64")
    p.parent.mkdir(parents=True, exist_ok=True)
    today.to_csv(p, index=False)
    return today
