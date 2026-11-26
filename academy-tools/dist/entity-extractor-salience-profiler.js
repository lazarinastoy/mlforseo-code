
const $ = id => document.getElementById(id);
const NLP = v => `https://language.googleapis.com/${v}/documents:analyzeEntities`;
const MAX_CHARS = 60000, FREE_UNITS = 5000, PRICE = 0.0010;
const units = t => t ? Math.max(1, Math.ceil(t.length/1000)) : 0;
const esc = s => String(s??"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const norm = s => String(s??"").toLowerCase().replace(/[^a-z0-9\s]/g," ").replace(/\s+/g," ").trim();

// Unicode-aware key for the filters, so non-Latin entity names are not reduced to "".
const fkey = s => String(s??"").normalize("NFKC").toLowerCase()
  .replace(/[^\p{L}\p{N}\s]/gu," ").replace(/\s+/g," ").trim();

/* Lesson 2.3: three noise filters, in order. */
const NOISE_TYPES = new Set(["NUMBER","DATE","PRICE","ADDRESS","PHONE_NUMBER"]);
const DEFAULT_STOP = ["one","two","three","four","five","data","content","course","lesson",
  "thing","things","way","ways","time","part","example","examples","step","steps","page","pages",
  "people","everything","anything","something","lot","bit","kind","type","types","number","numbers",
  "case","cases","point","points"];
const MIN_CHROME_PAGES = 10;   // below this, "a share of your pages" means nothing
const WHY = {structural:"structural type", generic:"generic noun", chrome:"site chrome"};
const WHY_PLURAL = {structural:"structural types", generic:"generic nouns", chrome:"site chrome"};

// DONE: one entry per document that came back, {doc, ents}. ENTITIES and PROFILES derive from it.
let DOCS = [], DONE = [], ENTITIES = [], PROFILES = [], CANDIDATES = [], abort = false;
let FLOOR = 0.05, ESORT = {k:"salience", asc:false};
const KEEP = new Set();        // chrome candidates the user unticked (by filter key)

/* ---- mode tabs ---- */
document.querySelectorAll('.tabs [role=tab]').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tabs [role=tab]').forEach(x => x.setAttribute('aria-selected', x===b));
  $("pane-paste").hidden = b.dataset.mode !== "paste";
  $("pane-csv").hidden   = b.dataset.mode !== "csv";
  if (b.dataset.mode === "paste") { DOCS = []; refresh(); }
});
$("version").onchange = e => { $("vnote").hidden = e.target.value !== "v2"; };

/* ---- CSV ---- */
function parseCSV(text){
  const rows=[]; let row=[], cell="", q=false;
  for (let i=0;i<text.length;i++){
    const c=text[i];
    if (q){ if(c==='"'){ if(text[i+1]==='"'){cell+='"';i++;} else q=false; } else cell+=c; }
    else if (c==='"') q=true;
    else if (c===","){ row.push(cell); cell=""; }
    else if (c==="\n"){ row.push(cell); rows.push(row); row=[]; cell=""; }
    else if (c!=="\r") cell+=c;
  }
  if (cell||row.length){ row.push(cell); rows.push(row); }
  const raw=(rows.shift()||[]).map(h=>h.trim());
  const {head, dupes} = dedupeHeaders(raw);
  return {head, dupes, rows:rows.filter(r=>r.some(v=>v!==""))
    .map(r=>Object.fromEntries(head.map((h,i)=>[h, r[i]??""])))};
}
const pick = (head, names) => head.find(h => names.includes(h.trim().toLowerCase()));

// Duplicate column names would silently collapse via Object.fromEntries (last
// value wins). Suffix repeats so every column survives and the user is told.
function dedupeHeaders(head){
  const seen = new Map(), out = [], dupes = [];
  for (const h of head){
    const k = h.trim();
    if (seen.has(k)){ const n = seen.get(k)+1; seen.set(k,n); dupes.push(k); out.push(`${k} (${n})`); }
    else { seen.set(k,1); out.push(k); }
  }
  return {head: out, dupes: [...new Set(dupes)]};
}

$("csvfile").onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  let parsed;
  try { parsed = parseCSV(await f.text()); }
  catch { $("csvinfo").innerHTML = "<strong>That file could not be read as CSV.</strong>"; return; }
  const {head, rows, dupes} = parsed;
  if (!rows.length){ $("csvinfo").innerHTML = "<strong>That CSV has a header but no rows.</strong>"; DOCS=[]; refresh(); return; }
  const uCol = pick(head, ["address","url","page","link"]);
  const cCol = pick(head, ["content","body","text","main content","extracted content"]);
  const iCol = pick(head, ["intended_entity","intended entity","target entity","intent"]);
  const tCol = pick(head, ["title 1","title","page title"]);
  const hCol = pick(head, ["h1-1","h1","h1 1"]);
  const mCol = pick(head, ["meta description 1","meta description","description"]);
  if (!cCol){
    $("csvinfo").innerHTML = `<strong>No content column found.</strong> Looked for content, body, text. Columns present: ${esc(head.slice(0,10).join(", "))}`;
    DOCS=[]; refresh(); return;
  }
  DOCS = rows.map((r,i) => ({
    url: (uCol ? r[uCol] : "") || `row ${i+2}`,
    text: (r[cCol]||"").slice(0, MAX_CHARS),
    intended: iCol ? (r[iCol]||"") : "",
    title: tCol ? (r[tCol]||"") : "", h1: hCol ? (r[hCol]||"") : "",
    meta: mCol ? (r[mCol]||"") : ""
  })).filter(d => d.text.trim());
  const skipped = rows.length - DOCS.length;
  $("csvinfo").innerHTML = `${dupes.length?`<strong>Duplicate column name(s): ${esc(dupes.join(", "))}</strong> — renamed so none are lost. ` : ""}<strong>${DOCS.length}</strong> documents ready${skipped?` · ${skipped} row(s) had no content and were skipped`:""}${uCol?"":" · no URL column, using row numbers"}${iCol?" · intended_entity found":""}${tCol||hCol||mCol?" · title/H1/meta found, placement will be scored":""}`;
  refresh();
};

["ptext","purl","pintent","ptitle","pmeta","key"].forEach(id => $(id).addEventListener("input", refresh));

function currentDocs(){
  if (!$("pane-csv").hidden) return DOCS;
  const t = $("ptext").value.trim();
  return t ? [{url: $("purl").value.trim() || "pasted text", text: t.slice(0,MAX_CHARS),
               intended: $("pintent").value.trim(), title: $("ptitle").value.trim(),
               h1: "", meta: $("pmeta").value.trim()}] : [];
}

function refresh(){
  const docs = currentDocs();
  const u = docs.reduce((a,d)=>a+units(d.text),0);
  const billable = Math.max(0, u - FREE_UNITS);
  $("est").hidden = !docs.length;
  $("e-docs").textContent = docs.length.toLocaleString();
  $("e-units").textContent = u.toLocaleString();
  $("e-free").textContent = Math.max(0, FREE_UNITS - u).toLocaleString();
  $("e-cost").textContent = "$" + (billable*PRICE).toFixed(2);
  $("run").disabled = !docs.length || !$("key").value.trim();
  if (!$("key").value.trim() && docs.length) $("status").textContent = "Add your API key to run.";
  else if (docs.length) $("status").textContent = `${docs.length} document(s) ready.`;
}

/* ---- extraction ---- */
async function analyze(doc, key, version){
  const res = await fetch(`${NLP(version)}?key=${encodeURIComponent(key)}`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({document:{type:"PLAIN_TEXT", content:doc.text}, encodingType:"UTF8"})
  });
  if (!res.ok){
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.error?.message || msg; } catch {}
    const e = new Error(msg); e.status = res.status; throw e;
  }
  return res.json();
}

function explainError(err){
  const m = (err.message||"").toLowerCase();
  if (err.status === 400 && m.includes("api key")) return "That API key isn't valid. Check for stray spaces.";
  if (err.status === 403 && m.includes("not been used")) return "The Cloud Natural Language API isn't enabled on this key's project. Enable it in the Google Cloud console, then wait a minute.";
  if (err.status === 403 && m.includes("billing")) return "Billing isn't enabled on that Google Cloud project. The NLP API needs it even inside the free tier.";
  if (err.status === 403) return "That key is rejected or restricted. Check its API restrictions.";
  if (err.status === 429) return "Rate limited by Google. Wait a minute and run again — completed documents are kept.";
  return err.message || "Request failed.";
}

$("stop").onclick = () => { abort = true; $("status").textContent = "Stopping…"; };

$("run").onclick = async () => {
  const key = $("key").value.trim(), version = $("version").value;
  const docs = currentDocs();
  FLOOR = parseFloat($("floor").value) || 0.05;
  abort = false;
  DONE = []; ENTITIES = []; PROFILES = []; KEEP.clear();
  $("run").disabled = true; $("stop").hidden = false;
  $("prog").hidden = false; $("prog").max = docs.length; $("prog").value = 0;

  let done = 0, failed = 0, firstError = null;
  for (const doc of docs){
    if (abort) break;
    try {
      const r = await analyze(doc, key, version);
      const ents = (r.entities||[]).map(e => ({
        url: doc.url, entity: e.name, type: e.type,
        salience: e.salience ?? null,
        mentions: (e.mentions||[]).length,
        proper: (e.mentions||[]).filter(m=>m.type==="PROPER").length,
        mid: e.metadata?.mid || "", wiki: e.metadata?.wikipedia_url || "",
        _key: fkey(e.name), _why: ""
      }));
      DONE.push({doc, ents});
      ENTITIES.push(...ents);
    } catch(err){
      failed++; if (!firstError) firstError = err;
      if (err.status === 400 || err.status === 403){ abort = true; }
    }
    done++; $("prog").value = done;
    $("status").textContent = `${done}/${docs.length} processed${failed?` · ${failed} failed`:""}`;
  }

  $("stop").hidden = true; $("prog").hidden = true; $("run").disabled = false;
  if (firstError && !ENTITIES.length){ $("status").textContent = explainError(firstError); return; }
  $("status").textContent = firstError
    ? `Done with errors — ${explainError(firstError)}`
    : `Done. ${ENTITIES.length} entity mentions across ${DONE.length} document(s).`;
  update();
};

/* ---- page profile: one row per URL ---- */
function profile(doc, list, floor){
  const ents = list.slice().sort((a,b) => (b.salience ?? b.mentions/100) - (a.salience ?? a.mentions/100));
  const top = ents[0];
  const dominant = top && (top.salience === null ? top.mentions >= 2 : top.salience >= floor) ? top : null;
  const dn = dominant ? norm(dominant.entity) : "";
  const inField = v => dn && norm(v||"").includes(dn) ? "yes" : "no";
  return {
    url: doc.url,
    entity_count: list.length,
    dominant_entity: dominant ? dominant.entity : "",
    dominant_type: dominant ? dominant.type : "",
    dominant_salience: dominant && dominant.salience !== null ? dominant.salience : "",
    dominant_mid: dominant ? dominant.mid : "",
    has_dominant_entity: dominant ? "yes" : "no",
    dominant_in_title: inField(doc.title),
    dominant_in_h1: inField(doc.h1),
    dominant_in_meta: inField(doc.meta),
    intended_entity: doc.intended || "",
    intent_match: !doc.intended ? "" :
           (dominant && dn === norm(doc.intended)) ? "ok" : "MISMATCH",
    _mentions: dominant ? dominant.mentions : 0,
    _dom: dominant
  };
}

/* ---- the three filters, in order ---- */
function chromeShare(){
  let s = parseFloat(String($("share").value).replace(",", "."));
  if (!(s > 0)) s = 10;
  return Math.min(s, 100) / 100;
}

function applyFilters(){
  const useT = $("f-types").checked, useG = $("f-generic").checked, useC = $("f-chrome").checked;
  const stop = new Set($("stoplist").value.split(/[\n,]+/).map(fkey).filter(Boolean));

  // 1 and 2 are row-level checks.
  for (const e of ENTITIES){
    e._why = "";
    if (useT && (NOISE_TYPES.has(e.type) || !e._key || /^[\p{N}\s]+$/u.test(e._key))) e._why = "structural";
    else if (useG && stop.has(e._key)) e._why = "generic";
  }

  // 3 is site-level: pages an entity appears on, and whether it is ever a proper noun.
  CANDIDATES = [];
  const pageCount = DONE.length;
  const minPages = Math.max(3, Math.ceil(chromeShare() * pageCount));
  if (useC && pageCount >= MIN_CHROME_PAGES){
    const stats = new Map();
    for (const e of ENTITIES){
      if (e._why) continue;
      let s = stats.get(e._key);
      if (!s){ s = {key:e._key, name:e.entity, pages:new Set(), proper:0, mentions:0, types:new Set()}; stats.set(e._key, s); }
      s.pages.add(e.url); s.proper += e.proper; s.mentions += e.mentions; s.types.add(e.type);
    }
    CANDIDATES = [...stats.values()]
      .filter(s => s.pages.size >= minPages && s.proper === 0)
      .sort((a,b) => b.pages.size - a.pages.size || b.mentions - a.mentions);
    const removed = new Set(CANDIDATES.filter(c => !KEEP.has(c.key)).map(c => c.key));
    for (const e of ENTITIES) if (!e._why && removed.has(e._key)) e._why = "chrome";
  }

  const fromFiltered = $("f-dominant").checked;
  PROFILES = DONE.map(d => profile(d.doc, fromFiltered ? d.ents.filter(e => !e._why) : d.ents, FLOOR));
  return {pageCount, minPages, useC};
}

function update(){
  if (!DONE.length){ $("results").hidden = true; return; }
  const f = applyFilters();
  render();
  renderFilters(f);
  renderEntities();
}

/* ---- render ---- */
function render(){
  $("results").hidden = false;
  const noDom = PROFILES.filter(p => p.has_dominant_entity === "no").length;
  const withIntent = PROFILES.filter(p => p.intended_entity);
  const mismatch = withIntent.filter(p => p.intent_match === "MISMATCH").length;
  const withMid = ENTITIES.filter(e => e.mid).length;

  $("tiles").innerHTML = [
    ["Documents", PROFILES.length, "profiled", "var(--accent)"],
    ["Entity mentions", ENTITIES.length.toLocaleString(), `${new Set(ENTITIES.map(e=>e._key)).size.toLocaleString()} distinct · ${ENTITIES.filter(e=>!e._why).length.toLocaleString()} kept by the filters`, "var(--accent)"],
    ["No dominant entity", noDom, noDom ? "machines can't tell the subject" : "every page has a subject",
      noDom ? "var(--crit)" : "var(--good)"],
    withIntent.length
      ? ["Intent mismatch", mismatch, `of ${withIntent.length} with an intended entity`, mismatch ? "var(--crit)" : "var(--good)"]
      : ["Carrying a MID", `${Math.round(withMid/ENTITIES.length*100)}%`, "linked to a graph node", "var(--accent)"]
  ].map(([k,v,d,c]) => `<div class="tile" style="--lvl:${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const hasIntent = withIntent.length > 0;
  $("profiles").innerHTML = `<thead><tr>
      <th>URL</th><th>Dominant entity</th><th>Type</th><th class="n">Salience</th>
      <th class="n">Mentions</th><th class="n">Entities</th>${hasIntent?"<th>Intended</th><th>Verdict</th>":""}
    </tr></thead><tbody>${
    PROFILES.map(p => `<tr>
      <td class="url" title="${esc(p.url)}">${esc(p.url)}</td>
      <td>${p.dominant_entity ? esc(p.dominant_entity) : '<span class="flag">none</span>'}${
        p._dom && p._dom._why ? ` <span class="type noise" title="Removed by the ${WHY[p._dom._why]} filter">noise</span>` : ""}</td>
      <td>${p.dominant_type ? `<span class="type">${esc(p.dominant_type)}</span>` : ""}</td>
      <td class="n">${p.dominant_salience === "" ? "&mdash;" : Number(p.dominant_salience).toFixed(3)}</td>
      <td class="n">${p._mentions}</td><td class="n">${p.entity_count}</td>
      ${hasIntent ? `<td>${esc(p.intended_entity)}</td><td>${
        p.intent_match === "MISMATCH" ? '<span class="flag">mismatch</span>'
        : p.intent_match === "ok" ? '<span class="flag ok">ok</span>' : ""}</td>` : ""}
    </tr>`).join("")}</tbody>`;

}

function renderFilters({pageCount, minPages, useC}){
  const count = why => ENTITIES.filter(e => e._why === why).length;
  const fmt = n => n ? `−${n.toLocaleString()} mentions` : "none removed";
  $("c-types").textContent = $("f-types").checked ? fmt(count("structural")) : "off";
  $("c-generic").textContent = $("f-generic").checked ? fmt(count("generic")) : "off";
  $("c-chrome").textContent = !useC ? "off" : pageCount < MIN_CHROME_PAGES ? "needs a crawl" : fmt(count("chrome"));

  const pct = Math.round(chromeShare()*1000)/10;
  $("chrome-note").innerHTML = !useC ? "" :
    pageCount < MIN_CHROME_PAGES
      ? `Needs at least ${MIN_CHROME_PAGES} pages to mean anything. This run has ${pageCount}: upload your crawl to use it.`
      : CANDIDATES.length
        ? `<strong>${CANDIDATES.length}</strong> candidate(s) at ${pct}%, so on ${minPages}+ of your ${pageCount} pages.`
        : `Nothing caught at ${pct}% (${minPages}+ of ${pageCount} pages). If button labels survive in the entity table below, lower it.`;

  $("chrome-review").hidden = !CANDIDATES.length;
  if (CANDIDATES.length){
    const wrap = $("chrome-table").parentElement, top = wrap.scrollTop;
    $("chrome-table").innerHTML = `<thead><tr><th>Remove</th><th>Entity</th><th class="n">Pages</th>
        <th class="n">Share</th><th class="n">Mentions</th><th>Type</th></tr></thead><tbody>${
      CANDIDATES.map(c => `<tr>
        <td class="c"><input type="checkbox" data-key="${esc(c.key)}" ${KEEP.has(c.key)?"":"checked"} aria-label="Remove ${esc(c.name)}"></td>
        <td>${esc(c.name)}</td>
        <td class="n">${c.pages.size}</td>
        <td class="n">${(c.pages.size/pageCount*100).toFixed(1)}%</td>
        <td class="n">${c.mentions}</td>
        <td>${[...c.types].map(t => `<span class="type">${esc(t)}</span>`).join(" ")}</td>
      </tr>`).join("")}</tbody>`;
    wrap.scrollTop = top;
  }

  const kept = ENTITIES.filter(e => !e._why);
  const parts = Object.keys(WHY).map(k => [k, count(k)]).filter(([,n]) => n)
    .map(([k,n]) => `${WHY_PLURAL[k]} ${n.toLocaleString()}`);
  $("f-summary").innerHTML = `<strong>${kept.length.toLocaleString()} of ${ENTITIES.length.toLocaleString()} mentions kept</strong>
    (${new Set(kept.map(e=>e._key)).size.toLocaleString()} distinct entities).
    ${parts.length ? `Removed mentions: ${parts.join(" · ")}.` : "Nothing removed."}
    Check what was removed with <em>Removed by the filters</em> below before you trust the result.`;
}

function renderEntities(){
  const view = $("eview").value;
  const data = ENTITIES.filter(e => view === "all" || (view === "kept" ? !e._why : !!e._why));
  const {k, asc} = ESORT;
  data.sort((a,b) => {
    const x = a[k] ?? (k === "salience" ? -1 : ""), y = b[k] ?? (k === "salience" ? -1 : "");
    const r = typeof x === "number" && typeof y === "number" ? x-y : String(x).localeCompare(String(y));
    return asc ? r : -r;
  });
  const maxSal = Math.max(...data.map(e => e.salience ?? 0), 0.0001);
  const head = [["entity","Entity"],["type","Type"],["salience","Salience"],
                ["mentions","Mentions"],["proper","Proper"],["mid","MID"],["url","URL"]];
  if (view !== "kept") head.push(["_why","Removed by"]);
  $("entities").innerHTML = `<thead><tr>${head.map(([key,l],i)=>
      `<th data-k="${key}" class="${i>=2&&i<=4?'n':''}">${l}${key===k?(asc?" ↑":" ↓"):""}</th>`).join("")}</tr></thead>
    <tbody>${data.slice(0,600).map(e => `<tr>
      <td>${esc(e.entity)}</td>
      <td><span class="type">${esc(e.type)}</span></td>
      <td class="n">${e.salience===null?"&mdash;":
        `<span class="bar" style="width:${Math.max(2,(e.salience/maxSal)*46)}px"></span>${e.salience.toFixed(3)}`}</td>
      <td class="n">${e.mentions}</td><td class="n">${e.proper}</td>
      <td class="mono">${e.mid ? esc(e.mid) : '<span style="color:var(--muted)">&mdash;</span>'}</td>
      <td class="url" title="${esc(e.url)}">${esc(e.url)}</td>
      ${view !== "kept" ? `<td>${e._why ? esc(WHY[e._why]) : ""}</td>` : ""}
    </tr>`).join("")}</tbody>`;
  $("ehint").textContent = data.length > 600
    ? `Showing the first 600 of ${data.length.toLocaleString()} rows · click a column to sort`
    : `${data.length.toLocaleString()} rows · click a column to sort`;
}

/* ---- filter controls: re-filter locally, never re-call the API ---- */
$("entities").onclick = ev => {
  const th = ev.target.closest("th"); if (!th) return;
  const k = th.dataset.k;
  ESORT = {k, asc: ESORT.k === k ? !ESORT.asc : false};
  renderEntities();
};
["f-types","f-generic","f-chrome","f-dominant"].forEach(id => $(id).addEventListener("change", update));
let filterTimer;
["stoplist","share"].forEach(id => $(id).addEventListener("input", () => {
  clearTimeout(filterTimer); filterTimer = setTimeout(update, 300);
}));
$("eview").onchange = renderEntities;
$("chrome-table").addEventListener("change", ev => {
  const key = ev.target.dataset.key; if (key === undefined) return;
  ev.target.checked ? KEEP.delete(key) : KEEP.add(key);
  update();
});
$("stoplist").value = DEFAULT_STOP.join(", ");

/* ---- export ---- */
async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use)
    ? await claude.use("downloads").catch(()=>null) : null;
  if (api){
    try { await api.save({filename, data:text}); return "saved"; }
    catch(e){ return e && e.code === "declined" ? "declined" : "failed"; }
  }
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([text],{type:mime}));
  a.download=filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
  return "saved";
}
const toCSV = (rows, cols) => {
  const q = v => `"${String(v??"").replace(/"/g,'""')}"`;
  return [cols.map(q).join(",")].concat(
    rows.map(r => cols.map(c => q(r[c])).join(","))).join("\n");
};
$("dl-profiles").onclick = async () => {
  const r = await offerFile("page_entity_profiles.csv",
    toCSV(PROFILES, ["url","entity_count","dominant_entity","dominant_type","dominant_salience","dominant_mid","has_dominant_entity","dominant_in_title","dominant_in_h1","dominant_in_meta","intended_entity","intent_match"]), "text/csv");
  $("status").textContent = r==="saved" ? "Profiles exported." : "Export cancelled.";
};
$("dl-entities").onclick = async () => {
  const r = await offerFile("entity_mentions.csv",
    toCSV(ENTITIES, ["url","entity","type","salience","mentions","proper","mid","wiki"]), "text/csv");
  $("status").textContent = r==="saved" ? "Entities exported." : "Export cancelled.";
};
// Same columns as entity_mentions.csv, so every downstream tool reads it unchanged.
$("dl-filtered").onclick = async () => {
  const r = await offerFile("entity_mentions_filtered.csv",
    toCSV(ENTITIES.filter(e => !e._why), ["url","entity","type","salience","mentions","proper","mid","wiki"]), "text/csv");
  $("status").textContent = r==="saved" ? "Filtered entities exported." : "Export cancelled.";
};
// The record of what was filtered: one row per entity removed, plus chrome candidates kept.
$("dl-record").onclick = async () => {
  const pageCount = DONE.length, agg = new Map();
  for (const e of ENTITIES){
    if (!e._why) continue;
    const id = e._why + "|" + e._key;
    let a = agg.get(id);
    if (!a){ a = {entity:e.entity, filter:WHY[e._why], pages:new Set(), mentions:0, proper:0, decision:"remove"}; agg.set(id, a); }
    a.pages.add(e.url); a.mentions += e.mentions; a.proper += e.proper;
  }
  for (const c of CANDIDATES) if (KEEP.has(c.key))
    agg.set("kept|" + c.key, {entity:c.name, filter:WHY.chrome, pages:c.pages, mentions:c.mentions, proper:c.proper, decision:"keep"});
  const rows = [...agg.values()].map(a => ({...a, pages:a.pages.size,
    page_share:(a.pages.size/pageCount).toFixed(4)})).sort((a,b) => b.pages - a.pages);
  const settings = `structural=${$("f-types").checked?"on":"off"}; generic=${$("f-generic").checked?"on":"off"}; chrome=${$("f-chrome").checked?`${Math.round(chromeShare()*1000)/10}%`:"off"}; pages=${pageCount}`;
  rows.forEach(r => r.settings = settings);
  const res = await offerFile("filter_decisions.csv",
    toCSV(rows, ["entity","filter","decision","pages","page_share","mentions","proper","settings"]), "text/csv");
  $("status").textContent = res==="saved" ? "Filter record exported." : "Export cancelled.";
};

refresh();
