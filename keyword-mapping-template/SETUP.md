# Setup: publish the keyword mapping template as a Google Sheet

These steps are for Lazarina (or whoever owns the MLforSEO Drive). Nothing here was done automatically: no Google account was touched while building the template.

## 1. Import to Google Drive

1. Download `keyword-mapping-template.xlsx` from this folder.
2. In Google Drive: **New > File upload**, pick the file.
3. Right-click the uploaded file > **Open with > Google Sheets**. Then **File > Save as Google Sheets** (this creates a native Sheet; delete the uploaded .xlsx afterwards if you like).
4. Rename it to **Keyword Mapping Template (MLforSEO)**.

## 2. Check that everything recalculated

Open the **Dashboard** tab and compare with the numbers the sample data should give:

| Metric | Expected |
|---|---|
| Keywords | 27 |
| Mapped to a URL | 26 |
| Not mapped yet | 1 |
| Target URLs | 18 |
| Planned (new) URLs | 6 |
| Clusters | 9 |
| Cannibalised keyword rows | 2 |
| URLs with too many primary keywords | 1 |
| URLs spanning 2+ clusters (keyword rows) | 2 |
| Intent mismatches | 1 |
| Ranking URL is not the target | 3 |
| Unclassified intent | 7 |

Then spot-check:

* **Keyword Map**: the Flags column shows "Cannibalisation" on both `running shoes for wide feet` rows, "Too many primary keywords on URL" on the two marathon rows, and "Intent mismatch" on `buy trail running shoes`.
* Dropdowns work on Page status, Page type, Keyword role and Intent (pasted).
* Conditional formatting: cannibalisation cells are soft red, other flags yellow, banding is lavender.

If a cell shows `#NAME?` or `#ERROR!`, note the cell and formula and tell the lead session. (Everything uses functions Sheets supports, so this shouldn't happen.)

## 3. Share it as a copy link

1. **Share > General access > Anyone with the link > Viewer**.
2. Copy the link. It looks like `https://docs.google.com/spreadsheets/d/<ID>/edit?usp=sharing`.
3. Replace `/edit?usp=sharing` with **`/copy`**: `https://docs.google.com/spreadsheets/d/<ID>/copy`. Anyone who opens it gets a "Make a copy" prompt and their own editable version.
4. Put that `/copy` link in:
   * the resource page's `resource_file` field (it currently points at this GitHub folder),
   * the "Get the Google Sheet" line in this folder's README.md.

## 4. Optional

* Protect the calculated columns (M:AB on Keyword Map, and the summary tabs) with **Data > Protect sheets and ranges > Show a warning**, so people don't type over formulas by accident.
* Keep the sample rows in the shared master: they show how the flags work. The Start here tab tells people to clear them.
