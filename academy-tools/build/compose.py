#!/usr/bin/env python3
"""Build the MLforSEO Academy tool pages from the standalone tools in ../tools/.

    python3 build/compose.py                 # dist/ + preview/ (assets referenced at @main)
    python3 build/compose.py --ref <sha>     # pin the page HTML to a commit (what the site publishes)

For each tool (../meta/<slug>.json + ../tools/<slug>.html) it writes:
  dist/<slug>.css         the tool CSS, scoped under .mlfs-tool (nothing leaks into the site)
  dist/<slug>.js          the tool code (the single inline <script> of the source)
  dist/<slug>.page.html   the WordPress page block: page chrome + tool markup + asset tags
  dist/mlfs-chrome.css    the shared page chrome (eyebrow, at-a-glance strip, steps, note)
  preview/<slug>.html     a local preview using the local files

Why the CSS and JS are separate files (served from this repo through jsDelivr) rather than inline:
WordPress filters page content at render time and turns `&&` next to `<` comparisons into
`&#038;&#038;`, which breaks inline JavaScript. External files avoid that whole class of bug and
keep each page small. Library <script src> tags in a tool source (papaparse, tfjs, three.js …)
are kept, in order, before the tool code.
"""
import hashlib
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from scope_css import scope_document  # noqa: E402
from page_chrome import CHROME_CSS, build_page  # noqa: E402
from tools_meta import TOOLS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "tools"
DIST = ROOT / "dist"
PREVIEW = ROOT / "preview"
CDN = "https://cdn.jsdelivr.net/gh/lazarinastoy/mlforseo-code@{ref}/academy-tools/dist"
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800'
         '&family=Inter:wght@400;500;600;700&display=swap">')


def split_assets(tool):
    """(css, js, libs, body_html) for one tool: CSS scoped, inline code split out, library tags kept."""
    raw = (SRC / tool["file"]).read_text(encoding="utf-8")
    css, body = scope_document(raw)
    # scope_document wraps the markup in <div class="mlfs-tool">; a source that already has that root
    # (newer tools) would end up double-wrapped, so drop the outer wrapper again.
    inner = re.match(r'<div class="mlfs-tool">\s*(<div class="mlfs-tool"[^>]*>.*)</div>\s*$', body, re.S)
    if inner:
        body = inner.group(1).strip()
    libs = re.findall(r'<script[^>]*\bsrc=["\'][^"\']+["\'][^>]*>\s*</script>', body, re.S)
    js = "\n".join(m for m in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", body, re.S) if m.strip())
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<(?:meta|title|link)\b[^>]*>(?:[^<]*</title>)?", "", body)
    body = body.replace('<div class="mlfs-tool">', '<div class="mlfs-tool" data-theme="light">', 1)
    return css, js, libs, body.strip()


def page_html(tool, base):
    css, js, libs, body = split_assets(tool)
    return (f'<link rel="stylesheet" href="{base}/mlfs-chrome.css">\n'
            f'<link rel="stylesheet" href="{base}/{tool["slug"]}.css">\n'
            f'{build_page(tool, body)}\n'
            + "".join(lib + "\n" for lib in libs)
            + f'<script src="{base}/{tool["slug"]}.js" defer></script>')


def wp_block(inner):
    bid = hashlib.md5(inner.encode()).hexdigest()[:8]
    return ('<!-- wp:uagb/container {"block_id":"%s","variationSelected":true,"isBlockRootParent":true} -->\n'
            '<div class="wp-block-uagb-container uagb-block-%s alignfull uagb-is-root-container">'
            '<div class="uagb-container-inner-blocks-wrap"><!-- wp:html -->\n%s\n'
            '<!-- /wp:html --></div></div>\n<!-- /wp:uagb/container -->') % (bid, bid, inner)


def main():
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else "main"
    base = CDN.format(ref=ref)
    DIST.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    (DIST / "mlfs-chrome.css").write_text(CHROME_CSS, encoding="utf-8")
    (PREVIEW / "mlfs-chrome.css").write_text(CHROME_CSS, encoding="utf-8")
    for t in TOOLS:
        if not (SRC / t["file"]).exists():
            print(f"  skip {t['slug']}: no tools/{t['file']}")
            continue
        css, js, libs, _ = split_assets(t)
        for ext, content in (("css", css), ("js", js)):
            (DIST / f"{t['slug']}.{ext}").write_text(content, encoding="utf-8")
            (PREVIEW / f"{t['slug']}.{ext}").write_text(content, encoding="utf-8")
        page = page_html(t, base)
        (DIST / f"{t['slug']}.page.html").write_text(wp_block(page) + "\n", encoding="utf-8")
        local = page.replace(base + "/", "")
        (PREVIEW / f"{t['slug']}.html").write_text(
            '<!doctype html><meta charset="utf-8">' + FONTS + '<style>body{margin:0;background:#1A0B32}</style>' + local,
            encoding="utf-8")
        print(f"  {t['slug']:48} css {len(css)//1024:3}KB  js {len(js)//1024:3}KB  libs {len(libs)}  page {len(page)//1024:2}KB")
    print(f"\ndist -> {DIST}  (assets @{ref})")


if __name__ == "__main__":
    main()
