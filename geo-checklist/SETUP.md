# Setup: publish Generative Engine Optimisation (GEO) Checklist as a Google Sheets template

This is a one-off job for Lazarina (or whoever owns the MLforSEO Google account). The workbook is built as an `.xlsx` file so nothing here touches a Google account automatically. Once it lives in Google Drive, the resource page can offer a **Make a copy** link instead of the GitHub folder.

## 1. Import the workbook

1. Download `geo-checklist.xlsx` from this folder (https://github.com/lazarinastoy/mlforseo-code/blob/main/geo-checklist/geo-checklist.xlsx, then **Download raw file**).
2. In Google Drive (signed in as the MLforSEO account), open the folder where MLforSEO templates live and choose **New > File upload**.
3. Right-click the uploaded file and choose **Open with > Google Sheets**. If the title bar shows an `.XLSX` badge, use **File > Save as Google Sheets** so you're working on a native Sheet. Delete the uploaded `.xlsx` afterwards to avoid two versions.
4. Rename the Sheet to **Generative Engine Optimisation (GEO) Checklist (MLforSEO)**.

## 2. Check it imported cleanly (5 minutes)

- **Start here**: title, legends and credit links show; the links are clickable.
- **Checklist**: 44 checks, header row frozen, filter arrows on the header. Click a Status cell: a dropdown with Not started / In progress / Done / N/A appears. Set one to Done: it turns green. High priorities are yellow.
- **AI crawlers**: 15 user-agent tokens, with dropdowns in 'Your decision' and 'In your robots.txt now'.
- **Prompt tracker**: two grey example rows (leave them in the master so visitors see how it works; the intro tells them to delete them). Assistant, Mentioned and Cited columns have dropdowns.
- **Progress**: numbers show (not `#NAME?` or `#REF!`). Change a Status on the Checklist and confirm the Progress numbers update. The AI visibility table at the bottom reads from the Prompt tracker.
- Fonts: the workbook uses Arial, Sheets' default, so nothing should change.
- Row heights: if any long text is cut off, select the rows, right-click **Resize rows > Fit to data**.
- Optional: protect the formula areas so people don't overwrite them by accident. **Data > Protect sheets and ranges**, choose the range, then **Show a warning when editing this range** (a warning, not a lock, so copies stay fully editable).

## 3. Share it as a template

1. **Share > General access > Anyone with the link > Viewer**. Viewers can't edit your master copy.
2. Copy the file ID from the address bar: the long string between `/d/` and `/edit` in `https://docs.google.com/spreadsheets/d/<ID>/edit`.
3. Build the copy link: `https://docs.google.com/spreadsheets/d/<ID>/copy`
4. Test it in a private window: it should open a **Make a copy** screen and create an editable copy in the visitor's own Drive.

## 4. Point everything at the copy link

- Resource page on mlforseo.com: replace `resource_file` (currently https://github.com/lazarinastoy/mlforseo-code/tree/main/geo-checklist) with the `/copy` link.
- This folder's `README.md`: replace the "Google Sheets version" placeholder with the `/copy` link.
- The idea list (RESOURCES-EXPANSION.csv) also mentions a PDF version. If you want one, **File > Download > PDF** on the Checklist tab (landscape, fit to width), or use `checklist.md`.

## Updating the template later

Edit `checks.csv` (and `build.py` for tab layout), run `python build.py`, check the new `.xlsx`, then either re-import it (steps 1 to 3; the file ID changes, so update the links) or copy the changed rows into the live Sheet by hand (the ID stays the same, which is usually easier).
