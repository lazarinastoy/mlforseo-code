# Automatically generate meta descriptions with Python: from BERT to LLMs

Companion code for the MLforSEO tutorial by Lazarina Stoy (originally published on lazarinastoy.com in 2021 as
"Automatically Generate Your Meta Descriptions Using Python and BERT", refreshed in October 2026).

Three notebooks. Each one takes the same input (a CSV of URLs and page text, or a plain list of URLs), writes a meta description
for every page, flags anything a human should check, and saves a CSV for review.

| Notebook | Method | Cost | Can it invent facts? |
|---|---|---|---|
| `01_bert_extractive_refreshed.ipynb` | The 2021 method: BERT extractive summarisation (`bert-extractive-summarizer`), with the bugs fixed | Free, local | No, it only picks existing sentences |
| `02_modern_local_embeddings_and_small_llm.ipynb` | (a) Sentence-embedding extraction steered by title/top query (`sentence-transformers`) and (b) a small open LLM (`Qwen/Qwen3-1.7B`) writing new descriptions | Free, local (GPU or Apple silicon recommended for (b)) | (a) No. (b) Yes, so outputs are checked |
| `03_llm_assisted_claude_with_guardrails.ipynb` | Hosted LLM (Claude via the Anthropic API) with a grounded prompt, cost estimate, dry-run mode and output checks | Paid per token | Yes, so outputs are checked and need human approval |

## Input

`inputdata.csv`, the same format as the 2021 tutorial:

- Column A: `URL`
- Column B: `Content` (the page's main text, e.g. from a Screaming Frog custom extraction)
- Optional: `Title`, `Top query` (e.g. the top Search Console query per page)

Or set `SCRAPE_FROM_URL_LIST = True` and put one URL per line in `urls.txt`. `trafilatura` then fetches the main text and the title for you.

The sample `inputdata.csv` contains five MLforSEO pages. The `Top query` values are illustrative, not real Search Console data.

## Output

`output_bert.csv`, `output_modern.csv`, `output_claude.csv`: one row per URL with the generated description(s) and a `check` column:

- `SHORT` / `LONG`: outside 70 to 155 characters
- `NUMBER NOT IN PAGE` / `NAME NOT IN PAGE`: a number or capitalised name in the description that doesn't appear in the page text (the most common hallucinations)
- `TOP QUERY MISSING`: none of the query's words made it into the description
- `DUPLICATE`: the same description on more than one URL
- `~page`: embedding similarity between the description and the page (low = drifted off-topic)

The checks flag problems; they don't prove a description is good. Review before you import anything.

`example_outputs/` has the outputs from our test run on the sample data (2026-10-21).

## Running

**Google Colab (easiest):** upload a notebook, upload `inputdata.csv`, run all. Each notebook installs what it needs in its first cell.
For notebook 02, switch to a GPU runtime (Runtime → Change runtime type → T4 GPU). For notebook 03, add `ANTHROPIC_API_KEY` under Secrets.

**Locally:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
jupyter notebook
```

First runs download models: `bert-large-uncased` (about 1.3 GB), `all-MiniLM-L6-v2` (about 90 MB) and `Qwen3-1.7B` (about 3.4 GB).

## What changed from the 2021 code

- `pd.read_csv(..., error_bad_lines=False)` → `on_bad_lines="skip"` (the old argument was removed in pandas 2.0).
- `Summarizer()` was created inside the loop, which reloaded BERT for every URL. It's now loaded once.
- `model(body, max_length=150)` didn't limit the output length: `min_length`/`max_length` filter which sentences are considered (in characters).
  Output size comes from `ratio` (default 20% of sentences) or `num_sentences`. On our sample pages the 2021 call returned 138 to 1,419 characters.
  The refreshed call uses `num_sentences=1, min_length=60, max_length=155` and exposes `use_first` (default `True`, which always keeps the first sentence).
- The "BERT only works on texts longer than 400 words" note was inaccurate: the library summarised a 233-word page fine. Very short texts (under ~40 words) are skipped and left for a human.
- New: scraping via `trafilatura`, quality checks, duplicate detection, the embedding and LLM methods, and cost estimation for hosted LLMs.

## Tested with

Python 3.9.6 on macOS (Apple silicon, MPS): pandas 2.3.3, torch 2.8.0, transformers 4.57.6, sentence-transformers 5.1.2,
bert-extractive-summarizer 0.10.1, spacy 3.7.5, trafilatura 2.0.0. Notebook 03 was run in `DRY_RUN` mode only (prompt building and cost
estimation). The live API call follows the current Anthropic Python SDK docs but was not executed during the refresh.

## Licence and credits

Code by Lazarina Stoy / MLforSEO. The BERT summariser is Derek Miller's `bert-extractive-summarizer` (MIT). Qwen3 is released by Alibaba under Apache 2.0.
