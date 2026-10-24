#!/usr/bin/env python3
"""Build content-audit-template.xlsx (MLforSEO, Lazarina Stoy).

    pip install openpyxl pandas
    python make_sample_data.py      # writes sample_data/ (synthetic exports)
    python build_template.py        # builds the workbook and fills it with the sample exports

Crawl (Screaming Frog), Search Console and GA4 are joined per URL with SUMIFS/INDEX/MATCH, and every URL gets a
Keep / Update / Merge / Prune / Redirect decision plus a plain-English reason. Thresholds live on the Rules tab.
Plain formulas only (no XLOOKUP, LET, LAMBDA, FILTER), so it behaves the same in Google Sheets and Excel.
"""
import os
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter as L

from brand_style import (DARK, F_DARK, F_GREEN, F_HI, F_LAV, F_RED, band, credits, esc, flag_rule, font, group_label,
                         header_row, legend, lines, list_validation, note, number_validation, sample_banner, title, widths)

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("OUT", HERE / "content-audit-template.xlsx"))
N = int(os.environ.get("N_ROWS", 2000))      # rows per input tab
IN_LAST = 1 + N                              # input tabs: header row 1, data 2..IN_LAST
AU_FIRST, AU_LAST = 3, 2 + N                 # Audit rows (Audit row r <-> Crawl row r-1)
DECISIONS = ["Keep", "Update", "Merge", "Prune", "Redirect"]
POST_URL = "https://www.mlforseo.com/machine-learning-implementation-guides/ai-search-optimisation/blog-site-architecture-ai-search/"
COURSE_URL = "https://www.mlforseo.com/courses/introduction-to-machine-learning-for-seo/"

CRAWL_W = 130           # paste zone A:DZ
CR_PATH, CR_NOQ, CR_KEY = "EA", "EB", "EC"
GSC_W = 5               # paste zone A:E ; helpers G..K
GA4_W = 11              # paste zone A:K ; helpers M..P

RULES = [  # row 5 onwards: label, value, explanation
    ("Low clicks (per period)", 10, "Below this a page counts as low traffic."),
    ("Impressions that show demand", 200, "At or above this, a page has search demand worth working on."),
    ("Decay: click drop vs previous period", 0.3, "0.3 = a 30% drop or worse flags decay."),
    ("Decay: minimum previous-period clicks", 20, "Ignore decay on pages that had fewer clicks than this."),
    ("Thin content: word count below", 300, "Screaming Frog Word Count. Lower it for product or category pages."),
    ("Striking distance: position from", 4, "Average position range where an update can move the page up."),
    ("Striking distance: position to", 20, ""),
    ("Overlap: semantic similarity at least", 0.9, "Screaming Frog Semantic Similarity Score (0-1). Near-duplicates always count."),
    ("Low sessions (GA4)", 20, "Below this, GA4 traffic from all channels counts as low."),
    ("Referring domains worth keeping", 1, "Pages being removed with at least this many referring domains get a 301 instead."),
]
COLMAP = [  # tab, field, default header in the export
    ("Crawl", "URL", "Address"), ("Crawl", "Status code", "Status Code"), ("Crawl", "Indexability", "Indexability"),
    ("Crawl", "Indexability status", "Indexability Status"), ("Crawl", "Word count", "Word Count"),
    ("Crawl", "Unique inlinks", "Unique Inlinks"), ("Crawl", "Near-duplicate match", "Closest Near Duplicate Match"),
    ("Crawl", "Near-duplicate count", "No. Near Duplicates"), ("Crawl", "Semantic match", "Closest Semantically Similar Address"),
    ("Crawl", "Semantic score", "Semantic Similarity Score"),
    ("GSC current", "Page", "Top pages"), ("GSC current", "Clicks", "Clicks"), ("GSC current", "Impressions", "Impressions"),
    ("GSC current", "Position", "Position"),
    ("GA4", "Landing page", "Landing page + query string"), ("GA4", "Sessions", "Sessions"),
    ("GA4", "Avg engagement time (s)", "Average engagement time per session"), ("GA4", "Key events", "Key events"),
]
# Rules!$H$<row> holds the column number found for each field (rows 5..22, in COLMAP order)
C = {f"{t}|{f}": f"Rules!$H${5 + i}" for i, (t, f, _) in enumerate(COLMAP)}


def path_helpers(ws, r, src, cols):
    """Path / path without query / key helper columns (mirrors url_key() in prepare_exports.py)."""
    p, q, k = cols
    ws[f"{p}{r}"] = f'=IF({src}{r}="","",IF(LEFT({src}{r},4)="http",IFERROR(MID({src}{r},FIND("/",{src}{r},FIND("//",{src}{r})+2),2000),"/"),{src}{r}))'
    ws[f"{q}{r}"] = f'=IF({p}{r}="","",IFERROR(LEFT(SUBSTITUTE({p}{r},"#","?"),FIND("?",SUBSTITUTE({p}{r},"#","?"))-1),{p}{r}))'
    ws[f"{k}{r}"] = f'=IF({q}{r}="","",LOWER(IF(AND(LEN({q}{r})>1,RIGHT({q}{r},1)="/"),LEFT({q}{r},LEN({q}{r})-1),{q}{r})))'


def input_tab(wb, name, default_headers, width, helper_cols, helper_names, banner, note_text):
    ws = wb.create_sheet(name)
    header_row(ws, 1, default_headers, 1, "input")
    for j, h in enumerate(helper_names):
        c = ws.cell(row=1, column=helper_cols[0] + j, value=h)
        c.fill = PatternFill("solid", fgColor="8448EF"); c.font = font(10, True, "FFFFFF")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "B2"
    band(ws, f"A2:{L(width)}{IN_LAST}", "A", 2)
    ws.column_dimensions["A"].width = 52
    return ws


def build():
    wb = Workbook()
    start = wb.active
    start.title = "Start here"
    ru = wb.create_sheet("Rules")

    # ============================================================ Rules
    title(ru, "A1", "Rules: thresholds and column names (edit the yellow cells)")
    note(ru, "A2", "Every decision on the Audit tab reads these cells. Change a number and the whole audit updates.")
    header_row(ru, 4, ["Threshold", "Value", "What it does"], 1, "input")
    for i, (k, v, why) in enumerate(RULES, start=5):
        ru.cell(row=i, column=1, value=k).font = font(10)
        c = ru.cell(row=i, column=2, value=v); c.fill = F_HI; c.font = font(10, True)
        if isinstance(v, float) and v < 1 and "similarity" not in k:
            c.number_format = "0%"
        ru.cell(row=i, column=3, value=why).font = font(9, italic=True, color="6B6880")
    header_row(ru, 4, ["Tab", "Field", "Header in your export", "Column # found"], 5, "input")
    ru["H4"].fill = PatternFill("solid", fgColor="8448EF")
    for i, (tab, field, hdr) in enumerate(COLMAP, start=5):
        ru.cell(row=i, column=5, value=tab).font = font(10)
        ru.cell(row=i, column=6, value=field).font = font(10)
        c = ru.cell(row=i, column=7, value=hdr); c.fill = F_HI
        last = {"Crawl": L(CRAWL_W), "GSC current": L(GSC_W), "GA4": L(GA4_W)}[tab]
        ru.cell(row=i, column=8, value=f"=IFERROR(MATCH(G{i},'{tab}'!$A$1:${last}$1,0),\"NOT FOUND\")")
    note(ru, "E24", "If a header shows NOT FOUND, type the exact header from your export in column G. 'GSC previous' uses the same headers as 'GSC current'.")
    note(ru, "E25", "Near-duplicate and semantic columns only fill when those Screaming Frog features are on. Without them, Merge never triggers.")
    flag_rule(ru, "H5:H22", '$H5="NOT FOUND"', F_RED, bold=True)
    header_row(ru, 27, ["Decision order (first rule that matches wins)"], 1, "calc")
    lines(ru, 28, [
        "1. Status 3xx → Redirect (already redirects: update internal links to the final URL).",
        "2. Status 4xx/5xx → Redirect if it still gets clicks or has referring domains, otherwise Prune.",
        "3. Non-indexable (noindex, canonicalised) → Keep, with a note to confirm it's intentional.",
        "4. Overlaps a page with more clicks (near-duplicate, or semantic score at/above the threshold) and no key events → Merge.",
        "5. Decaying, or in striking distance, or thin with search demand → Update.",
        "6. Low value (low clicks, impressions and sessions, no key events) → Prune, or Redirect if it has referring domains.",
        "7. Everything else → Keep. Your Override column always wins.",
    ])
    widths(ru, {"A": 40, "B": 10, "C": 62, "D": 3, "E": 14, "F": 24, "G": 38, "H": 14})

    # ============================================================ input tabs
    from make_sample_data import SF_HEADER
    cr = input_tab(wb, "Crawl", SF_HEADER, CRAWL_W, [131], ["Path (helper)", "Path, no query (helper)", "Key (helper)"],
                   "", "")
    for r in range(2, IN_LAST + 1):
        path_helpers(cr, r, "A", (CR_PATH, CR_NOQ, CR_KEY))
    for col in range(2, len(SF_HEADER) + 1):
        cr.column_dimensions[L(col)].width = 14
    for col in (CR_PATH, CR_NOQ, CR_KEY):
        cr.column_dimensions[col].width = 30

    gsc_tabs = {}
    for name in ("GSC current", "GSC previous"):
        ws = input_tab(wb, name, ["Top pages", "Clicks", "Impressions", "CTR", "Position"], GSC_W, [7],
                       ["Path (helper)", "Path, no query (helper)", "Key (helper)", "Clicks (helper)", "Impressions (helper)",
                        "Position × impressions (helper)", "In crawl? (helper)"], "", "")
        for r in range(2, IN_LAST + 1):
            path_helpers(ws, r, "A", ("G", "H", "I"))
            row = f"$A{r}:${L(GSC_W)}{r}"
            ws[f"J{r}"] = f'=IF(I{r}="","",IFERROR(N(INDEX({row},1,{C["GSC current|Clicks"]})),0))'
            ws[f"K{r}"] = f'=IF(I{r}="","",IFERROR(N(INDEX({row},1,{C["GSC current|Impressions"]})),0))'
            ws[f"L{r}"] = f'=IF(I{r}="","",IFERROR(N(INDEX({row},1,{C["GSC current|Position"]}))*K{r},0))'
            ws[f"M{r}"] = f'=IF(I{r}="","",IF(COUNTIF(Crawl!${CR_KEY}$2:${CR_KEY}${IN_LAST},I{r})>0,"Yes","No"))'
        widths(ws, {"B": 10, "C": 12, "D": 9, "E": 10, "F": 3, "G": 30, "H": 30, "I": 30, "J": 11, "K": 12, "L": 14, "M": 10})
        gsc_tabs[name] = ws

    ga = input_tab(wb, "GA4", ["Landing page + query string", "Sessions", "Active users", "New users",
                               "Average engagement time per session", "Key events", "Total revenue"], GA4_W, [13],
                   ["Path (helper)", "Path, no query (helper)", "Key (helper)", "Sessions (helper)",
                    "Engagement seconds (helper)", "Key events (helper)"], "", "")
    for r in range(2, IN_LAST + 1):
        path_helpers(ga, r, "A", ("M", "N", "O"))
        row = f"$A{r}:${L(GA4_W)}{r}"
        ga[f"P{r}"] = f'=IF(O{r}="","",IFERROR(N(INDEX({row},1,{C["GA4|Sessions"]})),0))'
        ga[f"Q{r}"] = f'=IF(O{r}="","",IFERROR(P{r}*N(INDEX({row},1,{C["GA4|Avg engagement time (s)"]})),0))'
        ga[f"R{r}"] = f'=IF(O{r}="","",IFERROR(N(INDEX({row},1,{C["GA4|Key events"]})),0))'
    widths(ga, {"B": 10, "C": 10, "D": 10, "E": 14, "F": 10, "G": 10, "L": 3, "M": 30, "N": 30, "O": 30, "P": 11, "Q": 14, "R": 11})

    # ============================================================ Audit
    au = wb.create_sheet("Audit")
    group_label(au, 1, 1, 10, "FROM THE CRAWL", "calc")
    group_label(au, 1, 11, 19, "SEARCH CONSOLE + GA4", "calc")
    group_label(au, 1, 20, 28, "SIGNALS AND DECISION", "calc")
    group_label(au, 1, 29, 32, "YOUR INPUT", "input")
    calc_h = ["URL", "Key", "Status code", "Indexability", "Indexability status", "Word count", "Unique inlinks",
              "Near duplicates", "Overlapping page", "Semantic similarity", "Clicks", "Impressions", "CTR", "Avg position",
              "Clicks (previous period)", "Click change", "Sessions", "Avg engagement time (s)", "Key events", "Thin?",
              "Decaying?", "Striking distance?", "Overlaps another page?", "Overlap has more clicks?", "Converts?",
              "Low value?", "Suggested decision", "Reason"]
    header_row(au, 2, calc_h, 1, "calc")
    header_row(au, 2, ["Referring domains (optional)", "Override", "Final decision", "Notes"], 29, "input")
    au["AE2"].fill = PatternFill("solid", fgColor="8448EF")
    R = {k: f"Rules!$B${5 + i}" for i, k in enumerate(["low", "demand", "decay", "minprev", "thin", "from", "to", "sim", "lowsess", "rd"])}
    gk = lambda tab: f"'{tab}'!$I$2:$I${IN_LAST}"
    GSC_HELPER = {"Clicks": "J", "Impressions": "K"}
    GA4_HELPER = {"Sessions": "P", "Key events": "R"}
    gcol = lambda tab, f: f"'{tab}'!${GSC_HELPER[f]}$2:${GSC_HELPER[f]}${IN_LAST}"
    acol = lambda f: f"GA4!${GA4_HELPER[f]}$2:${GA4_HELPER[f]}${IN_LAST}"
    for r in range(AU_FIRST, AU_LAST + 1):
        cr_r = r - 1
        crow = f"Crawl!$A{cr_r}:${L(CRAWL_W)}{cr_r}"
        cv = lambda f: f'IFERROR(INDEX({crow},1,{C["Crawl|" + f]}),"")'
        f = {
            "A": f'=IF(Crawl!A{cr_r}="","",Crawl!A{cr_r})',
            "B": f'=IF(A{r}="","",Crawl!{CR_KEY}{cr_r})',
            "C": f'=IF(A{r}="","",{cv("Status code")})',
            "D": f'=IF(A{r}="","",{cv("Indexability")}&"")',
            "E": f'=IF(A{r}="","",{cv("Indexability status")}&"")',
            "F": f'=IF(A{r}="","",{cv("Word count")})',
            "G": f'=IF(A{r}="","",{cv("Unique inlinks")})',
            "H": f'=IF(A{r}="","",{cv("Near-duplicate count")})',
            "I": (f'=IF(A{r}="","",IF(AND(N(H{r})>0,{cv("Near-duplicate match")}&""<>""),{cv("Near-duplicate match")}&"",'
                  f'IF(AND(ISNUMBER(J{r}),N(J{r})>={R["sim"]},{cv("Semantic match")}&""<>""),{cv("Semantic match")}&"","")))'),
            "J": f'=IF(A{r}="","",IF({cv("Semantic score")}&""="","",{cv("Semantic score")}))',
            "K": f'=IF(A{r}="","",IFERROR(SUMIFS({gcol("GSC current", "Clicks")},{gk("GSC current")},B{r}),0))',
            "L": f'=IF(A{r}="","",IFERROR(SUMIFS({gcol("GSC current", "Impressions")},{gk("GSC current")},B{r}),0))',
            "M": f'=IF(A{r}="","",IF(N(L{r})>0,K{r}/L{r},""))',
            "N": f"=IF(A{r}=\"\",\"\",IF(N(L{r})>0,SUMIFS('GSC current'!$L$2:$L${IN_LAST},{gk('GSC current')},B{r})/L{r},\"\"))",
            "O": f'=IF(A{r}="","",IFERROR(SUMIFS({gcol("GSC previous", "Clicks")},{gk("GSC previous")},B{r}),0))',
            "P": f'=IF(A{r}="","",IF(N(O{r})>0,(K{r}-O{r})/O{r},""))',
            "Q": f'=IF(A{r}="","",IFERROR(SUMIFS({acol("Sessions")},GA4!$O$2:$O${IN_LAST},B{r}),0))',
            "R": f'=IF(A{r}="","",IF(N(Q{r})>0,SUMIFS(GA4!$Q$2:$Q${IN_LAST},GA4!$O$2:$O${IN_LAST},B{r})/Q{r},""))',
            "S": f'=IF(A{r}="","",IFERROR(SUMIFS({acol("Key events")},GA4!$O$2:$O${IN_LAST},B{r}),0))',
            "T": f'=IF(A{r}="","",IF(AND(ISNUMBER(F{r}),LEFT(C{r}&"",1)="2"),IF(F{r}<{R["thin"]},"Yes","No"),"No"))',
            "U": f'=IF(A{r}="","",IF(AND(N(O{r})>={R["minprev"]},ISNUMBER(P{r})),IF(P{r}<=-{R["decay"]},"Yes","No"),"No"))',
            "V": f'=IF(A{r}="","",IF(AND(N(L{r})>={R["demand"]},ISNUMBER(N{r})),IF(AND(N{r}>={R["from"]},N{r}<={R["to"]}),"Yes","No"),"No"))',
            "W": f'=IF(A{r}="","",IF(I{r}<>"","Yes","No"))',
            "X": f'=IF(I{r}="","",IF(SUMIFS($K${AU_FIRST}:$K${AU_LAST},$A${AU_FIRST}:$A${AU_LAST},{esc(f"I{r}")})>N(K{r}),"Yes","No"))',
            "Y": f'=IF(A{r}="","",IF(N(S{r})>0,"Yes","No"))',
            "Z": f'=IF(A{r}="","",IF(AND(N(K{r})<{R["low"]},N(L{r})<{R["demand"]},N(Q{r})<{R["lowsess"]},Y{r}="No"),"Yes","No"))',
            "AA": (f'=IF(A{r}="","",IF(LEFT(C{r}&"",1)="3","Redirect",'
                   f'IF(OR(LEFT(C{r}&"",1)="4",LEFT(C{r}&"",1)="5"),IF(OR(N(K{r})>0,N(AC{r})>={R["rd"]}),"Redirect","Prune"),'
                   f'IF(D{r}="Non-Indexable","Keep",'
                   f'IF(AND(W{r}="Yes",X{r}="Yes",Y{r}="No"),"Merge",'
                   f'IF(OR(U{r}="Yes",V{r}="Yes",AND(T{r}="Yes",N(L{r})>={R["demand"]})),"Update",'
                   f'IF(Z{r}="Yes",IF(N(AC{r})>={R["rd"]},"Redirect","Prune"),"Keep")))))))'),
            "AB": (f'=IF(A{r}="","",IF(LEFT(C{r}&"",1)="3","Already redirects ("&C{r}&"). Update internal links to point at the final URL.",'
                   f'IF(OR(LEFT(C{r}&"",1)="4",LEFT(C{r}&"",1)="5"),IF(AA{r}="Redirect","Returns "&C{r}&" but still has "&N(K{r})&" clicks and "&N(AC{r})&" referring domains. 301 it to the closest live page.",'
                   f'"Returns "&C{r}&" with no clicks or links. Remove internal links and let it 404 or 410."),'
                   f'IF(D{r}="Non-Indexable","Non-indexable ("&E{r}&"). Keep if that is intentional; otherwise fix the canonical or noindex.",'
                   f'IF(AA{r}="Merge","Overlaps with "&I{r}&IF(N(J{r})>0," (similarity "&TEXT(J{r},"0.00")&")","")&", which gets more clicks. Merge the useful parts into it and 301 this URL.",'
                   f'IF(AA{r}="Update",MID(IF(U{r}="Yes","; Clicks down "&TEXT(-P{r},"0%")&" on the previous period","")'
                   f'&IF(V{r}="Yes","; Average position "&TEXT(N{r},"0.0")&" on "&TEXT(L{r},"#,##0")&" impressions (striking distance)","")'
                   f'&IF(AND(T{r}="Yes",N(L{r})>={R["demand"]}),"; Thin ("&F{r}&" words) but has search demand",""),3,400),'
                   f'IF(AA{r}="Prune","Low value: "&N(K{r})&" clicks, "&N(L{r})&" impressions, "&N(Q{r})&" sessions, no key events. Remove or noindex it and update internal links.",'
                   f'IF(AA{r}="Redirect","Low value but "&N(AC{r})&" referring domains. 301 it to the closest relevant page to keep those links.",'
                   f'IF(AND(Z{r}="No",Y{r}="Yes",N(K{r})<{R["low"]}),"Low search traffic but it converts (key events: "&S{r}&"). Keep it and link to it.",'
                   f'IF(W{r}="Yes","Stronger than the page it overlaps ("&I{r}&"). Keep; merge that page into this one.",'
                   f'"Healthy: "&N(K{r})&" clicks"&IF(ISNUMBER(N{r}),", average position "&TEXT(N{r},"0.0"),"")&". Keep and monitor."))))))))))'),
            "AE": f'=IF(A{r}="","",IF(AD{r}<>"",AD{r},AA{r}))',
        }
        for col, formula in f.items():
            au[f"{col}{r}"] = formula
        au[f"M{r}"].number_format = "0.0%"
        au[f"N{r}"].number_format = "0.0"
        au[f"P{r}"].number_format = "0%"
        au[f"R{r}"].number_format = "0"
        au[f"J{r}"].number_format = "0.00"
    list_validation(au, f"AD{AU_FIRST}:AD{AU_LAST}", '"' + ",".join(DECISIONS) + '"',
                    prompt="Your call. The override always wins over the suggested decision.")
    number_validation(au, f"AC{AU_FIRST}:AC{AU_LAST}", 0)
    band(au, f"A{AU_FIRST}:AF{AU_LAST}", "A", AU_FIRST)
    dec_fill = {"Keep": F_GREEN, "Update": F_HI, "Merge": PatternFill("solid", fgColor="D9CCF9"), "Prune": F_RED,
                "Redirect": PatternFill("solid", fgColor="E7DDFD")}
    for col in ("AA", "AE"):
        for d, fill in dec_fill.items():
            flag_rule(au, f"{col}{AU_FIRST}:{col}{AU_LAST}", f'${col}{AU_FIRST}="{d}"', fill, bold=True)
    for col in ("T", "U", "V", "W", "X", "Z"):
        flag_rule(au, f"{col}{AU_FIRST}:{col}{AU_LAST}", f'${col}{AU_FIRST}="Yes"', F_HI)
    flag_rule(au, f"Y{AU_FIRST}:Y{AU_LAST}", f'$Y{AU_FIRST}="Yes"', F_GREEN)
    flag_rule(au, f"AD{AU_FIRST}:AD{AU_LAST}", f'$AD{AU_FIRST}<>""', F_LAV, bold=True)
    widths(au, {"A": 52, "B": 30, "C": 8, "D": 14, "E": 16, "F": 9, "G": 9, "H": 9, "I": 40, "J": 10, "K": 9, "L": 11,
                "M": 8, "N": 9, "O": 11, "P": 9, "Q": 9, "R": 11, "S": 8, "T": 7, "U": 9, "V": 9, "W": 9, "X": 9,
                "Y": 8, "Z": 8, "AA": 12, "AB": 70, "AC": 12, "AD": 11, "AE": 12, "AF": 34})
    au.freeze_panes = "B3"
    au.auto_filter.ref = f"A2:AF{AU_LAST}"
    au.column_dimensions["B"].hidden = False

    # ============================================================ Dashboard
    da = wb.create_sheet("Dashboard")
    title(da, "A1", "Content audit dashboard")
    note(da, "A2", "Counts follow the Final decision (your overrides included). Clicks are Search Console clicks in the current period.")
    header_row(da, 4, ["Decision", "URLs", "Clicks", "Sessions", "Suggested (before overrides)"], 1, "calc")
    A = lambda c: f"Audit!${c}${AU_FIRST}:${c}${AU_LAST}"
    for i, d in enumerate(DECISIONS, start=5):
        da.cell(row=i, column=1, value=d).font = font(10, True)
        da.cell(row=i, column=2, value=f'=COUNTIF({A("AE")},A{i})')
        da.cell(row=i, column=3, value=f'=SUMIFS({A("K")},{A("AE")},A{i})')
        da.cell(row=i, column=4, value=f'=SUMIFS({A("Q")},{A("AE")},A{i})')
        da.cell(row=i, column=5, value=f'=COUNTIF({A("AA")},A{i})')
    for d, fill in dec_fill.items():
        flag_rule(da, "A5:A9", f'$A5="{d}"', fill, bold=True)
    da["A10"] = "Total"; da["A10"].font = font(10, True)
    for col in "BCDE":
        da[f"{col}10"] = f"=SUM({col}5:{col}9)"; da[f"{col}10"].font = font(10, True)
    header_row(da, 12, ["Check", "Count"], 1, "calc")
    checks = [
        ("URLs audited (crawl rows)", f"=SUMPRODUCT((LEN({A('A')})>0)*1)"),
        ("Decaying pages", f'=COUNTIF({A("U")},"Yes")'),
        ("Striking-distance pages", f'=COUNTIF({A("V")},"Yes")'),
        ("Thin pages", f'=COUNTIF({A("T")},"Yes")'),
        ("Pages overlapping another page", f'=COUNTIF({A("W")},"Yes")'),
        ("Pages that convert (key events)", f'=COUNTIF({A("Y")},"Yes")'),
        ("Overrides you've made", f"=SUMPRODUCT((LEN({A('AD')})>0)*1)"),
        ("Clicks on pages marked Prune (should be close to 0)", f'=SUMIFS({A("K")},{A("AE")},"Prune")'),
        ("Search Console pages with clicks that are not in the crawl",
         f"=COUNTIFS('GSC current'!$M$2:$M${IN_LAST},\"No\",{gcol('GSC current', 'Clicks')},\">0\")"),
        ("Column headers not found on Rules", '=COUNTIF(Rules!$H$5:$H$22,"NOT FOUND")'),
    ]
    for i, (k, v) in enumerate(checks, start=13):
        da.cell(row=i, column=1, value=k).font = font(10)
        c = da.cell(row=i, column=2, value=v); c.font = font(12, True, DARK); c.alignment = Alignment(horizontal="center")
    flag_rule(da, "B20:B22", "AND(ISNUMBER(B20),B20>0)", F_HI, bold=True)
    widths(da, {"A": 56, "B": 12, "C": 12, "D": 12, "E": 26})
    da.sheet_view.showGridLines = False

    # ============================================================ Start here
    s = start
    title(s, "A1", "Content Audit Template")
    s["A2"] = "Search Console + GA4 + Screaming Frog → Keep / Update / Merge / Prune / Redirect · by Lazarina Stoy · MLforSEO"
    s["A2"].font = font(11, False, "8448EF", True)
    r = lines(s, 4, [
        "What it does",
        "Joins your crawl, Search Console and GA4 data per URL, checks each page for decay, striking distance, thin content,",
        "overlap with another page and conversions, and suggests a decision with a plain-English reason. Every threshold sits on",
        "the Rules tab, so you can see (and change) exactly why a page got its label. Your Override column always wins.",
    ], bold_first=True)
    r = lines(s, r + 1, [
        "How to use it",
        "1. Crawl: run Screaming Frog (turn on near-duplicates and, if you can, embeddings for semantic similarity), then",
        "   Internal > HTML > Export. Paste the whole file into the Crawl tab from cell A1, headers included.",
        "2. GSC current: Search Console > Performance > last 3 months > Pages tab > Export > CSV. Paste Pages.csv from A1.",
        "3. GSC previous: the same export for the 3 months before (Date > Custom). Optional, but decay needs it.",
        "4. GA4: Reports > Engagement > Landing page, same dates > Share > Download CSV. Delete the lines starting with #, paste from A1.",
        "   Shortcut for steps 1-4: run prepare_exports.py (in the GitHub folder). It cleans the files and fills a copy of this workbook.",
        "5. Rules: check every header says a column number (not NOT FOUND), then tune the thresholds for your site.",
        "6. Audit: filter by Final decision. Read the Reason, add referring domains for pages you might remove, and override",
        "   anything you disagree with. Dashboard shows the totals.",
        "7. Delete the sample data first: clear the four input tabs below row 1 (keep the purple helper columns on the right).",
    ], bold_first=True)
    r = lines(s, r + 1, [
        "Good to know",
        "URLs are matched on their path: host, query string, #fragment, trailing slash and letter case are ignored. Audit one",
        "host (or subdomain) at a time. The Audit tab follows the Crawl tab row by row, so if you re-paste the crawl in a different",
        "order, your overrides and notes no longer line up: copy the Audit tab as values before you re-paste.",
        "Room for 2,000 URLs per tab. For more, copy the last formula row down on every tab.",
        "This is a decision aid. A rule can't see business context (seasonality, legal pages, links from campaigns), so read",
        "the reasons before you delete anything, and redirect rather than remove whenever a page has links or traffic.",
    ], bold_first=True)
    r = legend(s, r + 1)
    r = credits(s, r, "Read: Blog and site architecture for SEO and conversions in the AI search era (MLforSEO)", POST_URL,
                "Course: Introduction to Machine Learning for SEO (MLforSEO Academy)", COURSE_URL,
                [("Code and helper script: github.com/lazarinastoy/mlforseo-code/content-audit-template",
                  "https://github.com/lazarinastoy/mlforseo-code/tree/main/content-audit-template")])
    widths(s, {"A": 30, "B": 110})
    s.sheet_view.showGridLines = False
    s.sheet_properties.tabColor = DARK
    au.sheet_properties.tabColor = "8448EF"
    da.sheet_properties.tabColor = "FFDE59"
    ru.sheet_properties.tabColor = "FFDE59"
    order = ["Start here", "Audit", "Dashboard", "Rules", "Crawl", "GSC current", "GSC previous", "GA4"]
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    wb.save(OUT)
    return OUT


def fill_sample(path):
    """Fill the built workbook with the synthetic sample exports, plus two example manual inputs."""
    import prepare_exports as pe
    from openpyxl import load_workbook
    sd = HERE / "sample_data"
    frames = {"Crawl": pe.read_crawl(sd / "internal_html.csv"), "GSC current": pe.read_gsc(sd / "gsc_pages_current.csv"),
              "GSC previous": pe.read_gsc(sd / "gsc_pages_previous.csv"), "GA4": pe.read_ga4(sd / "ga4_landing_pages.csv")}
    pe.fill_workbook(path, path, frames)
    wb = load_workbook(path)
    au = wb["Audit"]
    urls = list(frames["Crawl"]["Address"])
    def row_of(suffix):
        return AU_FIRST + next(i for i, u in enumerate(urls) if u.endswith(suffix))
    au[f"AC{row_of('/blog/staff-picks-may-2020/')}"] = 4
    r = row_of("/blog/parkrun-guide/")
    au[f"AD{r}"] = "Keep"
    au[f"AF{r}"] = "Seasonal: clicks come back every spring"
    # mark sample rows clearly without touching the headers
    au["AF1"] = "SAMPLE DATA (synthetic site). Clear the input tabs to start."
    au["AF1"].fill = F_HI
    au["AF1"].font = font(9, True, DARK)
    wb.save(path)


if __name__ == "__main__":
    p = build()
    fill_sample(p)
    print("wrote", p)
