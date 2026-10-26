
const $ = id => document.getElementById(id);
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const SCHEMA = {
  type:"object",
  properties:{
    canonical_name:{type:"string", description:"The single surface form to use everywhere on this page"},
    disambiguation_sentence:{type:"string", description:"One sentence, placed early, that makes the entity unmistakable to a machine"},
    entities_to_add:{type:"array", items:{type:"object", properties:{
      entity:{type:"string"}, why:{type:"string"}, where:{type:"string"}},
      required:["entity","why","where"], additionalProperties:false}},
    attributes_to_cover:{type:"array", items:{type:"string"}},
    entities_to_avoid:{type:"array", items:{type:"string"}},
    internal_links:{type:"array", items:{type:"string"}},
    review_warnings:{type:"array", items:{type:"string"},
      description:"Claims a human must verify before publishing"}
  },
  required:["canonical_name","disambiguation_sentence","entities_to_add",
            "attributes_to_cover","entities_to_avoid","internal_links","review_warnings"],
  additionalProperties:false
};

const SYSTEM = `You write entity-optimisation briefs for SEO content teams.

You are given the output of an entity audit. Work only from that data plus the page content
supplied. Your job is to make the page's subject unmistakable to a machine without changing
what the page actually claims.

Rules:
- Never invent facts about the business, its products, prices, people or results.
- If the detected entity differs from the intended entity, the disambiguation sentence must
  fix precisely that confusion, naming the intended entity plainly.
- If the detected type is wrong (a technique typed as a LOCATION, a brand typed as a PERSON),
  say what the thing IS in the disambiguation sentence.
- Suggest entities to add only where they genuinely belong in this page's argument.
- Put anything you are not certain of into review_warnings rather than asserting it.`;

function fields(){
  return {
    url: $("url").value.trim(), intended: $("intended").value.trim(),
    detected: $("detected").value.trim(), dtype: $("dtype").value.trim(),
    missing: $("missing").value.trim(), canon: $("canon").value.trim(),
    content: $("content").value.trim()
  };
}
function refresh(){
  const f = fields();
  $("run").disabled = !$("key").value.trim() || !(f.url || f.intended);
}
["key","url","intended","detected","dtype","missing","canon","content"]
  .forEach(id => $(id).addEventListener("input", refresh));

function prompt(f){
  const bits = [];
  if (f.url) bits.push(`Page URL: ${f.url}`);
  if (f.intended) bits.push(`Intended entity (what this page should be about): ${f.intended}`);
  if (f.detected) bits.push(`Detected dominant entity: ${f.detected}${f.dtype?` — typed ${f.dtype} by Google's NLP API`:""}`);
  if (f.detected && f.intended && f.detected.toLowerCase() !== f.intended.toLowerCase())
    bits.push(`These do not match. The page is being read as being about "${f.detected}" rather than "${f.intended}".`);
  if (f.missing) bits.push(`Entities competitors cover that this page does not: ${f.missing}`);
  if (f.canon) bits.push(`Canonical naming rules that must be followed: ${f.canon}`);
  if (f.content) bits.push(`\nCurrent page content:\n"""\n${f.content.slice(0,24000)}\n"""`);
  return bits.join("\n") + "\n\nWrite the entity rewrite brief.";
}

function explainError(status, msg){
  const m = (msg||"").toLowerCase();
  if (status === 401) return "That API key was rejected. Check it starts with sk-ant- and has no stray spaces.";
  if (status === 400 && m.includes("credit")) return "That account has no credit. Top up in the Anthropic console.";
  if (status === 400) return msg || "The request was rejected.";
  if (status === 429) return "Rate limited. Wait a moment and try again.";
  if (status >= 500) return "Anthropic returned a server error. Try again shortly.";
  return msg || "Request failed.";
}

$("run").onclick = async () => {
  const f = fields(), key = $("key").value.trim();
  $("run").disabled = true; $("prog").hidden = false; $("status").textContent = "Generating…";
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method:"POST",
      headers:{
        "content-type":"application/json",
        "x-api-key":key,
        "anthropic-version":"2023-06-01",
        "anthropic-dangerous-direct-browser-access":"true"
      },
      body: JSON.stringify({
        model: $("model").value, max_tokens: 4000, system: SYSTEM,
        output_config:{format:{type:"json_schema", schema:SCHEMA}},
        messages:[{role:"user", content: prompt(f)}]
      })
    });
    if (!res.ok){
      let msg = `HTTP ${res.status}`;
      try { const b = await res.json(); msg = b.error?.message || msg; } catch {}
      $("status").textContent = explainError(res.status, msg);
      return;
    }
    const body = await res.json();
    if (body.stop_reason === "refusal"){
      $("status").textContent = "The model declined this request. Try rephrasing the page context.";
      return;
    }
    const text = (body.content||[]).filter(b=>b.type==="text").map(b=>b.text).join("");
    let brief;
    try { brief = JSON.parse(text); }
    catch { $("status").textContent = "The response wasn't valid JSON — try again."; return; }
    render(brief, f, body.usage||{});
    $("status").textContent = "Brief ready.";
    $("print").hidden = false; $("dl").hidden = false;
  } catch (err){
    $("status").textContent = "Network error: " + (err.message||"request failed");
  } finally {
    $("prog").hidden = true; refresh();
  }
};

let BRIEF = null, FIELDS = null;
function render(b, f, usage){
  BRIEF = b; FIELDS = f;
  const list = (arr, cls="") => (arr||[]).length
    ? `<div class="chips">${arr.map(x=>`<span class="chip ${cls}">${esc(x)}</span>`).join("")}</div>`
    : `<p style="color:var(--muted);font-size:13.5px">None identified.</p>`;
  $("out").innerHTML = `<div class="brief">
    <div class="head">
      <div class="eyebrow">Entity rewrite brief</div>
      <h2>${esc(b.canonical_name||f.intended||"Untitled page")}</h2>
      ${f.url?`<div class="url">${esc(f.url)}</div>`:""}
    </div>
    <div class="bsec"><h3>Use this name everywhere</h3><div class="canon">${esc(b.canonical_name)}</div></div>
    <div class="bsec"><h3>Disambiguation sentence — place it early</h3>
      <p>${esc(b.disambiguation_sentence)}</p></div>
    <div class="bsec"><h3>Entities to add</h3>
      ${(b.entities_to_add||[]).length ? `<ul class="plain">${b.entities_to_add.map(e=>
        `<li><b>${esc(e.entity)}</b> <span class="why">${esc(e.why)} &middot; ${esc(e.where)}</span></li>`).join("")}</ul>`
        : `<p style="color:var(--muted);font-size:13.5px">None identified.</p>`}</div>
    <div class="bsec"><h3>Attributes to cover</h3>${list(b.attributes_to_cover)}</div>
    <div class="bsec"><h3>Entities to avoid</h3>${list(b.entities_to_avoid,"avoid")}</div>
    <div class="bsec"><h3>Suggested internal links</h3>${list(b.internal_links)}</div>
    <div class="bsec"><h3>Check before publishing</h3>
      ${(b.review_warnings||[]).length ? `<ul class="plain warnlist">${b.review_warnings.map(w=>
        `<li>${esc(w)}</li>`).join("")}</ul>` : `<p style="color:var(--muted);font-size:13.5px">Nothing flagged — still read it before it ships.</p>`}</div>
    <div class="bsec" style="background:var(--sunk)">
      <h3>Run detail</h3><p style="font-size:12.5px;color:var(--muted)">
      ${esc($("model").value)} &middot; ${usage.input_tokens||0} in / ${usage.output_tokens||0} out tokens
      &middot; re-run the Extractor on the rewrite to prove the fix worked.</p></div>
  </div>`;
  $("out").hidden = false;
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
  if (!BRIEF) return;
  const md = [
    `# Entity rewrite brief — ${BRIEF.canonical_name}`,
    FIELDS.url ? `\n**Page:** ${FIELDS.url}` : "",
    `\n## Use this name everywhere\n${BRIEF.canonical_name}`,
    `\n## Disambiguation sentence\n${BRIEF.disambiguation_sentence}`,
    `\n## Entities to add\n` + (BRIEF.entities_to_add||[]).map(e=>`- **${e.entity}** — ${e.why} (${e.where})`).join("\n"),
    `\n## Attributes to cover\n` + (BRIEF.attributes_to_cover||[]).map(a=>`- ${a}`).join("\n"),
    `\n## Entities to avoid\n` + (BRIEF.entities_to_avoid||[]).map(a=>`- ${a}`).join("\n"),
    `\n## Suggested internal links\n` + (BRIEF.internal_links||[]).map(a=>`- ${a}`).join("\n"),
    `\n## Check before publishing\n` + (BRIEF.review_warnings||[]).map(a=>`- ${a}`).join("\n")
  ].join("\n");
  await offerFile("entity-brief.md", md, "text/markdown");
};
$("print").onclick = () => window.print();
refresh();
