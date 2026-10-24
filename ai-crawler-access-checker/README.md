# AI crawler access checker: robots.txt + llms.txt + bot rules

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/ai-crawler-access-checker/ai_crawler_access_checker.ipynb)

Companion code for the MLforSEO post **[Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/)** (Beatrice Gamba). Built by Lazarina Stoy, MLforSEO.

Most AI companies now run separate crawlers for **training**, **search** and **user-initiated fetches**. A "block AI" robots.txt written in 2023 often blocks the search bots too, which takes a site out of AI answers without anyone noticing. This checks what your robots.txt actually allows, for one domain or a whole list.

## What it does

| Section | What you get |
|---|---|
| 2. Crawler list | 27 AI crawlers and control tokens (OpenAI, Anthropic, Perplexity, Google, Apple, Microsoft, Amazon, Meta, Mistral, DuckDuckGo, Common Crawl, ByteDance), each with what it controls, whether the vendor says it follows robots.txt, and a link to the vendor's docs |
| 3. Audit | allow / block per crawler per sample URL, an access matrix, and a summary per site (training vs search vs user fetchers blocked) |
| 4. Flags | blanket `Disallow: /`, search bots blocked along with training bots (or instead of them), Googlebot blocked, Google-Extended and Applebot misunderstandings, typos (`Perplexity-Bot`), outdated tokens (`anthropic-ai`, `Claude-Web`), partial tokens (`Claude`), robots.txt errors, HTML served as robots.txt, files over Google's 500 KiB limit |
| 5. llms.txt | presence of `/llms.txt` and `/llms-full.txt`, soft 404s (200 + HTML), and basic [llmstxt.org](https://llmstxt.org/) structure (H1, summary, sections, links) |
| 6. Optional live check | requests a URL with each crawler's user-agent string and records status codes |
| 7. Export | one CSV per table and `ai_crawler_access_audit.xlsx` (open it in Google Sheets) |

The same code runs from the command line:

```bash
pip install -r requirements.txt
python ai_crawler_access.py www.example.com www.example.org --paths /,/blog/ --out results/
python ai_crawler_access.py --offline sample_data --paths /,/blog/,/checkout/   # no network
python ai_crawler_access.py www.example.com --live-ua https://www.example.com/
```

## How the rules are evaluated

* **Parser:** [Protego](https://github.com/scrapy/protego), which follows Google's robots.txt spec: longest matching rule wins, `Allow` wins ties, `*` and `$` wildcards supported. Python's `urllib.robotparser` applies rules in file order and gets these cases wrong.
* **Group matching:** exact product token, case-insensitive, as in [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309) and Google's parser (`meta-webindexer/1.1` is read as `meta-webindexer`). Protego on its own also matches prefixes (`User-agent: Claude` would apply to ClaudeBot); the helper removes that, and the `basis` column tells you when a lenient parser would disagree.
* **Status codes**, following [Google's documentation](https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt): 4xx = no restrictions; 5xx or 429 = treated as a full block.

## Crawler sources (checked 24 October 2026)

* OpenAI (GPTBot, OAI-SearchBot, ChatGPT-User): https://developers.openai.com/api/docs/bots
* Anthropic (ClaudeBot, Claude-SearchBot, Claude-User): https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
* Perplexity (PerplexityBot, Perplexity-User): https://docs.perplexity.ai/guides/bots
* Google (Googlebot): https://developers.google.com/search/docs/crawling-indexing/googlebot; (Google-Extended, Google-CloudVertexBot): https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers
* Apple (Applebot, Applebot-Extended): https://support.apple.com/en-us/119829
* Microsoft (Bingbot): https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0
* Amazon (Amazonbot, Amzn-SearchBot, Amzn-User): https://developer.amazon.com/amazonbot
* Meta (Meta-ExternalAgent, Meta-WebIndexer, Meta-ExternalFetcher, facebookexternalhit): https://developers.facebook.com/docs/sharing/webmasters/web-crawlers/
* Mistral AI (MistralAI-Training, MistralAI-Index, MistralAI-User): https://docs.mistral.ai/robots
* DuckDuckGo (DuckAssistBot): https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot
* Common Crawl (CCBot): https://commoncrawl.org/ccbot
* ByteDance (Bytespider): no official documentation found; listed because it appears in many robots.txt files

**Google-Extended does not affect Google Search.** In Google's words: "Google-Extended does not impact a site's inclusion in Google Search nor is it used as a ranking signal in Google Search." It controls Gemini model training and grounding in Gemini Apps and Vertex AI. AI Overviews and AI Mode run on Googlebot; to limit what they show, Google points to `nosnippet`, `data-nosnippet`, `max-snippet` and `noindex`.

## Requirements

* Python 3.9+; `protego`, `requests`, `pandas`, `openpyxl`, `jinja2` (Colab installs Protego in the first cell).
* No API keys or accounts.

## Sample data

`sample_data/robots/` holds robots.txt files saved on 24 October 2026 from www.mlforseo.com, www.nytimes.com, www.theguardian.com, www.bbc.co.uk, www.reddit.com and vercel.com, plus `example-shop.test`, a fictional file with the common mistakes. `sample_data/llms/` holds Vercel's llms.txt, a fictional valid llms.txt, and a stub standing in for the HTML page Reddit returned at `/llms.txt` with a 200 status. The live sites will have changed since; switch `USE_SAMPLE = False` to check them now.

## Caveats

* robots.txt is a request, not access control. Some vendors say their user-initiated fetchers may not follow it.
* The live user-agent check only detects blocking based on the user-agent header. CDNs verify real crawlers by IP or reverse DNS, so a spoofed request can be treated differently from the real bot. If the browser baseline isn't 200, your network is being blocked and the results say little. Only test sites you own or may test.
* Some sites serve different robots.txt files to different user agents or IPs.
* Crawler names change. Re-check the vendor pages above before you edit a live robots.txt.
* llms.txt is a community proposal; the major AI search providers haven't documented that they read it.

## Tested with

Python 3.12, protego 0.7.0, requests 2.34, pandas 3.1, openpyxl 3.1.5 on 24 October 2026:

* The notebook ran end to end in sample mode (`jupyter nbconvert --execute`).
* Live mode ran from the command line on www.mlforseo.com, www.nytimes.com, www.theguardian.com, www.bbc.co.uk, www.reddit.com, stripe.com, vercel.com and www.cloudflare.com (robots.txt, llms.txt, llms-full.txt).
* The live user-agent check ran on www.mlforseo.com (200 for every crawler) and www.nytimes.com (the browser baseline itself got a 403 from bot protection, which is exactly the case the warning covers).

## Files

* `ai_crawler_access_checker.ipynb`: the notebook (with sample-mode outputs)
* `ai_crawler_access.py`: the helper module and command-line tool
* `sample_data/`: saved robots.txt and llms.txt files
* `requirements.txt`

MIT licence. Credit: Lazarina Stoy, [MLforSEO](https://www.mlforseo.com).
