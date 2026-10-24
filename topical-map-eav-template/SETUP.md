# Setup: publish the topical map template as a Google Sheet

These steps are for Lazarina (or whoever owns the MLforSEO Drive). No Google account was touched while building the template.

## 1. Import to Google Drive

1. Download `topical-map-eav-template.xlsx` from this folder.
2. In Google Drive: **New > File upload**, pick the file.
3. Right-click it > **Open with > Google Sheets**, then **File > Save as Google Sheets** to create a native Sheet.
4. Rename it to **Topical Map Template (EAV) by MLforSEO**.

## 2. Check that everything recalculated

**Dashboard** with the sample data should show:

| Metric | Expected |
|---|---|
| Central entity | Running shoes |
| Attributes listed / included | 8 / 7 |
| Values listed / kept on the map | 28 / 26 |
| Rows on the topical map | 34 |
| Covered / Gaps | 9 / 25 |
| Coverage | 26% |
| Attribute checks to resolve | 0 |

Spot-check the **Topical Map** tab:

* Row 3 is the pillar "Running shoes: the complete guide", rows 4-10 are the seven clusters, rows 11-36 the supporting pages.
* "Road running shoes" links up to "Running shoes by terrain" and across to "Trail running shoes"; "Treadmill running shoes" loops back to "Road running shoes".
* Gaps are yellow, covered pages green.
* **Combinations** shows a 4 × 5 grid (terrain × foot type), starting "Road running shoes for wide feet".
* Dropdowns work on Entity type, attribute type, intent, relevance, include, and the Values attribute column (it lists the attributes you typed).

If any cell shows `#NAME?`, `#REF!` or `#ERROR!`, note the cell and tell the lead session.

## 3. Share it as a copy link

1. **Share > General access > Anyone with the link > Viewer**.
2. Copy the link and replace `/edit?usp=sharing` with **`/copy`**: `https://docs.google.com/spreadsheets/d/<ID>/copy`.
3. Put that `/copy` link in the resource page's `resource_file` field (it currently points at this GitHub folder) and in this folder's README.md.

## 4. Optional

* Protect the Topical Map, Dashboard and the calculated columns on Attributes (K:P) and Values (H:O) with **Data > Protect sheets and ranges > Show a warning**.
* Keep the sample in the shared master so people see a finished map before they clear it.
