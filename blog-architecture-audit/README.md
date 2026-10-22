# Blog architecture audit

Companion code for the MLforSEO guide **"Blog and Site Architecture for SEO and Conversions in the AI Search Era"** by Lazarina Stoy.

## What it does

`blog_architecture_audit.py` checks how a blog (or a whole site) is structured. It answers five questions:

| # | Question | Output |
|---|---|---|
| 1 | **Click depth.** How many clicks from the homepage is each page? Which pages are deeper than 3 clicks? | `pages.csv` (`click_depth`, `too_deep`) |
| 2 | **URL depth vs click depth.** Which pages look shallow in their URL but are buried in the links? | `pages.csv` (`url_depth`, `depth_gap`) |
| 3 | **Orphans.** Which sitemap URLs have no internal links? Which are unreachable from the homepage? Which posts have at most one contextual (in-content) link? | `orphans.csv`, `pages.csv` (`unique_inlinks`, `contextual_inlinks`) |
| 4 | **Category balance.** How many posts are in each section? Which sections are thin (<3 posts) or dominant (>40%)? | `sections.csv` |
| 5 | **Hub coverage.** Does each hub or category page link to all the posts in its folder, or only the latest few? | `hubs.csv` |

It also counts tag, author, date-archive, pagination and parameter URLs found in the crawl ("archive hygiene"). Everything is summarised in `summary.md`, which is also printed to the console.

## Two input modes

**A) Sitemap mode.** The script reads your XML sitemap or sitemap index (recursively; `.gz` is supported). It then crawls from the homepage, following normal `<a href>` links on the same host. It skips nofollow links, assets, admin, feed and search URLs. Links inside `<nav>`, `<header>` and `<footer>` are counted separately as navigation links, so "contextual inlinks" means links from the body of a page.

```bash
python blog_architecture_audit.py --sitemap https://www.example.com/sitemap_index.xml
```

**B) Screaming Frog mode.** No crawling. Use exports from a crawl you've already run:

- `internal_html.csv`: the Internal tab, HTML filter, Export
- `all_inlinks.csv` (optional): Bulk Export > Links > All Inlinks. You need this file for hub coverage and the contextual/navigation link split. It uses the "Link Position" column.

```bash
python blog_architecture_audit.py --sf-internal internal_html.csv \
    --sf-inlinks all_inlinks.csv --sitemap https://www.example.com/sitemap.xml
```

`--sitemap` is optional in this mode. Add it to find orphans.

## Useful options

| Option | Default | What it does |
|---|---|---|
| `--max-pages` | 1500 | Crawl limit (sitemap mode) |
| `--delay` | 0.5 | Seconds between requests. Be polite; only crawl sites you own or have permission to crawl |
| `--max-click-depth` | 3 | Pages deeper than this are flagged |
| `--section-level` | 0 | How to group posts into sections: 0 = parent folder; N = first N path segments |
| `--post-pattern` | auto | Regex that identifies posts, e.g. `'/blog/[^/]+/$'`. By default, any non-archive URL with 2+ folders counts as a post/leaf page |
| `--hub-pattern` | auto | Regex that identifies hubs, e.g. `'/category/'`. By default, any crawled URL that is the parent folder of 2+ other URLs is a hub |
| `--home` | sitemap host root | Where the crawl starts |
| `--out` | `audit_output` | Output folder |

## Requirements

- Python 3.9+
- `requests`, `beautifulsoup4`, `pandas`, `tabulate` (for the Markdown tables in the summary)

```bash
pip install -r requirements.txt
```

It runs fine in Google Colab too:

```python
!pip install -q -r requirements.txt
!python blog_architecture_audit.py --sitemap https://www.example.com/sitemap_index.xml
```

## Tested on

mlforseo.com's sitemap index on 22 October 2026: about 310 sitemap URLs across posts, pages, resources, glossary terms and categories. The guide discusses the results.

## Limitations

- The crawler doesn't render JavaScript. Links injected client-side won't be seen. Use Screaming Frog with JavaScript rendering for those sites.
- Click depth is measured from the homepage via any followed link, so it includes navigation links. That's how search engines discover pages, but it can make a site look shallower than it feels to readers. Use `contextual_inlinks` for the in-content picture.
- "Hubs" and "sections" are inferred from folders. If your URLs are flat (`/post-name/`), pass `--hub-pattern` and `--post-pattern`, or use Screaming Frog mode with your own segments.
- Orphan detection depends on your sitemap. URLs missing from both the sitemap and your links are invisible to this script, and to search engines.

## Files

- `blog_architecture_audit.py`: the script
- `requirements.txt`: dependencies
