# The AI-powered Entity Audit: course scripts

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/lazarinastoy/mlforseo-code/blob/main/the-ai-powered-entity-audit/run_in_colab.ipynb)

Scripts from the practical lessons of [The AI-powered Entity Audit](https://www.mlforseo.com/courses/the-ai-powered-entity-audit/) by **Lazarina Stoy, MLforSEO**. Each one reads the files the earlier lessons produce and writes a review file that **a person approves before anything reaches a live site**.

**Never run a script before? Use Google Colab** (the badge above): nothing to install, and every step is a button. The guide below covers both routes.

| Script | Lesson | What it does | Costs |
|---|---|---|---|
| [`module-4/ai_citation_queries.py`](module-4/ai_citation_queries.py) | Practical 4.3 | Formats your topics the way Lesson 4.3 says, prices the run, pulls samples of real AI answers and the domains they cite | DataForSEO, about $0.20 per topic |
| [`module-4/skills/ai-citation-analysis/`](module-4/skills/ai-citation-analysis/) | Practical 4.3 | The same rules as a Claude skill, for the DataForSEO MCP server | DataForSEO |
| [`module-4/ai_visibility_report_template.md`](module-4/ai_visibility_report_template.md) | Practical 4.3b | The structure of an honest AI-visibility report | – |
| [`module-4/strip_boilerplate.py`](module-4/strip_boilerplate.py) | Practical 4.4 | Finds repeated boilerplate text and chrome entities in every competitor corpus; your decisions are the record | Free |
| [`module-5/meta_descriptions.py`](module-5/meta_descriptions.py) + [`import_meta.php`](module-5/import_meta.php) | Practical 5.2 | Claude drafts entity-first meta descriptions → review sheet → WP-CLI import with a backup | Claude, cents per page |
| [`module-5/extraction_check.py`](module-5/extraction_check.py) | Practical 5.3 | The five extraction checks on any list of URLs; `--rewrite` drafts only the failing sections | Free (Claude only with `--rewrite`) |
| [`module-5/link_map.py`](module-5/link_map.py) | Practical 5.5 | Entity → owner-page map, minus links that already exist, in rounds of 20, plus link rules | Free |
| [`module-5/jsonld_from_registry.py`](module-5/jsonld_from_registry.py) | Practical 5.6 | Claude drafts JSON-LD from your entity registry; code checks graph integrity and evidence | Claude, cents per page |

The Claude analysis from Lesson 2.4 is now a browser tool, no code at all: the [Claude Entity Analyst](https://academy.mlforseo.com/tools/claude-entity-analyst/).

---

## Route 1 — Google Colab (nothing to install)

1. Click **Open in Colab** at the top of this page. Sign in with any Google account.
2. Click the **key icon** in the left sidebar → **Add new secret**. Add the keys the script needs, with notebook access switched on:
   - `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com/) → API Keys
   - `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` — from [app.dataforseo.com/api-access](https://app.dataforseo.com/api-access) (not your account password)
3. Run the **Setup** cell (the ▶ button on its left). It downloads these scripts and installs what they need.
4. Go to the section for your script. Its upload cell asks for the CSV files the lesson lists — choose them from your computer.
5. Run the script cell. Start with the `--limit 5` version the notebook suggests.
6. Run the download cell to get the results file, and open it in Google Sheets or Excel.

---

## Route 2 — your own computer

You do this once. It takes about ten minutes.

**1. Check you have Python.**
- **Mac:** press <kbd>Cmd</kbd>+<kbd>Space</kbd>, type *Terminal*, press Enter. In the window, type `python3 --version` and press Enter.
- **Windows:** press the Start key, type *PowerShell*, press Enter. Type `py --version` and press Enter.

If you see a version number (3.9 or higher), skip to step 2. If you see “command not found” or “not recognized”, install Python from [python.org/downloads](https://www.python.org/downloads/). **On Windows, tick “Add python.exe to PATH” on the first screen of the installer.** Then close and reopen the Terminal / PowerShell window.

**2. Download the scripts.** On [the repository page](https://github.com/lazarinastoy/mlforseo-code), click the green **Code** button → **Download ZIP**, and unzip it. The scripts are in `the-ai-powered-entity-audit/`.

**3. Open a terminal *in that folder*.**
- **Mac:** type `cd ` (with a space) in Terminal, drag the `module-5` (or `module-4`) folder onto the window, press Enter.
- **Windows:** open the folder in File Explorer, click the address bar, type `powershell`, press Enter.

Type `ls` (Mac) or `dir` (Windows) and press Enter: you should see the `.py` files listed. If you don't, you're in the wrong folder.

**4. Install what the scripts need** (once):

| Mac | Windows |
|---|---|
| `python3 -m pip install -r ../requirements.txt` | `py -m pip install -r ..\requirements.txt` |

**5. Give it your key for this session.** Paste your own key between the quotes. It lasts until you close the window, and it never goes into a file.

| Mac | Windows (PowerShell) |
|---|---|
| `export ANTHROPIC_API_KEY="sk-ant-..."` | `$env:ANTHROPIC_API_KEY="sk-ant-..."` |
| `export DATAFORSEO_LOGIN="..."` | `$env:DATAFORSEO_LOGIN="..."` |
| `export DATAFORSEO_PASSWORD="..."` | `$env:DATAFORSEO_PASSWORD="..."` |

**6. Put your files next to the script**, named the way the lesson says (for example `page_entity_profiles.csv` and `pages.csv`). Drag them into the same folder.

**7. Run it.** Start small:

| Mac | Windows |
|---|---|
| `python3 meta_descriptions.py --limit 5` | `py meta_descriptions.py --limit 5` |

The script prints what it is doing. When it finishes, the results file (for example `review.csv`) is in the same folder. Open it in Google Sheets or Excel.

### If something goes wrong

| You see | It means | Do this |
|---|---|---|
| `command not found: python3` / `'py' is not recognized` | Python isn't installed, or not on PATH | Step 1 again; on Windows reinstall with “Add to PATH” ticked |
| `No module named 'anthropic'` (or `pydantic`, `bs4`) | Step 4 was skipped or ran in another folder | Run step 4 again from this folder |
| `FileNotFoundError: ... .csv` | The file isn't in this folder, or is named differently | `ls` / `dir` to check, rename the file |
| `AuthenticationError` / `401` | The key is wrong or has a space in it | Step 5 again, copying the key carefully |
| `credit balance is too low` | No credit on the Anthropic account | Add credit in the Anthropic console |
| Anything else | – | Copy the last 10 lines of the error into Claude and ask what they mean — it is very good at this |

### Prefer to let Claude run it?

If you use [Claude Code](https://claude.com/claude-code) or Claude Desktop with file access, open this folder and ask, for example: *“Run meta_descriptions.py with --limit 5, explain what it did, and show me the first rows of review.csv.”* Read what it proposes to run before you approve it.

---

## Safety rules the scripts follow

- **Nothing publishes itself.** Every script writes a file for you to review; only `import_meta.php` writes to a site, and only for rows you approved, after a dry run, keeping the old value.
- **Keys come from the environment** (or Colab secrets), never from the code. Don't paste a key into a script you share.
- **Start with `--limit`.** Read five results before you run five hundred.

MIT-licensed (see the repository [LICENSE](../LICENSE)). Lesson text © Lazarina Stoy / MLforSEO.
