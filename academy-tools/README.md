# MLforSEO Academy tools

The free browser tools at [academy.mlforseo.com/tools](https://academy.mlforseo.com/tools/), one per course lesson
or workbook. Every tool runs in your browser: your data and any API key stay in the tab and are only sent to
the API provider the tool names (Google Cloud, OpenAI, Anthropic). Several need no key at all.

| Tool | Course | Needs |
|---|---|---|
| [Entity Extractor & Salience Profiler](tools/entity-extractor-salience-profiler.html) | The AI-powered Entity Audit | Google Cloud API key |
| [Entity Audit Scorecard](tools/entity-audit-scorecard.html) | The AI-powered Entity Audit | Nothing |
| [Knowledge Graph Reconciler](tools/knowledge-graph-reconciler.html) | The AI-powered Entity Audit | Google Cloud API key |
| [Entity Consistency Checker](tools/entity-consistency-checker.html) | The AI-powered Entity Audit | Nothing |
| [Entity Gap Matrix](tools/entity-gap-matrix.html) | The AI-powered Entity Audit | Nothing |
| [Entity Brief Generator](tools/entity-brief-generator.html) | The AI-powered Entity Audit | Anthropic API key |
| [Content Briefs Generator](tools/content-briefs-generator.html) | Semantic AI-powered SEO Keyword Research | Google Sheets + OpenAI API keys |
| [Semantic Intent Drift Analyzer](tools/semantic-intent-drift-analyzer.html) | Semantic AI-powered SEO Keyword Research | Nothing |
| [Synthetic vs User-generated Queries Classifier](tools/synthetic-vs-user-generated-queries-classifier.html) | Semantic AI-powered SEO Keyword Research | Nothing |
| [AI Blog-to-Social Post Transformer](tools/ai-blog-to-social-post-transformer.html) | Introduction to Machine Learning for SEO | OpenAI API key |
| [AI Meta Data Creator](tools/ai-meta-data-creator.html) | Introduction to Machine Learning for SEO | OpenAI API key |

## Run a tool locally

Each file in `tools/` is a standalone page. Download it and open it in a browser, or serve the folder:

```bash
cd academy-tools/tools && python3 -m http.server 8000   # then open http://localhost:8000/<tool>.html
```

## How the site uses this folder

```
tools/<slug>.html     the tool (source of truth): one <style> with the shared design tokens, markup in
                      <div class="mlfs-tool">, libraries via <script src>, the tool code in one inline <script>
meta/<slug>.json      the page copy: title, summary, course, what you need, cost, inputs, outputs, steps, note
build/compose.py      builds dist/: scoped CSS, the tool JS, and the WordPress page HTML for each tool
dist/                 what the academy pages load (through jsDelivr, pinned to a commit)
preview/              local previews of the built pages (not committed)
```

```bash
python3 academy-tools/build/compose.py               # build, assets referenced at @main
python3 academy-tools/build/compose.py --ref <sha>   # build pinned to a commit (what the site publishes)
```

Why the CSS and JS are separate files: WordPress filters page content when it renders and turns `&&` next to
`<` comparisons into `&#038;&#038;`, which breaks inline JavaScript. Serving the files from this repo through
jsDelivr avoids that, keeps each page small, and means the published code is exactly the code here.
`build/scope_css.py` rewrites every selector to sit under `.mlfs-tool`, so a tool never restyles the site.

## Design

All tools share one design system (the tokens and patterns at the top of each `tools/*.html`): light and dark
themes, Bricolage Grotesque + Inter, the MLforSEO palette, `.masthead`, `.panel`, `.actions`, file inputs,
tables and notices. A new tool starts as a copy of an existing one.

Licence: see the repository [LICENSE](../LICENSE).
