#!/usr/bin/env python3
"""Scope a standalone tool page so it can live inside a WordPress page.

The six audit tools are built as complete HTML documents: they style `body`,
declare `:root` custom properties and use a `*` reset. Pasted into a WP page as
they are, all three escape the tool and repaint the theme — which is exactly what
the existing Semantic Drift Analyzer page does to academy.mlforseo.com today.

This rewrites every selector so it only applies inside one wrapper element:

    :root { --a: 1 }          ->  .mlfs-tool { --a: 1 }
    body { background: x }    ->  .mlfs-tool { background: x }
    * { box-sizing: … }       ->  .mlfs-tool * { box-sizing: … }
    .panel h2 { … }           ->  .mlfs-tool .panel h2 { … }
    @media (…) { body { … } } ->  @media (…) { .mlfs-tool { … } }

@keyframes and @font-face bodies are left alone — their contents are not
selectors. Media and supports blocks are recursed into.
"""
import re

WRAP = ".mlfs-tool"
# At-rules whose blocks contain declarations or keyframe stops, not selectors.
OPAQUE = ("keyframes", "font-face", "counter-style", "property", "page", "viewport")


def _split_blocks(css):
    """Yield (prelude, body, is_at_rule) for each top-level rule."""
    out, i, depth, start = [], 0, 0, 0
    prelude = None
    while i < len(css):
        c = css[i]
        if c == "{":
            if depth == 0:
                prelude = css[start:i]
                body_start = i + 1
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append((prelude, css[body_start:i]))
                start = i + 1
        i += 1
    tail = css[start:].strip()
    if tail:
        out.append((tail, None))
    return out


def _scope_selector(sel):
    sel = sel.strip()
    if not sel:
        return sel
    parts = []
    for one in sel.split(","):
        s = one.strip()
        if not s:
            continue
        # :root and body BECOME the wrapper — the wrapper is the tool's root.
        if s in (":root", "html", "body") or s.startswith(":root:") or s.startswith("body:"):
            parts.append(WRAP + s.split(":root", 1)[-1].split("body", 1)[-1]
                         if s not in (":root", "html", "body") else WRAP)
        elif s == "*":
            parts.append(f"{WRAP} *")
        elif s.startswith(("html ", "body ")):
            parts.append(f"{WRAP} {s.split(' ', 1)[1]}")
        elif s.startswith("@"):
            parts.append(s)
        else:
            parts.append(f"{WRAP} {s}")
    return ", ".join(parts)


def scope_css(css):
    out = []
    for prelude, body in _split_blocks(css):
        if body is None:
            out.append(prelude)
            continue
        p = prelude.strip()
        if p.startswith("@"):
            name = p[1:].split()[0].split("(")[0].lower()
            if any(name.startswith(o) for o in OPAQUE):
                out.append(f"{p}{{{body}}}")
            else:                      # @media, @supports, @layer …
                out.append(f"{p}{{{scope_css(body)}}}")
        else:
            out.append(f"{_scope_selector(p)}{{{body}}}")
    return "\n".join(out)


def scope_document(html, extra_class=""):
    """Return (scoped_style, body_html) for a full standalone tool document."""
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
    scoped = "\n".join(scope_css(s) for s in styles)

    # Everything that is not head furniture is the tool's markup.
    body = html
    body = re.sub(r"<!DOCTYPE[^>]*>", "", body, flags=re.I)
    body = re.sub(r"</?html[^>]*>", "", body, flags=re.I)
    body = re.sub(r"<head[^>]*>.*?</head>", "", body, flags=re.S | re.I)
    body = re.sub(r"</?body[^>]*>", "", body, flags=re.I)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S | re.I)
    body = re.sub(r"<title[^>]*>.*?</title>", "", body, flags=re.S | re.I)
    body = re.sub(r'<meta[^>]*>', "", body, flags=re.I)
    body = re.sub(r'<link[^>]+rel="(?:preconnect|stylesheet|icon)"[^>]*>', "", body, flags=re.I)
    cls = ("mlfs-tool " + extra_class).strip()
    return scoped, f'<div class="{cls}">\n{body.strip()}\n</div>'


if __name__ == "__main__":
    import sys, pathlib
    src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
    css, body = scope_document(src)
    print(f"scoped CSS: {len(css)} bytes, body: {len(body)} bytes")
    bad = re.findall(r"(?m)^\s*(body|html|\*|:root)\s*[,{]", css)
    print("unscoped root selectors remaining:", bad or "none")
