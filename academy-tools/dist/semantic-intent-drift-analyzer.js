
const $ = id => document.getElementById(id);
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ROOT = document.querySelector(".mlfs-tool") || document.documentElement;
const tok = name => getComputedStyle(ROOT).getPropertyValue(name).trim();
const REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
const fmt = n => n.toFixed(1);

/* ---- drift bands: colour is a token, so the plot follows light and dark ---- */
const BANDS = [
  {max:30,       key:"minimal", label:"Minimal drift", csv:"Minimal Drift", token:"--good"},
  {max:50,       key:"low",     label:"Low drift",     csv:"Low Drift",     token:"--accent"},
  {max:70,       key:"medium",  label:"Medium drift",  csv:"Medium Drift",  token:"--warn"},
  {max:85,       key:"high",    label:"High drift",    csv:"High Drift",    token:"--crit"},
  {max:Infinity, key:"extreme", label:"Extreme drift", csv:"Extreme Drift", token:"--muted"}
];
const bandFor = drift => BANDS.find(b => drift < b.max);

/* ---- lexical similarity: Jaccard 40%, coverage 30%, character 3-gram cosine 30% ---- */
function tokenize(text){
  return String(text).toLowerCase().replace(/[^\w\s]/g," ").split(/\s+/).filter(w => w.length > 2);
}
function ngramVector(text, n = 3){
  const clean = String(text).toLowerCase().replace(/[^\w\s]/g,""), v = {};
  for (let i = 0; i <= clean.length - n; i++){ const g = clean.substring(i, i + n); v[g] = (v[g]||0) + 1; }
  return v;
}
function cosineObj(a, b){
  let dot = 0, ma = 0, mb = 0;
  new Set([...Object.keys(a), ...Object.keys(b)]).forEach(k => {
    const x = a[k]||0, y = b[k]||0; dot += x*y; ma += x*x; mb += y*y;
  });
  return (ma && mb) ? dot / (Math.sqrt(ma) * Math.sqrt(mb)) : 0;
}
function lexicalSimilarity(target, fan){
  const t = new Set(tokenize(target)), s = new Set(tokenize(fan));
  const inter = [...t].filter(x => s.has(x)).length;
  const union = new Set([...t, ...s]).size;
  const jaccard = union ? inter / union : 0;
  const coverage = Math.min(inter / Math.max(t.size, 1), 1);
  const ngram = cosineObj(ngramVector(target), ngramVector(fan));
  return (jaccard*0.4 + coverage*0.3 + ngram*0.3) * 100;
}
function sharedNote(target, fan){
  const t = new Set(tokenize(target));
  const common = [...new Set(tokenize(fan))].filter(x => t.has(x));
  return common.length
    ? `Shared anchors: ${common.slice(0,4).join(", ")}.`
    : "No shared words, so the score rests on meaning from the embeddings.";
}

/* ---- Universal Sentence Encoder, loaded on first use ---- */
let useModel = null, usePromise = null;
function loadUSE(){
  if (useModel) return Promise.resolve(useModel);
  if (typeof use === "undefined" || typeof tf === "undefined")
    return Promise.reject(new Error("the encoder script did not load (check your connection or an ad blocker)"));
  if (!usePromise)
    usePromise = use.load().then(m => (useModel = m)).catch(e => { usePromise = null; throw e; });
  return usePromise;
}
async function embedTexts(texts, onStep){
  const model = await loadUSE();
  const uniq = [...new Set(texts)], out = new Map();
  for (let i = 0; i < uniq.length; i += 64){
    const chunk = uniq.slice(i, i + 64);
    const t = await model.embed(chunk);
    const rows = await t.array();
    t.dispose();
    chunk.forEach((s, j) => out.set(s, rows[j]));
    if (onStep) onStep(Math.min(i + 64, uniq.length), uniq.length);
  }
  return out;
}
// cosine between sentence embeddings as 0..100 (below zero counts as 0). Not (c+1)/2: that put every
// unrelated pair near 55, so High and Extreme drift could never be reached with Semantic Boost on.
function useSimilarity(a, b){
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++){ dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]; }
  if (!na || !nb) return 0;
  return Math.max(0, Math.min(1, dot / Math.sqrt(na*nb))) * 100;
}
// final = lexical alone, or lexical x 0.4 + USE x 0.6 with Semantic Boost
function score(target, fan, vecs){
  const lexical = lexicalSimilarity(target, fan);
  let similarity = lexical, note = "";
  if (vecs){
    similarity = lexical*0.4 + useSimilarity(vecs.get(target), vecs.get(fan))*0.6;
    note = sharedNote(target, fan);
  }
  const drift = 100 - similarity;
  return {similarity, drift, band: bandFor(drift), note};
}

/* ---- single analysis ---- */
let RESULT = null, busy = false;
const setStatus = html => { $("status").innerHTML = html; };

// stable vertical offset per query, so the same input always draws the same plot
function hash01(s){
  let h = 2166136261;
  for (let i = 0; i < s.length; i++){ h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 10000) / 10000;
}

async function analyse(){
  if (busy) return;
  const target = $("target").value.trim();
  const lines = $("fanouts").value.split("\n").map(s => s.trim()).filter(Boolean);
  const fans = [...new Set(lines)];
  if (!target || !fans.length){ setStatus("<strong>Add a target query and at least one fan-out.</strong>"); return; }
  busy = true;
  const btn = $("analyzeBtn"); btn.disabled = true; btn.textContent = "Analysing…";
  let boost = $("useToggle").checked, vecs = null, warn = "";
  try {
    if (boost){
      setStatus(useModel ? "Embedding your queries…"
        : "Loading the sentence encoder. The first run downloads the model, so allow a minute…");
      try { vecs = await embedTexts([target, ...fans]); }
      catch (e){
        boost = false;
        warn = `<strong>The sentence encoder did not load (${esc(e.message)}).</strong> These scores are word overlap only. `;
      }
    }
    const rows = fans.map((query, i) => {
      const r = score(target, query, vecs);
      const dist = r.drift / 20, ang = (i / fans.length) * Math.PI * 2;
      return {target, query, ...r,
        pos:{x:Math.cos(ang)*dist, y:(hash01(query) - 0.5)*dist*0.5, z:Math.sin(ang)*dist}};
    });
    RESULT = {target, boost, rows};
    drawPlot();
    render();
    const dupes = lines.length - fans.length;
    setStatus(warn + `Scored ${rows.length} fan-out${rows.length === 1 ? "" : "s"} `
      + (boost ? "with Semantic Boost." : "on word overlap.")
      + (dupes ? ` ${dupes} duplicate line${dupes === 1 ? "" : "s"} skipped.` : ""));
  } catch (e){
    setStatus(`<strong>Something went wrong:</strong> ${esc(e.message)}`);
  } finally {
    busy = false; btn.disabled = false; btn.textContent = "Analyse drift";
  }
}

function render(){
  const {rows, boost} = RESULT;
  $("results").hidden = false;
  const avg = rows.reduce((n, r) => n + r.similarity, 0) / rows.length;
  const close = rows.filter(r => r.drift < 50).length;
  const far = rows.filter(r => r.drift >= 70).length;
  $("tiles").innerHTML = [
    ["Fan-outs", rows.length, "scored against one target", ""],
    ["Average similarity", fmt(avg) + "%", boost ? "word overlap + encoder" : "word overlap only", ""],
    ["Close to intent", close, "drift under 50%", "good"],
    ["Drifted away", far, "drift of 70% or more", far ? "crit" : "good"]
  ].map(([k, v, d, c]) => `<div class="tile ${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");

  const sorted = [...rows].sort((a, b) => b.similarity - a.similarity);
  $("table").innerHTML = `<thead><tr>
      <th>Fan-out query</th><th>Drift band</th><th class="n">Similarity</th><th class="n">Drift</th>
      ${boost ? "<th>Semantic notes</th>" : ""}
    </tr></thead><tbody>${sorted.map(r => `<tr>
      <td class="q">${esc(r.query)}</td>
      <td class="band"><span><i class="sw b-${r.band.key}"></i>${r.band.label}</span></td>
      <td class="n">${fmt(r.similarity)}%</td>
      <td class="n">${fmt(r.drift)}%</td>
      ${boost ? `<td class="notes">${esc(r.note)}</td>` : ""}
    </tr>`).join("")}</tbody>`;
  $("exportBtn").disabled = false;
}

/* ---- the 3D plot (three.js r128 + OrbitControls) ---- */
const P = {ok:false, nodes:[], lines:[]};
function hasWebGL(){
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl") || c.getContext("experimental-webgl")); }
  catch { return false; }
}
function plotNotice(msg){ $("plotnote").textContent = msg; $("plotnote").hidden = false; $("plot").hidden = true; }
function colour(name, fallback){ return new THREE.Color(tok(name) || fallback); }

function initPlot(){
  if (typeof THREE === "undefined"){ plotNotice("The 3D library did not load, so the plot is unavailable. The results table still works."); return; }
  if (!hasWebGL()){ plotNotice("This browser cannot start WebGL, so the 3D plot is unavailable. The results table still works."); return; }
  const canvas = $("plot");
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias:true}); }
  catch { plotNotice("The 3D plot could not start in this browser. The results table still works."); return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
  camera.position.set(5, 3, 5); camera.lookAt(0, 0, 0);
  let controls = null;
  if (THREE.OrbitControls){
    controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = 0.05;
    controls.minDistance = 3; controls.maxDistance = 15;
  }
  scene.add(new THREE.AmbientLight(0xffffff, 0.62));
  const key = new THREE.DirectionalLight(0xffffff, 0.55); key.position.set(5, 8, 6); scene.add(key);
  const fill = new THREE.DirectionalLight(0xffffff, 0.2); fill.position.set(-5, -4, -5); scene.add(fill);
  const target = new THREE.Mesh(new THREE.SphereGeometry(0.3, 32, 32), new THREE.MeshPhongMaterial({shininess:60}));
  target.userData = {isTarget:true};
  scene.add(target);
  Object.assign(P, {ok:true, renderer, scene, camera, controls, target,
    geo:new THREE.SphereGeometry(0.15, 24, 24), ray:new THREE.Raycaster(), mouse:new THREE.Vector2()});
  sizePlot();
  if (window.ResizeObserver) new ResizeObserver(sizePlot).observe($("stage"));
  else window.addEventListener("resize", sizePlot);
  applyPlotTheme();
  canvas.addEventListener("pointermove", onHover);
  canvas.addEventListener("pointerleave", hideTip);
  loop();
}
function sizePlot(){
  const st = $("stage"), w = st.clientWidth, h = st.clientHeight;
  if (!P.ok || !w || !h) return;
  P.renderer.setSize(w, h, false);
  P.camera.aspect = w / h; P.camera.updateProjectionMatrix();
}
function nodeMaterial(c){
  return new THREE.MeshPhongMaterial({color:c, emissive:c.clone().multiplyScalar(0.18), shininess:50});
}
function applyPlotTheme(){
  if (!P.ok) return;
  const bg = colour("--sunk", "#F3EFFA");
  P.scene.background = bg;
  P.scene.fog = new THREE.Fog(bg, 10, 24);
  if (P.grid){ P.scene.remove(P.grid); P.grid.geometry.dispose(); P.grid.material.dispose(); }
  P.grid = new THREE.GridHelper(10, 20, colour("--line-strong", "#CFC3E4"), colour("--line", "#E4DDF0"));
  P.grid.position.y = -2;
  P.scene.add(P.grid);
  P.target.material.color = colour("--ink", "#1A0B32");
  P.nodes.forEach(n => {
    const c = colour(n.userData.band.token, "#6B5F80");
    n.material.color = c; n.material.emissive = c.clone().multiplyScalar(0.18);
  });
  P.lines.forEach(l => { l.material.color = colour(l.userData.token, "#6B5F80"); });
}
function drawPlot(){
  if (!P.ok) return;
  P.nodes.forEach(n => { P.scene.remove(n); n.material.dispose(); });
  P.lines.forEach(l => { P.scene.remove(l); l.geometry.dispose(); l.material.dispose(); });
  P.nodes = []; P.lines = [];
  P.target.userData = {isTarget:true, query:RESULT.target};
  RESULT.rows.forEach(r => {
    const c = colour(r.band.token, "#6B5F80");
    const m = new THREE.Mesh(P.geo, nodeMaterial(c));
    m.position.set(r.pos.x, r.pos.y, r.pos.z);
    m.userData = r;
    P.scene.add(m); P.nodes.push(m);
    const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), m.position.clone()]);
    const l = new THREE.Line(g, new THREE.LineBasicMaterial({color:c, transparent:true, opacity:0.4}));
    l.userData = {token:r.band.token};
    P.scene.add(l); P.lines.push(l);
  });
}
function loop(){
  requestAnimationFrame(loop);
  if (P.controls) P.controls.update();
  if (!REDUCED) P.target.scale.setScalar(1 + Math.sin(Date.now()*0.002)*0.05);
  P.renderer.render(P.scene, P.camera);
}

/* ---- hover tooltip ---- */
function onHover(e){
  const rect = e.currentTarget.getBoundingClientRect();
  P.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  P.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  P.ray.setFromCamera(P.mouse, P.camera);
  const hit = P.ray.intersectObjects([P.target, ...P.nodes])[0];
  if (hit && (hit.object.userData.query)) showTip(e.clientX, e.clientY, hit.object.userData); else hideTip();
}
function showTip(x, y, a){
  const tip = $("tip");
  tip.innerHTML = a.isTarget
    ? `<div class="tq">${esc(a.query)}</div><div class="tb"><i class="sw target"></i>Target query</div>`
    : `<div class="tq">${esc(a.query)}</div>
       <div>Similarity <strong>${fmt(a.similarity)}%</strong> &middot; Drift <strong>${fmt(a.drift)}%</strong></div>
       <div class="tb"><i class="sw b-${a.band.key}"></i>${a.band.label}</div>
       ${a.note ? `<div class="tn">${esc(a.note)}</div>` : ""}`;
  tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  tip.style.left = Math.max(8, x + 15 + w > innerWidth ? x - w - 15 : x + 15) + "px";
  tip.style.top = Math.max(8, y + 15 + h > innerHeight ? y - h - 15 : y + 15) + "px";
}
function hideTip(){ $("tip").hidden = true; }

/* ---- explanation panel, follows the toggle ---- */
function renderCalc(){
  const on = $("useToggle").checked;
  $("calc").innerHTML = `
    <div><h3>1. Jaccard similarity</h3><p>Shared words divided by all distinct words in both queries. ${on ? "40% of the word-overlap score." : "40% of the score."}</p></div>
    <div><h3>2. Word coverage</h3><p>How much of the target&rsquo;s vocabulary appears in the fan-out. 30%.</p></div>
    <div><h3>3. Character 3-gram cosine</h3><p>Catches close word forms such as &ldquo;running&rdquo; and &ldquo;runner&rdquo;. 30%.</p></div>
    ${on
      ? `<div><h3>4. Semantic Boost<span class="tag">On</span></h3><p>Universal Sentence Encoder cosine &times; 100 (below zero counts as 0). Final = word overlap &times; 0.4 + encoder &times; 0.6.</p></div>`
      : `<div><h3>4. Final score</h3><p>(Jaccard &times; 0.4 + coverage &times; 0.3 + 3-gram &times; 0.3) &times; 100. Drift = 100 &minus; similarity.</p></div>`}`;
  $("calcNote").innerHTML = on
    ? "<p><strong>Why the encoder helps:</strong> it scores meaning, not wording, so &ldquo;footwear&rdquo; sits close to &ldquo;shoes&rdquo;. It runs in this tab; your queries are not sent anywhere.</p>"
      + "<p><strong>Reading boosted scores:</strong> off-topic queries still share a little meaning in the encoder (a cosine of about 0.2), so an unrelated fan-out lands at around 85&ndash;90% drift rather than 100%. Close rewordings of the target usually stay under 35%.</p>"
    : "<p><strong>Tip:</strong> switch on Semantic Boost to catch synonyms and context that word overlap misses. Words shorter than three letters are ignored.</p>";
}

/* ---- CSV in and out ---- */
function parseCSV(text){
  text = text.replace(/^﻿/, "");
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
  const head = (rows.shift() || []).map(h => h.trim());
  return {head, rows:rows.filter(r => r.some(v => v.trim() !== ""))};
}
const pickIdx = (head, names) => head.findIndex(h => names.includes(h.trim().toLowerCase()));
const cell = v => typeof v === "number" ? fmt(v) : `"${String(v??"").replace(/"/g,'""')}"`;
function toCSV(rows, boost){
  const head = ["Target Query","Query Fan-Out","Similarity %","Drift %","Drift Level"].concat(boost ? ["Semantic Notes"] : []);
  return [head.map(cell).join(",")].concat(rows.map(r =>
    [r.target, r.query, r.similarity, r.drift, r.band.csv].concat(boost ? [r.note] : []).map(cell).join(","))).join("\n");
}
async function offerFile(filename, text, mime){
  const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(()=>null) : null;
  if (api){ try { await api.save({filename, data:text}); return "saved"; }
    catch(e){ return e && e.code === "declined" ? "declined" : "failed"; } }
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type:mime}));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000); return "saved";
}

$("exportBtn").onclick = async () => {
  if (!RESULT) return;
  await offerFile("semantic-drift-analysis.csv", toCSV(RESULT.rows, RESULT.boost), "text/csv");
};

let BULK = null;
$("csvUpload").onchange = async e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  const st = $("bulkStatus"), prog = $("bulkProg");
  $("bulkAgain").hidden = true; BULK = null;
  let parsed;
  try { parsed = parseCSV(await f.text()); }
  catch { st.innerHTML = "<strong>That file could not be read as CSV.</strong>"; return; }
  const {head, rows} = parsed;
  if (head.length < 2){ st.innerHTML = "<strong>The CSV needs two columns:</strong> Target Query and Query Fan-Outs."; return; }
  let ti = pickIdx(head, ["target query","target","target_query","query"]);
  let fi = pickIdx(head, ["query fan-outs","query fan-out","query fanouts","fan-outs","fan-out","fanouts","fanout","query_fan_outs"]);
  if (ti < 0 || fi < 0 || ti === fi){ ti = 0; fi = 1; }
  const pairs = rows.map(r => [(r[ti]||"").trim(), (r[fi]||"").trim()]).filter(([a, b]) => a && b);
  if (!pairs.length){ st.innerHTML = "<strong>No complete query pairs found.</strong> Every row needs a target and a fan-out."; return; }

  let boost = $("useToggle").checked, vecs = null, warn = "";
  prog.hidden = false; prog.value = 0;
  try {
    if (boost){
      st.textContent = useModel ? "Embedding queries…" : "Loading the sentence encoder…";
      try {
        vecs = await embedTexts(pairs.flat(), (done, total) => {
          prog.value = Math.round(done / total * 100);
          st.textContent = `Embedding queries… ${done.toLocaleString()} of ${total.toLocaleString()}`;
        });
      } catch (err){
        boost = false;
        warn = `<strong>The sentence encoder did not load (${esc(err.message)}).</strong> Scored on word overlap only. `;
      }
    }
    const out = pairs.map(([target, query]) => ({target, query, ...score(target, query, vecs)}));
    BULK = {rows:out, boost};
    prog.value = 100;
    const saved = await offerFile("semantic-drift-bulk-analysis.csv", toCSV(out, boost), "text/csv");
    const skipped = rows.length - pairs.length;
    st.innerHTML = warn + `Processed <strong>${out.length.toLocaleString()}</strong> query pair${out.length === 1 ? "" : "s"}`
      + (boost ? " with Semantic Boost" : "")
      + (skipped ? `, skipped ${skipped} incomplete row${skipped === 1 ? "" : "s"}` : "")
      + (saved === "saved" ? ". The download has started." : ".");
    $("bulkAgain").hidden = false;
  } catch (err){
    st.innerHTML = `<strong>Error processing the CSV:</strong> ${esc(err.message)}`;
  } finally {
    setTimeout(() => { prog.hidden = true; }, 600);
  }
};
$("bulkAgain").onclick = async () => {
  if (BULK) await offerFile("semantic-drift-bulk-analysis.csv", toCSV(BULK.rows, BULK.boost), "text/csv");
};

/* ---- wiring ---- */
$("analyzeBtn").onclick = analyse;
$("target").addEventListener("keydown", e => { if (e.key === "Enter") analyse(); });
$("useToggle").onchange = () => {
  renderCalc();
  const on = $("useToggle").checked;
  if (on && !useModel){
    setStatus("Loading the sentence encoder in the background…");
    loadUSE()
      .then(() => { if (!busy) setStatus("Encoder ready. Press Analyse drift to rescore with Semantic Boost."); })
      .catch(e => { if (!busy) setStatus(`<strong>The sentence encoder did not load:</strong> ${esc(e.message)}`); });
  } else if (RESULT && RESULT.boost !== on && !busy){
    setStatus("Press Analyse drift to rescore.");
  }
};
if (window.matchMedia) matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyPlotTheme);
if (window.MutationObserver){
  const mo = new MutationObserver(applyPlotTheme);
  [document.documentElement, ROOT].forEach(el => mo.observe(el, {attributes:true, attributeFilter:["data-theme"]}));
}

initPlot();
renderCalc();
analyse();
