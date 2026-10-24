# Setup: publish the content audit template as a Google Sheet

These steps are for Lazarina (or whoever owns the MLforSEO Drive). No Google account was touched while building the template.

## 1. Import to Google Drive

1. Download `content-audit-template.xlsx` from this folder (about 1.6 MB: it holds formulas for 2,000 URLs).
2. In Google Drive: **New > File upload**, pick the file.
3. Right-click it > **Open with > Google Sheets**, then **File > Save as Google Sheets**. The first recalculation can take 10-20 seconds.
4. Rename it to **Content Audit Template (MLforSEO)**.

## 2. Check that everything recalculated

**Rules** tab: every row in "Column # found" shows a number (Address 1, Status Code 3, Word Count 37, Unique Inlinks 47, Top pages 1, Clicks 2, Sessions 2, and so on). None should say NOT FOUND.

**Dashboard** with the sample data should show:

| Final decision | URLs | Clicks |
|---|---|---|
| Keep | 13 | 3,618 |
| Update | 4 | 1,190 |
| Merge | 2 | 12 |
| Prune | 2 | 0 |
| Redirect | 3 | 25 |
| Total | 24 | 4,845 |

Suggested (before overrides): Keep 12, Update 5 (the parkrun guide is overridden to Keep). Checks: 24 URLs audited, 4 decaying, 7 striking distance, 4 thin, 4 overlapping, 14 converting, 1 override, 0 clicks on Prune pages, 1 Search Console page with clicks missing from the crawl, 0 headers not found.

Spot-check the **Audit** tab:

* `/blog/hoka-vs-brooks-2023/` → Merge, reason "Overlaps with …/blog/hoka-vs-brooks/, which gets more clicks…".
* `/blog/best-trail-running-shoes/` → Update, "Clicks down 60% on the previous period; Average position 7.9 on 9,800 impressions (striking distance)".
* `/blog/staff-picks-may-2020/` → Redirect (4 referring domains entered in column AC).
* Percentages and positions show as `4.1%` and `3.1`. If your Sheets locale uses a decimal comma, the reason text still works, but the `TEXT()` formats follow your locale.

If any cell shows `#NAME?`, `#REF!`, `#VALUE!` or `#ERROR!`, note the cell and tell the lead session.

## 3. Share it as a copy link

1. **Share > General access > Anyone with the link > Viewer**.
2. Copy the link and replace `/edit?usp=sharing` with **`/copy`**: `https://docs.google.com/spreadsheets/d/<ID>/copy`.
3. Put the `/copy` link in the resource page's `resource_file` field (it currently points at this GitHub folder) and in this folder's README.md. The resource idea was planned as email-gated: decide whether the download sits behind the Kit form.

## 4. Optional

* Protect the helper columns on the input tabs (purple headers) and the Audit tab except columns AC, AD and AF, with **Data > Protect sheets and ranges > Show a warning**.
* Keep the sample data in the shared master: the Start here tab tells people how to clear it.
