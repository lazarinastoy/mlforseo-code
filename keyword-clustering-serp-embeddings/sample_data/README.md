# Sample data (synthetic)

**Everything in this folder is made up.** It exists so the notebook runs end to end without an API key or a paid SEO tool.

| File | What it is |
|---|---|
| `keywords.csv` | 160 home-coffee keywords across 8 topics (espresso machines, grinders, cold brew, pour over, beans, milk and latte art, cleaning and water, caffeine and decaf). The keywords are realistic searches; **the volumes are invented** (a few head terms set by hand, the rest random, rounded to the buckets keyword tools use). |
| `serp_top10.csv` | A **synthetic** top 10 for 157 of the keywords (three have none on purpose, to show the fallback). One row per ranking URL: `keyword`, `rank`, `url`. All URLs sit on fictional `.example` domains, so they can't be mistaken for real rankings. |
| `generate_sample_data.py` | The script that made both files (seeded, so it reproduces exactly). Read its docstring to see how the fake SERPs are built. |

How the fake SERPs behave: each keyword belongs to a hidden "SERP group" (keywords one page could plausibly rank for), and most of its top 10 comes from that group's URL pool, plus a few topic-wide hub pages and some per-keyword video, marketplace and forum results. A handful of keywords deliberately blend two groups, as real SERPs often do. That gives the notebook something realistic to disagree about, but it is not evidence of how any real SERP looks.

To use your own data, set `USE_SAMPLE = False` in the notebook and point it at your files with the same column names.
