
const $ = id => document.getElementById(id);
const esc = s => String(s??"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ENDPOINT = "https://api.openai.com/v1/chat/completions";
const MAX_CHARS = 8000, CONCURRENCY = 3, TABLE_ROWS = 100;
const TITLE_RANGE = [50, 60], META_RANGE = [150, 160];
const CSV_COLS = ["URL","Original_Title","Content","Title_Option_1","Title_Option_2","Title_Option_3",
  "Heading_Suggestions","Meta_Description_1","Meta_Description_2","Meta_Description_3"];

// chatgpt-4o-latest was retired on 17 Feb 2026 (its successor gpt-5.1-chat-latest on
// 23 Jul 2026); OpenAI's replacement is gpt-5.6-sol. gpt-4o shuts down on 14 Jan 2027,
// replacement gpt-6-luna. The two newer models are reasoning models: they take
// reasoning_effort, count reasoning against max_completion_tokens, and reject
// temperature/top_p unless effort is "none".
const MODELS = {
  "gpt-5.6-sol": {reasoning:true},
  "gpt-6-luna":  {reasoning:true},
  "gpt-4o":      {reasoning:false}
};

let mode = "article", busy = false, abort = false;
let ROWS = null, COLS = null, FILE = "";
let ARTICLE = null, BULK = null;

/* ---------- small helpers ---------- */
function say(msg, kind){
  $("status").textContent = msg;
  $("status").className = "hint" + (kind === "err" ? " err" : "");
}
function fail(msg, focusId){ say(msg, "err"); if (focusId) $(focusId).focus(); return false; }
const words = t => (t.match(/\S+/g) || []).length;
const readTime = t => Math.max(1, Math.ceil(words(t) / 220));
const asText = v => Array.isArray(v) ? v.map(x => typeof x === "string" ? x : (x?.text ?? JSON.stringify(x))).join("\n")
  : (v == null ? "" : String(v));
const asList = v => Array.isArray(v) ? v.map(asText).join("; ") : asText(v);
const hasKw = (text, kw) => !!kw && text.toLowerCase().replace(/\s+/g," ").includes(kw.toLowerCase().replace(/\s+/g," ").trim());
const inRange = (n, [lo, hi]) => n >= lo && n <= hi;
const clip = (s, n) => { s = String(s ?? ""); return s.length > n ? s.slice(0, n) + "…" : s; };

async function copyText(text, btn){
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.className = "offscreen";
    (document.querySelector(".mlfs-tool") || document.body).appendChild(ta);
    ta.select();
    try { ok = document.execCommand("copy"); } catch {}
    ta.remove();
  }
  if (btn){
    const old = btn.dataset.label || btn.textContent; btn.dataset.label = old;
    btn.textContent = ok ? "Copied" : "Copy failed";
    setTimeout(() => { btn.textContent = old; }, 1400);
  }
  return ok;
}

async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use)
    ? await claude.use("downloads").catch(()=>null) : null;
  if (api){
    try { await api.save({filename, data:text}); return "saved"; }
    catch(e){ return e && e.code === "declined" ? "declined" : "failed"; }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], {type:mime}));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return "saved";
}
const q = v => `"${String(v ?? "").replace(/"/g,'""')}"`;
const toCSV = (rows, cols) => [cols.join(",")].concat(rows.map(r => cols.map(c => q(r[c])).join(","))).join("\n");

/* ---------- mode tabs ---------- */
document.querySelectorAll('.tabs [role=tab]').forEach(b => b.onclick = () => setMode(b.dataset.mode));
function setMode(m){
  if (busy) return;
  mode = m;
  document.querySelectorAll('.tabs [role=tab]').forEach(x => x.setAttribute("aria-selected", x.dataset.mode === m));
  $("pane-article").hidden = m !== "article";
  $("pane-csv").hidden = m !== "csv";
  $("out-article").hidden = m !== "article" || !ARTICLE;
  $("out-csv").hidden = m !== "csv" || !BULK;
  $("run").textContent = m === "article" ? "Generate metadata" : "Generate for every row";
  readyMessage();
}
function readyMessage(){
  const key = $("key").value.trim();
  if (mode === "article"){
    if (!$("text").value.trim()) return say(key ? "Paste an article to begin." : "Add your key and some content to begin.");
    return say(key ? "Ready." : "Add your API key to run.");
  }
  if (!ROWS) return say(key ? "Upload a CSV to begin." : "Add your key and a CSV to begin.");
  say(key ? `${ROWS.length} row(s) ready. Each row is one API call.` : "Add your API key to run.");
}
["key","text"].forEach(id => $(id).addEventListener("input", readyMessage));
$("text").addEventListener("input", () => {
  const t = $("text").value;
  if (!t.trim()){ $("textinfo").textContent = "The first line longer than eight characters is treated as the current title. Only the first 8,000 characters are sent."; return; }
  $("textinfo").textContent = `${words(t).toLocaleString()} words · about ${readTime(t)} min read · ${t.length.toLocaleString()} characters`
    + (t.length > MAX_CHARS ? `. Only the first ${MAX_CHARS.toLocaleString()} are sent.` : "");
});

/* ---------- OpenAI ---------- */
function apiError(status, message, fatal){ const e = new Error(message); e.status = status; e.fatal = !!fatal; return e; }

async function openaiJSON({apiKey, model, messages, budget}){
  const spec = MODELS[model] || {reasoning:false};
  const body = {model, messages, response_format:{type:"json_object"}};
  if (spec.reasoning){ body.reasoning_effort = "low"; body.max_completion_tokens = budget * 3; }
  else { body.max_completion_tokens = budget; }

  let res;
  try {
    res = await fetch(ENDPOINT, {
      method:"POST",
      headers:{"Content-Type":"application/json", "Authorization":`Bearer ${apiKey}`},
      body:JSON.stringify(body)
    });
  } catch { throw apiError(0, "Could not reach OpenAI. Check your connection and try again."); }

  if (!res.ok){
    let msg = `${res.status} ${res.statusText}`, code = "";
    try { const p = await res.json(); msg = p.error?.message || msg; code = p.error?.code || ""; } catch {}
    if (res.status === 401) throw apiError(401, "OpenAI rejected that API key. Check it for stray spaces.", true);
    if (res.status === 403) throw apiError(403, `OpenAI refused the request: ${msg}`, true);
    if (res.status === 404 || code === "model_not_found") throw apiError(res.status, `This key cannot use ${model}. Pick another model.`, true);
    if (res.status === 429 && /quota|billing/i.test(msg + code))
      throw apiError(429, "Your OpenAI account is out of credit. Check your billing, then try again.", true);
    if (res.status === 429) throw apiError(429, "OpenAI's rate limit was reached. Wait a minute and try again.");
    throw apiError(res.status, msg);
  }

  const data = await res.json();
  const choice = data.choices?.[0] || {};
  const raw = choice.message?.content || "";
  const cutOff = choice.finish_reason === "length";
  if (!raw.trim()){
    if (choice.message?.refusal) throw apiError(0, `The model declined: ${choice.message.refusal}`);
    throw apiError(0, cutOff ? "The model ran out of room before it answered. Try again, or send less text." : "The model returned an empty answer. Try again.");
  }
  try { return JSON.parse(raw); }
  catch {
    const m = raw.match(/\{[\s\S]*\}/);
    if (m){ try { return JSON.parse(m[0]); } catch {} }
    throw apiError(0, cutOff ? "The answer was cut off before it finished. Try again." : "The model did not return valid JSON. Try again.");
  }
}

/* ---------- prompts ---------- */
function buildMetadataPrompt({title, content, targetKeyword, audience, contentGoal, includeCompetitor}){
  const shortened = content.slice(0, MAX_CHARS);
  const serpSchema = includeCompetitor ? `,
  "serp": {
    "query": "string",
    "source": "inferred",
    "top_results": [
      {"rank":1,"title":"string","source":"domain","notes":"the angle that helps it rank"},
      {"rank":2,"title":"string","source":"domain","notes":"..."},
      {"rank":3,"title":"string","source":"domain","notes":"..."},
      {"rank":4,"title":"string","source":"domain","notes":"..."},
      {"rank":5,"title":"string","source":"domain","notes":"..."}
    ],
    "competitor_gaps": ["short bullets of must-cover topics the content lacks"],
    "serp_features": ["People also ask","Featured snippet","Videos","Sitelinks"]
  }` : "";

  const schemaHint = `
You MUST return STRICT JSON matching:
{
  "title_options":[
    {"label":"Option 1","text":"..."},
    {"label":"Option 2","text":"..."},
    {"label":"Option 3","text":"..."}
  ],
  "heading_suggestions":"multiline headings where H2 lines start with '## ' and H3 with '### '",
  "meta_descriptions":[
    {"label":"Meta 1","text":"..."},
    {"label":"Meta 2","text":"..."},
    {"label":"Meta 3","text":"..."}
  ]${serpSchema}
}
Rules:
- Titles: 3 options, EACH 50–60 characters, include the target keyword naturally, no clickbait.
- Meta descriptions: 3 options, EACH 150–160 characters, lead with value, include keyword once.
- Heading suggestions: 6–12 total H2/H3 lines; H2 lines prefixed "## ", H3 with "### "; include an FAQ H2 with 3–5 H3s.
- Match audience tone and the content goal/intent.
- Use concise, specific language. No emojis. Do NOT include backticks. JSON ONLY.
${includeCompetitor ? `- You cannot browse the web. Base "serp" on what you know about the pages that typically rank for this keyword, set serp.source="inferred", and do not invent URLs.` : `- Do not include a "serp" object.`}
`;

  const competitorNote = includeCompetitor
    ? `Infer the 5 results most likely to rank for the target keyword, the angle each takes, and the topics this content is missing compared with them.`
    : `Skip competitor analysis.`;

  return [
    {role:"system", content:"You are an elite SEO strategist. Output STRICT JSON only, no prose."},
    {role:"user", content:
`Task: Create SEO-optimized titles, meta descriptions, and an H2/H3 outline for the provided article content, tuned to the target keyword, audience, and intent.

${schemaHint}

Inputs:
- Target keyword: "${targetKeyword || "not specified"}"
- Audience: ${audience || "general readers"}
- Content goal/intent: ${contentGoal || "informational"}
- Original (guessed) title: ${title || "Untitled"}

${competitorNote}

Article content (truncated ~8k chars):
${shortened}`}
  ];
}

function buildCsvMetadataPrompt({title, content, audience, contentGoal, includeCompetitor}){
  const shortened = content.slice(0, MAX_CHARS);
  return [
    {role:"system", content:"You are an elite SEO strategist. Output STRICT JSON only, no prose."},
    {role:"user", content:
`Return STRICT JSON:
{
  "title_option_1":"50–60 char title incl. main topic",
  "title_option_2":"50–60 char title incl. main topic",
  "title_option_3":"50–60 char title incl. main topic",
  "heading_suggestions":"multiline with H2 lines prefixed '## ' and H3 '### '",
  "meta_desc_1":"150–160 chars, compelling, includes topic once",
  "meta_desc_2":"150–160 chars, compelling, includes topic once",
  "meta_desc_3":"150–160 chars, compelling, includes topic once"${includeCompetitor ? `,
  "competitor_gaps":"3–5 must-cover topics that competing pages on this topic usually cover and this content lacks, separated by semicolons"` : ""}
}
Rules:
- Be specific to the content provided.
- Audience: ${audience || "general"}.
- Goal/intent: ${contentGoal || "informational"}.
- No markup, no backticks, JSON only.${includeCompetitor ? `
- You cannot browse the web; base competitor_gaps on what you know about pages that rank for this topic.` : ""}

Title: ${title || "Untitled"}

Content (truncated):
${shortened}`}
  ];
}

/* ---------- run ---------- */
function setBusy(on, total){
  busy = on;
  $("run").disabled = on; $("clear").disabled = on;
  document.querySelectorAll('.tabs [role=tab]').forEach(b => b.disabled = on);
  $("stop").hidden = !(on && total);
  $("prog").hidden = !(on && total);
  if (on && total){ $("prog").max = total; $("prog").value = 0; }
}

$("run").onclick = () => mode === "article" ? runArticle() : runCsv();
$("stop").onclick = () => { abort = true; say("Stopping after the rows already in flight…"); };

async function runArticle(){
  const apiKey = $("key").value.trim(), model = $("model").value;
  const text = $("text").value.trim(), keyword = $("keyword").value.trim();
  if (!apiKey) return fail("Add your OpenAI API key first.", "key");
  if (!text) return fail("Paste the article text first.", "text");
  if (!keyword) return fail("Add a target keyword. Single-article mode needs one.", "keyword");

  const title = (text.split("\n").find(l => l.trim().length > 8) || "Blog post").trim().slice(0, 120);
  const competitor = $("compA").checked;
  const messages = buildMetadataPrompt({title, content:text, targetKeyword:keyword,
    audience:$("audience").value.trim(), contentGoal:$("goal").value, includeCompetitor:competitor});

  setBusy(true);
  say(`Writing titles, meta descriptions and an outline with ${model}…`);
  try {
    const data = await openaiJSON({apiKey, model, messages, budget:2048});
    ARTICLE = {title, keyword, content:text, words:words(text), readTime:readTime(text), competitor, data};
    renderArticle();
    say(`Done with ${model}. Check the counts, edit, then copy or export.`);
  } catch(err){
    say(err.message, "err");
  } finally { setBusy(false); }
}

async function pool(items, n, fn){
  let next = 0;
  const worker = async () => { while (!abort && next < items.length){ const i = next++; await fn(items[i], i); } };
  await Promise.all(Array.from({length:Math.min(n, items.length)}, worker));
}

async function runCsv(){
  const apiKey = $("key").value.trim(), model = $("model").value;
  if (!apiKey) return fail("Add your OpenAI API key first.", "key");
  if (!ROWS || !ROWS.length) return fail("Upload a CSV with URL, Title and Content columns first.");
  const audience = $("audience").value.trim(), contentGoal = $("goal").value;
  const competitor = $("compC").checked;

  abort = false;
  const out = new Array(ROWS.length);
  let done = 0, failed = 0, fatal = null;
  setBusy(true, ROWS.length);
  say(`Processing ${ROWS.length} row(s) with ${model}, ${CONCURRENCY} at a time…`);

  await pool(ROWS, CONCURRENCY, async (row, i) => {
    const url = row[COLS.url] || "", title = row[COLS.title] || `Row ${i + 1}`, content = row[COLS.content] || "";
    const base = {URL:url, Original_Title:title, Content:content.slice(0, 500) + (content.length > 500 ? "..." : "")};
    try {
      if (!content.trim()) throw apiError(0, "This row has no content.");
      const d = await openaiJSON({apiKey, model, budget:1200,
        messages:buildCsvMetadataPrompt({title, content, audience, contentGoal, includeCompetitor:competitor})});
      out[i] = {...base,
        Title_Option_1:asText(d.title_option_1), Title_Option_2:asText(d.title_option_2), Title_Option_3:asText(d.title_option_3),
        Heading_Suggestions:asText(d.heading_suggestions),
        Meta_Description_1:asText(d.meta_desc_1), Meta_Description_2:asText(d.meta_desc_2), Meta_Description_3:asText(d.meta_desc_3),
        Competitor_Gaps:competitor ? asList(d.competitor_gaps) : "", _ok:true};
    } catch(err){
      failed++;
      out[i] = {...base, Title_Option_1:`ERROR: ${err.message}`, Title_Option_2:"", Title_Option_3:"",
        Heading_Suggestions:"", Meta_Description_1:"", Meta_Description_2:"", Meta_Description_3:"",
        Competitor_Gaps:"", _ok:false};
      if (err.fatal){ abort = true; fatal = fatal || err; }
    }
    done++; $("prog").value = done;
    if (!fatal) say(`${done}/${ROWS.length} processed${failed ? ` · ${failed} failed` : ""}`);
  });

  const stopped = abort && !fatal;
  setBusy(false);
  const rows = out.filter(Boolean);
  if (!rows.length || (fatal && rows.every(r => !r._ok))){
    BULK = null; $("out-csv").hidden = true;
    return say(fatal ? fatal.message : "Nothing was processed.", "err");
  }
  BULK = {rows, competitor, total:ROWS.length, model};
  renderBulk();
  if (fatal) say(`Stopped after ${rows.length} row(s): ${fatal.message}`, "err");
  else if (stopped) say(`Stopped. ${rows.length} of ${ROWS.length} row(s) processed; the export has those rows.`);
  else say(`Done. ${rows.length - failed} of ${rows.length} row(s) succeeded${failed ? `; ${failed} failed, marked ERROR in the export` : ""}.`, failed ? "err" : "");
}

/* ---------- single-article results ---------- */
function outCard(id, label, text, range){
  return `<div class="out">
    <div class="top"><span class="lbl">${esc(label)}</span>
      <span class="meta">${range ? `<span class="count" id="${id}-n"></span>` : ""}<button class="ghost small" data-copy="${id}">Copy</button></span>
    </div>
    <textarea id="${id}" class="${range ? "" : "outline"}" ${range ? `data-range="${range.join(",")}"` : ""} spellcheck="true">${esc(text)}</textarea>
  </div>`;
}

function renderArticle(){
  const {title, keyword, data, competitor} = ARTICLE;
  const pickText = v => typeof v === "string" ? v : (v?.text || "");
  const titles = (data.title_options || []).map(pickText);
  const metas = (data.meta_descriptions || []).map(pickText);
  const outline = asText(data.heading_suggestions) || "No heading suggestions came back. Try again.";

  $("a-context").innerHTML = `Current title: <b>${esc(title)}</b> · Target keyword: <b>${esc(keyword)}</b>`;
  $("a-titles").innerHTML = titles.length ? titles.map((t,i) => outCard(`t${i}`, `Title option ${i+1}`, t, TITLE_RANGE)).join("")
    : `<p class="hint err">No title options came back. Try again.</p>`;
  $("a-metas").innerHTML = metas.length ? metas.map((m,i) => outCard(`m${i}`, `Meta description ${i+1}`, m, META_RANGE)).join("")
    : `<p class="hint err">No meta descriptions came back. Try again.</p>`;
  $("a-outline").innerHTML = outCard("outline", "Improved H2/H3 structure", outline, null);

  const serp = data.serp;
  $("a-serp").hidden = !(competitor && serp);
  if (competitor && serp){
    const top = Array.isArray(serp.top_results) ? serp.top_results : [];
    $("a-serp-table").innerHTML = `<thead><tr><th class="n">#</th><th>Likely result</th><th>Site</th><th>Angle</th></tr></thead><tbody>${
      top.map((r,i) => `<tr><td class="n">${esc(r.rank ?? i+1)}</td><td>${esc(r.title)}</td>
        <td class="url">${esc(r.source)}</td><td>${esc(r.notes || r.description)}</td></tr>`).join("")
      || `<tr><td colspan="4" class="hint">No likely results came back.</td></tr>`}</tbody>`;
    const gaps = Array.isArray(serp.competitor_gaps) ? serp.competitor_gaps : (serp.competitor_gaps ? [serp.competitor_gaps] : []);
    const feats = Array.isArray(serp.serp_features) ? serp.serp_features : [];
    $("a-gaps").innerHTML = `<strong>Likely gaps in your content</strong>${gaps.length
      ? `<ul class="gaps">${gaps.map(g => `<li>${esc(asText(g))}</li>`).join("")}</ul>` : `<div class="hint">None suggested.</div>`}`;
    $("a-features").innerHTML = `<strong>SERP features to plan for</strong>${feats.length
      ? `<div class="chips">${feats.map(f => `<span class="chip">${esc(asText(f))}</span>`).join("")}</div>` : `<div class="hint">None suggested.</div>`}`;
  }

  document.querySelectorAll("#out-article textarea[data-range]").forEach(ta => {
    ta.addEventListener("input", () => { updateCount(ta); renderArticleTiles(); });
    updateCount(ta);
  });
  document.querySelectorAll("#out-article [data-copy]").forEach(b => b.onclick = () => copyText($(b.dataset.copy).value, b));
  renderArticleTiles();
  $("out-article").hidden = false;
}

function updateCount(ta){
  const range = ta.dataset.range.split(",").map(Number);
  const n = ta.value.trim().length, el = $(ta.id + "-n");
  const kw = ARTICLE.keyword;
  el.textContent = `${n} characters` + (kw ? (hasKw(ta.value, kw) ? " · keyword in" : " · no keyword") : "");
  el.className = "count " + (inRange(n, range) ? "ok" : "off");
}

function currentArticle(){
  const vals = sel => [...document.querySelectorAll(sel)].map(t => t.value.trim());
  return {titles:vals('#a-titles textarea'), metas:vals('#a-metas textarea'), outline:($("outline")?.value || "").trim()};
}

function renderArticleTiles(){
  const {titles, metas} = currentArticle();
  const tOk = titles.filter(t => inRange(t.length, TITLE_RANGE)).length;
  const mOk = metas.filter(m => inRange(m.length, META_RANGE)).length;
  const kOk = [...titles, ...metas].filter(t => hasKw(t, ARTICLE.keyword)).length;
  const lvl = (n, of) => n === of ? "good" : n === 0 ? "crit" : "warn";
  $("a-tiles").innerHTML = [
    ["Read time", `${ARTICLE.readTime} min`, `${ARTICLE.words.toLocaleString()} words`, ""],
    ["Titles in range", `${tOk}/${titles.length}`, "50 to 60 characters", lvl(tOk, titles.length)],
    ["Metas in range", `${mOk}/${metas.length}`, "150 to 160 characters", lvl(mOk, metas.length)],
    ["Keyword used", `${kOk}/${titles.length + metas.length}`, "titles and metas that contain it", lvl(kOk, titles.length + metas.length)]
  ].map(([k,v,d,c]) => `<div class="tile ${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");
}

function articleRow(){
  const {titles, metas, outline} = currentArticle();
  const c = ARTICLE.content;
  return {URL:"", Original_Title:ARTICLE.title, Content:c.slice(0, 500) + (c.length > 500 ? "..." : ""),
    Title_Option_1:titles[0] || "", Title_Option_2:titles[1] || "", Title_Option_3:titles[2] || "",
    Heading_Suggestions:outline,
    Meta_Description_1:metas[0] || "", Meta_Description_2:metas[1] || "", Meta_Description_3:metas[2] || "",
    Competitor_Gaps:ARTICLE.competitor && ARTICLE.data.serp ? asList(ARTICLE.data.serp.competitor_gaps) : ""};
}

$("copy-all").onclick = e => {
  const {titles, metas, outline} = currentArticle();
  const r = articleRow();
  const text = [`Current title: ${ARTICLE.title}`, `Target keyword: ${ARTICLE.keyword}`, "",
    "TITLE OPTIONS", ...titles.map((t,i) => `${i+1}. ${t} (${t.length} characters)`), "",
    "META DESCRIPTIONS", ...metas.map((m,i) => `${i+1}. ${m} (${m.length} characters)`), "",
    "HEADING OUTLINE", outline]
    .concat(r.Competitor_Gaps ? ["", "LIKELY COMPETITOR GAPS (inferred)", r.Competitor_Gaps] : []).join("\n");
  copyText(text, e.currentTarget);
};
$("dl-article").onclick = async () => {
  const cols = ARTICLE.competitor ? [...CSV_COLS, "Competitor_Gaps"] : CSV_COLS;
  const r = await offerFile("seo-metadata-generated.csv", toCSV([articleRow()], cols), "text/csv");
  say(r === "saved" ? "Exported seo-metadata-generated.csv." : "Export cancelled.");
};

/* ---------- CSV upload ---------- */
function csvInfo(html){ $("csvinfo").innerHTML = html; }

$("csvfile").onchange = e => {
  const f = e.target.files[0];
  if (!f) return;
  ROWS = null; COLS = null; $("csvpreview").hidden = true;
  if (!/\.csv$/i.test(f.name) && f.type !== "text/csv"){
    e.target.value = "";
    csvInfo(`<strong>That is not a .csv file.</strong> Export your sheet as CSV and try again.`);
    return readyMessage();
  }
  if (typeof Papa === "undefined"){
    csvInfo(`<strong>The CSV reader did not load.</strong> Check your connection or ad blocker, then reload the page.`);
    return readyMessage();
  }
  Papa.parse(f, {
    header:true, skipEmptyLines:"greedy",
    complete: res => onParsed(res, f.name),
    error: () => { csvInfo("<strong>That file could not be read as CSV.</strong>"); readyMessage(); }
  });
};

function onParsed(res, name){
  const head = (res.meta?.fields || []).filter(h => h != null && String(h).trim() !== "");
  const find = (exact, loose) => head.find(h => exact.includes(h.trim().toLowerCase())) || head.find(h => loose.test(h));
  const cols = {
    url: find(["url","address","page","link"], /url/i),
    title: find(["title","title 1","page title","original_title"], /title/i),
    content: find(["content","body","text","main content","extracted content"], /^(?!.*content.?type).*content/i)
  };
  const missing = [["URL",cols.url],["Title",cols.title],["Content",cols.content]].filter(([,v]) => !v).map(([k]) => k);
  if (missing.length){
    csvInfo(`<strong>Missing column${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}.</strong> Found: ${esc(head.slice(0,10).join(", ") || "none")}`);
    return readyMessage();
  }
  const rows = (res.data || []).filter(r => Object.values(r).some(v => String(v ?? "").trim()));
  if (!rows.length){
    csvInfo("<strong>That CSV has a header but no rows.</strong>");
    return readyMessage();
  }
  ROWS = rows; COLS = cols; FILE = name;
  const empty = rows.filter(r => !String(r[cols.content] ?? "").trim()).length;
  const shown = [cols.url, cols.title, cols.content];
  $("csvtable").innerHTML = `<thead><tr>${shown.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${
    rows.slice(0, 6).map(r => `<tr>${shown.map(h => `<td class="clip" title="${esc(clip(r[h], 300))}">${esc(clip(r[h], 80))}</td>`).join("")}</tr>`).join("")}</tbody>`;
  $("csvpreview").hidden = false;
  csvInfo(`<strong>${rows.length.toLocaleString()}</strong> row(s) ready from ${esc(name)}`
    + `${rows.length > 6 ? " · preview shows the first 6" : ""}`
    + `${empty ? ` · <strong>${empty}</strong> with no content will be skipped` : ""}`
    + `${res.errors?.length ? ` · ${res.errors.length} parse warning(s), check the preview` : ""}`);
  readyMessage();
}

/* ---------- CSV results ---------- */
function renderBulk(){
  const {rows, competitor, total} = BULK;
  const ok = rows.filter(r => r._ok);
  const titles = ok.flatMap(r => [r.Title_Option_1, r.Title_Option_2, r.Title_Option_3]).filter(Boolean);
  const metas = ok.flatMap(r => [r.Meta_Description_1, r.Meta_Description_2, r.Meta_Description_3]).filter(Boolean);
  const pct = (arr, range) => arr.length ? Math.round(arr.filter(t => inRange(t.trim().length, range)).length / arr.length * 100) : 0;
  const failed = rows.length - ok.length;
  const tp = pct(titles, TITLE_RANGE), mp = pct(metas, META_RANGE);
  const lvl = p => p >= 80 ? "good" : p >= 50 ? "warn" : "crit";
  $("c-tiles").innerHTML = [
    ["Rows processed", `${rows.length}/${total}`, rows.length < total ? "stopped early" : "every row", rows.length < total ? "warn" : ""],
    ["Failed", failed, failed ? "marked ERROR in the export" : "no errors", failed ? "crit" : "good"],
    ["Titles in range", `${tp}%`, "of all options, 50 to 60 characters", lvl(tp)],
    ["Metas in range", `${mp}%`, "of all options, 150 to 160 characters", lvl(mp)]
  ].map(([k,v,d,c]) => `<div class="tile ${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const n = s => String(s ?? "").trim().length;
  $("c-table").innerHTML = `<thead><tr><th>URL</th><th>Original title</th><th>Title option 1</th><th class="n">Chars</th>
      <th>Meta description 1</th><th class="n">Chars</th>${competitor ? "<th>Competitor gaps</th>" : ""}</tr></thead><tbody>${
    rows.slice(0, TABLE_ROWS).map(r => `<tr>
      <td class="url" title="${esc(r.URL)}">${esc(r.URL)}</td>
      <td class="clip" title="${esc(r.Original_Title)}">${esc(r.Original_Title)}</td>
      ${r._ok ? `<td class="wrap-cell">${esc(r.Title_Option_1)}</td><td class="n">${n(r.Title_Option_1)}</td>
      <td class="wrap-cell">${esc(r.Meta_Description_1)}</td><td class="n">${n(r.Meta_Description_1)}</td>`
      : `<td colspan="4"><span class="flag">error</span> ${esc(r.Title_Option_1.replace(/^ERROR: /, ""))}</td>`}
      ${competitor ? `<td class="wrap-cell">${esc(r.Competitor_Gaps)}</td>` : ""}
    </tr>`).join("")}</tbody>`;
  $("c-note").textContent = rows.length > TABLE_ROWS
    ? `Showing the first ${TABLE_ROWS} of ${rows.length} rows. The download has every row, all three options and the outlines.`
    : "The download has all three title and meta options per row, plus the heading outlines.";
  $("out-csv").hidden = mode !== "csv";
}

$("dl-csv").onclick = async () => {
  const cols = BULK.competitor ? [...CSV_COLS, "Competitor_Gaps"] : CSV_COLS;
  const r = await offerFile("seo-metadata-generated.csv", toCSV(BULK.rows, cols), "text/csv");
  say(r === "saved" ? "Downloaded seo-metadata-generated.csv." : "Download cancelled.");
};
$("copy10").onclick = e => {
  const text = BULK.rows.slice(0, 10).map((r, i) =>
    `#${i + 1} ${r.Original_Title}\n\nTitle Option 1: ${r.Title_Option_1}\nTitle Option 2: ${r.Title_Option_2}\nTitle Option 3: ${r.Title_Option_3}`
  ).join("\n\n---\n\n");
  copyText(text, e.currentTarget);
};

/* ---------- clear ---------- */
$("clear").onclick = () => {
  if (mode === "article"){
    $("text").value = ""; $("keyword").value = ""; $("compA").checked = true;
    $("text").dispatchEvent(new Event("input"));
    ARTICLE = null; $("out-article").hidden = true;
  } else {
    $("csvfile").value = ""; ROWS = null; COLS = null; FILE = "";
    $("csvpreview").hidden = true; $("csvtable").innerHTML = "";
    csvInfo("Needs URL, Title and Content columns. One row per page.");
    $("compC").checked = false;
    BULK = null; $("out-csv").hidden = true;
  }
  $("audience").value = ""; $("goal").value = "";
  readyMessage();
};

readyMessage();
