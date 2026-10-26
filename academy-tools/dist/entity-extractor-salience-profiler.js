
const $ = id => document.getElementById(id);
const NLP = v => `https://language.googleapis.com/${v}/documents:analyzeEntities`;
const MAX_CHARS = 60000, FREE_UNITS = 5000, PRICE = 0.0010;
const units = t => t ? Math.max(1, Math.ceil(t.length/1000)) : 0;
const esc = s => String(s??"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const norm = s => String(s??"").toLowerCase().replace(/[^a-z0-9\s]/g," ").replace(/\s+/g," ").trim();

let DOCS = [], ENTITIES = [], PROFILES = [], abort = false;

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
  const docs = currentDocs(), floor = parseFloat($("floor").value) || 0.05;
  abort = false;
  ENTITIES = []; PROFILES = [];
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
        mid: e.metadata?.mid || "", wiki: e.metadata?.wikipedia_url || ""
      }));
      ENTITIES.push(...ents);
      ents.sort((a,b) => (b.salience ?? b.mentions/100) - (a.salience ?? a.mentions/100));
      const top = ents[0];
      const dominant = top && (top.salience === null ? top.mentions >= 2 : top.salience >= floor) ? top : null;
      const dn = dominant ? norm(dominant.entity) : "";
      const inField = v => dn && norm(v||"").includes(dn) ? "yes" : "no";
      PROFILES.push({
        url: doc.url,
        entity_count: ents.length,
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
        _mentions: dominant ? dominant.mentions : 0
      });
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
    : `Done. ${ENTITIES.length} entity mentions across ${PROFILES.length} document(s).`;
  render(floor);
};

/* ---- render ---- */
function render(floor){
  if (!PROFILES.length){ $("results").hidden = true; return; }
  $("results").hidden = false;
  const noDom = PROFILES.filter(p => p.has_dominant_entity === "no").length;
  const withIntent = PROFILES.filter(p => p.intended_entity);
  const mismatch = withIntent.filter(p => p.intent_match === "MISMATCH").length;
  const withMid = ENTITIES.filter(e => e.mid).length;

  $("tiles").innerHTML = [
    ["Documents", PROFILES.length, "profiled", "var(--accent)"],
    ["Entity mentions", ENTITIES.length.toLocaleString(), `${new Set(ENTITIES.map(e=>norm(e.entity))).size} distinct`, "var(--accent)"],
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
      <td>${p.dominant_entity ? esc(p.dominant_entity) : '<span class="flag">none</span>'}</td>
      <td>${p.dominant_type ? `<span class="type">${esc(p.dominant_type)}</span>` : ""}</td>
      <td class="n">${p.dominant_salience === "" ? "&mdash;" : Number(p.dominant_salience).toFixed(3)}</td>
      <td class="n">${p._mentions}</td><td class="n">${p.entity_count}</td>
      ${hasIntent ? `<td>${esc(p.intended_entity)}</td><td>${
        p.intent_match === "MISMATCH" ? '<span class="flag">mismatch</span>'
        : p.intent_match === "ok" ? '<span class="flag ok">ok</span>' : ""}</td>` : ""}
    </tr>`).join("")}</tbody>`;

  const maxSal = Math.max(...ENTITIES.map(e => e.salience ?? 0), 0.0001);
  const rows = ENTITIES.slice().sort((a,b)=>(b.salience??0)-(a.salience??0));
  const head = [["entity","Entity"],["type","Type"],["salience","Salience"],
                ["mentions","Mentions"],["proper","Proper"],["mid","MID"],["url","URL"]];
  const draw = data => `<thead><tr>${head.map(([k,l],i)=>
      `<th data-k="${k}" class="${i>=2&&i<=4?'n':''}">${l}</th>`).join("")}</tr></thead>
    <tbody>${data.slice(0,600).map(e => `<tr>
      <td>${esc(e.entity)}</td>
      <td><span class="type">${esc(e.type)}</span></td>
      <td class="n">${e.salience===null?"&mdash;":
        `<span class="bar" style="width:${Math.max(2,(e.salience/maxSal)*46)}px"></span>${e.salience.toFixed(3)}`}</td>
      <td class="n">${e.mentions}</td><td class="n">${e.proper}</td>
      <td class="mono">${e.mid ? esc(e.mid) : '<span style="color:var(--muted)">&mdash;</span>'}</td>
      <td class="url" title="${esc(e.url)}">${esc(e.url)}</td>
    </tr>`).join("")}</tbody>`;
  $("entities").innerHTML = draw(rows);
  let dir = {};
  $("entities").querySelectorAll("th").forEach(th => th.onclick = () => {
    const k = th.dataset.k; dir[k] = !dir[k];
    rows.sort((a,b) => {
      const x=a[k]??"", y=b[k]??"";
      const r = typeof x === "number" && typeof y === "number" ? x-y : String(x).localeCompare(String(y));
      return dir[k] ? r : -r;
    });
    $("entities").innerHTML = draw(rows);
    $("entities").querySelectorAll("th").forEach(t2 => t2.onclick = th.onclick);
  });
}

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

refresh();
