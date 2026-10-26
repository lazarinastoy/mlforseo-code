
const $ = id => document.getElementById(id);
const KG = "https://kgsearch.googleapis.com/v1/entities:search";
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const norm = s => String(s??"").toLowerCase().replace(/[^a-z0-9\s]/g," ").replace(/\s+/g," ").trim();
const toks = s => new Set(norm(s).split(" ").filter(Boolean));

/* NLP type -> the schema.org type the Knowledge Graph would use */
const TYPE_MAP = {PERSON:"Person", ORGANIZATION:"Organization", LOCATION:"Place",
  EVENT:"Event", WORK_OF_ART:"CreativeWork", CONSUMER_GOOD:"Product"};

let INPUT = [], RESULTS = [], MIDGROUPS = [], abort = false, filter = "all";

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
  return {head, dupes, rows:rows.filter(r=>r.some(v=>v!=="")).map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]??""])))};
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
  const f = e.target.files[0]; if(!f) return;
  let parsed; try { parsed = parseCSV(await f.text()); }
  catch { $("csvinfo").innerHTML = "<strong>That file could not be read as CSV.</strong>"; return; }
  const {head, rows, dupes} = parsed;
  if (!rows.length){ $("csvinfo").innerHTML = "<strong>That CSV has no data rows.</strong>"; return; }
  const eCol = pick(head,["entity","name","entity_name"]);
  const tCol = pick(head,["type","entity_type","nlp_type"]);
  const mCol = pick(head,["mid","kg_mid","metadata_mid"]);
  if (!eCol){
    $("csvinfo").innerHTML = `<strong>No entity column found.</strong> Looked for entity, name. Columns present: ${esc(head.slice(0,10).join(", "))}`;
    return;
  }
  const agg = new Map();
  for (const r of rows){
    const name = (r[eCol]||"").trim(); if (!name) continue;
    const k = norm(name); if (!k) continue;
    if (!agg.has(k)) agg.set(k, {entity:name, freq:0, types:{}, mids:{}});
    const a = agg.get(k); a.freq++;
    if (tCol && r[tCol]) a.types[r[tCol]] = (a.types[r[tCol]]||0)+1;
    if (mCol && r[mCol]) a.mids[r[mCol]] = (a.mids[r[mCol]]||0)+1;
  }
  INPUT = [...agg.values()].map(a => ({
    entity:a.entity, freq:a.freq,
    nlpType: Object.entries(a.types).sort((x,y)=>y[1]-x[1])[0]?.[0] || "",
    nlpMid:  Object.entries(a.mids ).sort((x,y)=>y[1]-x[1])[0]?.[0] || ""
  })).sort((a,b)=>b.freq-a.freq);
  $("list").value = INPUT.slice(0,2000).map(i=>i.entity).join("\n");
  $("csvinfo").innerHTML = `${dupes.length?`<strong>Duplicate column name(s): ${esc(dupes.join(", "))}</strong> — renamed. ` : ""}<strong>${INPUT.length}</strong> distinct entities${tCol?" · NLP types found":""}${mCol?" · MIDs found (over-linking detection enabled)":""}`;
  refresh();
};

$("list").addEventListener("input", () => {
  const lines = $("list").value.split("\n").map(s=>s.trim()).filter(Boolean);
  const known = new Map(INPUT.map(i=>[norm(i.entity), i]));
  INPUT = lines.map(l => known.get(norm(l)) || {entity:l, freq:1, nlpType:"", nlpMid:""});
  refresh();
});
$("key").addEventListener("input", refresh);

function refresh(){
  const cap = parseInt($("cap").value,10) || 500;
  $("run").disabled = !INPUT.length || !$("key").value.trim();
  $("status").textContent = INPUT.length
    ? `${Math.min(INPUT.length,cap)} lookup(s) queued${INPUT.length>cap?` (of ${INPUT.length}; raise the cap to include the rest)`:""}.`
    : "Add a key and some entities to begin.";
}

async function lookup(name, key){
  const url = `${KG}?query=${encodeURIComponent(name)}&limit=5&languages=en&key=${encodeURIComponent(key)}`;
  const res = await fetch(url);
  if (!res.ok){
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.error?.message || msg; } catch {}
    const e = new Error(msg); e.status = res.status; throw e;
  }
  return res.json();
}
function explainError(err){
  const m = (err.message||"").toLowerCase();
  if (err.status === 403 && m.includes("not been used")) return "The Knowledge Graph Search API isn't enabled on this key's project. Enable it in the Google Cloud console, then wait a minute.";
  if (err.status === 403) return "That key is rejected or restricted for this API.";
  if (err.status === 400) return "That API key isn't valid. Check for stray spaces.";
  if (err.status === 429) return "Rate limited. Wait a minute and run again — completed lookups are kept.";
  return err.message || "Request failed.";
}

$("stop").onclick = () => { abort = true; $("status").textContent = "Stopping…"; };

$("run").onclick = async () => {
  const key = $("key").value.trim();
  const floor = parseFloat($("floor").value) || 20;
  const cap = parseInt($("cap").value,10) || 500;
  const queue = INPUT.slice(0, cap);
  abort = false; RESULTS = [];
  $("run").disabled = true; $("stop").hidden = false;
  $("prog").hidden = false; $("prog").max = queue.length; $("prog").value = 0;

  let done = 0, failed = 0, firstError = null;
  const CONCURRENCY = 5;
  let cursor = 0;
  async function worker(){
    while (cursor < queue.length && !abort){
      const item = queue[cursor++];
      try {
        const body = await lookup(item.entity, key);
        const cands = (body.itemListElement||[]).map(it => {
          const r = it.result||{};
          return {mid:r["@id"]||"", name:r.name||"",
                  types:(r["@type"]||[]).filter(t=>t!=="Thing").join(", "),
                  desc:r.description||"", score:it.resultScore||0};
        }).sort((a,b)=>b.score-a.score);
        const top = cands[0];
        let status = "unmatched";
        if (top && top.score >= floor){
          status = (cands[1] && cands[1].score >= top.score*0.6) ? "ambiguous" : "matched";
        }
        const expected = TYPE_MAP[item.nlpType];
        const conflict = status==="matched" && expected && top.types && !top.types.includes(expected);
        RESULTS.push({...item, status, conflict,
          kgMid:top?.mid||"", kgName:top?.name||"", kgTypes:top?.types||"",
          kgDesc:top?.desc||"", score:top?top.score:0, candidates:cands.length,
          alts:cands.slice(1,3).map(c=>`${c.name} (${Math.round(c.score)})`).join(" · ")});
      } catch(err){
        failed++; if(!firstError) firstError = err;
        if (err.status===400 || err.status===403) abort = true;
      }
      done++; $("prog").value = done;
      $("status").textContent = `${done}/${queue.length} reconciled${failed?` · ${failed} failed`:""}`;
    }
  }
  await Promise.all(Array.from({length:CONCURRENCY}, worker));

  $("stop").hidden = true; $("prog").hidden = true; $("run").disabled = false;
  if (firstError && !RESULTS.length){ $("status").textContent = explainError(firstError); return; }
  $("status").textContent = firstError ? `Done with errors — ${explainError(firstError)}`
                                       : `Done. ${RESULTS.length} entities reconciled.`;
  buildOverlink();
  render();
};

/* over-linking: entities the NLP API gave the SAME MID but which read differently */
function buildOverlink(){
  const byMid = new Map();
  for (const r of INPUT){
    if (!r.nlpMid) continue;
    if (!byMid.has(r.nlpMid)) byMid.set(r.nlpMid, []);
    byMid.get(r.nlpMid).push(r);
  }
  MIDGROUPS = [];
  for (const [mid, members] of byMid){
    if (members.length < 2) continue;
    const canonical = members.slice().sort((a,b)=>b.freq-a.freq)[0];
    const ct = toks(canonical.entity);
    const divergent = members.filter(m => m!==canonical && [...toks(m.entity)].filter(t=>!ct.has(t)).length >= 2);
    if (!divergent.length) continue;
    const kg = RESULTS.find(r => r.kgMid && r.kgMid.replace("kg:","") === mid);
    MIDGROUPS.push({mid, canonical:canonical.entity, canonicalFreq:canonical.freq,
      resolvesTo: kg ? `${kg.kgName}${kg.kgDesc?` — ${kg.kgDesc}`:""}` : "",
      members: members.map(m=>`${m.entity} (${m.freq})`).join(" | "),
      divergent: divergent.map(m=>m.entity).join(" | "), count: members.length});
  }
  MIDGROUPS.sort((a,b)=>b.count-a.count);
}

function render(){
  if (!RESULTS.length){ $("results").hidden = true; return; }
  $("results").hidden = false;
  const n = RESULTS.length;
  const c = s => RESULTS.filter(r=>r.status===s).length;
  const conflicts = RESULTS.filter(r=>r.conflict).length;
  $("tiles").innerHTML = [
    ["Reconciled", n, "entities looked up", "var(--accent)"],
    ["Matched", `${c("matched")}`, `${Math.round(c("matched")/n*100)}% of the list`, "var(--good)"],
    ["Ambiguous", `${c("ambiguous")}`, "more than one plausible node", "var(--warn)"],
    ["Unmatched", `${c("unmatched")}`, "no node in the graph", "var(--crit)"],
    ["Type conflicts", conflicts, "NLP and KG disagree", conflicts?"var(--crit)":"var(--good)"]
  ].map(([k,v,d,col])=>`<div class="tile" style="--lvl:${col}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const counts = {all:n, matched:c("matched"), ambiguous:c("ambiguous"), unmatched:c("unmatched"), conflict:conflicts};
  $("filters").innerHTML = Object.entries(counts).map(([k,v])=>
    `<button data-f="${k}" aria-pressed="${filter===k}">${k[0].toUpperCase()+k.slice(1)} (${v})</button>`).join("");
  $("filters").querySelectorAll("button").forEach(b => b.onclick = () => { filter=b.dataset.f; render(); });

  const rows = RESULTS.filter(r => filter==="all" ? true : filter==="conflict" ? r.conflict : r.status===filter)
    .sort((a,b)=>b.freq-a.freq);
  $("table").innerHTML = `<thead><tr>
      <th>Entity</th><th class="n">Uses</th><th>Status</th><th>Matched node</th>
      <th>KG types</th><th class="n">Score</th><th>MID</th>
    </tr></thead><tbody>${rows.slice(0,800).map(r=>`<tr>
      <td><strong>${esc(r.entity)}</strong>${r.nlpType?`<div class="cands">NLP: ${esc(r.nlpType)}</div>`:""}</td>
      <td class="n">${r.freq}</td>
      <td><span class="status ${r.status}">${r.status}</span>${r.conflict?'<div><span class="chip">type conflict</span></div>':""}</td>
      <td>${r.kgName?esc(r.kgName):'<span style="color:var(--muted)">&mdash;</span>'}
        ${r.kgDesc?`<div class="desc">${esc(r.kgDesc)}</div>`:""}
        ${r.status==="ambiguous"&&r.alts?`<div class="cands">also: ${esc(r.alts)}</div>`:""}</td>
      <td class="desc">${esc(r.kgTypes)||"&mdash;"}</td>
      <td class="n">${r.score?Math.round(r.score):"&mdash;"}</td>
      <td class="mono">${r.kgMid?esc(r.kgMid):"&mdash;"}</td>
    </tr>`).join("")}</tbody>`;

  if (MIDGROUPS.length){
    $("overlinkwrap").hidden = false;
    $("overlink").innerHTML = `<thead><tr>
        <th>MID assigned by the NLP API</th><th>Which resolves to</th>
        <th>Dominant form</th><th>Also given this MID</th><th class="n">Forms</th>
      </tr></thead><tbody>${MIDGROUPS.slice(0,120).map(g=>`<tr>
        <td class="mono">${esc(g.mid)}</td>
        <td>${g.resolvesTo?esc(g.resolvesTo):'<span style="color:var(--muted)">not resolvable</span>'}</td>
        <td><strong>${esc(g.canonical)}</strong> <span style="color:var(--muted)">(${g.canonicalFreq})</span></td>
        <td class="desc">${esc(g.divergent)}</td>
        <td class="n">${g.count}</td>
      </tr>`).join("")}</tbody>`;
  } else $("overlinkwrap").hidden = true;
}

async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(()=>null) : null;
  if (api){ try { await api.save({filename, data:text}); return "saved"; }
    catch(e){ return e && e.code==="declined" ? "declined" : "failed"; } }
  const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([text],{type:mime}));
  a.download=filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href),2000); return "saved";
}
$("dl").onclick = async () => {
  // Column names match freeze/derive.py exactly, so the Scorecard (and any
  // downstream tool) accepts output from this tool or the Python pipeline
  // interchangeably. Renaming these silently breaks the chain.
  const cols = ["entity","entity_norm","corpus_frequency","nlp_type","status","flag",
                "kg_mid","kg_name","kg_types","kg_description","kg_result_score","candidate_count"];
  const q = v => `"${String(v??"").replace(/"/g,'""')}"`;
  const row = r => ({
    entity:r.entity, entity_norm:norm(r.entity), corpus_frequency:r.freq,
    nlp_type:r.nlpType, status:r.status, flag:r.conflict ? "type_conflict" : "",
    kg_mid:r.kgMid, kg_name:r.kgName, kg_types:r.kgTypes, kg_description:r.kgDesc,
    kg_result_score:r.score ? Math.round(r.score*100)/100 : 0, candidate_count:r.candidates
  });
  const csv = [cols.map(q).join(",")]
    .concat(RESULTS.map(r=>{ const o=row(r); return cols.map(c=>q(o[c])).join(","); })).join("\n");
  const res = await offerFile("kg_reconciliation.csv", csv, "text/csv");
  $("status").textContent = res==="saved" ? "Exported." : "Export cancelled.";
};
refresh();
