
const $ = id => document.getElementById(id);
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* ---- normalisation. This IS the tool. ---- */
const STOP = new Set(["the","a","an","of","for","and","or","to","in","on","with","your","you","this","that","is","are","we","our","it"]);
function normalise(name){
  let s = String(name??"").toLowerCase();
  s = s.replace(/[‘’“”]/g, "'");
  s = s.replace(/^(the|a|an)\s+/,"");
  s = s.replace(/'s\b/g,"");
  s = s.replace(/[^a-z0-9&\s-]/g," ");
  s = s.replace(/[-\s]+/g," ").trim();
  // Light singularisation: plural forms of one entity are one entity.
  // Order matters. A naive trailing-s rule turns "analysis" into "analysi"
  // and "analyses" into "analys" — neither collapses and both are wrong.
  s = s.split(" ").map(w => {
    if (w.length <= 3) return w;
    if (/yses$/.test(w)) return w.slice(0,-4) + "ysis";        // analyses -> analysis
    if (/(?:sis|xis|us|ss|is)$/.test(w)) return w;             // analysis, axis, status, class
    if (/ies$/.test(w)) return w.slice(0,-3) + "y";            // categories -> category
    if (/(?:ses|xes|zes|ches|shes)$/.test(w)) return w.slice(0,-2); // boxes -> box
    if (/s$/.test(w)) return w.slice(0,-1);                    // SEOs -> seo
    return w;
  }).join(" ");
  return s;
}
const NOISE_TYPES = new Set(["NUMBER","DATE","PRICE","PHONE_NUMBER","ADDRESS"]);

const SLOTS = [
  {id:"you",   label:"Your site", you:true,  name:"Your site"},
  {id:"comp1", label:"Competitor 1", name:"Competitor 1"},
  {id:"comp2", label:"Competitor 2", name:"Competitor 2"},
  {id:"comp3", label:"Competitor 3", name:"Competitor 3"}
];
const DATA = {};
let ROWS = [], filter = "all", NORMSTAT = null;

$("slots").innerHTML = SLOTS.map(s => `
  <div class="slot ${s.you?"you":""}">
    <div class="tag">${s.you?"Your corpus (required)":"Competitor (optional)"}</div>
    <input type="text" id="name-${s.id}" value="${esc(s.name)}" aria-label="Label for ${esc(s.label)}">
    <label class="file">Choose CSV<input type="file" id="file-${s.id}" accept=".csv"></label>
    <div class="state" id="state-${s.id}">No file loaded.</div>
  </div>`).join("");

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

SLOTS.forEach(s => {
  $(`file-${s.id}`).onchange = async e => {
    const f = e.target.files[0]; if(!f) return;
    const st = $(`state-${s.id}`);
    let parsed; try { parsed = parseCSV(await f.text()); }
    catch { st.innerHTML = "<b>Could not read that file as CSV.</b>"; delete DATA[s.id]; refresh(); return; }
    const {head, rows, dupes} = parsed;
    if (!rows.length){ st.innerHTML = "<b>That CSV has no data rows.</b>"; delete DATA[s.id]; refresh(); return; }
    const eCol = pick(head,["entity","name","entity_name"]);
    const uCol = pick(head,["url","address","page"]);
    const sCol = pick(head,["salience"]);
    const tCol = pick(head,["type","entity_type"]);
    if (!eCol){
      st.innerHTML = `<b>No entity column.</b> Looked for entity, name. Found: ${esc(head.slice(0,6).join(", "))}`;
      delete DATA[s.id]; refresh(); return;
    }
    const agg = new Map(); let raw = 0, dropped = 0, badSal = 0;
    for (const r of rows){
      const name = (r[eCol]||"").trim(); if(!name) continue;
      if (tCol && NOISE_TYPES.has(r[tCol])){ dropped++; continue; }
      const k = normalise(name); if(!k || k.length<3 || STOP.has(k)){ dropped++; continue; }
      raw++;
      if(!agg.has(k)) agg.set(k,{key:k, forms:new Map(), urls:new Set(), sal:[]});
      const a = agg.get(k);
      a.forms.set(name,(a.forms.get(name)||0)+1);
      if (uCol && r[uCol]) a.urls.add(r[uCol]);
      const sv = sCol ? parseFloat(r[sCol]) : NaN;
      // salience is a 0-1 proportion; anything outside that is a bad file,
      // not a signal. Drop it rather than render a nonsense heat cell.
      if (!isNaN(sv) && sv >= 0 && sv <= 1) a.sal.push(sv);
      else if (!isNaN(sv)) badSal++;
    }
    DATA[s.id] = {
      name: $(`name-${s.id}`).value.trim() || s.name,
      entities: agg, rawMentions: raw, dropped,
      surfaceForms: [...agg.values()].reduce((n,a)=>n+a.forms.size,0)
    };
    st.innerHTML = `${dupes.length?`<b>Duplicate column(s) renamed: ${esc(dupes.join(", "))}</b> · ` : ""}<b>${agg.size.toLocaleString()}</b> entities from ${raw.toLocaleString()} mentions`
      + (dropped?` · ${dropped.toLocaleString()} filtered as noise`:"")
      + (badSal?` · ${badSal.toLocaleString()} salience value(s) outside 0–1 ignored`:"")
      + (sCol?"":" · no salience column, using page counts");
    refresh();
  };
  $(`name-${s.id}`).addEventListener("input", () => {
    if (DATA[s.id]) DATA[s.id].name = $(`name-${s.id}`).value.trim() || s.name;
  });
});

function refresh(){
  const comps = SLOTS.filter(s=>!s.you && DATA[s.id]).length;
  $("run").disabled = !DATA.you || !comps;
  $("status").textContent = !DATA.you ? "Load your own corpus."
    : !comps ? "Load at least one competitor." : `Ready — you plus ${comps} competitor(s).`;
}

$("run").onclick = () => {
  const active = SLOTS.filter(s => DATA[s.id]);
  const you = DATA.you, comps = active.filter(s=>!s.you);

  const all = new Set();
  active.forEach(s => DATA[s.id].entities.forEach((_,k)=>all.add(k)));

  const stat = active.map(s => `<strong>${esc(DATA[s.id].name)}</strong>: ${DATA[s.id].surfaceForms.toLocaleString()} surface forms collapsed to ${DATA[s.id].entities.size.toLocaleString()} entities`);
  NORMSTAT = stat;

  ROWS = [...all].map(key => {
    const cells = {};
    active.forEach(s => {
      const e = DATA[s.id].entities.get(key);
      cells[s.id] = e ? {pages:e.urls.size||[...e.forms.values()].reduce((a,b)=>a+b,0),
                         sal: e.sal.length ? e.sal.reduce((a,b)=>a+b,0)/e.sal.length : null,
                         forms:[...e.forms.keys()]} : null;
    });
    const mine = cells.you, theirs = comps.filter(s=>cells[s.id]);
    let verdict;
    if (!mine && theirs.length) verdict = "missing";
    else if (mine && !theirs.length) verdict = "unique";
    else if (mine && theirs.length){
      const myW = (mine.sal ?? 0) || mine.pages/100;
      const bestW = Math.max(...theirs.map(s => (cells[s.id].sal ?? 0) || cells[s.id].pages/100));
      verdict = (bestW > myW * 2) ? "thin" : "shared";
    } else verdict = "shared";
    const label = (mine?.forms?.[0]) || theirs.map(s=>cells[s.id].forms[0])[0] || key;
    const compCount = theirs.length;
    const compWeight = theirs.reduce((a,s)=>a+((cells[s.id].sal ?? 0)||cells[s.id].pages/100),0);
    return {key, label, cells, verdict, compCount, compWeight,
            mineWeight: mine ? ((mine.sal ?? 0)||mine.pages/100) : 0,
            allForms: [...new Set(active.flatMap(s=>cells[s.id]?cells[s.id].forms:[]))]};
  });

  const rank = {missing:0, thin:1, shared:2, unique:3};
  ROWS.sort((a,b)=> rank[a.verdict]-rank[b.verdict] || b.compCount-a.compCount || b.compWeight-a.compWeight);
  render(active, comps);
};

function render(active, comps){
  $("results").hidden = false;
  const n = ROWS.length;
  const count = v => ROWS.filter(r=>r.verdict===v).length;
  $("tiles").innerHTML = [
    ["Entities compared", n.toLocaleString(), "after normalisation", "var(--accent)"],
    ["Missing", count("missing"), "competitors have, you don't", count("missing")?"var(--crit)":"var(--good)"],
    ["Thin", count("thin"), "you have, but far weaker", "var(--warn)"],
    ["Shared", count("shared"), "comparable coverage", "var(--good)"],
    ["Unique to you", count("unique"), "yours alone", "var(--accent)"]
  ].map(([k,v,d,c])=>`<div class="tile" style="--lvl:${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  $("normnote").innerHTML = `<strong>Normalisation applied before comparison.</strong> ${NORMSTAT.join(" &middot; ")}. Case, punctuation, leading articles, possessives and simple plurals are collapsed, and structural types (numbers, dates, prices) are dropped. Without this step the same entity appears as several different rows and the matrix is meaningless.`;

  const counts = {all:n, missing:count("missing"), thin:count("thin"), shared:count("shared"), unique:count("unique")};
  $("filters").innerHTML = Object.entries(counts).map(([k,v])=>
    `<button data-f="${k}" aria-pressed="${filter===k}">${k[0].toUpperCase()+k.slice(1)} (${v})</button>`).join("");
  $("filters").querySelectorAll("button").forEach(b=>b.onclick=()=>{filter=b.dataset.f; render(active,comps);});

  const maxW = Math.max(...ROWS.flatMap(r=>active.map(s=>r.cells[s.id]?((r.cells[s.id].sal??0)||r.cells[s.id].pages/100):0)),0.0001);
  const rows = ROWS.filter(r=>filter==="all"||r.verdict===filter).slice(0,500);

  $("matrix").innerHTML = `<thead><tr>
      <th>Entity</th>
      ${active.map(s=>`<th class="site">${esc(DATA[s.id].name)}</th>`).join("")}
      <th>Verdict</th></tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td class="name">${esc(r.label)}
        ${r.allForms.length>1?`<span class="forms">${esc(r.allForms.slice(0,3).join(" · "))}${r.allForms.length>3?" …":""}</span>`:""}</td>
      ${active.map(s=>{
        const c = r.cells[s.id];
        if (!c) return `<td class="cell empty">&mdash;</td>`;
        const w = ((c.sal ?? 0)||c.pages/100)/maxW;
        return `<td class="cell" style="background:rgba(var(--heat),${(0.10+w*0.75).toFixed(3)})">
          ${c.pages}${c.sal!==null?`<br><span style="font-size:11px;opacity:.75">${c.sal.toFixed(3)}</span>`:""}</td>`;
      }).join("")}
      <td class="verdict"><span class="v-tag ${r.verdict}">${r.verdict}</span></td>
    </tr>`).join("")}</tbody>`;
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
  const active = SLOTS.filter(s=>DATA[s.id]);
  const q = v => `"${String(v??"").replace(/"/g,'""')}"`;
  const head = ["entity","normalised","verdict","competitors_with_it"]
    .concat(active.flatMap(s=>[`${DATA[s.id].name} pages`, `${DATA[s.id].name} salience`]));
  const lines = [head.map(q).join(",")].concat(ROWS.map(r =>
    [r.label, r.key, r.verdict, r.compCount].concat(
      active.flatMap(s=>{ const c=r.cells[s.id];
        return [c?c.pages:"", c&&c.sal!==null?c.sal.toFixed(4):""]; })
    ).map(q).join(",")));
  const res = await offerFile("entity_gap_matrix.csv", lines.join("\n"), "text/csv");
  $("status").textContent = res==="saved" ? "Exported." : "Export cancelled.";
};
refresh();
