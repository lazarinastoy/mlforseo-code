#!/usr/bin/env python3
"""
Image SEO + multimodal audit for a list of pages.

Companion code for the MLforSEO guide "Image SEO in the age of multimodal
search" by Lazarina Stoy. It does four things:

  1. Crawls a list of page URLs and extracts every <img>, <picture> source,
     inline CSS background image, og:image and figcaption.
  2. Downloads each image once and audits it: real format, file size, pixel
     dimensions, alt text, file name, width/height attributes, srcset,
     lazy-loading on the first (likely LCP) image, and whether the server
     negotiates AVIF/WebP from the Accept header.
  3. (Optional) Suggests alt text for images with a missing alt attribute,
     using an open vision-language model from Hugging Face (default) or a
     pluggable API backend (OpenAI or Gemini). Keys come from environment
     variables only. Nothing is hardcoded.
  4. (Optional) Classifies every image zero-shot with CLIP (product shot,
     lifestyle, stock people, infographic, screenshot, logo...) so you can see
     your image mix at a glance.
  5. (Optional) Finds near-duplicate images across the whole site with CLIP
     embeddings (cosine similarity) plus a perceptual hash for exact-ish copies.

Usage:
    python image_seo_audit.py --urls urls.txt --out results/
    python image_seo_audit.py --urls urls.txt --out results/ --dedupe --suggest-alt
    python image_seo_audit.py --urls urls.txt --suggest-alt --alt-backend openai

    python image_seo_audit.py --urls urls.txt --classify --labels "red shoe|blue shoe|shoe box"

Outputs (CSV): images.csv, pages.csv, duplicates.csv (if --dedupe).

Suggested alt text is a DRAFT for a human to review. Read the guide's section on
the caveats before you paste anything into a CMS.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import re
import sys
import time
import warnings
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urljoin, urlparse, unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image

warnings.filterwarnings("ignore")

try:  # AVIF decoding on older Pillow builds
    import pillow_avif  # noqa: F401
except Exception:
    pass

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36 mlforseo-image-audit/1.0")
ACCEPT_MODERN = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
ACCEPT_LEGACY = "image/jpeg,image/png,image/*;q=0.8"

GENERIC_NAME = re.compile(
    r"^(img|image|dsc|dscn|dcim|pxl|photo|pic|screenshot|screen[-_ ]?shot|"
    r"untitled|unnamed|download|whatsapp[-_ ]?image|capture|frame|copy[-_ ]?of)"
    r"[-_ ]?\d*|^\d+$|^[a-f0-9]{16,}$", re.I)
LEGACY_FORMATS = {"JPEG", "PNG", "GIF", "BMP", "TIFF"}


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------
@dataclass
class ImageRow:
    page_url: str
    image_url: str
    position: int                     # order on the page (1 = first in HTML)
    source: str                       # img | picture-source | css-background | og:image
    alt: Optional[str] = None         # None = attribute missing, "" = empty (decorative)
    has_alt_attr: bool = False
    figcaption: str = ""
    nearby_text: str = ""
    width_attr: str = ""
    height_attr: str = ""
    loading: str = ""
    fetchpriority: str = ""
    has_srcset: bool = False
    picture_types: str = ""
    # filled after download
    status: Optional[int] = None
    content_type: str = ""
    format: str = ""
    bytes: Optional[int] = None
    px_width: Optional[int] = None
    px_height: Optional[int] = None
    negotiates_modern: Optional[bool] = None
    issues: list = field(default_factory=list)
    alt_suggestion: str = ""


# --------------------------------------------------------------------------
# Crawling
# --------------------------------------------------------------------------
def get(url: str, accept: str = "text/html,*/*", timeout: int = 20, stream=False):
    return requests.get(url, headers={"User-Agent": UA, "Accept": accept},
                        timeout=timeout, stream=stream, allow_redirects=True)


def best_from_srcset(srcset: str) -> str:
    """Return the largest candidate URL from a srcset string."""
    best, best_w = "", -1.0
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0.0
        if len(bits) > 1:
            d = bits[1]
            try:
                w = float(d[:-1]) * (1 if d.endswith("w") else 1000)
            except ValueError:
                w = 0.0
        if w > best_w:
            best, best_w = bits[0], w
    return best


def text_near(tag, limit=300) -> str:
    """Grab a little visible text around an image, for context."""
    for parent in tag.parents:
        if parent.name in ("figure", "p", "li", "section", "article", "div"):
            txt = " ".join(parent.get_text(" ", strip=True).split())
            if len(txt) > 40:
                return txt[:limit]
    return ""


def extract_images(page_url: str, html: str) -> tuple[list[ImageRow], dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[ImageRow] = []
    pos = 0

    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or img.get("data-lazy-src") or "")
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        if (not src or src.startswith("data:")) and srcset:
            src = best_from_srcset(srcset)
        if not src or src.startswith("data:"):
            continue
        pos += 1
        picture = img.find_parent("picture")
        types = ""
        if picture:
            types = ",".join(s.get("type", "?") for s in picture.find_all("source"))
        fig = img.find_parent("figure")
        cap = fig.find("figcaption").get_text(" ", strip=True) if fig and fig.find("figcaption") else ""
        rows.append(ImageRow(
            page_url=page_url, image_url=urljoin(page_url, src.strip()), position=pos,
            source="img", alt=img.get("alt"), has_alt_attr=img.has_attr("alt"),
            figcaption=cap[:300], nearby_text=text_near(img),
            width_attr=str(img.get("width", "")), height_attr=str(img.get("height", "")),
            loading=(img.get("loading") or "").lower(),
            fetchpriority=(img.get("fetchpriority") or "").lower(),
            has_srcset=bool(srcset), picture_types=types,
        ))

    # Inline CSS background images: Google doesn't index these as images.
    for el in soup.select("[style*='background']"):
        for m in re.finditer(r"url\(['\"]?([^'\")]+)['\"]?\)", el.get("style", "")):
            if m.group(1).startswith("data:"):
                continue
            pos += 1
            rows.append(ImageRow(page_url=page_url, image_url=urljoin(page_url, m.group(1)),
                                 position=pos, source="css-background"))

    meta = {
        "title": (soup.title.get_text(strip=True) if soup.title else ""),
        "og_image": "",
        "h1": (soup.h1.get_text(" ", strip=True) if soup.h1 else ""),
        "max_image_preview": "",
    }
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        meta["og_image"] = urljoin(page_url, og["content"])
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    if robots and "max-image-preview" in (robots.get("content") or ""):
        m = re.search(r"max-image-preview:\s*(\w+)", robots["content"])
        meta["max_image_preview"] = m.group(1) if m else ""
    return rows, meta


# --------------------------------------------------------------------------
# Image download + checks
# --------------------------------------------------------------------------
_cache: dict[str, dict] = {}


def fetch_image(url: str, max_bytes: int = 15_000_000) -> dict:
    if url in _cache:
        return _cache[url]
    info = {"status": None, "content_type": "", "bytes": None, "format": "",
            "px_width": None, "px_height": None, "negotiates_modern": None, "img": None}
    try:
        for attempt in range(3):  # be polite: back off on HTTP 429
            r = get(url, accept=ACCEPT_MODERN, timeout=25)
            if r.status_code != 429:
                break
            wait = r.headers.get("Retry-After", "")
            time.sleep(min(int(wait), 60) if wait.isdigit() else 5 * (attempt + 1))
        info["status"] = r.status_code
        info["content_type"] = r.headers.get("Content-Type", "").split(";")[0]
        data = r.content[:max_bytes]
        info["bytes"] = len(r.content)
        if r.ok and "svg" in info["content_type"]:
            info["format"] = "SVG"
        elif r.ok:
            im = Image.open(io.BytesIO(data))
            info["format"] = (im.format or "").upper()
            info["px_width"], info["px_height"] = im.size
            im.load()
            info["img"] = im.convert("RGB")
        # Does the server/CDN swap formats based on the Accept header?
        if r.ok and info["format"] in ("AVIF", "WEBP"):
            r2 = requests.head(url, headers={"User-Agent": UA, "Accept": ACCEPT_LEGACY},
                               timeout=15, allow_redirects=True)
            ct2 = r2.headers.get("Content-Type", "")
            info["negotiates_modern"] = ("avif" not in ct2 and "webp" not in ct2) or None
    except Exception as e:  # keep going, record the failure
        info["content_type"] = info["content_type"] or f"error: {type(e).__name__}"
    _cache[url] = info
    return info


def file_stem(url: str) -> str:
    name = unquote(os.path.basename(urlparse(url).path))
    return os.path.splitext(name)[0]


def audit_row(row: ImageRow, max_kb: int, alt_max: int, first_img_pos: Optional[int]):
    iss = row.issues
    stem = file_stem(row.image_url)
    if row.source == "css-background":
        iss.append("css_background_not_indexed")
    if row.source == "img":
        if not row.has_alt_attr:
            iss.append("missing_alt_attribute")
        elif (row.alt or "").strip() == "":
            iss.append("empty_alt_check_if_decorative")
        else:
            a = row.alt.strip()
            if len(a) > alt_max:
                iss.append(f"alt_over_{alt_max}_chars")
            if a.lower().replace(" ", "-") == stem.lower() or re.match(r"^(img|image|dsc)[-_ ]?\d+", a, re.I):
                iss.append("alt_looks_like_filename")
            words = re.findall(r"\w+", a.lower())
            if len(words) >= 6 and len(set(words)) / len(words) < 0.6:
                iss.append("alt_repetitive_possible_stuffing")
        if not (row.width_attr and row.height_attr):
            iss.append("missing_width_height_attrs")
        if row.position == first_img_pos and row.loading == "lazy":
            iss.append("first_image_lazy_loaded_lcp_risk")
    if row.px_width and row.px_height and row.px_width <= 2 and row.px_height <= 2:
        row.issues[:] = ["tracking_pixel_ignored"]
        return
    if GENERIC_NAME.match(stem or ""):
        iss.append("generic_file_name")
    if row.status and row.status >= 400:
        iss.append(f"http_{row.status}")
    if row.bytes and row.bytes > max_kb * 1024 and row.format != "SVG":
        iss.append(f"over_{max_kb}kb")
    if row.format in LEGACY_FORMATS and (row.bytes or 0) > 50 * 1024 and "avif" not in row.picture_types and "webp" not in row.picture_types:
        iss.append("legacy_format_consider_avif_webp")
    if row.px_width and row.px_width >= 800 and row.source == "img" and not row.has_srcset:
        iss.append("large_image_no_srcset")
    try:
        if row.px_width and row.width_attr and row.px_width > 2.5 * float(row.width_attr):
            iss.append("intrinsic_much_larger_than_declared")
    except ValueError:
        pass


# --------------------------------------------------------------------------
# Alt-text suggestions: pluggable backends
# --------------------------------------------------------------------------
ALT_PROMPT = ("Write alt text for this image, for a web page titled \"{title}\". "
              "Nearby text: \"{context}\". Describe what matters for someone who "
              "can't see it, in one plain sentence under 125 characters. Don't start "
              "with 'Image of' or 'Picture of'. No keyword lists. If the image is purely "
              "decorative, reply DECORATIVE. If it contains important text, include it.")


class AltBackend:
    def suggest(self, img: Image.Image, title: str, context: str) -> str:
        raise NotImplementedError


class HFBackend(AltBackend):
    """Open vision-language model running locally (CPU is fine for small models).

    Works with any Hugging Face "image-text-to-text" chat model, e.g.
    HuggingFaceTB/SmolVLM-500M-Instruct (default, Apache 2.0, ~0.5B params) or
    Qwen/Qwen3-VL-2B-Instruct (Apache 2.0, better, slower on CPU).
    """

    def __init__(self, model_id: str = "HuggingFaceTB/SmolVLM-500M-Instruct", use_context: bool = False):
        # Small models tend to parrot the page title back if you give it to them,
        # so page context is off by default for local models.
        self.use_context = use_context
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id, dtype=torch.float16 if self.device == "cuda" else torch.float32
        ).to(self.device).eval()

    def suggest(self, img, title, context):
        prompt_text = "Describe this image in one short, specific sentence for alt text."
        if self.use_context and title:
            prompt_text = (f"This image appears on a web page titled \"{title[:120]}\". "
                           "Write one short, specific sentence of alt text describing what the image shows.")
        msgs = [{"role": "user", "content": [{"type": "image", "image": img},
                                             {"type": "text", "text": prompt_text}]}]
        img = img.copy()
        img.thumbnail((768, 768))
        msgs[0]["content"][0]["image"] = img
        inputs = self.processor.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=60, do_sample=False)
        text = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:],
                                           skip_special_tokens=True)[0]
        return clean_alt(text)


FILLER = re.compile(
    r"^(alt(ernative)? text:\s*)?"
    r"((in )?(the|this) (image|picture|photo|photograph|screenshot)"
    r"(,)?( (is|shows|depicts|features|contains|displays))?( of)?( we can see| there (is|are))?"
    r"|(an? )?(image|picture|photo) of)\s*", re.I)


def clean_alt(text: str, max_chars: int = 150) -> str:
    """Strip the 'In this image we can see...' filler small models love, and
    keep only the first sentence if the model rambles."""
    t = " ".join(text.split()).strip().strip('"')
    t = FILLER.sub("", t).strip(" ,.")
    if len(t) > max_chars and ". " in t:
        t = t.split(". ")[0]
    return (t[:1].upper() + t[1:] + ".") if t else ""


def _b64_jpeg(img: Image.Image) -> str:
    img = img.copy()
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _raise_for_api_error(r: requests.Response) -> None:
    """Like raise_for_status(), but keeps the API's own reason (e.g. no credit, unknown model)."""
    if r.status_code != 200:
        try:
            err = r.json().get("error", {})
            detail = err.get("code") or err.get("status") or ""
            msg = err.get("message", "")
        except ValueError:
            detail, msg = "", r.text[:200]
        raise RuntimeError(f"HTTP {r.status_code} {detail}: {msg[:200]}".strip())


class OpenAIBackend(AltBackend):
    """Needs OPENAI_API_KEY in the environment. Model via OPENAI_VISION_MODEL."""

    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY")
        if not self.key:
            sys.exit("Set OPENAI_API_KEY in your environment to use --alt-backend openai")
        self.model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4.1-mini")

    def suggest(self, img, title, context):
        body = {"model": self.model, "max_completion_tokens": 120, "messages": [{"role": "user", "content": [
            {"type": "text", "text": ALT_PROMPT.format(title=title, context=context[:300])},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64_jpeg(img)}",
                                                "detail": "low"}}]}]}
        r = requests.post("https://api.openai.com/v1/chat/completions", json=body, timeout=60,
                          headers={"Authorization": f"Bearer {self.key}"})
        _raise_for_api_error(r)
        return clean_alt(r.json()["choices"][0]["message"]["content"])


class GeminiBackend(AltBackend):
    """Needs GEMINI_API_KEY in the environment. Model via GEMINI_VISION_MODEL."""

    def __init__(self):
        self.key = os.environ.get("GEMINI_API_KEY")
        if not self.key:
            sys.exit("Set GEMINI_API_KEY in your environment to use --alt-backend gemini")
        self.model = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")

    def suggest(self, img, title, context):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {"contents": [{"parts": [
            {"text": ALT_PROMPT.format(title=title, context=context[:300])},
            {"inline_data": {"mime_type": "image/jpeg", "data": _b64_jpeg(img)}}]}]}
        r = requests.post(url, json=body, timeout=60, headers={"x-goog-api-key": self.key})
        _raise_for_api_error(r)
        return clean_alt(r.json()["candidates"][0]["content"]["parts"][0]["text"])


def make_backend(name: str, model_id: Optional[str]) -> AltBackend:
    if name == "hf":
        return HFBackend(model_id) if model_id else HFBackend()
    if name == "openai":
        return OpenAIBackend()
    if name == "gemini":
        return GeminiBackend()
    raise ValueError(name)


# --------------------------------------------------------------------------
# Near-duplicate detection: CLIP embeddings + perceptual hash
# --------------------------------------------------------------------------
def find_duplicates(images: dict[str, Image.Image], threshold: float = 0.95, phash_max: int = 8,
                    model_id: str = "openai/clip-vit-base-patch32") -> pd.DataFrame:
    """Pairs of images that are copies (pHash Hamming distance <= phash_max) or
    visually near-identical (CLIP cosine >= threshold). Calibrate the threshold
    on your own images: two *different* photos of the same dog breed scored
    ~0.92 in my tests, and the same photo at 250px vs 1280px scored ~0.95."""
    import numpy as np
    import torch
    from transformers import CLIPModel, CLIPProcessor
    try:
        import imagehash
    except ImportError:
        imagehash = None

    urls = list(images)
    if len(urls) < 2:
        return pd.DataFrame()
    model = CLIPModel.from_pretrained(model_id).eval()
    proc = CLIPProcessor.from_pretrained(model_id)
    embs = []
    for i in range(0, len(urls), 16):
        batch = [images[u] for u in urls[i:i + 16]]
        with torch.no_grad():
            e = model.get_image_features(**proc(images=batch, return_tensors="pt"))
        if not torch.is_tensor(e):  # newer transformers may return a model output
            e = getattr(e, "image_embeds", None) or e.pooler_output
        embs.append(torch.nn.functional.normalize(e, dim=-1).numpy())
    E = np.vstack(embs)
    sims = E @ E.T
    hashes = {u: imagehash.phash(images[u]) for u in urls} if imagehash else {}

    rows = []
    for i in range(len(urls)):
        for j in range(i + 1, len(urls)):
            s = float(sims[i, j])
            hd = int(hashes[urls[i]] - hashes[urls[j]]) if hashes else None
            same_pixels = hd is not None and hd <= phash_max
            if s >= threshold or same_pixels:
                rows.append({"image_a": urls[i], "image_b": urls[j], "clip_cosine": round(s, 4),
                             "phash_distance": hd,
                             "verdict": ("same image (resized or re-encoded copy)" if same_pixels
                                         else "visually near-identical (check: same scene, template or crop?)")})
    return pd.DataFrame(rows).sort_values("clip_cosine", ascending=False) if rows else pd.DataFrame()


DEFAULT_LABELS = [
    "a product photo on a plain white background",
    "a lifestyle photo of a product in use",
    "a stock photo of smiling people in an office",
    "an infographic or chart with text",
    "a screenshot of software or a website",
    "a logo or icon",
    "a photo of a person's face, a headshot",
    "a diagram or illustration",
    "a landscape or building photo",
    "an animal photo",
]


def classify_images(images: dict[str, Image.Image], labels: list[str] = DEFAULT_LABELS,
                    model_id: str = "openai/clip-vit-base-patch32") -> pd.DataFrame:
    """Zero-shot image classification with CLIP: which of your labels does each
    image look most like? No training data needed; write labels as captions."""
    import torch
    from transformers import CLIPModel, CLIPProcessor
    model = CLIPModel.from_pretrained(model_id).eval()
    proc = CLIPProcessor.from_pretrained(model_id)
    urls, rows = list(images), []
    for i in range(0, len(urls), 16):
        batch = [images[u] for u in urls[i:i + 16]]
        with torch.no_grad():
            out = model(**proc(text=labels, images=batch, return_tensors="pt", padding=True))
        probs = out.logits_per_image.softmax(dim=-1)
        for u, p in zip(urls[i:i + 16], probs):
            top = int(p.argmax())
            rows.append({"image_url": u, "clip_label": labels[top], "clip_label_score": round(float(p[top]), 3)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def run(urls: list[str], out: str, max_kb: int = 200, alt_max: int = 125,
        suggest_alt: bool = False, alt_backend: str = "hf", alt_model: Optional[str] = None,
        alt_limit: int = 25, dedupe: bool = False, dup_threshold: float = 0.95,
        delay: float = 1.0, phash_max: int = 8,
        classify: bool = False, labels: Optional[list] = None) -> dict[str, pd.DataFrame]:
    os.makedirs(out, exist_ok=True)
    all_rows: list[ImageRow] = []
    pages = []
    for url in urls:
        print(f"Crawling {url}")
        try:
            r = get(url)
            r.raise_for_status()
        except Exception as e:
            pages.append({"page_url": url, "error": str(e)})
            continue
        rows, meta = extract_images(r.url, r.text)
        if meta["og_image"]:
            rows.append(ImageRow(page_url=r.url, image_url=meta["og_image"], position=0, source="og:image"))
        first_img = min((x.position for x in rows if x.source == "img"), default=None)
        for row in rows:
            info = fetch_image(row.image_url)
            for k in ("status", "content_type", "bytes", "format", "px_width", "px_height", "negotiates_modern"):
                setattr(row, k, info[k])
            audit_row(row, max_kb, alt_max, first_img)
        if meta["og_image"]:
            og = next(x for x in rows if x.source == "og:image")
            if og.px_width and og.px_width < 1200:
                og.issues.append("og_image_under_1200px_wide")
        imgs = [x for x in rows if x.source == "img"]
        pages.append({
            "page_url": r.url, "title": meta["title"], "images": len(imgs),
            "missing_alt_attr": sum("missing_alt_attribute" in x.issues for x in imgs),
            "empty_alt": sum("empty_alt_check_if_decorative" in x.issues for x in imgs),
            "legacy_format_heavy": sum("legacy_format_consider_avif_webp" in x.issues for x in rows),
            f"over_{max_kb}kb": sum(f"over_{max_kb}kb" in x.issues for x in rows),
            "missing_dimensions": sum("missing_width_height_attrs" in x.issues for x in imgs),
            "first_image_lazy": any("first_image_lazy_loaded_lcp_risk" in x.issues for x in imgs),
            "css_backgrounds": sum(x.source == "css-background" for x in rows),
            "total_image_kb": round(sum((x.bytes or 0) for x in rows if x.source != "og:image") / 1024),
            "og_image": meta["og_image"], "max_image_preview": meta["max_image_preview"] or "(not set)",
        })
        all_rows.extend(rows)
        time.sleep(delay)

    if suggest_alt:
        targets = [x for x in all_rows if "missing_alt_attribute" in x.issues
                   and _cache.get(x.image_url, {}).get("img") is not None][:alt_limit]
        if targets:
            print(f"Suggesting alt text for {len(targets)} images with backend '{alt_backend}'")
            backend = make_backend(alt_backend, alt_model)
            title_of = {p["page_url"]: p.get("title", "") for p in pages}
            for x in targets:
                try:
                    x.alt_suggestion = backend.suggest(_cache[x.image_url]["img"],
                                                       title_of.get(x.page_url, ""),
                                                       x.figcaption or x.nearby_text)
                except Exception as e:
                    x.alt_suggestion = f"(error: {e})"

    df = pd.DataFrame([{**asdict(x), "issues": "; ".join(x.issues)} for x in all_rows])
    usable = {u: i["img"] for u, i in _cache.items() if i.get("img") is not None
              and (i.get("px_width") or 0) >= 64 and (i.get("px_height") or 0) >= 64}
    if classify and usable and not df.empty:
        print(f"Classifying {len(usable)} unique images with CLIP (zero-shot)")
        df = df.merge(classify_images(usable, labels or DEFAULT_LABELS), on="image_url", how="left")
    pages_df = pd.DataFrame(pages)
    df.to_csv(os.path.join(out, "images.csv"), index=False)
    pages_df.to_csv(os.path.join(out, "pages.csv"), index=False)
    result = {"images": df, "pages": pages_df}

    if dedupe:
        uniq = usable
        print(f"Embedding {len(uniq)} unique images with CLIP for near-duplicate detection")
        dups = find_duplicates(uniq, dup_threshold, phash_max)
        dups.to_csv(os.path.join(out, "duplicates.csv"), index=False)
        result["duplicates"] = dups
    print(f"Done. Results in {out}/")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", required=True, help="Text file with one page URL per line, or a single URL")
    ap.add_argument("--out", default="results")
    ap.add_argument("--max-kb", type=int, default=200, help="Flag images heavier than this (default 200)")
    ap.add_argument("--alt-max", type=int, default=125, help="Flag alt text longer than this (default 125)")
    ap.add_argument("--suggest-alt", action="store_true", help="Draft alt text for images missing it")
    ap.add_argument("--alt-backend", choices=["hf", "openai", "gemini"], default="hf")
    ap.add_argument("--alt-model", default=None, help="Hugging Face image-text-to-text model id (default SmolVLM-500M-Instruct)")
    ap.add_argument("--alt-limit", type=int, default=25, help="Max images to caption (cost/time guard)")
    ap.add_argument("--dedupe", action="store_true", help="Find near-duplicates with CLIP")
    ap.add_argument("--dup-threshold", type=float, default=0.95)
    ap.add_argument("--classify", action="store_true", help="Zero-shot CLIP classification (product, lifestyle, stock, infographic...)")
    ap.add_argument("--labels", default=None, help="Your own labels, separated by |")
    ap.add_argument("--phash-max", type=int, default=8, help="Max pHash distance to call two images copies")
    ap.add_argument("--delay", type=float, default=1.0, help="Seconds between page requests")
    a = ap.parse_args()
    if os.path.exists(a.urls):
        urls = [l.strip() for l in open(a.urls) if l.strip() and not l.startswith("#")]
    else:
        urls = [a.urls]
    run(urls, a.out, a.max_kb, a.alt_max, a.suggest_alt, a.alt_backend, a.alt_model,
        a.alt_limit, a.dedupe, a.dup_threshold, a.delay, a.phash_max,
        a.classify, a.labels.split("|") if a.labels else None)


if __name__ == "__main__":
    main()
