
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const MAX_CHARS = 30000, MAX_PAGES = 200, OUT_TOKENS = 3800;
const TYPES = ["PERSON","ORGANIZATION","PRODUCT","CONCEPT","LOCATION","EVENT","WORK","OTHER"];

/* ---------- the contract every answer must match ---------- */
const SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["page_subject","entities","relationships","attributes","naming","uncertainty"],
  properties: {
    page_subject: { type: "object", additionalProperties: false,
      required: ["entity","type","matches_intended","explanation","competing_entities"],
      properties: {
        entity: { type: "string", description: "What the page is actually about, as one entity" },
        type: { type: "string", enum: TYPES },
        matches_intended: { type: "string", enum: ["yes","partly","no","no intended entity given"] },
        explanation: { type: "string" },
        competing_entities: { type: "array", items: { type: "string" } } } },
    entities: { type: "array", items: { type: "object", additionalProperties: false,
      required: ["name","type","presence","role","evidence"],
      properties: {
        name: { type: "string" }, type: { type: "string", enum: TYPES },
        presence: { type: "string", enum: ["explicit","implicit"], description: "explicit = the name appears in the text; implicit = the page is about it without naming it" },
        role: { type: "string", enum: ["main","supporting","mentioned"] },
        evidence: { type: "string", description: "A short verbatim quote from the text (under 25 words) that supports this entity" } } } },
    relationships: { type: "array", items: { type: "object", additionalProperties: false,
      required: ["subject","predicate","object","evidence"],
      properties: { subject: { type: "string" }, predicate: { type: "string" }, object: { type: "string" },
        evidence: { type: "string", description: "Verbatim quote, under 25 words" } } } },
    attributes: { type: "object", additionalProperties: false, required: ["entity","covered","missing"],
      properties: {
        entity: { type: "string" },
        covered: { type: "array", items: { type: "object", additionalProperties: false, required: ["attribute","evidence"],
          properties: { attribute: { type: "string" }, evidence: { type: "string", description: "Verbatim quote, under 25 words" } } } },
        missing: { type: "array", items: { type: "object", additionalProperties: false, required: ["attribute","why_readers_expect_it"],
          properties: { attribute: { type: "string" }, why_readers_expect_it: { type: "string" } } } } } },
    naming: { type: "array", items: { type: "object", additionalProperties: false,
      required: ["entity","variants_on_page","suggested_canonical","ambiguous","note"],
      properties: { entity: { type: "string" }, variants_on_page: { type: "array", items: { type: "string" } },
        suggested_canonical: { type: "string" }, ambiguous: { type: "boolean" }, note: { type: "string" } } } },
    uncertainty: { type: "array", items: { type: "string" }, description: "What you are unsure about, stated plainly" }
  }
};

const SYSTEM = `You are an entity analyst for SEO audits. You read one web page's main content and describe it
in a fixed JSON shape. Work only from the text supplied.

Rules:
- Every "evidence" field is a short VERBATIM quote copied exactly from the text (under 25 words). Never paraphrase it.
- Mark an entity "explicit" only if its name appears in the text. Otherwise it is "implicit", and its evidence is the passage that implies it.
- Do not add entities, facts or relationships the text does not support. When unsure, say so in "uncertainty".
- Fill every field. Sections the task does not ask for stay as empty arrays (or brief values), never invented.`;

const TASKS = {
  map: "Task: build an ENTITY MAP. List every entity the page is about or meaningfully mentions (up to 40), with presence, role and evidence, and the relationships between them stated in the text (up to 25). Fill page_subject. Leave attributes.covered/missing and naming as empty arrays.",
  eav: "Task: ATTRIBUTE GAPS for the intended entity (or, if none is given, the page's main entity). In attributes, list the attributes of that entity the page covers (with evidence) and the attributes a reader searching for it would expect but cannot find here (up to 12, with why). Fill page_subject and list only the entities needed to support it (up to 10). Leave relationships and naming empty.",
  subject: "Task: SUBJECT CHECK. Decide what the page is actually about as a single entity and whether it matches the intended entity. In competing_entities, name what competes with it for the subject. List the entities that make up the page's subject (up to 15) with roles. Leave relationships, attributes and naming empty.",
  naming: "Task: NAMING AND AMBIGUITY. In naming, list entities that appear under more than one name on the page (with each variant exactly as written) and entities whose names could be resolved to a different real-world thing; suggest one canonical name for each. List the entities involved (up to 20). Fill page_subject. Leave relationships and attributes empty."
};

/* ---------- state ---------- */
let ROWS = [], CSV_HEAD = [], NLP = null, RESULTS = [], STOP = false, USAGE = { in: 0, out: 0 };
const mode = () => document.querySelector('input[name="mode"]:checked').value;
const price = () => { const o = $("model").selectedOptions[0]; return { in: +o.dataset.in, out: +o.dataset.out }; };
let SOURCE = "one";

/* ---------- inputs ---------- */
function setTab(t){
  SOURCE = t;
  $("tabOne").setAttribute("aria-selected", t === "one"); $("tabCsv").setAttribute("aria-selected", t === "csv");
  $("paneOne").hidden = t !== "one"; $("paneCsv").hidden = t !== "csv"; refresh();
}
$("tabOne").onclick = () => setTab("one"); $("tabCsv").onclick = () => setTab("csv");

function guess(cols, re){ return cols.find(c => re.test(c)) || ""; }
$("csv").onchange = e => {
  const f = e.target.files[0]; if (!f) return;
  Papa.parse(f, { header: true, skipEmptyLines: true, complete: r => {
    ROWS = r.data; CSV_HEAD = r.meta.fields || [];
    const opts = (sel, none) => (none ? `<option value="">— none —</option>` : "") + CSV_HEAD.map(c => `<option>${esc(c)}</option>`).join("");
    $("colUrl").innerHTML = opts(); $("colText").innerHTML = opts(); $("colIntended").innerHTML = opts(0, true);
    $("colUrl").value = guess(CSV_HEAD, /^(address|url)$/i) || CSV_HEAD[0];
    $("colText").value = guess(CSV_HEAD, /content|body|text|extraction|main/i) || CSV_HEAD[1] || CSV_HEAD[0];
    $("colIntended").value = guess(CSV_HEAD, /intended/i);
    $("csvCols").hidden = false; $("csvFilter").hidden = false;
    $("csvInfo").textContent = `${ROWS.length.toLocaleString()} rows loaded. Check the columns, then choose how many pages to analyse.`;
    refresh();
  }});
};
const normUrl = u => String(u || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/[?#].*$/, "").replace(/\/+$/, "");
const normEnt = s => String(s || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, " ").trim().replace(/s$/, "");
$("nlp").onchange = e => {
  const f = e.target.files[0]; if (!f) return;
  Papa.parse(f, { header: true, skipEmptyLines: true, complete: r => {
    const uc = (r.meta.fields || []).find(c => /^url$/i.test(c)), ec = (r.meta.fields || []).find(c => /^entity$/i.test(c));
    if (!uc || !ec){ $("nlpInfo").textContent = "That file has no url and entity columns — use the Entity Extractor's entity_mentions.csv."; NLP = null; return; }
    NLP = new Map();
    r.data.forEach(row => { const k = normUrl(row[uc]); if (!NLP.has(k)) NLP.set(k, new Set()); NLP.get(k).add(normEnt(row[ec])); });
    $("nlpInfo").textContent = `NLP cross-check loaded: ${r.data.length.toLocaleString()} mentions across ${NLP.size.toLocaleString()} URLs.`;
  }});
};

function pages(){
  if (SOURCE === "one"){
    const t = $("content").value.trim();
    return t ? [{ url: $("url").value.trim() || "pasted page", intended: $("intended").value.trim(), text: t }] : [];
  }
  if (!ROWS.length) return [];
  const uc = $("colUrl").value, tc = $("colText").value, ic = $("colIntended").value;
  const filt = $("urlFilter").value.trim().toLowerCase(), all = $("intendedAll").value.trim();
  const n = Math.max(1, Math.min(MAX_PAGES, parseInt($("maxPages").value, 10) || 10));
  return ROWS.filter(r => String(r[tc] || "").trim().length > 200 && (!filt || String(r[uc]).toLowerCase().includes(filt)))
    .slice(0, n).map(r => ({ url: r[uc], intended: (ic && r[ic]) || all, text: String(r[tc]).trim() }));
}

/* ---------- cost estimate ---------- */
function estimate(ps){
  const p = price();
  const inTok = ps.reduce((s, x) => s + Math.ceil((Math.min(x.text.length, MAX_CHARS) + 2600) / 4), 0);
  const outTok = ps.length * OUT_TOKENS;
  return { inTok, outTok, usd: inTok / 1e6 * p.in + outTok / 1e6 * p.out };
}
function refresh(){
  const ps = pages(), e = estimate(ps);
  $("est").innerHTML = `<div><b>${ps.length}</b><span>page${ps.length === 1 ? "" : "s"}</span></div>
    <div><b>~${(e.inTok / 1000).toFixed(1)}k</b><span>input tokens</span></div>
    <div><b>~${(e.outTok / 1000).toFixed(1)}k</b><span>output tokens (estimate)</span></div>
    <div><b>~$${e.usd < 0.01 ? e.usd.toFixed(3) : e.usd.toFixed(2)}</b><span>at ${$("model").selectedOptions[0].text.split(" —")[0]} list prices</span></div>`;
  $("run").disabled = !$("key").value.trim() || !ps.length;
  if (!RUNNING) $("status").textContent = !$("key").value.trim() ? "Add your Anthropic API key." : !ps.length ? "Add some content." : "Ready. Nothing has been sent yet.";
}
["key","url","intended","content","urlFilter","maxPages","intendedAll","model","colUrl","colText","colIntended"].forEach(id => $(id).addEventListener("input", refresh));
document.querySelectorAll('input[name="mode"]').forEach(r => r.addEventListener("change", refresh));

/* ---------- the call ---------- */
function userPrompt(p){
  const text = p.text.slice(0, MAX_CHARS);
  return `${TASKS[mode()]}\n\nPage URL: ${p.url}\nIntended entity: ${p.intended || "(none given)"}\n` +
    (p.text.length > MAX_CHARS ? `(Text trimmed to the first ${MAX_CHARS} characters.)\n` : "") +
    `\nMain content:\n"""\n${text}\n"""`;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function ask(p, key){
  for (let attempt = 0; attempt < 4; attempt++){
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true" },
      body: JSON.stringify({ model: $("model").value, max_tokens: 6000, system: SYSTEM,
        output_config: { format: { type: "json_schema", schema: SCHEMA } },
        messages: [{ role: "user", content: userPrompt(p) }] })
    });
    if (res.ok){
      const body = await res.json();
      if (body.stop_reason === "refusal") throw new Error("The model declined this page.");
      if (body.stop_reason === "max_tokens") throw new Error("The answer was cut off — try a shorter page or a narrower analysis.");
      const txt = (body.content || []).filter(b => b.type === "text").map(b => b.text).join("");
      USAGE.in += body.usage?.input_tokens || 0; USAGE.out += body.usage?.output_tokens || 0;
      return JSON.parse(txt);
    }
    let msg = `HTTP ${res.status}`; try { msg = (await res.json()).error?.message || msg; } catch {}
    if (res.status === 401) { const e = new Error("That API key was rejected. Check it starts with sk-ant- and has no stray spaces."); e.fatal = true; throw e; }
    if (res.status === 400 && /credit/i.test(msg)) { const e = new Error("That account has no credit. Top up in the Anthropic console."); e.fatal = true; throw e; }
    if (res.status === 429 || res.status === 529 || res.status >= 500){ await sleep(2000 * 2 ** attempt); continue; }
    throw new Error(msg);
  }
  throw new Error("Still rate-limited after four tries — run fewer pages at once.");
}

/* ---------- the checks ---------- */
const flat = s => String(s || "").toLowerCase().replace(/[‘’‛′]/g, "'").replace(/[“”″]/g, '"')
  .replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
function inText(quote, text){
  const q = flat(quote).replace(/^[."'\s]+|[."'\s]+$/g, "").replace(/\.\.\.|…/g, " ");
  if (!q) return false;
  const T = flat(text);
  if (T.includes(q)) return true;
  // a quote with an ellipsis or a trimmed end: every 6-word run must be on the page
  const w = q.split(" "); if (w.length < 6) return false;
  for (let i = 0; i + 6 <= w.length; i += 3) if (!T.includes(w.slice(i, i + 6).join(" "))) return false;
  return true;
}
function check(p, r){
  const nlp = NLP ? NLP.get(normUrl(p.url)) : null;
  (r.entities || []).forEach(e => {
    e._quote = inText(e.evidence, p.text);
    e._named = flat(p.text).includes(flat(e.name));
    e._nlp = nlp ? nlp.has(normEnt(e.name)) : null;
    e._tier = !e._quote ? "discard"
      : e.presence === "explicit" && !e._named ? "discard"
      : e.presence === "explicit" && e._nlp ? "solid"
      : e.presence === "explicit" ? "likely" : "candidate";
  });
  (r.relationships || []).forEach(x => x._quote = inText(x.evidence, p.text));
  (r.attributes?.covered || []).forEach(x => x._quote = inText(x.evidence, p.text));
  (r.naming || []).forEach(x => x._found = (x.variants_on_page || []).filter(v => flat(p.text).includes(flat(v))).length);
  return r;
}

/* ---------- run ---------- */
let RUNNING = false;
$("run").onclick = async () => {
  const ps = pages(), key = $("key").value.trim();
  if (!ps.length) return;
  RUNNING = true; STOP = false; RESULTS = []; USAGE = { in: 0, out: 0 };
  $("run").disabled = true; $("stop").hidden = false; $("prog").hidden = false; $("prog").max = ps.length; $("prog").value = 0;
  $("pages").innerHTML = ""; $("out").hidden = false;
  let i = 0, done = 0, fatal = null;
  async function worker(){
    while (!STOP && !fatal && i < ps.length){
      const p = ps[i++];
      $("status").textContent = `Analysing ${done + 1} of ${ps.length}…`;
      try { RESULTS.push({ page: p, result: check(p, await ask(p, key)) }); }
      catch (e){ if (e.fatal) fatal = e.message; RESULTS.push({ page: p, error: e.message }); }
      done++; $("prog").value = done; render();
    }
  }
  await Promise.all([worker(), worker()]);
  RUNNING = false; $("stop").hidden = true; $("prog").hidden = true; refresh();
  const p = price(), cost = USAGE.in / 1e6 * p.in + USAGE.out / 1e6 * p.out;
  $("status").textContent = fatal || `${STOP ? "Stopped" : "Done"}: ${RESULTS.filter(r => !r.error).length} page(s) analysed · ${USAGE.in.toLocaleString()} in / ${USAGE.out.toLocaleString()} out tokens · about $${cost.toFixed(cost < 0.01 ? 4 : 2)}.`;
};
$("stop").onclick = () => { STOP = true; $("status").textContent = "Stopping after the pages already in flight…"; };

/* ---------- render ---------- */
const mark = v => v === null || v === undefined ? `<span class="na">–</span>` : v ? `<span class="ok">✓</span>` : `<span class="no">✗</span>`;
function render(){
  const ents = RESULTS.flatMap(r => r.result?.entities || []);
  const count = t => ents.filter(e => e._tier === t).length;
  $("sum").innerHTML = `<div><b>${RESULTS.length}</b><span>pages</span></div><div><b>${count("solid")}</b><span>Solid</span></div>
    <div><b>${count("likely")}</b><span>Likely</span></div><div><b>${count("candidate")}</b><span>Candidate</span></div><div><b>${count("discard")}</b><span>Discard</span></div>`;
  $("pages").innerHTML = RESULTS.map(({ page: p, result: r, error }) => {
    if (error) return `<details class="page"><summary><span class="u">${esc(p.url)}</span><span class="verdict bad">Error</span></summary><div class="inner"><p>${esc(error)}</p></div></details>`;
    const s = r.page_subject || {};
    const v = s.matches_intended === "yes" ? "good" : s.matches_intended === "no" ? "bad" : "";
    const ents = (r.entities || []).map(e => `<tr><td><b>${esc(e.name)}</b></td><td>${esc(e.type)}</td><td>${esc(e.presence)}</td><td>${esc(e.role)}</td>
      <td class="ev">“${esc(e.evidence)}”</td><td>${mark(e._quote)}</td><td>${mark(NLP ? e._nlp : null)}</td><td><span class="tier ${e._tier}">${e._tier[0].toUpperCase() + e._tier.slice(1)}</span></td></tr>`).join("");
    const rels = (r.relationships || []).map(x => `<tr><td>${esc(x.subject)}</td><td>${esc(x.predicate)}</td><td>${esc(x.object)}</td><td class="ev">“${esc(x.evidence)}”</td><td>${mark(x._quote)}</td></tr>`).join("");
    const cov = (r.attributes?.covered || []).map(x => `<tr><td>${esc(x.attribute)}</td><td class="ev">“${esc(x.evidence)}”</td><td>${mark(x._quote)}</td></tr>`).join("");
    const mis = (r.attributes?.missing || []).map(x => `<tr><td><b>${esc(x.attribute)}</b></td><td class="ev">${esc(x.why_readers_expect_it)}</td></tr>`).join("");
    const nam = (r.naming || []).map(x => `<tr><td><b>${esc(x.entity)}</b></td><td>${esc((x.variants_on_page || []).join(" · "))}</td><td>${esc(x.suggested_canonical)}</td><td>${x.ambiguous ? "yes" : "no"}</td><td class="ev">${esc(x.note)}</td><td>${x._found}/${(x.variants_on_page || []).length}</td></tr>`).join("");
    const tbl = (head, rows) => rows ? `<div class="tablewrap"><table><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>` : "";
    return `<details class="page" ${RESULTS.length === 1 ? "open" : ""}><summary><span class="u">${esc(p.url)}</span>
      <span class="verdict ${v}">About: ${esc(s.entity || "?")}</span>${p.intended ? `<span class="verdict ${v}">Intended match: ${esc(s.matches_intended)}</span>` : ""}
      <span class="small">${(r.entities || []).length} entities</span></summary><div class="inner">
      <p style="margin:6px 0 0;color:var(--ink)">${esc(s.explanation || "")}</p>
      ${(s.competing_entities || []).length ? `<p class="small">Competing for the subject: ${esc(s.competing_entities.join(", "))}</p>` : ""}
      ${ents ? `<h3>Entities</h3>` + tbl(["Entity","Type","Presence","Role","Evidence","Quote on page","NLP agrees","Tier"], ents) : ""}
      ${rels ? `<h3>Relationships</h3>` + tbl(["Subject","Relationship","Object","Evidence","Quote on page"], rels) : ""}
      ${cov ? `<h3>Attributes covered — ${esc(r.attributes.entity)}</h3>` + tbl(["Attribute","Evidence","Quote on page"], cov) : ""}
      ${mis ? `<h3>Attributes readers would expect — suggestions to check</h3>` + tbl(["Attribute","Why readers expect it"], mis) : ""}
      ${nam ? `<h3>Naming and ambiguity</h3>` + tbl(["Entity","Variants on the page","Suggested canonical","Ambiguous","Note","Variants found"], nam) : ""}
      ${(r.uncertainty || []).length ? `<h3>What the model was unsure about</h3><ul>${r.uncertainty.map(u => `<li>${esc(u)}</li>`).join("")}</ul>` : ""}
      </div></details>`;
  }).join("");
}

/* ---------- exports ---------- */
const csvCell = v => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
const toCsv = (head, rows) => [head, ...rows].map(r => r.map(csvCell).join(",")).join("\n");
async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(() => null) : null;
  if (api){ try { await api.save({ filename, data: text }); return; } catch (e) { return; } }
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
const ok = () => RESULTS.filter(r => r.result);
$("dlEnt").onclick = () => offerFile("claude_entities.csv", toCsv(["url","entity","type","presence","role","evidence","quote_on_page","nlp_agrees","tier","model","mode"],
  ok().flatMap(({ page: p, result: r }) => r.entities.map(e => [p.url, e.name, e.type, e.presence, e.role, e.evidence, e._quote, e._nlp ?? "", e._tier, $("model").value, mode()]))), "text/csv");
$("dlRel").onclick = () => offerFile("claude_relationships.csv", toCsv(["url","subject","relationship","object","evidence","quote_on_page"],
  ok().flatMap(({ page: p, result: r }) => r.relationships.map(x => [p.url, x.subject, x.predicate, x.object, x.evidence, x._quote]))), "text/csv");
$("dlAttr").onclick = () => offerFile("claude_attributes.csv", toCsv(["url","entity","attribute","status","evidence_or_reason","quote_on_page"],
  ok().flatMap(({ page: p, result: r }) => [...r.attributes.covered.map(x => [p.url, r.attributes.entity, x.attribute, "covered", x.evidence, x._quote]),
    ...r.attributes.missing.map(x => [p.url, r.attributes.entity, x.attribute, "missing", x.why_readers_expect_it, ""])])), "text/csv");
$("dlName").onclick = () => offerFile("claude_naming.csv", toCsv(["url","entity","variants_on_page","suggested_canonical","ambiguous","note"],
  ok().flatMap(({ page: p, result: r }) => r.naming.map(x => [p.url, x.entity, (x.variants_on_page || []).join(" | "), x.suggested_canonical, x.ambiguous, x.note]))), "text/csv");
$("dlJson").onclick = () => offerFile("claude_entity_analysis.json", JSON.stringify({ model: $("model").value, mode: mode(), date: new Date().toISOString(),
  pages: RESULTS.map(({ page: p, result: r, error }) => ({ url: p.url, intended: p.intended, error, result: r })) }, null, 1), "application/json");

refresh();

