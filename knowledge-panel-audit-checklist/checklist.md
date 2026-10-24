# Knowledge Panel & Brand SERP Audit Checklist

*36 checks for your Google knowledge panel eligibility and brand SERP, ending with a prioritised action plan. By [Lazarina Stoy](https://www.mlforseo.com/experts/lazarina-stoy/) for [MLforSEO](https://www.mlforseo.com/), built on [Beatrice Gamba](https://www.mlforseo.com/experts/beatrice-gamba/)'s entity SEO articles. Checked October 2026.*

This is the plain-text version of `knowledge-panel-audit-checklist.xlsx`. The Google Sheets version adds a fact sheet that flags mismatches across platforms, a brand SERP log, a Knowledge Graph lookup log, an action plan and a progress dashboard.

Knowledge panels are generated automatically when Google's Knowledge Graph holds enough consistent, verifiable information about an entity; you can't apply for one. The work below builds those signals, and the same signals help AI assistants describe you accurately. Each check has an **evidence level**:

| Evidence | Meaning |
|---|---|
| Google-documented | Stated in Google Search Central or Google Help documentation |
| Platform-documented | Stated in another platform's own docs (Wikidata / Wikimedia, schema.org) |
| MLforSEO practice | What we teach and use in audits; sensible and low-risk, but not confirmed by the platforms |

**Priority:** High = fix first. Medium = do next. Low = monitor or nice to have.

## 1. Brand SERP baseline

- [ ] **K01 · Capture page one for your exact brand name, on desktop and mobile**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Your brand SERP is what people (and AI systems summarising the web) see when they look you up. You need a dated baseline before changing anything.  
  **How to check:** Search your brand name in a private window, set to your main country and language. Screenshot page one on desktop and mobile, then log each result in the 'Brand SERP log' tab.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K02 · Record which results you own or control**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Owned pages and official profiles are results you can keep accurate. Third-party results show how others describe you, for better or worse.  
  **How to check:** In the Brand SERP log, mark each result as Owned site, Official profile, Third party (positive / neutral / negative) or Namesake. The Progress tab shows your owned share.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K03 · Note which SERP features appear for your brand query and which kind of panel it is**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** A knowledge panel (an entity in Google's Knowledge Graph) and a Business Profile (a local business listing) look alike but are managed in different ways. Sitelinks, AI Overviews, videos and People Also Ask also shape the page.  
  **How to check:** List every feature on page one: knowledge panel, Business Profile, sitelinks, AI Overview, People Also Ask, Top stories, videos, images, social posts, reviews. Entity panels usually carry a short description (often sourced from a site such as Wikipedia) and may offer 'Claim this knowledge panel'; a panel with hours, directions and reviews is usually a Business Profile.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/) · [Google Help: about knowledge panels](https://support.google.com/knowledgepanel/answer/9163198)

- [ ] **K04 · Check the brand + modifier searches people actually run**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Searches like '[brand] reviews', '[brand] pricing', '[brand] vs [competitor]' and '[founder name]' are where wrong or negative information tends to surface.  
  **How to check:** Pull branded queries from Search Console (filter queries containing the brand). Search the top five modifiers and log anything inaccurate or unowned.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K05 · Ask AI assistants who you are and compare the answer with your canonical facts**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** AI answers draw on the same records as your knowledge panel. Wrong founding dates, products or locations point to the sources you need to correct.  
  **How to check:** Ask 'What is [brand]?' and 'Who founded [brand]?' in Google AI Mode, Gemini, ChatGPT and Perplexity. Compare against the Fact sheet tab and note every mismatch and the source cited.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/)

## 2. Knowledge Graph status

- [ ] **K06 · Look up your brand (and founder) in the Knowledge Graph Search API**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** The API shows whether Google's Knowledge Graph holds an entity for your name, its machine ID (kg:/m/... or kg:/g/...), type and description. No entity means a recognition problem comes before anything else.  
  **How to check:** Use the API Explorer on Google's Knowledge Graph Search API page or the MLforSEO Knowledge Graph API notebook with your own API key. Log the ID, name, @type, description and resultScore in the 'KG lookup log' tab. Google now points new projects to Cloud Enterprise Knowledge Graph and says this API isn't for production-critical use; it is fine for audits.  
  **Learn more:** [Knowledge Graph API notebook](https://www.mlforseo.com/resource/knowledge-graph-api-extraction-and-entity-relationship-analysis-for-semantic-keyword-research-notebook/) · [Google: Knowledge Graph Search API](https://developers.google.com/knowledge-graph)

- [ ] **K07 · Confirm the entity returned is you, not a namesake**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** If a famous person, place or another company with the same name comes back first, you have a disambiguation problem, and AI systems may attribute your content to the wrong entity.  
  **How to check:** Read the description and type of the top results. Search the API with your full name plus category (for example 'Acme Software'). Record which entity wins.  
  **Learn more:** [Entity disambiguation in practice](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/entity-disambiguation-in-practice/)

- [ ] **K08 · Open your entity's ID in Google Search to see the panel tied to it**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Searching by machine ID shows the panel Google associates with that entity, even when your brand query shows something else.  
  **How to check:** Search https://www.google.com/search?kgmid=/g/XXXX (use the ID from the API without the 'kg:' prefix). Screenshot the result.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K09 · Look for duplicate or fragmented entities for your brand**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Name variants ('Acme', 'Acme Corp', 'Acme Corporation') can create several thin entities instead of one strong one.  
  **How to check:** Query each name variant and your founder in the API. If more than one ID describes your organisation, note them all and make naming consistent everywhere (area 5).  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/)

- [ ] **K10 · Treat resultScore as a relative signal only**  
  *Priority: Low · Evidence: Google-documented*  
  **Why it matters:** Google documents resultScore as an indicator of how well an entity matched the request and publishes no thresholds. It moves with the query, so compare it only with itself over time.  
  **How to check:** Run the same query monthly and log the score in the KG lookup log. Rising scores and a stable ID are good signs; a changing ID is worth investigating.  
  **Learn more:** [Entity disambiguation in practice](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/entity-disambiguation-in-practice/) · [Google: Knowledge Graph Search API](https://developers.google.com/knowledge-graph)

## 3. Wikidata & Wikipedia

- [ ] **K11 · Search Wikidata for an existing item before creating anything**  
  *Priority: High · Evidence: Platform-documented*  
  **Why it matters:** Duplicate items are the most common reason brand entries get deleted. Someone may already have created one for you.  
  **How to check:** Search wikidata.org for your brand, legal name and founders. Record any Q-IDs in the Fact sheet. If one exists, improve it rather than starting again.  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikidata: notability policy](https://www.wikidata.org/wiki/Wikidata:Notability)

- [ ] **K12 · If an item exists, check it is accurate, neutral and referenced**  
  *Priority: High · Evidence: Platform-documented*  
  **Why it matters:** Wikidata is openly licensed and widely reused by search and AI systems, so errors there spread. Unreferenced statements are easy to challenge.  
  **How to check:** Check label, description (short and neutral, no promotional language), instance of, country, official website, inception, founders, headquarters and social media IDs. Every statement should cite an external source.  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikidata: notability policy](https://www.wikidata.org/wiki/Wikidata:Notability)

- [ ] **K13 · If there is no item, check notability before creating one**  
  *Priority: Medium · Evidence: Platform-documented*  
  **Why it matters:** Wikidata accepts entities that can be described using serious, publicly available references: registries, authority records, databases and independent coverage. Your own website on its own isn't enough.  
  **How to check:** List your external references (company registry, Crunchbase, trade press, conference programmes, industry databases). If you have two or three solid ones, you likely qualify; if not, earn coverage first (area 6).  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikidata: notability policy](https://www.wikidata.org/wiki/Wikidata:Notability)

- [ ] **K14 · Declare any conflict of interest when you or your agency edit**  
  *Priority: High · Evidence: Platform-documented*  
  **Why it matters:** Editing your own organisation's item or article is a conflict of interest. On Wikipedia, paid editing must be disclosed under the Wikimedia Terms of Use, and you should propose changes on the article's Talk page rather than editing directly.  
  **How to check:** Use a personal, clearly identifiable account. Note your connection on your user page. For Wikipedia, request edits on the Talk page with independent sources.  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikipedia: conflict of interest guideline](https://en.wikipedia.org/wiki/Wikipedia:Conflict_of_interest)

- [ ] **K15 · Record whether a Wikipedia article exists and is accurate**  
  *Priority: Low · Evidence: Platform-documented*  
  **Why it matters:** Wikipedia is a strong source for knowledge panels, but its notability bar (significant coverage in independent, reliable sources) excludes most small and mid-size brands. Not having one is normal.  
  **How to check:** Search Wikipedia in your main languages. If an article exists, log factual errors and suggest corrections on its Talk page with sources. Don't write your own article.  
  **Learn more:** [Wikidata for brands](https://www.mlforseo.com/knowledge-graph-strategy/wikidata-for-brands-notability-criteria-and-a-realistic-path/) · [Wikipedia: conflict of interest guideline](https://en.wikipedia.org/wiki/Wikipedia:Conflict_of_interest)

## 4. On-site entity markup

- [ ] **K16 · Organization (or Person / ProfilePage) markup sits on your home or about page**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Google recommends placing Organization markup on the home page or a single page describing the organisation. It helps Google understand your details and which logo to show, including in knowledge panels. For a person, ProfilePage markup with a Person as mainEntity does the same job.  
  **How to check:** View Source on the home and about pages. Check for name, alternateName, legalName, url, logo, description, foundingDate, founder, address, contactPoint and sameAs. Validate with the Rich Results Test and Schema Markup Validator.  
  **Learn more:** [Structured data and entity understanding](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/how-structured-data-reinforces-entity-understanding-in-ai-search/) · [Google: Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization)

- [ ] **K17 · The logo in your markup is a crawlable image of at least 112 x 112 px**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google's Organization guidelines set this minimum and say the logo property helps Google choose the logo for Search results and knowledge panels.  
  **How to check:** Open the logo URL from the markup: it should load directly (not blocked by robots.txt), be square-friendly and look right on a white background.  
  **Learn more:** [Structured data and entity understanding](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/how-structured-data-reinforces-entity-understanding-in-ai-search/) · [Google: Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization)

- [ ] **K18 · Organization and founders have stable @id values that other markup points to**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** A stable @id lets every article, product and author page reference the same entity, so signals add up instead of scattering across separate declarations.  
  **How to check:** Check the Organization @id never changes between pages, and that Article publisher, Person worksFor and Product brand reference it.  
  **Learn more:** [What schema.org @id does](https://www.mlforseo.com/machine-learning-implementation-guides/structured-data-audit/what-schema-org-id-does-and-why-your-entity-graph-falls-apart-without-it/)

- [ ] **K19 · Every sameAs link resolves to an official profile showing the same name**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** schema.org defines sameAs as a page that unambiguously indicates the item's identity. A broken or mismatched link is a failed confirmation, which is worse than no link.  
  **How to check:** Open each sameAs URL; log status code and displayed name in the Fact sheet. Include Wikidata, LinkedIn, Crunchbase, official social profiles and relevant industry directories.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [schema.org: sameAs](https://schema.org/sameAs)

- [ ] **K20 · Your about page states the canonical facts in plain text, matching the markup**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Structured data should describe what is visible on the page. Plain-text facts also give AI systems and journalists something to quote.  
  **How to check:** Compare the about page text with the JSON-LD and the Fact sheet: name, founding date, founders, headquarters, what you do in one sentence.  
  **Learn more:** [Consistency beats completeness](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/consistency-beats-completeness-structured-data/) · [Google: structured data policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)

- [ ] **K21 · Your brand is the most prominent entity on your home and about pages**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** If navigation labels or product names outscore your brand in entity extraction, the pages meant to define you send a weak signal.  
  **How to check:** Run Google's Natural Language API (or the MLforSEO no-code template) on the full page and on the main content only. Your brand should lead on salience. Use <nav>, <main> and <footer> elements.  
  **Learn more:** [Why navigation outranks your brand](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/why-navigation-elements-outrank-your-brand-in-entity-analysis/)

## 5. Cross-platform consistency

- [ ] **K22 · Create a single source of truth for your canonical facts**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** One agreed version of each fact makes every later update quick and consistent. Without it, teams rediscover the platform list each time and miss some.  
  **How to check:** Fill in column B of the 'Fact sheet' tab: canonical name, legal name, founding date, founders, headquarters, website URL, one-sentence description, category, employee range, logo URL.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/)

- [ ] **K23 · Audit every profile against the fact sheet**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** Each platform holding facts about you is a verification point for Google and AI systems. Consistent points add confidence; inconsistent ones subtract it.  
  **How to check:** Fill the platform columns in the Fact sheet: website and schema, LinkedIn, Crunchbase, Wikidata, Business Profile, X, YouTube, industry directories, company registry. Cells that differ from column B turn red.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/)

- [ ] **K24 · Fix contradictions first, then fill gaps**  
  *Priority: High · Evidence: MLforSEO practice*  
  **Why it matters:** A missing fact is neutral. Conflicting facts (founded 2011 here, 2013 there) are a conflict systems can't resolve, so they may drop the fact or lower confidence in the whole entity.  
  **How to check:** Sort the Fact sheet by red cells. Correct the platforms you control, then request corrections from third parties with a link to an authoritative source.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/)

- [ ] **K25 · Founders and leaders have consistent, linked profiles**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** People entities reinforce the organisation. Consistent names, titles and employers across author pages, speaker bios and LinkedIn give systems a second route to recognising you.  
  **How to check:** Check each founder's LinkedIn, author page, speaker bios and Wikidata (if any) use the same name, title and employer. Link the person's markup to the Organization @id.  
  **Learn more:** [Trust isn't a schema field](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/trust-is-not-a-schema-field/) · [Google: ProfilePage structured data](https://developers.google.com/search/docs/appearance/structured-data/profile-page)

## 6. Corroboration

- [ ] **K26 · List the independent sources that already describe you**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Google cross-checks your claims against external sources. Five consistent mentions in respected publications do more than fifty thin directory listings.  
  **How to check:** Search your brand in news, trade publications, podcasts, conference programmes, registries and databases. Log each source and whether its facts match the Fact sheet.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K27 · Plan coverage that would make your key facts independently verifiable**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Panels appear when enough independent sources agree. Most brands need more third-party coverage before anything else moves.  
  **How to check:** Pick realistic targets: industry publications, podcast interviews, conference talks, guest articles, partner pages, awards. Track them in the Action plan tab.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

- [ ] **K28 · Third-party mentions place you next to your category and peers**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** Co-occurrence with category terms, partners and competitors tells systems which 'Acme' you are and what you're relevant for.  
  **How to check:** Check how press and partner pages describe you. Ask for your full name plus a short category descriptor in bios and boilerplates.  
  **Learn more:** [How LLMs co-cite](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/how-llms-co-cite-building-authority-by-association/)

## 7. Claim & manage

- [ ] **K29 · If a knowledge panel shows, claim it through an official profile**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Verified representatives can suggest changes to their panel and choose a featured image. Not every panel is claimable yet, so check back if the option is missing.  
  **How to check:** Signed in to a Google Account, search for the entity, click 'Claim this knowledge panel' at the bottom of the panel, then sign in to one of the listed official sites or profiles (such as Search Console, YouTube, X or Facebook).  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/) · [Google Help: get verified on Google](https://support.google.com/knowledgepanel/answer/7534902)

- [ ] **K30 · Once verified, suggest corrections with evidence and add team members**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Feedback from verified representatives is prioritised, and edits backed by links to verifying pages are more likely to be accepted.  
  **How to check:** Use Feedback below the panel, flag the fact, describe the correction and link to pages that confirm it. Add colleagues as Contributors or Managers at google.com/search/contributions/manage.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/) · [Google Help: get verified on Google](https://support.google.com/knowledgepanel/answer/7534902)

- [ ] **K31 · Local businesses: claim and verify your Business Profile separately**  
  *Priority: High · Evidence: Google-documented*  
  **Why it matters:** Business Profiles look like knowledge panels but cover businesses serving customers at a location or in a service area, and are managed through Google Business Profile.  
  **How to check:** Claim or create the profile in Google Business Profile, verify it, and make name, address, phone, hours and website match the Fact sheet.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/) · [Google Help: about knowledge panels](https://support.google.com/knowledgepanel/answer/9163198)

- [ ] **K32 · If the panel mixes you up with someone else or shows the wrong profiles, contact support**  
  *Priority: Medium · Evidence: Google-documented*  
  **Why it matters:** Google's knowledge panel help lists mixed-up entities and wrong websites or profiles as cases for its support team, and runs an account recovery process if someone else already manages your panel.  
  **How to check:** Follow the troubleshooting steps in Google's 'Get verified on Google' help article. Keep screenshots and links to authoritative sources ready.  
  **Learn more:** [Entity disambiguation in practice](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/entity-disambiguation-in-practice/) · [Google Help: get verified on Google](https://support.google.com/knowledgepanel/answer/7534902)

- [ ] **K33 · Own more of page one for brand and brand + modifier searches**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Official profiles, a clear site structure (for sitelinks) and pages answering pricing, reviews and comparison questions keep accurate information near the top.  
  **How to check:** Fill gaps from the Brand SERP log: complete official profiles, add or improve pages for top branded modifiers, link profiles from the site and markup.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

## 8. Monitor

- [ ] **K34 · Monthly: check the top five platforms and rerun the brand SERP and KG lookups**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** Third parties edit your records and Google updates panels automatically as the web changes. Small, regular checks stop drift.  
  **How to check:** Each month: website, LinkedIn, Wikidata, Crunchbase, Business Profile against the Fact sheet; add a new row to the KG lookup log; note SERP changes in the Brand SERP log.  
  **Learn more:** [Entity audit cadence](https://www.mlforseo.com/machine-learning-tutorials/entity-analysis/entity-audit-cadence-what-to-check-weekly-monthly-quarterly/)

- [ ] **K35 · Update every platform within a week of a material change**  
  *Priority: Medium · Evidence: MLforSEO practice*  
  **Why it matters:** New leadership, a move, an acquisition or a rebrand makes old facts wrong everywhere at once. Stale data on Wikidata and profiles propagates to other systems.  
  **How to check:** Update the Fact sheet first, then work through every platform column. Add the change to the Action plan with an owner and date.  
  **Learn more:** [Cross-platform entity consistency](https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/cross-platform-entity-consistency-the-llm-era/)

- [ ] **K36 · Quarterly: repeat the full audit and the AI answer check**  
  *Priority: Low · Evidence: MLforSEO practice*  
  **Why it matters:** Panels usually take months of consistent signals to appear: six to eighteen months for most brands in MLforSEO's experience. Quarterly reviews show whether the work is moving the entity.  
  **How to check:** Duplicate this sheet (or add a dated column to the logs), rerun every check, and compare KG ID, panel presence, owned share of page one and AI answer accuracy with last quarter.  
  **Learn more:** [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/)

---

## Prioritised action plan

1. Agree the canonical facts and fill in the fact sheet (K22).
2. Fix contradictions on your own site and markup: about page, Organization markup, @id, sameAs (K16 to K21, K24).
3. Align the profiles you control: LinkedIn, Crunchbase, social profiles, directories, Business Profile (K23 to K25, K31).
4. Claim the knowledge panel if one exists and submit evidence-backed corrections (K29, K30, K32).
5. Improve or create the Wikidata item if you meet notability, declaring any conflict of interest (K11 to K14).
6. Earn independent coverage that confirms your key facts (K26 to K28).
7. Fill the gaps on page one for brand and brand + modifier searches (K33).
8. Put the monthly and quarterly checks in your calendar (K34 to K36).

## Realistic expectations

Google doesn't publish a threshold for showing a panel. In MLforSEO's experience it takes six to eighteen months of consistent signals for most brands. The same work helps AI assistants recognise and describe you, so it pays off before a panel appears.

## Go deeper

- [What it takes to earn a Google knowledge panel](https://www.mlforseo.com/knowledge-graph-strategy/what-it-takes-to-earn-a-google-knowledge-panel/) (Beatrice Gamba)
- [AI Search & LLMs: Entity SEO and Knowledge Graph Strategies for Brands](https://www.mlforseo.com/courses/ai-search-llms-entity-seo-and-knowledge-graph-strategies-for-brands/) (MLforSEO Academy)
- [Knowledge Graph API notebook](https://www.mlforseo.com/resource/knowledge-graph-api-extraction-and-entity-relationship-analysis-for-semantic-keyword-research-notebook/)

Created by Lazarina Stoy · MLforSEO. Free to use and adapt under the repository's MIT licence; please keep the credit.
