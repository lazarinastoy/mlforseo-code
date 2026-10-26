
const LEVEL = [
  {name:"critical", color:"var(--crit)"},
  {name:"weak",     color:"var(--crit)"},
  {name:"partial",  color:"var(--warn)"},
  {name:"solid",    color:"var(--good)"}
];
const pct = (a,b) => b ? Math.round(a/b*100) : 0;
const $ = id => document.getElementById(id);

/* ---- the rubric. This is Lesson 1.3, expressed as code. ---- */
const DIMENSIONS = [
  {
    key:"clarity", name:"Clarity",
    question:"Can a machine tell what this page is about?",
    score(d){
      const t = pct(d.clarity.in_title, d.pages);
      if (t >= 80 && pct(d.clarity.weak,d.pages) < 10) return 3;
      if (t >= 60) return 2;
      if (t >= 35) return 1;
      return 0;
    },
    why(d){
      return `Only ${pct(d.clarity.in_meta,d.pages)}% of pages name their main entity in the meta description, and ${pct(d.clarity.weak,d.pages)}% have a subject too diffuse to read confidently.`;
    },
    metrics(d){ const n=d.pages; return [
      ["Dominant entity in title", `${d.clarity.in_title}/${n}`, pct(d.clarity.in_title,n), 80,60],
      ["Dominant entity in H1", `${d.clarity.in_h1}/${n}`, pct(d.clarity.in_h1,n), 80,60],
      ["Dominant entity in meta description", `${d.clarity.in_meta}/${n}`, pct(d.clarity.in_meta,n), 80,60],
      ["No dominant entity at all", `${d.clarity.no_dominant}`, 100-pct(d.clarity.no_dominant,n), 97,92],
      ["Weak subject (salience under 0.12)", `${d.clarity.weak}`, 100-pct(d.clarity.weak,n), 90,80]
    ];}
  },
  {
    key:"coverage", name:"Coverage",
    question:"Are the right entities and attributes present at all?",
    score(d){
      const thin = pct(d.coverage.thin, d.coverage.crawled);
      if (thin < 5) return 3; if (thin < 15) return 2; if (thin < 30) return 1; return 0;
    },
    why(d){
      return `${d.coverage.thin} of ${d.coverage.crawled} crawled pages hold under 400 characters. Thin pages cannot carry entity meaning, and they dilute every sitewide signal.`;
    },
    metrics(d){ const c=d.coverage; return [
      ["Pages under 400 characters", `${c.thin}/${c.crawled}`, 100-pct(c.thin,c.crawled), 95,85],
      ["Duplicate-content groups", `${c.dup_groups}`, c.dup_groups<10?100:40, 90,60],
      ["URLs sharing identical content", `${c.dup_urls}`, 100-pct(c.dup_urls,c.crawled), 95,85]
    ];}
  },
  {
    key:"consistency", name:"Consistency",
    question:"Is each entity named the same way everywhere?",
    score(d){
      const high = (d.consistency.by_type.mid_variant||0);
      const per100 = high / d.pages * 100;
      if (d.consistency.brand_forms <= 1 && per100 < 2) return 3;
      if (d.consistency.brand_forms <= 2 && per100 < 8) return 2;
      if (per100 < 20) return 1;
      return 0;
    },
    why(d){
      return `The brand appears as ${d.consistency.brand_forms} surface forms and is typed ${d.consistency.brand_types} different ways by the same NLP model. Machines cannot merge what you do not name consistently.`;
    },
    metrics(d){ const c=d.consistency, t=c.by_type||{}; return [
      ["Brand surface forms", `${c.brand_forms}`, c.brand_forms<=1?100:30, 95,70],
      ["Brand entity types assigned", `${c.brand_types}`, c.brand_types<=1?100:20, 95,70],
      ["High-confidence variant clusters", `${t.mid_variant||0}`, 100-Math.min(100,(t.mid_variant||0)/d.pages*100*5), 90,70],
      ["Suspected entity over-linking", `${t.mid_overlink_review||0}`, 100-Math.min(100,(t.mid_overlink_review||0)*2), 90,70]
    ];}
  },
  {
    key:"connection", name:"Connection",
    question:"Is it linked to a known node in the graph?",
    score(d){
      const c=d.connection;
      const matched = pct(c.matched, c.queried);
      if (c.brand_status==="matched" && matched>=60) return 3;
      if (c.brand_status==="matched") return 2;
      if (matched >= 40) return 1;
      return 0;
    },
    why(d){
      return `The brand entity has no Knowledge Graph node, and only ${pct(d.connection.mentions_with_mid,d.connection.mentions)}% of entity mentions carry a MID. Google can know your topic without connecting it to you.`;
    },
    metrics(d){ const c=d.connection; return [
      ["Brand reconciled to the Knowledge Graph", c.brand_status, c.brand_status==="matched"?100:0, 99,50],
      ["Entities matched", `${c.matched}/${c.queried}`, pct(c.matched,c.queried), 60,40],
      ["Entities ambiguous", `${c.ambiguous}`, 100-pct(c.ambiguous,c.queried), 90,80],
      ["Mentions carrying a MID", `${pct(c.mentions_with_mid,c.mentions)}%`, pct(c.mentions_with_mid,c.mentions)*4, 60,30],
      ["NLP / KG type conflicts", `${c.type_conflicts}`, 100-Math.min(100,c.type_conflicts/2), 90,70]
    ];}
  },
  {
    key:"corroboration", name:"Corroboration",
    question:"Does the rest of the web agree you exist?",
    score(d){
      const c=d.corroboration;
      if (c.llm_parametric && c.kg_results) return 3;
      if (c.kg_results || c.ai_mentions > 100) return 2;
      if (c.ai_mentions > 0) return 1;
      return 0;
    },
    why(d){
      return `Asked cold, language models hold nothing about the brand in their weights. Retrieval-based AI search does surface it ${d.corroboration.ai_mentions} times &mdash; a different thing, and a thinner one.`;
    },
    metrics(d){ const c=d.corroboration; return [
      ["Recognised in model weights (no search)", c.llm_parametric?"yes":"no", c.llm_parametric?100:0, 99,50],
      ["Knowledge Graph search results", `${c.kg_results}`, c.kg_results?100:0, 99,50],
      ["AI-search mentions", `${c.ai_mentions}`, Math.min(100,c.ai_mentions*3), 70,30],
      ["…via Google", `${c.ai_google}`, Math.min(100,c.ai_google*4), 70,30],
      ["…via ChatGPT", `${c.ai_chatgpt}`, Math.min(100,c.ai_chatgpt*8), 70,30]
    ];}
  }
];

/* ---- fixes, keyed to the six remediation patterns ---- */
function buildFixes(d, scores){
  const f = [];
  const n = d.pages;
  if (pct(d.clarity.in_meta,n) < 60) f.push({
    t:"Name the page's main entity in its meta description",
    p:`${n - d.clarity.in_meta} pages omit their own dominant entity from the snippet Google displays. This is the cheapest Clarity gain available.`,
    tags:["Entity-first structure","Clarity"], effort:"Low", impact:9,
    n:`${n - d.clarity.in_meta} pages`});
  if (d.connection.brand_status !== "matched") f.push({
    t:"Establish a Knowledge Graph node for the brand entity",
    p:"The brand returns zero Knowledge Graph results. Until a node exists, every other entity signal points at something machines cannot resolve.",
    tags:["Corroboration","Connection"], effort:"High", impact:10, n:"brand-wide"});
  if (d.consistency.brand_forms > 1) f.push({
    t:"Pick one canonical brand form and enforce it",
    p:`The brand appears as ${d.consistency.brand_forms} surface forms and is typed ${d.consistency.brand_types} ways. Choose one, use it in title, H1, schema and body copy.`,
    tags:["Canonical naming","Consistency"], effort:"Medium", impact:9, n:"sitewide"});
  if ((d.consistency.by_type||{}).mid_overlink_review) f.push({
    t:"Resolve entity over-linking on the brand name",
    p:"Mentions are resolving to a generic concept rather than the brand itself. Disambiguating copy and sameAs references pull the link back.",
    tags:["Disambiguation","Connection"], effort:"Medium", impact:8,
    n:`${d.consistency.by_type.mid_overlink_review} clusters`});
  if (pct(d.coverage.thin,d.coverage.crawled) > 10) f.push({
    t:"Fill or remove thin pages",
    p:`${d.coverage.thin} pages hold under 400 characters. Each one either earns real content or leaves the index.`,
    tags:["Attribute completion","Coverage"], effort:"High", impact:7,
    n:`${d.coverage.thin} pages`});
  if (d.clarity.no_dominant) f.push({
    t:"Give every page a single clear subject",
    p:`${d.clarity.no_dominant} pages have no dominant entity and ${d.clarity.weak} more have one too weak to read confidently.`,
    tags:["Entity-first structure","Clarity"], effort:"Medium", impact:7,
    n:`${d.clarity.no_dominant + d.clarity.weak} pages`});
  if (d.connection.type_conflicts) f.push({
    t:"Review NLP / Knowledge Graph type conflicts",
    p:`${d.connection.type_conflicts} entities are typed one way by the NLP model and another by the Knowledge Graph — usually a disambiguation failure worth checking by hand.`,
    tags:["Disambiguation","Connection"], effort:"Low", impact:5,
    n:`${d.connection.type_conflicts} entities`});
  return f.sort((a,b)=>b.impact-a.impact);
}

let CURRENT = null;

function render(d){
  const scores = DIMENSIONS.map(dim => ({dim, s: dim.score(d)}));
  const total = scores.reduce((a,x)=>a+x.s,0);
  CURRENT = {site:d.site, captured:d.captured, total,
             scores:Object.fromEntries(scores.map(x=>[x.dim.key,x.s])), data:d};

  $("total").textContent = total;
  $("captured").textContent = `${d.site} · ${d.captured}`;
  const worst = scores.slice().sort((a,b)=>a.s-b.s)[0];
  $("headline").innerHTML =
    total >= 12 ? "Machines understand this site well." :
    total >= 8  ? "Machines partly understand this site." :
    total >= 5  ? "Machines are guessing about this site."
                : "Machines cannot reliably tell what this site is.";
  $("subline").innerHTML =
    `Weakest dimension: <strong style="color:#fff">${worst.dim.name}</strong> at ${worst.s}/3. ` +
    worst.dim.why(d).replace(/<[^>]+>/g,"");

  $("gauge").innerHTML = scores.map(({dim,s}) => `
    <div class="dim" style="--lvl:${LEVEL[s].color}">
      <div class="blocks">${[0,1,2].map(i=>`<div class="b ${i<s?'on':''}"></div>`).join("")}</div>
      <div class="lbl"><span>${dim.name}</span><span>${s}/3</span></div>
    </div>`).join("");

  $("cards").innerHTML = scores.map(({dim,s}) => `
    <article class="card" style="--lvl:${LEVEL[s].color}">
      <div class="head"><h3>${dim.name}</h3><span class="pill">${s}/3 ${LEVEL[s].name}</span></div>
      <div class="eyebrow" style="margin-top:6px">${dim.question}</div>
      <p class="why">${dim.why(d)}</p>
      <ul class="metrics">${dim.metrics(d).map(([k,v,q,good,mid])=>{
        const cls = q>=good ? "ok" : q>=mid ? "mid" : "bad";
        return `<li><span class="k">${k}</span><span class="v ${cls}">${v}</span></li>`;
      }).join("")}</ul>
    </article>`).join("");

  $("fixes").innerHTML = buildFixes(d, scores).map(f => `
    <li class="fix">
      <div class="rank"></div>
      <div>
        <h4>${f.t}</h4><p>${f.p}</p>
        <div class="tags">${f.tags.map(t=>`<span class="tag">${t}</span>`).join("")}</div>
      </div>
      <div class="effort"><b>${f.effort}</b>effort · ${f.n}</div>
    </li>`).join("");

  $("report").hidden = false;
  $("status").textContent = `Scored ${d.pages} pages · ${total}/15`;
}

/* ---- demo: the real, frozen MLforSEO baseline ---- */
const DEMO = {
  "site": "mlforseo.com + academy.mlforseo.com",
  "captured": "2026-08-20",
  "pages": 637,
  "clarity": {
    "in_title": 266,
    "in_h1": 192,
    "in_meta": 128,
    "no_dominant": 30,
    "weak": 163
  },
  "coverage": {
    "thin": 177,
    "crawled": 647,
    "dup_groups": 76,
    "dup_urls": 174
  },
  "consistency": {
    "clusters": 220,
    "by_type": {
      "mid_variant": 76,
      "mid_overlink_review": 42,
      "containment_review": 30,
      "punctuation": 72
    },
    "brand_forms": 4,
    "brand_types": 3
  },
  "connection": {
    "matched": 2118,
    "ambiguous": 776,
    "unmatched": 2106,
    "queried": 5000,
    "mentions_with_mid": 4587,
    "mentions": 102752,
    "type_conflicts": 149,
    "brand_status": "unmatched"
  },
  "corroboration": {
    "llm_parametric": 0,
    "ai_mentions": 17,
    "ai_google": 14,
    "ai_chatgpt": 3,
    "kg_results": 0
  }
};
$("demo").onclick = () => render(JSON.parse(JSON.stringify(DEMO)));

/* ---- CSV ingest ---- */
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
  const head=rows.shift()||[];
  return rows.filter(r=>r.length>1).map(r=>Object.fromEntries(head.map((h,i)=>[h.trim(),r[i]??""])));
}

$("files").onchange = async e => {
  const files=[...e.target.files]; if(!files.length) return;
  const d = JSON.parse(JSON.stringify(DEMO));
  d.site="Uploaded audit"; d.captured=new Date().toISOString().slice(0,10);
  let used=[];
  for (const f of files){
    const rows = parseCSV(await f.text());
    if (!rows.length) continue;
    const k = Object.keys(rows[0]);
    if (k.includes("dominant_entity") || k.includes("dominant")){
      d.pages = rows.length; used.push("page profiles");
      d.clarity = {
        in_title: rows.filter(r=>r.dominant_in_title==="yes").length,
        in_h1: rows.filter(r=>r.dominant_in_h1==="yes").length,
        in_meta: rows.filter(r=>r.dominant_in_meta==="yes").length,
        no_dominant: rows.filter(r=>(r.has_dominant_entity||(r.dominant_entity||r.dominant?"yes":"no"))==="no").length,
        weak: rows.filter(r=>r.has_dominant_entity==="yes" && parseFloat(r.dominant_salience||0)<0.12).length
      };
    } else if (k.includes("kg_mid")){
      used.push("KG reconciliation");
      d.connection.queried = rows.length;
      d.connection.matched = rows.filter(r=>r.status==="matched").length;
      d.connection.ambiguous = rows.filter(r=>r.status==="ambiguous").length;
      d.connection.unmatched = rows.filter(r=>r.status==="unmatched").length;
      d.connection.type_conflicts = rows.filter(r=>r.flag==="type_conflict").length;
    } else if (k.includes("cluster_type")){
      used.push("consistency clusters");
      const by={}; rows.forEach(r=>by[r.cluster_type]=(by[r.cluster_type]||0)+1);
      d.consistency.clusters = rows.length; d.consistency.by_type = by;
    }
  }
  if (!used.length){ $("status").textContent="No recognised audit CSVs in that selection."; return; }
  render(d);
  $("status").textContent = `Scored from ${used.join(", ")}`;
};

/* ---- save / diff ---- */
/* Two hosting contexts, two save paths. On academy.mlforseo.com a plain
   blob link works. Inside the Claude artifact viewer it silently does
   nothing, so route through the downloads capability when it exists. */
async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use)
    ? await claude.use("downloads").catch(()=>null) : null;
  if (api){
    try { await api.save({filename, data:text}); return "saved"; }
    catch(err){
      if (err && err.code === "declined") return "declined";
      return "failed";
    }
  }
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([text],{type:mime}));
  a.download=filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
  return "saved";
}

$("save").onclick = async () => {
  if (!CURRENT){ $("status").textContent="Nothing to save yet — load or upload an audit first."; return; }
  const r = await offerFile(`entity-scorecard-${CURRENT.captured}.json`,
                            JSON.stringify(CURRENT,null,2), "application/json");
  $("status").textContent =
    r === "saved"    ? "Saved. Re-run in 90 days and compare against this file."
  : r === "declined" ? "Save cancelled."
                     : "Could not save here — try the Print / PDF button instead.";
};

$("csv").onclick = async () => {
  if (!CURRENT){ $("status").textContent="Nothing to export yet."; return; }
  const q = v => `"${String(v).replace(/"/g,'""')}"`;
  const lines = [["dimension","score","max"].map(q).join(",")];
  DIMENSIONS.forEach(d => lines.push([d.name, CURRENT.scores[d.key], 3].map(q).join(",")));
  lines.push(["Total", CURRENT.total, 15].map(q).join(","), "");
  lines.push(["rank","fix","patterns","effort","scope"].map(q).join(","));
  buildFixes(CURRENT.data, null).forEach((f,i) =>
    lines.push([i+1, f.t, f.tags.join(" / "), f.effort, f.n].map(q).join(",")));
  const r = await offerFile(`entity-scorecard-${CURRENT.captured}.csv`,
                            lines.join("\n"), "text/csv");
  $("status").textContent = r === "saved" ? "Exported." :
    r === "declined" ? "Export cancelled." : "Could not export here.";
};

$("prev").onchange = async e => {
  const f=e.target.files[0]; if(!f||!CURRENT) return;
  let old; try{ old=JSON.parse(await f.text()); }catch{ $("status").textContent="That file isn't a saved scorecard."; return; }
  const rows = DIMENSIONS.map(dim=>{
    const a=old.scores?.[dim.key] ?? 0, b=CURRENT.scores[dim.key], delta=b-a;
    const cls = delta>0?"up":delta<0?"down":"same";
    const sign = delta>0?"+":"";
    return `<div class="diffrow"><span>${dim.name}</span>
      <span><span class="num" style="color:var(--muted)">${a}</span> → <span class="num">${b}</span>
      <span class="delta ${cls}" style="margin-left:10px">${sign}${delta}</span></span></div>`;
  }).join("");
  const td = CURRENT.total - (old.total ?? 0);
  $("diff").innerHTML = rows + `<div class="diffrow" style="border-top:2px solid var(--line-strong);margin-top:6px;padding-top:10px">
    <strong>Total</strong><span><span class="num" style="color:var(--muted)">${old.total ?? 0}</span> → <span class="num"><strong>${CURRENT.total}</strong></span>
    <span class="delta ${td>0?'up':td<0?'down':'same'}" style="margin-left:10px">${td>0?'+':''}${td}</span></span></div>`;
  $("diffwrap").hidden = false;
  $("status").textContent = `Compared against ${old.captured || "saved scorecard"}.`;
};

$("print").onclick = () => window.print();
