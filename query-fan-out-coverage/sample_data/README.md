# Sample data (fictional)

Everything here was written for this notebook so it runs end to end with no API key and no web requests.

| File | What it is |
|---|---|
| `pages/espresso-machine-buying-guide.txt` | A fictional beginner's buying guide on a made-up site (`homebaristahq.example`). It deliberately covers some sub-topics well, touches others lightly and skips a few (grinders, grind size, named models, accessories) so the coverage check has gaps to find. |
| `pages/how-to-descale-espresso-machine.txt` | A fictional supporting page on the same site, to show how checking a page *with* its supporting pages changes coverage. |
| `example_llm_fanout.json` | **An illustrative example, not a live model response.** Written by hand to show the JSON shape the fan-out prompt asks for and the kind of sub-queries an LLM tends to return. Run the notebook with an API key to generate real ones. |

Page file format (also usable for your own pages via `LOCAL_TEXT_FILES`): a `URL:` line, a `TITLE:` line, then the content with `#`-style headings and blank lines between paragraphs.
