# SEO Site Migration Checklist

*43 checks across seven phases, from scoping to the first year after launch. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/). Built on Google's site move documentation and MLforSEO's fuzzy-matching redirect workflow. Checked October 2026.*

This is the plain-text version of the checklist in `site-migration-checklist.xlsx`. The spreadsheet adds a **Redirect map** tab: paste the output of MLforSEO's fuzzy-matching notebooks, decide per URL, and it builds final destinations, source paths, Apache rules and warning flags, then tracks QA for every URL.

Each check has an **evidence level**:

| Evidence | Meaning |
|---|---|
| Google-documented | Stated in Google Search Central or Google Help documentation |
| Platform-documented | Stated in another platform's own docs (Microsoft Bing, IndexNow) |
| MLforSEO practice | What we teach and use on migrations; sensible and low-risk, but not confirmed by the platforms |

**Priority:** High = skipping it risks lost traffic, indexing or link value. Medium = reduces risk and speeds recovery. Low = tidy-up and documentation.

## 1. Scope & plan

- [ ] **M01 · Write down exactly what is changing: domain, protocol, URL structure, CMS, design, hosting**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Each kind of change carries different risks and needs different steps. A hosting move with no URL changes needs no redirects; a domain change needs redirects and the Change of Address tool.  
  **How to check:** List every change in the Notes column. If URLs don't change, follow Google's 'moving hosting without URL changes' guide instead of this full process.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M02 · Change one thing at a time where you can**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google recommends moving domain first and redesigning later, for example. Stacking changes makes it hard to tell what caused a drop.  
  **How to check:** Agree the order of changes with stakeholders. If everything must ship together, plan extra benchmarking and monitoring.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M03 · Decide whether to move everything at once or in sections**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google recommends moving small and medium sites all at once, and suggests large sites can move section by section to spot problems early.  
  **How to check:** Size the site from a crawl and the sitemap. For large sites, pick a test section that changes rarely and isn't driven by unpredictable events.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M04 · Pick a launch window in a quieter traffic period, with a freeze and a rollback plan**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Fewer users meet any problems, and more server capacity is left for Googlebot's extra crawling after the move.  
  **How to check:** Check seasonality in analytics. Avoid launches before weekends or holidays. Agree a content and code freeze, who can sign off, and how to roll back.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M05 · Set expectations: rankings fluctuate, and a medium site can take a few weeks or more to settle**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google says visibility may fluctuate while it recrawls; medium sites can take a few weeks or more for new URLs to replace old ones, larger sites longer. Agreeing this upfront avoids panic decisions.  
  **How to check:** Share the timeline and the KPIs you'll report on (indexed URLs, organic clicks by section, key conversions) with stakeholders before launch.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M06 · Keep the old domain registered (at least a year, ideally for good) with a valid TLS certificate**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google recommends paying for the old domain for at least a year so nobody else can buy and misuse it. Redirects from https:// URLs also need a working certificate on the old host.  
  **How to check:** Check the registrar renewal date and auto-renew. Confirm the old host keeps serving HTTPS long enough to return the redirects.  
  **Learn more:** [Google Help: Change of Address tool](https://support.google.com/webmasters/answer/9370220)

## 2. Benchmark

- [ ] **M07 · Crawl the old site in full and save the export**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** The crawl is your record of what existed: URLs, status codes, titles, H1s, H2s, meta descriptions, canonicals, hreflang and structured data. It also feeds the fuzzy-matching notebook.  
  **How to check:** Screaming Frog (or similar) with the Internal: HTML export; keep Address, Title 1, H1-1, H2-1, H2-2 and Meta Description 1 for redirect matching. Store the file with the launch date.  
  **Learn more:** [Triple fuzzy matching redirect notebook](https://www.mlforseo.com/resource/automated-redirect-mapping-with-triple-fuzzy-matching-for-site-migrations-notebook/)

- [ ] **M08 · Export Search Console and analytics data per URL**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** You need before-and-after numbers by page and section, and the old property's data becomes harder to compare once URLs change.  
  **How to check:** Search Console: page and query performance for the last 16 months, Page indexing report, Links report. GA4: landing pages with sessions and key events.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M09 · List every old URL that needs a decision, including images, PDFs and video**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google suggests starting with your most important URLs and including embedded content such as images, videos, PDFs, JavaScript and CSS, which may be getting traffic or links.  
  **How to check:** Combine sitemaps, the crawl, server logs, analytics landing pages, the Search Console Links report and a CMS export. Deduplicate into the Redirect map tab.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/) · [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M10 · Export the pages with backlinks and save the list of linking sites**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Old URLs with links pass their value on through permanent redirects. You'll also contact the most valuable linking sites after launch.  
  **How to check:** Search Console > Links (top linked pages and linking sites), plus Ahrefs or Semrush if you have them. Add referring domains to the Redirect map.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M11 · Record your AI search and SERP feature baseline**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Migrations can break the URLs AI assistants and SERP features cite. A baseline shows whether you lost citations, rich results or a knowledge panel link.  
  **How to check:** Note rich results by type (Search Console Enhancements), AI Overview appearances for key queries, and a quick citation check in ChatGPT, Perplexity and Gemini for your top questions.  
  **Learn more:** [Your rank tracker is lying to you about AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/rank-tracker-ai-search-measurement/)

## 3. Redirect mapping

- [ ] **M12 · Map every old URL to its closest equivalent new URL, one to one where possible**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Relevant one-to-one redirects keep users and signals on the right page. Google recommends a full old-to-new mapping for any move beyond a simple domain swap.  
  **How to check:** Use the Redirect map tab. For a straight domain change with identical paths, a wildcard rule may be enough; still test a sample.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/) · [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M13 · Draft the map at scale with fuzzy matching, then review it**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Matching hundreds or thousands of URLs by hand takes days. Fuzzy matching on URL, title, H1, H2 and meta description shortlists the best candidates in minutes.  
  **How to check:** Under about 300 URLs: the MLforSEO fuzzy matching Google Sheets template. Larger: the triple fuzzy matching notebook (old vs new crawl) or the 404 mapping notebook. Paste results into the Redirect map tab.  
  **Learn more:** [Triple fuzzy matching redirect notebook](https://www.mlforseo.com/resource/automated-redirect-mapping-with-triple-fuzzy-matching-for-site-migrations-notebook/) · [Fuzzy matching Google Sheets template](https://www.mlforseo.com/resource/fuzzy-matching-for-seo-google-sheets-template/)

- [ ] **M14 · Review every partial or low-scoring match by hand**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** String similarity has no understanding of meaning or intent. Two similar slugs can be different products; a strong score can still be wrong for the user.  
  **How to check:** Sort the Redirect map by Similarity. Validate a sample to choose your own threshold, accept only above it, and set a Decision for everything below. Matches where several algorithms agree are safer.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/)

- [ ] **M15 · Don't redirect lots of old URLs to the home page or an unrelated page**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google may treat irrelevant redirects as soft 404s, and they confuse users. Redirecting several old pages to one new page that consolidates their content is fine.  
  **How to check:** Check the Flags column in the Redirect map for 'Home page redirect'. For content with no equivalent, choose 410 or 404 instead.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/) · [Google: HTTP status codes and soft 404s](https://developers.google.com/search/docs/crawling-indexing/http-network-errors)

- [ ] **M16 · Content you're retiring returns 404 or 410**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google's guide asks for a 404 or 410 on deleted content rather than a redirect to something unrelated.  
  **How to check:** Set Decision to '410 Gone' or '404' in the Redirect map. Make sure the 404 page returns a real 404 status code.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M17 · Plan server-side permanent redirects (301 or 308) straight to the final URL**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Permanent redirects don't lose PageRank. Googlebot follows up to 10 hops, but Google advises redirecting to the final destination directly, and ideally no more than 3 hops.  
  **How to check:** Agree the implementation with developers: server config (.htaccess, nginx), CDN rules or the CMS. Client-side (JavaScript or meta refresh) redirects are a last resort.  
  **Learn more:** [Google: redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects)

- [ ] **M18 · Update existing redirects so they point at the new final URLs**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Redirects from earlier migrations will otherwise chain through the old site (old > older > new).  
  **How to check:** Export current redirect rules, run them through the same mapping, and rewrite each to point directly at the new destination.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

## 4. Pre-launch (staging)

- [ ] **M19 · Keep staging out of search, and list exactly what to unblock at launch**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Staging sites get indexed by accident. Google's guide notes that if you block crawling or use noindex during development, you need a ready list of what to remove at launch.  
  **How to check:** Password-protect staging (HTTP authentication) where possible. If you use noindex or robots.txt blocks, record each one in Notes so none are left behind.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M20 · Crawl staging and compare it with the old-site crawl**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Missing pages, empty titles, lost H1s, dropped structured data or thinner content show up in a side-by-side comparison before they cost traffic.  
  **How to check:** Crawl staging (with authentication) and compare URL counts, titles, H1s, meta descriptions, word counts and structured data by template with the benchmark crawl.  
  **Learn more:** [Web scraping with Screaming Frog](https://www.mlforseo.com/machine-learning-implementation-guides/content-audit/web-scraping-screaming-frog/)

- [ ] **M21 · Every new URL has a self-referencing canonical, and hreflang uses the new URLs**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Canonicals or hreflang still pointing at old or staging URLs send mixed signals about which version to index.  
  **How to check:** Crawl staging and check canonical and hreflang targets. None should point to the staging host or the old domain.  
  **Learn more:** [Google: canonical URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

- [ ] **M22 · Internal links point straight at new URLs, not through redirects**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Updating internal links reduces redirect load and helps Google find the new URLs faster.  
  **How to check:** Use the mapping to find-and-replace links in content, navigation, footers and templates. Crawl staging and filter internal links returning 3xx.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M23 · A sitemap of the new URLs is ready, plus one of the old URLs**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Submitting the new sitemap helps Google discover the new URLs. Google's guide also suggests submitting the old-URL sitemap so you can watch old URLs drop out (redirect warnings there are expected).  
  **How to check:** Generate the new XML sitemap (indexable 200 URLs only). Keep the old sitemap file from the benchmark.  
  **Learn more:** [Google: build a sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)

- [ ] **M24 · The new robots.txt is ready and keeps your AI crawler decisions**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** A robots.txt copied from staging can block the whole site. Rebuilds also tend to drop rules for AI search crawlers (OAI-SearchBot, PerplexityBot, Claude-SearchBot), or a CDN default may start blocking them.  
  **How to check:** Prepare the production robots.txt in advance and diff it against the old one. Check CDN bot settings on the new setup. If you publish llms.txt, update its URLs.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [Google: robots.txt introduction](https://developers.google.com/search/docs/crawling-indexing/robots/intro)

- [ ] **M25 · Structured data uses new URLs, and entity @id values stay stable**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Markup often hard-codes URLs (url, logo, sameAs, breadcrumbs, @id). If @id values change, the connections between your entities break.  
  **How to check:** Search templates and the CMS for the old domain in JSON-LD. Keep @id values unchanged, or map them deliberately if they were built from page URLs.  
  **Learn more:** [What schema.org @id does](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/what-schema-org-id-does-and-why-your-entity-graph-falls-apart-without-it/)

- [ ] **M26 · Analytics, tag manager and Search Console verification work on the new templates**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Missing tracking on launch day leaves a hole in your data. Search Console verification can break if the HTML file or meta tag isn't carried over.  
  **How to check:** Test tags on staging. Verify both old and new sites in Search Console, including all variants (www and non-www, http and https).  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M27 · The server and CDN can handle extra crawling**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google says it will temporarily crawl the new site more heavily than usual after a move. Slow or failing responses slow down the whole migration.  
  **How to check:** Warn your host for large sites. Make sure rate limits and WAF rules allow verified Googlebot and Bingbot.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M28 · If the new domain was bought second-hand, check its history**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** A previous owner may have left manual actions or URL removal requests in place.  
  **How to check:** Verify the new domain in Search Console and check Manual actions and Removals before launch.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M29 · Test the full redirect map on staging**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Mistakes in rules (wrong destinations, loops, chains, missing trailing slashes, lost query strings) are cheapest to fix before launch.  
  **How to check:** Crawl the list of old URLs against staging in list mode with redirects followed. Fill in Status code, Hops and Final URL returns 200 in the Redirect map.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/)

## 5. Launch day

- [ ] **M30 · Switch on the redirects and remove the staging blocks**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Leftover noindex tags or robots.txt blocks are one of the most common reasons a new site fails to get indexed.  
  **How to check:** Deploy redirects; remove noindex and authentication; publish the production robots.txt. Spot-check with URL Inspection.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M31 · Crawl every old URL: each returns 301 or 308 in one hop to a URL that returns 200**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google frequently sees redirects pointing to wrong or non-existent URLs. A list crawl catches them in minutes.  
  **How to check:** List-mode crawl of all old URLs with redirects followed. Filter for chains, loops, 4xx and 5xx destinations and anything not matching the Final destination column.  
  **Learn more:** [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/) · [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M32 · Domain or subdomain change: submit Change of Address for every verified variant**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** The tool tells Google to prefer the new site and forwards signals for 180 days. You don't need it for HTTP to HTTPS, www to non-www, or path changes on the same domain.  
  **How to check:** Search Console > Settings > Change of Address on the old domain-level property. Repeat for www, non-www and any subdomains, even unused ones.  
  **Learn more:** [Google Help: Change of Address tool](https://support.google.com/webmasters/answer/9370220)

- [ ] **M33 · Submit sitemaps in Search Console and Bing Webmaster Tools, and ping IndexNow**  
  *Priority: Medium · Evidence: Platform-documented*  
  **Why it matters:** Sitemaps speed up discovery in Google. Bing Webmaster Tools has its own site move tool, and IndexNow notifies Bing and other participating engines of changed URLs.  
  **How to check:** Submit the new sitemap (and the old-URL sitemap) in both tools. Use Bing's site move tool for domain changes. Send old and new URLs through IndexNow.  
  **Learn more:** [The IndexNow API guide](https://www.mlforseo.com/machine-learning-implementation-guides/indexnow-api-python/) · [Bing Webmaster Tools](https://www.bing.com/webmasters/)

- [ ] **M34 · Re-upload any disavow file to the new property**  
  *Priority: Low · Evidence: Google-documented*  
  **Why it matters:** Google recommends re-uploading the old site's disavow file to the new Search Console property if you used one.  
  **How to check:** Download it from the old property's disavow tool and upload to the new one.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M35 · Inspect one URL from each key template**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Confirms Googlebot sees the right rendered content, canonical and indexability on the live site.  
  **How to check:** Search Console > URL Inspection > Test live URL for the home page, a category, a product or service page and an article.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

## 6. First weeks

- [ ] **M36 · Monitor indexing, crawl stats and errors every day for the first two weeks**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Old URLs should drop out while new ones are indexed. Spikes in 404s, 5xx errors or 'Page with redirect' on new URLs need fixing fast.  
  **How to check:** Search Console: Page indexing (old and new properties), Sitemaps, Crawl stats. Server logs: Googlebot status codes on old and new URLs.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M37 · Fix 404s on old URLs that have traffic or links within days**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Each one is lost value and a broken journey. The 404 notebook can map a new batch of broken URLs to live pages quickly.  
  **How to check:** Pull 404s from Search Console, logs and the analytics 404 page. Map them with the Redirect map tab or the 404 mapping notebook and deploy in batches.  
  **Learn more:** [Mapping 404s to live pages (notebook)](https://www.mlforseo.com/resource/mapping-404-urls-to-live-pages-with-fuzzy-matching-guide/)

- [ ] **M38 · Update the links you control and ask for the important external ones to change**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Redirects are slow for users. Google suggests updating profile links, ad campaigns and high-value backlinks to point straight at new URLs.  
  **How to check:** Update social profiles, Business Profile, Wikidata 'official website', Crunchbase, email templates, ads and partner pages. Contact the top linking sites from your benchmark list.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/) · [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M39 · Compare organic traffic and conversions with the benchmark by section**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Sitewide totals hide problems. Section or template comparisons show exactly where something broke.  
  **How to check:** Weekly: clicks, impressions and key events by section, against the same weeks last year and the pre-launch baseline. Annotate the launch date in GA4 and your reports.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M40 · Recheck AI answers and SERP features for your key queries**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** Assistants and knowledge panels can keep citing old URLs for a while. Checking shows whether they now point to working, correct pages.  
  **How to check:** Rerun the baseline questions from M11. Check rich results in Search Console Enhancements and that your knowledge panel shows the new website.  
  **Learn more:** [Your rank tracker is lying to you about AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/rank-tracker-ai-search-measurement/)

## 7. Months 1 to 12

- [ ] **M41 · Keep redirects for at least a year, ideally permanently**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google recommends keeping redirects as long as possible, generally at least one year, so it can recrawl and transfer signals, and suggests users benefit from keeping them indefinitely.  
  **How to check:** Document redirects somewhere other than one developer's memory (this workbook). Add a calendar reminder before any server or CMS change that could drop them.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M42 · Remove the old-URL sitemap once old URLs have dropped out**  
  *Priority: Low · Evidence: Google-documented*  
  **Why it matters:** Once Google uses the new sitemap, the old one has done its job.  
  **How to check:** When the old sitemap shows close to zero indexed URLs in Search Console, remove it.  
  **Learn more:** [Google: how to move a site (URL changes)](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)

- [ ] **M43 · Review results at 3, 6 and 12 months and write down what you learned**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** A short write-up makes the next migration faster and shows stakeholders the outcome.  
  **How to check:** Compare traffic, indexed URLs and conversions by section with the benchmark. Note what went wrong, what you'd repeat and any redirects still pending.  

---

## Redirect mapping tools

| Situation | Tool |
|---|---|
| Under about 300 URLs | [Fuzzy Matching for SEO Google Sheets template](https://www.mlforseo.com/resource/fuzzy-matching-for-seo-google-sheets-template/) |
| Old crawl vs new crawl (URL, title, H1, H2, meta description) | [Triple fuzzy matching redirect notebook](https://www.mlforseo.com/resource/automated-redirect-mapping-with-triple-fuzzy-matching-for-site-migrations-notebook/) |
| 404s to live pages | [Mapping 404 URLs to live pages notebook](https://www.mlforseo.com/resource/mapping-404-urls-to-live-pages-with-fuzzy-matching-guide/) |
| Python on GitHub | [`fuzzy-matching-for-seo/`](../fuzzy-matching-for-seo/) |

Fuzzy matching compares characters, not meaning, so review every partial match before it goes live. The walkthrough is in [404 and redirect mapping with fuzzy matching](https://www.mlforseo.com/machine-learning-tutorials/fuzzy-matching/404-and-redirect-mapping-with-fuzzy-matching-in-google-colab-python/).

## Go deeper

- [Google: how to move a site with URL changes](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)
- [Introduction to Machine Learning for SEO](https://www.mlforseo.com/courses/introduction-to-machine-learning-for-seo/) (fuzzy matching module, MLforSEO Academy)

Created by Lazarina Stoy · MLforSEO. Free to use and adapt under the repository's MIT licence; please keep the credit.
