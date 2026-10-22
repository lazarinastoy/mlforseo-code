"""Write formulas.csv and FORMULAS.md from formulas.py (run after editing formulas.py)."""
import csv
import formulas as F

with open("formulas.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "what it does", "input cells", "formula"])
    for f in F.FORMULAS:
        w.writerow([f["id"], f["title"], f["input"], f["formula"]])

lines = ["# Copyable formula sheet", "",
         "Generated from `formulas.py` by `build.py`. Paste a formula into row 2 of an empty column, "
         "then drag it down (or use the BYROW / MAP versions to fill the whole column at once).", ""]
for i, f in enumerate(F.FORMULAS, 1):
    lines += [f"## {i}. {f['title']}", "", f"Input: {f['input']}", "", "```", f["formula"], "```", ""]
open("FORMULAS.md", "w").write("\n".join(lines))
print(len(F.FORMULAS), "formulas written")
