
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt = n => Number(n).toLocaleString("en-GB");
const cut = (s, n) => { s = String(s ?? ""); return s.length > n ? s.slice(0, n) + "…" : s; };

const API = "https://api.openai.com/v1/chat/completions";
const MAX_CHARS = 9000;          // the old tool's limit: longer articles are truncated
const CONCURRENCY = 3;           // CSV rows in flight at once
const TOKENS = {article: 6000, row: 2500};   // max_completion_tokens ceilings
// Rough per-request sizes for the estimate (prompt overhead and typical replies).
const EST = {article: {over: 350, out: 1400}, row: {over: 250, out: 350}};

// chatgpt-4o-latest (the old default) was switched off on 17 Feb 2026, and its
// named successor gpt-5.1-chat-latest is gone too. chat-latest is the same idea:
// the model ChatGPT runs. gpt-4o is deprecated (off 14 Jan 2027); OpenAI names
// gpt-6-luna as its replacement. Luna is a reasoning model, so reasoning_effort
// "none" keeps it as quick and literal as gpt-4o was.
const MODELS = {
  "chat-latest": {price: [5, 30], note: "Replaces chatgpt-4o-latest, which OpenAI switched off in February 2026. $5 in, $30 out per million tokens."},
  "gpt-6-luna":  {price: [0.10, 0.50], effort: "none", note: "OpenAI's replacement for gpt-4o. $0.10 in, $0.50 out per million tokens."},
  "other":       {price: null, note: "Type the ID below. The cost estimate is only shown for the listed models."}
};

let mode = "article", running = false, controller = null;
let CSV = {rows: [], cols: {}, empty: 0};
let SINGLE = null, OUT = [];

/* ---------- helpers ---------- */
const words = t => t.split(/\s+/).filter(Boolean).length;
const readMins = t => Math.max(1, Math.ceil(words(t) / 220));
const guessTitle = t => (t.split("\n").find(l => l.trim().length > 8) || "Article").trim().slice(0, 120);
const modelId = () => $("model").value === "other" ? $("custommodel").value.trim() : $("model").value;

function opts(){
  return {
    allowEmoji: $("emoji").checked,
    includeHashtags: $("hashtags").checked,
    audience: $("audience").value.trim(),
    persona: $("voice").value.trim(),
    ctaText: $("cta").value.trim()
  };
}

function setStatus(msg){ $("status").textContent = msg; }
function showError(html){ $("err").innerHTML = html; $("err").hidden = !html; }

/* ---------- prompts (unchanged from the original tool) ---------- */
function buildArticlePrompt({ title, url, content, allowEmoji, includeHashtags, audience, persona, ctaText }){
  const shortened = content.length > MAX_CHARS ? content.slice(0, MAX_CHARS) : content;
  const ctaInstruction = ctaText ? `\n- Include this call-to-action when appropriate: "${ctaText}"` : "";
  return [
    { role: "system", content: "You are a world-class social copywriter. Output STRICT JSON only." },
    { role: "user", content:
      "Create social copy from a web article.\n\n" +
      "Constraints:\n" +
      '- Return JSON with keys: {"linkedin_posts":[{"label":"...","text":"..."}], "tweets":[{"label":"...","text":"..."}]}\n' +
      "- For LinkedIn: write 3 distinct posts, 500–1,200 characters each. Each must start with a strong hook. " + (allowEmoji ? "Emojis allowed sparingly." : "Do NOT use any emojis.") + "\n" +
      "- For Twitter/X: write 5 distinct tweets, each ≤ 280 chars. " + (allowEmoji ? "Emojis allowed sparingly." : "No emojis.") + "\n" +
      "- Prefer specifics and insights from the content. Add " + (includeHashtags ? "2–5 relevant hashtags" : "no hashtags") + ".\n" +
      "- Audience: " + (audience || "general professional readers") + ". Voice: " + (persona || "helpful and practical") + "." +
      ctaInstruction + "\n" +
      "- Keep claims faithful to the source. Avoid clickbait.\n\n" +
      "Title: " + title + "\nURL: " + url + "\n\nExtracted content (truncated):\n" + shortened }
  ];
}

function buildRowPrompt({ title, content, allowEmoji, includeHashtags, audience, persona, ctaText }){
  const shortened = content.length > MAX_CHARS ? content.slice(0, MAX_CHARS) : content;
  const ctaInstruction = ctaText ? `\n- Include this call-to-action when appropriate: "${ctaText}"` : "";
  return [
    { role: "system", content: "You are a concise social copywriter. Output STRICT JSON only." },
    { role: "user", content:
      "Create one LinkedIn post and one tweet from the article content below.\n" +
      'Return JSON: {"linkedin_post":"...","tweet":"..."}\n' +
      "- LinkedIn: 500–1,000 characters, start with a hook. " + (allowEmoji ? "Emojis allowed sparingly." : "No emojis.") + " " + (includeHashtags ? "Add 2–5 relevant hashtags" : "No hashtags") + ".\n" +
      "- Tweet: ≤ 280 characters. " + (allowEmoji ? "Emojis allowed sparingly." : "No emojis.") + " " + (includeHashtags ? "Add 1–3 relevant hashtags if space allows" : "No hashtags") + ".\n" +
      "- Audience: " + (audience || "professionals") + ". Voice: " + (persona || "clear and useful") + "." +
      ctaInstruction + "\n" +
      "- Be factual; avoid hype.\n\n" +
      "Title: " + title + "\n\nContent (truncated):\n" + shortened }
  ];
}

/* ---------- OpenAI ---------- */
function fail(msg, status){ const e = new Error(msg); e.status = status; return e; }

async function openaiJSON({ key, model, messages, maxTokens, signal }){
  const body = { model, messages, max_completion_tokens: maxTokens, response_format: { type: "json_object" } };
  const effort = MODELS[model] && MODELS[model].effort;
  if (effort) body.reasoning_effort = effort;
  let res;
  try {
    res = await fetch(API, {
      method: "POST", signal,
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${key}` },
      body: JSON.stringify(body)
    });
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    throw fail("network", 0);
  }
  if (!res.ok){
    let msg = `HTTP ${res.status}`, code = "";
    try { const b = await res.json(); msg = (b.error && b.error.message) || msg; code = (b.error && (b.error.code || b.error.type)) || ""; } catch {}
    const e = fail(msg, res.status); e.code = code; throw e;
  }
  const data = await res.json();
  const choice = (data.choices && data.choices[0]) || {};
  const raw = (choice.message && choice.message.content) || "";
  const cutOff = choice.finish_reason === "length";
  if (!raw) throw fail((choice.message && choice.message.refusal) || "empty reply", cutOff ? "length" : "empty");
  try { return JSON.parse(raw); }
  catch {
    const m = raw.match(/\{[\s\S]*\}/);
    if (m) { try { return JSON.parse(m[0]); } catch {} }
    throw fail("invalid JSON", cutOff ? "length" : "json");
  }
}

function explainError(err){
  const m = String((err && err.message) || "");
  if (err && err.name === "AbortError") return "Stopped.";
  switch (err && err.status){
    case 0: return "Could not reach OpenAI. Check your connection, or whether an extension or network policy blocks api.openai.com.";
    case 401: return "OpenAI rejected that API key. Check for stray spaces, or create a new key.";
    case 403: return "That key is not allowed to make this request: " + m;
    case 404: return "That model is not available to your key. Choose another model. (" + m + ")";
    case 429: return /quota|billing|credit/i.test(m + " " + (err.code || ""))
      ? "Your OpenAI account has run out of credit. Add credit in the OpenAI billing settings, then try again."
      : "Rate limited by OpenAI. Wait a minute and try again.";
    case 400: return "OpenAI rejected the request: " + m;
    case "length": return "The reply was cut off before it finished. Try again, or choose another model.";
    case "json": return "The model did not return valid JSON. Try again, or choose another model.";
    case "empty": return "The model returned an empty reply" + (m && m !== "empty reply" ? ": " + m : ".");
    case "noposts": return "The model replied, but without any posts. Try again, or choose another model.";
    default: return m || "Request failed.";
  }
}
// Errors that will fail every remaining CSV row the same way.
const isFatal = err => [0, 400, 401, 403, 404].includes(err.status) ||
  (err.status === 429 && /quota|billing|credit/i.test(err.message + " " + (err.code || "")));

/* ---------- mode tabs ---------- */
document.querySelectorAll(".tabs [role=tab]").forEach(b => b.addEventListener("click", () => {
  if (running) return;
  mode = b.dataset.mode;
  document.querySelectorAll(".tabs [role=tab]").forEach(x => x.setAttribute("aria-selected", String(x === b)));
  $("pane-article").hidden = mode !== "article";
  $("pane-csv").hidden = mode !== "csv";
  showError("");
  refresh();
}));

/* ---------- model ---------- */
function onModel(){
  const v = $("model").value;
  $("customwrap").hidden = v !== "other";
  $("modelnote").textContent = MODELS[v].note;
  refresh();
}
$("model").addEventListener("change", onModel);

/* ---------- CSV input ---------- */
// PapaParse does the work; this small parser is only a fallback in case the
// CDN script is blocked or stripped, so the tool still reads a file.
function fallbackParse(text){
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++){
    const c = text[i];
    if (q){ if (c === '"'){ if (text[i+1] === '"'){ cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === ","){ row.push(cell); cell = ""; }
    else if (c === "\n"){ row.push(cell); rows.push(row); row = []; cell = ""; }
    else if (c !== "\r") cell += c;
  }
  if (cell || row.length){ row.push(cell); rows.push(row); }
  const seen = new Map(), fields = [], renamed = [];
  for (const h of (rows.shift() || []).map(h => h.trim())){
    if (seen.has(h)){ const n = seen.get(h) + 1; seen.set(h, n); renamed.push(h); fields.push(`${h}_${n-1}`); }
    else { seen.set(h, 1); fields.push(h); }
  }
  return { fields, renamed: [...new Set(renamed)],
    rows: rows.filter(r => r.some(v => v.trim() !== "")).map(r => Object.fromEntries(fields.map((h, i) => [h, r[i] ?? ""]))) };
}

function parseCSV(text){
  text = text.replace(/^﻿/, "");
  if (window.Papa && Papa.parse){
    const r = Papa.parse(text, { header: true, skipEmptyLines: "greedy", transformHeader: h => h.trim() });
    const renamed = r.meta && r.meta.renamedHeaders ? [...new Set(Object.values(r.meta.renamedHeaders))] : [];
    return { fields: (r.meta && r.meta.fields) || [], rows: r.data || [], renamed };
  }
  return fallbackParse(text);
}

// Exact name first, then the loose match the original tool used (/url/i etc.).
function findCol(fields, exact, loose){
  return fields.find(f => exact.includes(f.toLowerCase())) || fields.find(f => loose.test(f));
}

function resetCSV(msg){
  CSV = { rows: [], cols: {}, empty: 0 };
  $("csvpreview").hidden = true; $("csvtable").innerHTML = "";
  if (msg) $("csvinfo").innerHTML = msg;
  refresh();
}

$("csvfile").addEventListener("change", async e => {
  const f = e.target.files && e.target.files[0];
  if (!f) return;
  showError("");
  if (!/\.csv$/i.test(f.name) && f.type !== "text/csv"){
    e.target.value = "";
    return resetCSV("<strong>Please choose a .csv file.</strong>");
  }
  let parsed;
  try { parsed = parseCSV(await f.text()); }
  catch { return resetCSV("<strong>That file could not be read as CSV.</strong>"); }
  const { fields, rows, renamed } = parsed;
  if (!fields.length) return resetCSV("<strong>That CSV has no header row.</strong>");
  const cols = {
    url: findCol(fields, ["url", "address", "link", "page"], /url/i),
    title: findCol(fields, ["title", "page title", "title 1", "post title"], /title/i),
    content: findCol(fields, ["content", "body", "text", "article", "article text"], /content/i)
  };
  if (!cols.content){
    return resetCSV(`<strong>No content column found.</strong> Looked for Content, Body, Text. Columns present: ${esc(fields.slice(0, 10).join(", "))}`);
  }
  if (!rows.length) return resetCSV("<strong>That CSV has a header but no rows.</strong>");
  const empty = rows.filter(r => !String(r[cols.content] || "").trim()).length;
  CSV = { rows, cols, empty };

  $("csvinfo").innerHTML =
    (renamed.length ? `<strong>Duplicate column name(s): ${esc(renamed.join(", "))}</strong>, renamed so none are lost. ` : "") +
    `<strong>${fmt(rows.length - empty)}</strong> article${rows.length - empty === 1 ? "" : "s"} ready from <code>${esc(f.name)}</code>` +
    ` · content from <code>${esc(cols.content)}</code>` +
    (cols.title ? ` · titles from <code>${esc(cols.title)}</code>` : " · no Title column, rows are numbered instead") +
    (cols.url ? "" : " · no URL column") +
    (empty ? ` · ${fmt(empty)} row${empty === 1 ? " has" : "s have"} no content and will be skipped` : "");

  const head = fields.map(h => `<th>${esc(h)}</th>`).join("");
  const body = rows.slice(0, 6).map(r => `<tr>${fields.map(h => `<td>${esc(cut(r[h], 80))}</td>`).join("")}</tr>`).join("");
  $("csvtable").innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;
  $("csvpreview").hidden = false;
  refresh();
});

/* ---------- readiness + estimate ---------- */
function problem(){
  if (mode === "article" && !$("atext").value.trim()) return "Paste an article to begin.";
  if (mode === "csv" && !CSV.rows.length) return "Choose a CSV to begin.";
  if (mode === "csv" && CSV.rows.length === CSV.empty) return "Every row in that CSV has an empty content column.";
  if (!$("key").value.trim()) return "Add your OpenAI API key to run.";
  if (!modelId()) return "Type a model ID, or choose one from the list.";
  return "";
}

function money(x){
  if (x === 0) return "$0.00";
  return x < 0.01 ? "under $0.01" : "$" + x.toFixed(2);
}

function updateEstimate(){
  let req = 0, tin = 0, tout = 0;
  if (mode === "article"){
    const t = $("atext").value.trim();
    if (t){ req = 1; tin = Math.ceil(Math.min(t.length, MAX_CHARS) / 4) + EST.article.over; tout = EST.article.out; }
  } else if (CSV.rows.length){
    for (const r of CSV.rows){
      const c = String(r[CSV.cols.content] || "").trim();
      if (!c) continue;
      req++; tin += Math.ceil(Math.min(c.length, MAX_CHARS) / 4) + EST.row.over; tout += EST.row.out;
    }
  }
  $("est").hidden = !req;
  $("e-req").textContent = fmt(req);
  $("e-in").textContent = fmt(tin);
  $("e-out").textContent = fmt(tout);
  const m = MODELS[$("model").value];
  $("e-cost").textContent = m && m.price ? money((tin * m.price[0] + tout * m.price[1]) / 1e6) : "unknown";
}

function articleInfo(){
  const t = $("atext").value.trim();
  if (!t){ $("textinfo").textContent = "Only the first 9,000 characters are sent to the model."; return; }
  let s = `${fmt(words(t))} words · about ${readMins(t)} min read · ${fmt(t.length)} characters`;
  s += t.length > MAX_CHARS ? `. Only the first ${fmt(MAX_CHARS)} are sent to the model.` : "";
  $("textinfo").textContent = s;
}

function refresh(){
  articleInfo();
  updateEstimate();
  const ready = mode === "article" || CSV.rows.length;
  $("run").textContent = mode === "csv" && ready
    ? `Generate for ${fmt(CSV.rows.length - CSV.empty)} row${CSV.rows.length - CSV.empty === 1 ? "" : "s"}`
    : "Generate posts";
  if (running) return;
  const p = problem();
  $("run").disabled = !!p;
  setStatus(p || (mode === "csv" ? "Ready. Rows run three at a time." : "Ready."));
}

["key", "custommodel", "atext", "atitle", "aurl"].forEach(id => $(id).addEventListener("input", refresh));

/* ---------- busy state ---------- */
function busy(on){
  running = on;
  $("run").disabled = on;
  $("stop").hidden = !on;
  $("clear").disabled = on;
  $("csvfile").disabled = on;
  document.querySelectorAll(".tabs [role=tab]").forEach(b => b.disabled = on);
  // Results always describe the last run, so a new run clears the old ones.
  if (on){ $("results").hidden = true; $("res-article").hidden = true; $("res-csv").hidden = true; }
  else { $("prog").hidden = true; controller = null; }
}

$("stop").addEventListener("click", () => { if (controller) controller.abort(); setStatus("Stopping…"); });

/* ---------- run: one article ---------- */
async function runArticle(){
  const key = $("key").value.trim(), model = modelId();
  const text = $("atext").value.trim();
  const title = $("atitle").value.trim() || guessTitle(text);
  const url = $("aurl").value.trim();
  controller = new AbortController();
  busy(true); showError("");
  setStatus("Writing 3 LinkedIn posts and 5 tweets…");
  try {
    const data = await openaiJSON({ key, model, maxTokens: TOKENS.article, signal: controller.signal,
      messages: buildArticlePrompt({ title, url: url || "Manual input", content: text, ...opts() }) });
    const list = (a, fallback) => (Array.isArray(a) ? a : []).map((p, i) => ({
      label: String((p && p.label) || `${fallback} ${i + 1}`), text: String((p && p.text) || (typeof p === "string" ? p : "")).trim()
    })).filter(p => p.text);
    const posts = list(data.linkedin_posts, "Variant"), tweets = list(data.tweets, "Tweet");
    if (!posts.length && !tweets.length) throw fail("no posts", "noposts");
    SINGLE = { title, url, mins: readMins(text), posts, tweets };
    renderArticle();
    setStatus(`Done. ${posts.length} LinkedIn post${posts.length === 1 ? "" : "s"} and ${tweets.length} tweet${tweets.length === 1 ? "" : "s"}.`);
  } catch (err){
    const m = explainError(err);
    setStatus(err.name === "AbortError" ? "Stopped." : "Something went wrong.");
    if (err.name !== "AbortError") showError(`<strong>Something went wrong.</strong> ${esc(m)}`);
  } finally { busy(false); }
}

/* ---------- run: CSV rows ---------- */
async function runCSV(){
  const key = $("key").value.trim(), model = modelId();
  const { rows, cols } = CSV, o = opts();
  OUT = new Array(rows.length);
  controller = new AbortController();
  const signal = controller.signal;
  busy(true); showError("");
  $("prog").hidden = false; $("prog").max = rows.length; $("prog").value = 0;
  let next = 0, done = 0, fatal = null;

  const worker = async () => {
    while (!fatal && !signal.aborted && next < rows.length){
      const i = next++, r = rows[i];
      const url = cols.url ? String(r[cols.url] || "").trim() : "";
      const title = (cols.title ? String(r[cols.title] || "").trim() : "") || `Row ${i + 1}`;
      const content = String(r[cols.content] || "").trim();
      if (!content){
        OUT[i] = { URL: url, Title: title, LinkedIn_Post: "SKIPPED: no content", Tweet: "SKIPPED: no content", state: "skipped" };
      } else {
        try {
          const data = await openaiJSON({ key, model, maxTokens: TOKENS.row, signal,
            messages: buildRowPrompt({ title, content, ...o }) });
          const li = String(data.linkedin_post || "").trim(), tw = String(data.tweet || "").trim();
          if (!li && !tw) throw fail("no posts", "noposts");
          OUT[i] = { URL: url, Title: title, LinkedIn_Post: li, Tweet: tw, state: "ok" };
        } catch (err){
          if (err.name === "AbortError") break;
          const m = explainError(err);
          OUT[i] = { URL: url, Title: title, LinkedIn_Post: `ERROR: ${m}`, Tweet: `ERROR: ${m}`, state: "error" };
          if (isFatal(err) && !fatal){ fatal = err; controller.abort(); }
        }
      }
      done++;
      $("prog").value = done;
      if (!fatal && !signal.aborted) setStatus(`Processed ${fmt(done)}/${fmt(rows.length)}…`);
    }
  };
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, rows.length) }, worker));

  const got = OUT.filter(Boolean);
  const ok = got.filter(r => r.state === "ok").length;
  const failed = got.filter(r => r.state === "error").length;
  busy(false);

  if (fatal){
    showError(`<strong>Run stopped.</strong> ${esc(explainError(fatal))}`);
    setStatus(ok ? `Stopped after ${fmt(ok)} row${ok === 1 ? "" : "s"}.` : "Nothing was generated.");
    if (!ok) return;
  } else if (signal.aborted){
    setStatus(`Stopped. ${fmt(ok)} of ${fmt(rows.length)} rows generated.`);
    if (!got.length) return;
  } else {
    setStatus(`Done. ${fmt(ok)} row${ok === 1 ? "" : "s"} generated${failed ? `, ${fmt(failed)} failed` : ""}.`);
  }
  renderCSV(rows.length);
}

$("run").addEventListener("click", () => {
  if (running) return;
  const p = problem();
  if (p){ setStatus(p); return; }
  (mode === "csv" ? runCSV : runArticle)();
});

/* ---------- render: one article ---------- */
function postCard(item, kind, i){
  const card = document.createElement("div");
  card.className = "post" + (kind === "tweet" ? " tweet" : "");
  const head = document.createElement("div"); head.className = "post-head";
  const h = document.createElement("h3"); h.textContent = item.label;
  const count = document.createElement("span"); count.className = "count";
  const btn = document.createElement("button"); btn.className = "ghost small"; btn.textContent = "Copy";
  const ta = document.createElement("textarea");
  ta.value = item.text; ta.id = `${kind}-${i}`;
  ta.setAttribute("aria-label", `${kind === "tweet" ? "Tweet" : "LinkedIn post"}: ${item.label}`);
  const recount = () => {
    const n = ta.value.length;
    item.text = ta.value;
    if (kind === "tweet"){ count.textContent = `${n}/280`; count.classList.toggle("over", n > 280); }
    else { count.textContent = `${fmt(n)} characters`; count.classList.toggle("over", n > 3000); }
  };
  ta.addEventListener("input", recount); recount();
  btn.addEventListener("click", () => copyText(ta.value, btn));
  head.append(h, count, btn);
  card.append(head, ta);
  return card;
}

function renderArticle(){
  const s = SINGLE;
  $("chips").innerHTML =
    `<span><b>Title:</b> ${esc(s.title)}</span>` +
    `<span><b>Source:</b> ${s.url ? `<a href="${esc(/^https?:\/\//i.test(s.url) ? s.url : "https://" + s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : "pasted text"}</span>` +
    `<span><b>About ${s.mins} min read</b></span>`;
  $("li-title").textContent = `LinkedIn posts (${s.posts.length})`;
  $("tw-title").textContent = `Tweets (${s.tweets.length})`;
  $("li-list").replaceChildren(...s.posts.map((p, i) => postCard(p, "linkedin", i)));
  $("tw-list").replaceChildren(...s.tweets.map((t, i) => postCard(t, "tweet", i)));
  $("res-csv").hidden = true; $("res-article").hidden = false; $("results").hidden = false;
}

/* ---------- render: CSV ---------- */
function renderCSV(total){
  const got = OUT.filter(Boolean);
  const n = st => got.filter(r => r.state === st).length;
  const tiles = [
    ["Rows processed", `${fmt(got.length)}`, `of ${fmt(total)} in the file`, ""],
    ["Generated", fmt(n("ok")), "one LinkedIn post and one tweet each", "good"],
    ["Failed", fmt(n("error")), n("error") ? "the error is in the post columns" : "no errors", n("error") ? "crit" : "good"]
  ];
  if (n("skipped")) tiles.push(["Skipped", fmt(n("skipped")), "no content in the row", "warn"]);
  $("tiles").innerHTML = tiles.map(([k, v, d, l]) =>
    `<div class="tile"${l ? ` data-lvl="${l}"` : ""}><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const SHOW = 500;
  const flag = r => r.state === "error" ? '<span class="flag">error</span> ' : r.state === "skipped" ? '<span class="flag skip">skipped</span> ' : "";
  $("outtable").innerHTML = `<thead><tr><th class="n">#</th><th>URL</th><th>Title</th><th>LinkedIn post</th><th>Tweet</th><th class="n">Tweet chars</th></tr></thead><tbody>${
    OUT.map((r, i) => r ? { r, i } : null).filter(Boolean).slice(0, SHOW).map(({ r, i }) => `<tr>
      <td class="n">${i + 1}</td>
      <td class="url" title="${esc(r.URL)}">${esc(r.URL) || "&ndash;"}</td>
      <td class="title">${esc(r.Title)}</td>
      <td class="text">${flag(r)}${esc(cut(r.LinkedIn_Post.replace(/^(ERROR|SKIPPED): /, ""), 140))}</td>
      <td class="text">${r.state === "ok" ? esc(cut(r.Tweet, 120)) : ""}</td>
      <td class="n">${r.state === "ok" ? r.Tweet.length : ""}</td>
    </tr>`).join("")}</tbody>`;
  $("outnote").textContent = (got.length > SHOW ? `Showing the first ${fmt(SHOW)} rows. ` : "") +
    "Posts are shortened here; the CSV has the full text.";
  $("copy10").disabled = !n("ok");
  $("res-article").hidden = true; $("res-csv").hidden = false; $("results").hidden = false;
}

/* ---------- copy + export ---------- */
async function copyText(text, btn){
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", "");
    ta.style.position = "fixed"; ta.style.top = "0"; ta.style.left = "-9999px";
    (btn ? btn.parentNode : document.body).appendChild(ta);
    ta.select();
    try { ok = document.execCommand("copy"); } catch {}
    ta.remove();
  }
  if (btn){
    const old = btn.textContent;
    btn.textContent = ok ? "Copied" : "Copy failed";
    setTimeout(() => { btn.textContent = old; }, 1400);
  }
  return ok;
}

async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use)
    ? await claude.use("downloads").catch(() => null) : null;
  if (api){
    try { await api.save({ filename, data: text }); return "saved"; }
    catch (e){ return e && e.code === "declined" ? "declined" : "failed"; }
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return "saved";
}
const toCSV = (rows, cols, keys) => {
  const q = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [cols.map(q).join(",")].concat(rows.map(r => keys.map(k => q(r[k])).join(","))).join("\n");
};

$("dl-csv").addEventListener("click", async () => {
  const r = await offerFile("generated-social-posts.csv",
    toCSV(OUT.filter(Boolean), ["URL", "Title", "LinkedIn Post", "Tweet"], ["URL", "Title", "LinkedIn_Post", "Tweet"]), "text/csv");
  setStatus(r === "saved" ? "CSV downloaded." : "Download cancelled.");
});

$("copy10").addEventListener("click", () => {
  const text = OUT.filter(r => r && r.state === "ok").slice(0, 10)
    .map((r, i) => `#${i + 1}: ${r.Title}\n\n${r.LinkedIn_Post}`).join("\n\n---\n\n");
  copyText(text, $("copy10"));
});

$("dl-article").addEventListener("click", async () => {
  if (!SINGLE) return;
  const rows = [
    ...SINGLE.posts.map(p => ({ platform: "LinkedIn", label: p.label, text: p.text, chars: p.text.length })),
    ...SINGLE.tweets.map(t => ({ platform: "X", label: t.label, text: t.text, chars: t.text.length }))
  ].map(r => ({ ...r, title: SINGLE.title, url: SINGLE.url }));
  const keys = ["platform", "label", "text", "chars", "title", "url"];
  const r = await offerFile("social-posts.csv", toCSV(rows, keys, keys), "text/csv");
  setStatus(r === "saved" ? "Posts exported." : "Export cancelled.");
});

/* ---------- clear ---------- */
$("clear").addEventListener("click", () => {
  if (running) return;
  if (mode === "article"){
    $("atext").value = ""; $("atitle").value = ""; $("aurl").value = "";
    SINGLE = null; $("res-article").hidden = true;
  } else {
    $("csvfile").value = "";
    OUT = []; $("res-csv").hidden = true;
    resetCSV('Needs a <code>Content</code> column. <code>URL</code> and <code>Title</code> columns are used when present.');
  }
  $("results").hidden = $("res-article").hidden && $("res-csv").hidden;
  showError("");
  refresh();
});

onModel();
})();
