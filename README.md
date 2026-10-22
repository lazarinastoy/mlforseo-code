# MLforSEO code

Notebooks, scripts and templates from [MLforSEO](https://www.mlforseo.com/) tutorials: practical machine learning and AI-search workflows for SEOs and marketers, by [Lazarina Stoy](https://lazarinastoy.com/).

Each folder belongs to one tutorial and has its own README (what it does, how to run it, what to install). Most notebooks run in Google Colab with no local setup.

| Folder | Tutorial | What's inside |
|---|---|---|
| [`fuzzy-matching-for-seo/`](fuzzy-matching-for-seo/) | What fuzzy matching is, and where it fits in SEO | RapidFuzz / TheFuzz / PolyFuzz comparison, redirect & duplicate matching, phonetic matching |
| [`pytrends-google-trends-api/`](pytrends-google-trends-api/) | The ultimate guide to PyTrends: the Google Trends API (with Python code examples) | Tested 2026 PyTrends methods, 429 handling, TrendSpy fallbacks, share of search |
| [`meta-descriptions-python/`](meta-descriptions-python/) | How to automatically generate meta descriptions with Python: from BERT to LLMs | BERT extractive (refreshed), embeddings + small open model, LLM with guardrails |
| [`sentiment-analysis-methods/`](sentiment-analysis-methods/) | Sentiment analysis: theory, methods and 7 practical applications | VADER/AFINN vs TF-IDF+LogReg vs RoBERTa benchmark, Google NL API v1/v2, SERP title sentiment chart |
| [`topic-modeling-lda/`](topic-modeling-lda/) | Topic modeling for SEO with LDA | gensim LDA + coherence/perplexity, pyLDAvis, short-text tests, internal-link candidates |
| [`topic-modeling-bertopic/`](topic-modeling-bertopic/) | Topic modeling for SEO with BERTopic | BERTopic 0.17 pipeline, short-text limitations and fixes, LDA/NMF/BERTopic comparison |
| [`search-intent-regex-classifier/`](search-intent-regex-classifier/) | Search intent classification with machine learning approaches | Rule-based multi-label intent classifier; exports Data Studio calculated field + Sheets formula |
| [`search-intent-classification/`](search-intent-classification/) | Search intent classification with machine learning approaches | Five free Colabs: rule-based (query), SERP features, semantic (Google NL + spaCy), BART zero-shot, content format/platform from SERP |
| [`intent-mismatch-audit/`](intent-mismatch-audit/) | How to build a search intent-first website architecture | Search Console page/query export → intent match/mismatch audit, KPIs per page type, link suggestions |
| [`multilingual-intent-classification/`](multilingual-intent-classification/) | How to do intent-driven international keyword research | EN/ES/DE/FR intent filters, false-friend checks, per-market comparison, regex export |
| [`serp-analysis-machine-learning/`](serp-analysis-machine-learning/) | 4 ways to boost your SERP competitor analysis with machine learning | SERP categorisation, spaCy entities, n-grams (+ Sheets custom function), LLM structured outputs |
| [`indexnow-api-python/`](indexnow-api-python/) | The ultimate guide to the IndexNow API (with Python) | Working IndexNow submitter (batches, retries, logs) + URL Inspection API indexation checker |
| [`structured-data-automation/`](structured-data-automation/) | Structured data automation with Python | Audit existing markup, generate connected JSON-LD from CSV/SQL, validate vs schema.org + Google |
| [`screaming-frog-web-scraping/`](screaming-frog-web-scraping/) | Web scraping of page content with Screaming Frog | Test CSS/XPath selectors before crawling; clean custom-extraction exports into CSV/JSONL |
| [`internal-link-audit-topic-clustering/`](internal-link-audit-topic-clustering/) | SEO internal link audit and topic clustering with ML | Link metrics, anchor classification, embeddings + clustering, missing-link suggestions |
| [`youtube-seo-audit-benchmark/`](youtube-seo-audit-benchmark/) | How to do a YouTube SEO audit | YouTube Data API competitor benchmark table for channel audits |
| [`google-sheets-formulas-for-seo/`](google-sheets-formulas-for-seo/) | 12 Google Sheets formulas for SEO keyword research & content analysis | Copyable modern formulas (LET/LAMBDA/BYROW), rules tabs, sample data, 107-check test script |
| [`image-seo-multimodal/`](image-seo-multimodal/) | Image SEO in 2026: advanced tactics and multimodal search | Page image audit (format, size, alt), vision-model alt-text drafts, CLIP classification + near-duplicate detection |

More folders arrive as tutorials are refreshed. The full list of MLforSEO templates, Colabs and workbooks, free and Academy, is in [CATALOGUE.md](CATALOGUE.md).

## Learn the method
These notebooks pair with the courses on the [MLforSEO Academy](https://academy.mlforseo.com/), starting with *Introduction to Machine Learning for SEO*.

## Licence
Code is MIT-licensed (see [LICENSE](LICENSE)). Tutorial text and templates © Lazarina Stoy / MLforSEO.
