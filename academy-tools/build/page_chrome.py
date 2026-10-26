"""Shared, on-brand page chrome for every entity-audit tool page.

The existing academy tool pages each carry their own look. These six are a
cluster and are built to look like one set: same header, same at-a-glance strip,
same steps, same note — using the MLforSEO Brand v2 palette and the flat-solid
button rule (no gradients).

Everything is scoped under .mlfs-page, and every chrome class is mlfs- prefixed so it cannot
match anything inside a tool (tools have their own .eyebrow, .note, .wrap, h2 ...).
"""
import html

CHROME_CSS = """
.mlfs-page{--ink:#1A0B32;--surface:#251046;--surface-2:#2e1650;--purple:#8448ef;
  --purple-mid:#6b36c2;--lav:#CBADFF;--lav-out:#c5a4fe;--lav-soft:#f6eafe;
  --yellow:#ffde59;--head:#f6eafe;--body:#d9c9e6;--muted:#8a7aa0;
  font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
  color:var(--body);background:var(--ink);
  padding:0 20px 8px;margin:0 auto;max-width:1180px;box-sizing:border-box}
.mlfs-page *{box-sizing:border-box}
.mlfs-page .mlfs-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--lav-out);font-weight:600;margin:0 0 10px}
.mlfs-page > h1{font-family:"Bricolage Grotesque",Inter,sans-serif;font-weight:800;
  font-size:clamp(30px,4.4vw,46px);line-height:1.08;letter-spacing:-.02em;
  color:var(--head);margin:0 0 16px}
.mlfs-page .mlfs-lede{font-size:17px;line-height:1.6;color:var(--body);max-width:68ch;margin:0 0 30px}
.mlfs-page .mlfs-glance{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:12px;margin:0 0 34px}
.mlfs-page .mlfs-glance div{background:var(--surface);border:1px solid #3a2060;
  border-radius:8px;padding:15px 17px}
.mlfs-page .mlfs-glance dt{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--lav-out);font-weight:700;margin:0 0 6px}
.mlfs-page .mlfs-glance dd{margin:0;font-size:13.5px;line-height:1.5;color:var(--head)}
.mlfs-page > h2{font-family:"Bricolage Grotesque",Inter,sans-serif;font-weight:700;
  font-size:23px;color:var(--head);margin:0 0 16px;letter-spacing:-.01em}
.mlfs-page .mlfs-steps{counter-reset:s;list-style:none;padding:0;margin:0 0 28px;
  display:grid;gap:10px}
.mlfs-page .mlfs-steps li{counter-increment:s;position:relative;padding:13px 16px 13px 52px;
  background:var(--surface);border:1px solid #3a2060;border-radius:8px;
  font-size:14.5px;line-height:1.55;color:var(--body)}
.mlfs-page .mlfs-steps li::before{content:counter(s);position:absolute;left:15px;top:12px;
  width:25px;height:25px;border-radius:6px;background:var(--purple);color:#fff;
  font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center}
.mlfs-page .mlfs-note{background:var(--surface-2);border-left:3px solid var(--yellow);
  border-radius:0 8px 8px 0;padding:15px 18px;margin:0 0 36px;font-size:14px;
  line-height:1.6;color:var(--head)}
.mlfs-page .mlfs-note b{color:var(--yellow)}
.mlfs-page .mlfs-toolwrap{background:var(--lav-soft);border-radius:12px;padding:6px;
  margin:0 0 34px;border:1px solid #3a2060}
/* The page chrome already carries the title, eyebrow and description, so the
   tool's own masthead would repeat all three. Hide it inside the page; the
   standalone tool file still shows it. */
.mlfs-page .mlfs-toolwrap .masthead{display:none}
.mlfs-page .mlfs-toolwrap .wrap{padding-top:26px}
@media (max-width:640px){.mlfs-page{padding:0 14px 8px}}
"""


def build_page(tool, scoped_body):
    """The page around one tool. The course block and the link back to /tools/ come from the site
    (mlforseo-chrome adds the same "This tool comes from the course" block to every tool page)."""
    e = html.escape
    steps = "\n".join(f"      <li>{e(s)}</li>" for s in tool["how"])
    glance = [
        ("What you need", tool["needs"]),
        ("Cost", tool["cost"]),
        ("Feed it", tool["inputs"]),
        ("You get back", tool["outputs"]),
    ]
    cards = "\n".join(
        f'      <div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>' for k, v in glance)
    note = f'\n  <p class="mlfs-note"><b>Worth knowing.</b> {e(tool["note"])}</p>\n' if tool.get("note") else ""
    return f"""<div class="mlfs-page">
  <p class="mlfs-eyebrow">MLforSEO Academy &middot; {e(tool['course_name'])}</p>
  <h1>{e(tool['title'])}</h1>
  <p class="mlfs-lede">{e(tool['short'])}</p>

  <dl class="mlfs-glance">
{cards}
  </dl>

  <h2>How to use it</h2>
  <ol class="mlfs-steps">
{steps}
  </ol>
{note}
  <div class="mlfs-toolwrap">
{scoped_body}
  </div>
</div>"""
