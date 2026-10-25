# Image SEO + multimodal audit (2026)

Companion code for the MLforSEO guide **"Image SEO in 2026: the complete guide to image optimisation, advanced tactics and multimodal search"** by Lazarina Stoy.

## What it does

`image_seo_audit.py` (script) and `image_seo_multimodal_audit.ipynb` (Colab wrapper) take a list of page URLs and:

| Step | What you get | How |
|---|---|---|
| 1. Crawl | Every `<img>` (incl. `data-src` lazy-load patterns and `srcset`), `<picture>` source types, inline CSS background images, `og:image`, `figcaption`, `max-image-preview` | requests + BeautifulSoup |
| 2. Audit | Real format (from the bytes, not the extension), file size, pixel size, AVIF/WebP negotiation via the `Accept` header, plus the checks below | Pillow |
| 3. Alt-text drafts (optional) | A suggested alt text for each image with **no alt attribute** | Open vision-language model from Hugging Face (default `HuggingFaceTB/SmolVLM-500M-Instruct`, Apache 2.0), or the OpenAI / Gemini API |
| 4. Classification (optional) | A zero-shot label for every image (product on white, lifestyle, stock people, infographic, screenshot, logo, headshot...) so you can see your image mix | CLIP `openai/clip-vit-base-patch32`, your own labels via `--labels` |
| 5. Near-duplicates (optional) | Pairs of images that are resized copies (perceptual hash) or visually near-identical (CLIP cosine similarity) | `openai/clip-vit-base-patch32` + ImageHash pHash |

### Checks (the `issues` column)

| Issue | Meaning |
|---|---|
| `missing_alt_attribute` | No `alt` at all. Fix it (screen readers fall back to the file name) |
| `empty_alt_check_if_decorative` | `alt=""`. Correct for decorative images, wrong for meaningful ones |
| `alt_over_125_chars` | Long alt text (accessibility convention, not a Google limit). Threshold: `--alt-max` |
| `alt_looks_like_filename`, `alt_repetitive_possible_stuffing` | Lazy or stuffed alt text |
| `generic_file_name` | `IMG_0023.jpg`, `Untitled-design-39.png`, `screenshot-1.png`... |
| `missing_width_height_attrs` | Layout shift (CLS) risk |
| `first_image_lazy_loaded_lcp_risk` | The first image in the HTML has `loading="lazy"`; if it's your LCP image, that delays it. Heuristic: check which element really is LCP in PageSpeed Insights |
| `over_200kb` | Heavier than `--max-kb` (no official Google threshold; Screaming Frog's default is 100 KB) |
| `legacy_format_consider_avif_webp` | JPEG/PNG/GIF over 50 KB with no AVIF/WebP `<source>` |
| `large_image_no_srcset` | 800px+ wide with no responsive variants |
| `intrinsic_much_larger_than_declared` | File is 2.5x+ wider than its `width` attribute |
| `css_background_not_indexed` | Inline CSS background image. Google doesn't index CSS images |
| `og_image_under_1200px_wide` | Below the size Google recommends for Discover / large previews |
| `http_4xx/5xx` | Broken image |
| `tracking_pixel_ignored` | 1x1 pixels are skipped |

## Usage

```bash
pip install -r requirements.txt

# audit only (fast, no ML)
python image_seo_audit.py --urls urls.txt --out results

# + alt-text drafts with a local open model, CLIP classification and near-duplicate detection
python image_seo_audit.py --urls urls.txt --out results --suggest-alt --classify --dedupe

# your own classification labels (write them as captions)
python image_seo_audit.py --urls urls.txt --classify --labels "a red trainer|a blue trainer|a shoe box"

# a stronger open model (better on a GPU; ~11 s/image on an M-series CPU)
python image_seo_audit.py --urls urls.txt --suggest-alt --alt-model Qwen/Qwen3-VL-2B-Instruct

# an API instead (keys from the environment only)
export OPENAI_API_KEY=...   # optional: OPENAI_VISION_MODEL (default gpt-4.1-mini)
python image_seo_audit.py --urls urls.txt --suggest-alt --alt-backend openai
export GEMINI_API_KEY=...   # optional: GEMINI_VISION_MODEL (default gemini-2.5-flash)
python image_seo_audit.py --urls urls.txt --suggest-alt --alt-backend gemini
```

`urls.txt` has one page URL per line (`#` lines are ignored). Useful flags: `--max-kb`, `--alt-max`, `--alt-limit` (cap on images captioned per run, default 25), `--dup-threshold` (CLIP cosine, default 0.95), `--phash-max` (default 8), `--delay` (seconds between pages, default 1).

In Colab, open the notebook, put your URLs in cell 2 and run everything. API keys go in Colab's Secrets panel.

## Outputs

* `images.csv`: one row per image occurrence, with all attributes, measurements, `issues`, `alt_suggestion` and (with `--classify`) `clip_label` + `clip_label_score`
* `pages.csv`: per-page counts (missing alt, heavy images, missing dimensions, total image KB, og:image, max-image-preview)
* `duplicates.csv`: image pairs with `clip_cosine`, `phash_distance` and a verdict

`example_output/` has the results of the test run below.

## Tested (22 October 2026)

Python 3.12, torch 2.14.1, transformers 5.20.2, Pillow 13.0.0, on four public pages (mlforseo.com, Google's Image SEO best practices doc, web.dev's image CDN article, Wikipedia's Labrador Retriever article). Findings worth knowing before you trust the ML parts:

* **Alt-text drafts are drafts.** On seven test images (`example_output/alt_model_comparison.csv`), SmolVLM-500M invented text on a dog's vest ("SERVICE" and "TURF") and an imaginary breed ("Whiskey Stout"). Qwen3-VL-2B was more accurate but still called a chocolate Labrador black. Neither model could explain what Google's diagrams were *for*. Both need a human.
* **Page context can make small models worse.** Passing the page title to SmolVLM made it reply with the title ("Golden Retriever - Wikipedia"). Context is off by default for local models and on for the API backends (larger models generally use context better, and the OpenAI backend was tested on 25 October 2026 with `gpt-4.1-mini` on two images: both drafts were accurate, one left out the dog's colour, so review them all the same; model names change often, so set `OPENAI_VISION_MODEL` / `GEMINI_VISION_MODEL` to a current vision model).
* **CLIP thresholds need calibrating.** Two *different* photos of Labradors scored ~0.92; the *same* photo at 250px and 1280px scored ~0.95; two different Google diagrams built on the same template scored 0.97. That's why the script also uses a perceptual hash: a pHash distance of 0 caught the resized copy straight away.
* **Wikimedia rate-limits non-standard thumbnail sizes** (HTTP 429). The script backs off and retries; if you audit Wikipedia-hosted images, expect some gaps.
* **Zero-shot labels were right on every clear case** (logos, headshots, animal photos, Google's diagrams as "infographic or chart") and least confident on mixed images (a URL-anatomy diagram scored 0.38 as "screenshot"). Treat scores under ~0.5 as "look at this one".
* Transformers v5 removed the old `image-to-text` pipeline. The script uses `AutoModelForImageTextToText`, which works on 4.57+ and 5.x.

## Files

* `image_seo_audit.py`: the script (CLI + importable `run()`)
* `image_seo_multimodal_audit.ipynb`: Colab notebook (outputs cleared)
* `requirements.txt`: dependencies
* `example_output/`: CSVs from the test run
