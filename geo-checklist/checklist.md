# Generative Engine Optimisation (GEO) Checklist

*44 checks to help AI search systems find, understand, trust and cite your content. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/), built on [Beatrice Gamba](https://www.mlforseo.com/experts/beatrice-gamba/)'s AI search series. Checked October 2026.*

This is the plain-text version of `geo-checklist.xlsx` (the Google Sheets version has status dropdowns, an AI crawler reference tab, a prompt tracker and a progress dashboard). The areas follow the order AI systems process content: reach it, recognise it, extract it, trust it, and then measure what happened.

Google says there are no extra requirements to appear in AI Overviews or AI Mode beyond being indexed and eligible for a snippet, so the foundations come first. Each check has an **evidence level**:

| Evidence | Meaning |
|---|---|
| Google-documented | Stated in Google Search Central or Google Help documentation |
| Platform-documented | Stated in another platform's own docs (OpenAI, Anthropic, Perplexity, Microsoft Bing, Apple, Meta, Wikidata, schema.org) |
| Research-backed | Supported by published research or a large public dataset; may not carry over to every site |
| MLforSEO practice | What we teach and use in audits, based on how retrieval and entity systems work; not confirmed by the platforms |
| Unconfirmed (optional) | A cheap extra no major platform has confirmed using |

**Priority:** High = fix first (blocks access, eligibility or recognition, or misrepresents you). Medium = do next. Low = nice to have or an early-warning signal.

## 1. Crawl access

- [ ] **G01 · Googlebot can crawl every page you want in Google's AI Overviews and AI Mode**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google's AI features use the normal Search index and follow your robots.txt rules for Googlebot. There is no separate AI crawler to allow for them.  
  **How to check:** Search Console > Settings > robots.txt report, then URL Inspection on your key templates. Look for Disallow rules that catch important folders.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] **G02 · AI search crawlers are allowed in robots.txt: OAI-SearchBot, Claude-SearchBot, PerplexityBot and Bingbot**  
  *Priority: High · Evidence: Platform-documented*  
  **Why it matters:** These bots decide whether you can be shown and linked in ChatGPT search, Claude's web search, Perplexity and Bing / Copilot answers. OpenAI says sites that block OAI-SearchBot won't be shown in ChatGPT search answers.  
  **How to check:** Open yourdomain.com/robots.txt. Check for a User-agent group per bot, or a catch-all (User-agent: *) group that blocks them. The 'AI crawlers' tab lists every token with its docs.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [OpenAI: crawlers and user agents](https://platform.openai.com/docs/bots)

- [ ] **G03 · Training crawlers are a deliberate business decision: GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, Meta-ExternalAgent, CCBot**  
  *Priority: Medium · Evidence: Platform-documented*  
  **Why it matters:** Blocking training crawlers is separate from search visibility. Google-Extended does not affect inclusion in Google Search, including AI Overviews. Make the choice on purpose, and write down why.  
  **How to check:** Agree the policy with legal / leadership, record it in the 'AI crawlers' tab (Your decision column), then match robots.txt to it.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [Google: common crawlers (Google-Extended)](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers)

- [ ] **G04 · Your CDN, firewall or bot-management settings aren't blocking the crawlers you allowed**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** A robots.txt Allow means nothing if a WAF rule, a 'block AI bots' toggle or a rate limit returns 403, 429 or a challenge page. Google lists CDN and hosting blocks among the things to check.  
  **How to check:** Check your CDN / WAF dashboard (for example Cloudflare's AI crawler and bot settings). In server logs, filter for the bot user agents and look for 403, 429 and 503 responses. Verify bots against their published IP ranges.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [Perplexity: crawlers](https://docs.perplexity.ai/guides/bots)

- [ ] **G05 · Fetching a key page with an AI user-agent string returns the real content**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Agents fail silently: no error, just a skipped page. A quick fetch shows whether they get your content or a block page, cookie wall or empty shell.  
  **How to check:** From a terminal: curl -A "ClaudeBot" https://yourdomain.com/key-page | head (repeat with OAI-SearchBot and PerplexityBot). Some firewalls also check IP ranges, so confirm in logs too.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/)

- [ ] **G06 · Main content, links and JSON-LD are in the raw HTML, not only added by JavaScript**  
  *Priority: High · Evidence: Research-backed*  
  **Why it matters:** Google renders JavaScript, but the major AI crawlers studied in 2024 (GPTBot, ClaudeBot, PerplexityBot and others) fetched JavaScript files without executing them. Content that only appears after rendering may be invisible to them.  
  **How to check:** Compare View Source (raw HTML) with Inspect / rendered DOM on each template, or crawl with JavaScript rendering off. Anything missing from the raw HTML is at risk.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [Vercel and MERJ: the rise of the AI crawler](https://vercel.com/blog/the-rise-of-the-ai-crawler)

- [ ] **G07 · Key facts sit near the top of the page and priority pages aren't bloated**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Agents read against a token budget, so facts buried deep in long pages can be cut. Our working budget is under about 15,000 tokens for product and category pages (roughly 60,000 characters of text).  
  **How to check:** Copy the page text into a text editor, divide the character count by four for an approximate token count. Check that the answer, price or policy appears in the first screen of text.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/)

- [ ] **G08 · Optional: an llms.txt file, if you want one, lists your most useful pages with short descriptions**  
  *Priority: Low · Evidence: Unconfirmed (optional)*  
  **Why it matters:** llms.txt is a proposed standard. No major AI provider has confirmed that its crawlers read it, and Google says you don't need AI text files to appear in its AI features. Treat it as a cheap extra after everything above.  
  **How to check:** If you publish one, keep it short, Markdown, at yourdomain.com/llms.txt, organised by task, and keep it in sync with the site. Don't block it in robots.txt.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/) · [llmstxt.org proposal](https://llmstxt.org/)

- [ ] **G09 · AI crawler activity is visible in your server logs**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Logs show which pages the AI bots fetch, how often, and whether they get errors. A page crawled heavily but never cited points to an extraction or selection problem rather than an access one.  
  **How to check:** Export logs (host, CDN or log analyser such as Screaming Frog Log File Analyser) and segment by user agent. Verify genuine bots against the IP lists each provider publishes.  
  **Learn more:** [Your rank tracker is lying to you about AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/rank-tracker-ai-search-measurement/) · [OpenAI: crawlers and user agents](https://platform.openai.com/docs/bots)

## 2. Indexing & eligibility

- [ ] **G10 · Priority pages are indexed in Google and eligible for a snippet**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** To be a supporting link in AI Overviews or AI Mode, a page must be indexed and eligible to show with a snippet. nosnippet, max-snippet:0 or data-nosnippet on the main content removes that eligibility.  
  **How to check:** Search Console > URL Inspection for each priority URL; check the page source and HTTP headers for noindex, nosnippet, max-snippet and data-nosnippet.  
  **Learn more:** [Indexed is not selected (Beatrice Gamba)](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/indexed-is-not-selected/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] **G11 · Priority pages are indexed in Bing, and changes are pushed with IndexNow**  
  *Priority: Medium · Evidence: Platform-documented*  
  **Why it matters:** Bing's index feeds Bing results and Microsoft Copilot answers. IndexNow tells Bing (and other participating engines) about new and updated URLs within minutes.  
  **How to check:** Bing Webmaster Tools > URL Inspection; set up IndexNow through your CMS, CDN or a script.  
  **Learn more:** [The IndexNow API guide](https://www.mlforseo.com/machine-learning-implementation-guides/indexnow-api-python/) · [Bing Webmaster Tools](https://www.bing.com/webmasters/)

- [ ] **G12 · Priority pages are reachable through internal links (no orphans) within a few clicks**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google lists internal links among the SEO basics that still matter for AI features, and crawlers of every kind discover pages through links.  
  **How to check:** Crawl the site and compare crawled URLs with your sitemap and analytics landing pages. Check click depth for priority pages.  
  **Learn more:** [Blog and site architecture in the AI search era](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/blog-site-architecture-ai-search/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

## 3. Entity clarity

- [ ] **G13 · Your organisation (or person) is described in Organization / Person markup on the home or about page**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** This is how you state who you are in a format machines parse directly: name, URL, logo, description and the profiles that confirm you. Google recommends placing it on the home page or a single page about the organisation.  
  **How to check:** View Source on the home and about pages, then run the Rich Results Test and the Schema Markup Validator. Check name, url, logo, description and sameAs are present.  
  **Learn more:** [Structured data and entity understanding](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/how-structured-data-reinforces-entity-understanding-in-ai-search/) · [Google: Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization)

- [ ] **G14 · One canonical brand name is used, character for character, everywhere**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** 'Acme', 'Acme Corp' and 'Acme Corporation' can be read as three different entities. Consistent naming stops your entity fragmenting across the site, profiles and knowledge bases.  
  **How to check:** Write the canonical form into your style guide. Search the site (and your schema) for variants; compare with LinkedIn, Crunchbase, Wikidata and directory listings.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/)

- [ ] **G15 · Core entities have a stable @id that other markup points to**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** A stable @id turns separate Organization, Person and Article blocks into one connected graph: the publisher of every article, the employer of every author, the brand of every product.  
  **How to check:** In the JSON-LD on several page types, check that the Organization has an @id that never changes, and that publisher, author, worksFor and brand reference those @id values.  
  **Learn more:** [What schema.org @id does](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/what-schema-org-id-does-and-why-your-entity-graph-falls-apart-without-it/) · [Structured data automation with Python](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/structured-data-automation-python/)

- [ ] **G16 · Every sameAs link works and shows the same name as your markup**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** schema.org defines sameAs as a page that unambiguously indicates the item's identity. A broken link, or a profile showing a different name, gives systems a contradiction instead of a confirmation.  
  **How to check:** Open each sameAs URL. Record the status code and the displayed name. Remove or fix anything that 404s, redirects somewhere unrelated or shows a different name.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [schema.org: sameAs](https://schema.org/sameAs)

- [ ] **G17 · On its own page, your main entity is the most prominent entity (navigation isn't drowning it)**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Entity extraction weighs the whole page. Repeated menu and footer labels can outscore your brand or topic on the very page meant to define it.  
  **How to check:** Run Google's Natural Language API (or the MLforSEO no-code template) on the full page, then on the main content only. Check the brand or topic leads on salience. Wrap layout in <nav>, <main>, <aside> and <footer>.  
  **Learn more:** [Why navigation outranks your brand](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/why-navigation-elements-outrank-your-brand-in-entity-analysis/)

- [ ] **G18 · If your brand name is shared with something else, it's disambiguated**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** When systems can't tell which entity you mean, your content gets attributed elsewhere or not at all. Full names plus category context and sameAs links resolve the collision.  
  **How to check:** Query your brand in the Knowledge Graph Search API and in AI assistants. If another entity dominates, use the full name with a category descriptor in the H1, intro, meta description and schema description.  
  **Learn more:** [Entity disambiguation in practice](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/entity-disambiguation-in-practice/) · [Google: Knowledge Graph Search API](https://developers.google.com/knowledge-graph)

- [ ] **G19 · Content covers the sub-questions your key topics fan out into**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google says AI Overviews and AI Mode may use query fan-out: several related searches across subtopics. Pages that answer one sub-question clearly can be picked for that slice of the answer.  
  **How to check:** For each priority topic, list the sub-questions a real buyer asks (People Also Ask, sales calls, support tickets, AI follow-up suggestions). Map each to a page or section; mark gaps.  
  **Learn more:** [How entities power query fan-out](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/how-entities-power-query-fan-out-in-ai-search/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

## 4. Chunk extractability

- [ ] **G20 · Headings say what the section answers, in the words a person would search**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Retrieval systems cut pages into passages and judge each on its own. A heading like 'What does X cost for small teams?' is a strong signal for that passage; 'A closer look' carries none.  
  **How to check:** Read every H2 and H3 out of context. Could each stand alone as a search query or a clear label? Rewrite the vague ones.  
  **Learn more:** [The chunk, not the page](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/chunk-not-the-page/)

- [ ] **G21 · Every section makes sense on its own (no 'as noted above', no orphan 'it' or 'this')**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** An extracted passage carries no memory of the rest of the page. Back-references and pronouns without a named subject become broken references once the chunk is lifted out.  
  **How to check:** Search the page for 'as mentioned', 'as noted above', 'see below', 'as we discussed' and drive them to zero. Name the subject in the first sentence of each section.  
  **Learn more:** [The chunk, not the page](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/chunk-not-the-page/)

- [ ] **G22 · One main idea per headed section**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** A paragraph that mixes problem, cause and fix is a blend that matches no single query well. Separate sections give each idea its own sharp passage.  
  **How to check:** Skim each long section: if it answers more than one question, split it under separate headings.  
  **Learn more:** [The chunk, not the page](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/chunk-not-the-page/)

- [ ] **G23 · Each section leads with the direct answer, then the detail**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Answer-first writing puts the extractable claim where both readers and machines find it first. Detail and nuance can follow.  
  **How to check:** Check the first one or two sentences under each heading. Do they answer the heading directly? If the answer appears three paragraphs in, move it up.  
  **Learn more:** [The chunk, not the page](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/chunk-not-the-page/)

- [ ] **G24 · Comparisons, specs and prices are in HTML tables with a sentence explaining them**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Tables pack structured facts into far fewer tokens than prose. The explanatory sentence keeps the meaning attached if the table is extracted on its own.  
  **How to check:** Find prose that lists attributes, plans, sizes or specs. Convert to a real <table> (not an image), with a one-sentence summary directly above it.  
  **Learn more:** [Your robots.txt might be the silent killer of your AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/robots-txt-silent-killer-ai-traffic/)

- [ ] **G25 · Sources, dates and named entities sit in the same sentence as the statistic**  
  *Priority: High · Evidence: Research-backed*  
  **Why it matters:** Bylines, footnotes and reference lists don't travel with an extracted chunk. In the GEO study, adding citations, quotations and statistics raised source visibility in generative answers by up to 40% on their benchmark.  
  **How to check:** For every number or claim you want cited, check the sentence names the source, the scope and the date. Replace 'our research found' with the named organisation and study.  
  **Learn more:** [The chunk, not the page](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/chunk-not-the-page/) · [Aggarwal et al., GEO: Generative Engine Optimization (KDD 2024)](https://arxiv.org/abs/2311.09735)

## 5. Claim quality

- [ ] **G26 · Key claims pass the three-property test: extract-friendly, verifiable, specific**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** A claim with no value to lift, nothing to cross-check and no exact detail gives a system nothing to select. Vague sentences are skipped, not ranked lower.  
  **How to check:** List the 5 to 10 claims you most want cited (price, use case, size, founding year, key results). Score each against the three properties and rewrite failures.  
  **Learn more:** [Vagueness is a disqualifier](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/vagueness-is-a-disqualifier/)

- [ ] **G27 · Marketing phrases are backed by the exact fact underneath**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** 'Flexible pricing' and 'many integrations' name nothing. '£25 per user per month' and '50 integrations including Slack and Jira' can be extracted and checked. Keep the persuasive line if you like, but add the fact.  
  **How to check:** Search priority pages for 'leading', 'world-class', 'many', 'flexible', 'affordable', 'best-in-class'. Add the number, name or date behind each.  
  **Learn more:** [Vagueness is a disqualifier](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/vagueness-is-a-disqualifier/) · [Aggarwal et al., GEO: Generative Engine Optimization (KDD 2024)](https://arxiv.org/abs/2311.09735)

- [ ] **G28 · Time-sensitive facts carry a date ('as of October 2026') and the page shows when it was updated**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Words like 'current' and 'latest' decay and give no fixed point. A date lets systems and readers judge freshness.  
  **How to check:** Check prices, stats, product details and policies for an 'as of' date. Make sure the visible updated date is real (changed content, not a cosmetic bump).  
  **Learn more:** [Vagueness is a disqualifier](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/vagueness-is-a-disqualifier/)

- [ ] **G29 · Each priority page offers something others don't: original data, first-hand experience or a clear point of view**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** If ten sources say the same thing, any one of them will do. Google's helpful content guidance asks whether content provides original information, reporting or analysis.  
  **How to check:** Compare your page with the top results and AI answers for its main query. Note what only you can say (data, examples, tests, expert input) and make it prominent.  
  **Learn more:** [What is information gain in SEO?](https://www.mlforseo.com/ml-fundamentals/what-is-information-gain-in-seo/) · [Google: creating helpful content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

## 6. Structured data

- [ ] **G30 · Structured data matches the visible text on the page**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google lists this among the SEO basics for AI features. Markup that disagrees with the page is a contradiction, and it breaks Google's structured data policies.  
  **How to check:** Spot-check prices, ratings, dates, names and FAQs in the JSON-LD against the rendered page.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [Google: structured data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)

- [ ] **G31 · Each page uses the type that matches what it is**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** A CMS that stamps Organization on every URL tells systems your blog posts are the company. Article, Product, Service, ProfilePage and Organization each belong on their own kind of page.  
  **How to check:** Crawl with structured data extraction on (for example Screaming Frog), then pivot schema types by page template.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [Structured data automation with Python](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/structured-data-automation-python/)

- [ ] **G32 · Commercial facts are machine-readable: price, currency, availability, returns, shipping, opening hours**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Recommendation and shopping agents compare typed fields. If a returns policy or price exists only in prose, an agent may treat it as unknown. Google also asks you to keep Merchant Center and Business Profile up to date.  
  **How to check:** Check Product / Offer markup (price, priceCurrency, availability), MerchantReturnPolicy and shipping details, LocalBusiness openingHoursSpecification. Compare with Merchant Center and Business Profile.  
  **Learn more:** [Your audience is no longer only human](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/audience-no-longer-only-human-agentic-seo/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] **G33 · The same fact has the same value across every page, schema block and profile**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Gaps are neutral; contradictions are negative. A founding year of 2011 in schema, 2013 in a press release and 2012 on LinkedIn gives systems a conflict they can't resolve.  
  **How to check:** Pull the values for name, founding date, employee count, address, prices and leadership from schema, about page, press kit and profiles. Use ranges (QuantitativeValue) for figures that change.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/)

## 7. Trust & corroboration

- [ ] **G34 · Your three most important facts are confirmed by independent sources, with the same values**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Claims that appear only on your own site are self-assertion. When an assistant cross-checks sources at answer time, independently confirmed claims are the ones that survive.  
  **How to check:** Pick three facts (price, ideal customer, company size, founding year). Search each and count independent, non-promotional sources that state the same value. Zero is a gap to close.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/)

- [ ] **G35 · Canonical facts match across LinkedIn, Crunchbase, Wikidata, Business Profile, review sites and directories**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Every platform holding facts about you is a verification point. Consistent points add confidence; inconsistent ones subtract it.  
  **How to check:** Keep a single source of truth (the Knowledge Panel checklist has a fact sheet tab). Audit each profile against it and fix mismatches, contradictions first.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/)

- [ ] **G36 · Authors are real, identifiable people with consistent profiles**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google's guidance asks you to make clear who created content and why they're qualified. Author pages, Person markup with sameAs, and a consistent external footprint (talks, publications, LinkedIn) let systems check that.  
  **How to check:** Check bylines link to author pages; author pages state expertise in plain text and link to external profiles; Person markup uses a stable @id referenced from Article author.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/) · [Google: creating helpful content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

- [ ] **G37 · You are present in the third-party places your category is discussed**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Assistants build answers from many sources. Reviews, comparisons, trade press, podcasts and conference programmes that name you next to your category and peers give them independent material to cite.  
  **How to check:** Ask assistants for 'best [category] for [use case]' and list the sources they cite. Check which mention you, which don't, and whether the facts about you are right.  
  **Learn more:** [How LLMs co-cite](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/how-llms-co-cite-building-authority-by-association/)

- [ ] **G38 · If you qualify, your organisation has an accurate, referenced Wikidata item**  
  *Priority: Medium · Evidence: Platform-documented*  
  **Why it matters:** Wikidata is openly licensed, widely reused and a common reference for entity systems. Items need serious, publicly available references, and editing your own item is a conflict of interest to declare.  
  **How to check:** Search Wikidata for an existing item first. Check label, description, instance of, official website and that statements have external references. See the Knowledge Panel checklist for the full audit.  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikidata: notability policy](https://www.wikidata.org/wiki/Wikidata:Notability)

## 8. Measurement

- [ ] **G39 · You have a fixed set of 10 to 50 real customer questions to test in AI assistants**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Rankings measure visibility to people scanning a results page; they can't show whether an assistant selected you. A fixed prompt set, rerun on a schedule, gives you a citation-rate baseline.  
  **How to check:** Use the 'Prompt tracker' tab. Pull questions from sales calls, support tickets, Search Console queries and People Also Ask. Keep the wording fixed between runs.  
  **Learn more:** [Your rank tracker is lying to you about AI search](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/rank-tracker-ai-search-measurement/)

- [ ] **G40 · Monthly: record whether you are mentioned, cited and described accurately in each assistant**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Answers vary between runs, so trends matter more than one result. Unoptimised content often sits around a 5 to 15% citation rate in MLforSEO's experience; accuracy problems point to the source records to fix.  
  **How to check:** Run each prompt in ChatGPT, Perplexity, Claude, Gemini, Google AI Mode and Copilot (logged out where possible). Log results in the Prompt tracker; the Progress tab calculates the rates.  
  **Learn more:** [Dark AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/dark-ai-traffic-hidden-in-direct/)

- [ ] **G41 · GA4 shows AI assistant referrals as their own channel**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Since May 2026 GA4's default channel group includes an AI Assistant channel for visits from assistants such as ChatGPT, Gemini, Copilot and Grok. Clicks from Google's AI Overviews and AI Mode count as Google organic traffic and appear in Search Console's Performance report (Web search type).  
  **How to check:** GA4 > Reports > Acquisition > Traffic acquisition (default channel group). If you need control over which sources count, add a custom channel group with a referrer regex.  
  **Learn more:** [Dark AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/dark-ai-traffic-hidden-in-direct/) · [Google: AI features and your website](https://developers.google.com/search/docs/appearance/ai-features)

- [ ] **G42 · You watch for 'dark' AI traffic: direct visits growing faster than branded search**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** Many AI-influenced visits arrive with no referrer and land in Direct. If direct grows much faster than branded search, part of the gap is likely AI-driven.  
  **How to check:** Each month, put the trend of GA4 Direct sessions next to branded clicks in Search Console (filter queries containing your brand). Note the gap and any launches or campaigns that explain it.  
  **Learn more:** [Dark AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/dark-ai-traffic-hidden-in-direct/)

- [ ] **G43 · You track early signals: AI crawl frequency and your entity's Knowledge Graph result**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** Changes in crawling and in how confidently Google recognises your entity tend to show up before changes in citations and traffic.  
  **How to check:** Monthly: AI bot hits per priority page from logs; Knowledge Graph Search API result for your brand (ID, name, resultScore). Google publishes no thresholds for resultScore, so compare it only with itself over time.  
  **Learn more:** [Dark AI traffic](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/dark-ai-traffic-hidden-in-direct/) · [Google: Knowledge Graph Search API](https://developers.google.com/knowledge-graph)

- [ ] **G44 · Wrong or outdated AI answers about you are traced back to their sources and fixed there**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Assistants repeat what their sources say. Correcting your own pages and the third-party records they rely on is the lasting fix; arguing with one answer is not.  
  **How to check:** For each inaccurate answer in the Prompt tracker, open the cited sources, find the wrong fact, and fix it on your site or request a correction from the third party. Recheck next month.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/)

---

## What this checklist can't promise

No checklist guarantees citations. AI answers vary by prompt wording, location, account and run, and providers change their systems often. Use the checks to remove the reasons you would be skipped, then measure what happens.

## Go deeper

- [AI Search Optimisation & Agentic SEO course](https://www.mlforseo.com/courses/ai-search-optimisation-agentic-seo/) (Beatrice Gamba, MLforSEO Academy)
- [MLforSEO resources library](https://www.mlforseo.com/resources-library/)

Created by Lazarina Stoy · MLforSEO. Free to use and adapt under the repository's MIT licence; please keep the credit.
