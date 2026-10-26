
const $ = id => document.getElementById(id);
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* ---- settings ---- */
const SHEET_NAMES = [
  "Keyword Categorisation",
  "Topics and Descriptions",
  "Keywords to Topics with sBERT",
  "Keyword Suggestions",
  "Entity Sentiment Data",
  "Semantic Entity Relationships",
  "SERP Features Analysis",
  "Google/YouTube Autosuggest Terms",
  "Query Paths - PAA",
  "Query Paths - Suggested Topics",
  "Bulk Google SERP"
];
const MAX_TOPICS = 3, MAX_BRIEFS = 20, CALLS_PER_BRIEF = 7;
const OPENAI_URL = "https://api.openai.com/v1/chat/completions";
// gpt-3.5-turbo was shut down on 23 Oct 2026; OpenAI names gpt-5.6-terra as its replacement.
// Prices are US$ per million tokens (input, output), October 2026.
const MODELS = {"gpt-5.6-terra": {inP: 2, outP: 12}, "gpt-6-luna": {inP: 0.1, outP: 0.5}};
const EST_IN = 350, EST_OUT = 600;

let TOPICS = [], loadedSig = "", BRIEFS = [], RUN = null, LAST = null, CURRENT = -1;

/* ---- small helpers ---- */
function setStatus(id, msg, kind){ const el = $(id); el.textContent = msg; el.className = "hint" + (kind ? " " + kind : ""); }
function extractSpreadsheetId(url){
  const m = String(url||"").match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  return m ? m[1] : null;
}
// Read a column by name: exact header first, then a case- and space-insensitive match.
function val(row, ...names){
  if (!row) return "";
  for (const n of names) if (row[n] !== undefined && row[n] !== "") return String(row[n]);
  const keys = Object.keys(row);
  for (const n of names){
    const k = keys.find(h => h.trim().toLowerCase() === n.trim().toLowerCase());
    if (k && row[k] !== "") return String(row[k]);
  }
  return "";
}
// Sheets returns formatted values, so "1,200" has to become 1200, not 1.
const num = v => parseFloat(String(v??"").replace(/[^0-9.\-]/g, ""));
const lc = s => String(s||"").trim().toLowerCase();
function findColumnName(rows, possibleNames){
  if (!rows.length) return null;
  const headers = Object.keys(rows[0]);
  for (const n of possibleNames){ const f = headers.find(h => lc(h) === lc(n)); if (f) return f; }
  for (const n of possibleNames){ const f = headers.find(h => lc(h).includes(lc(n))); if (f) return f; }
  return headers[0];
}
function dedupeHeaders(head){
  const seen = new Map(), out = [];
  for (const h of head){
    const k = String(h??"").trim();
    if (seen.has(k)){ const n = seen.get(k)+1; seen.set(k,n); out.push(`${k} (${n})`); }
    else { seen.set(k,1); out.push(k); }
  }
  return out;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ---- Google Sheets ---- */
async function fetchSheet(spreadsheetId, sheetName, apiKey, signal){
  const range = `${sheetName}!A:Z`;
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${encodeURIComponent(range)}?key=${encodeURIComponent(apiKey)}`;
  const res = await fetch(url, {signal});
  if (!res.ok){
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.error?.message || msg; } catch {}
    const e = new Error(msg); e.status = res.status; throw e;
  }
  const result = await res.json();
  const values = result.values || [];
  if (!values.length) return [];
  const headers = dedupeHeaders(values[0]);
  return values.slice(1)
    .filter(r => r.some(v => String(v??"").trim() !== ""))
    .map(r => { const o = {}; headers.forEach((h,i) => { if (h) o[h] = r[i] ?? ""; }); return o; });
}
const isMissingTab = e => e && e.status === 400 && /unable to parse range/i.test(e.message||"");
function explainSheetsError(e){
  const m = (e && e.message || "").toLowerCase();
  if (e && e.name === "TypeError") return "Couldn't reach Google Sheets. Check your connection and try again.";
  if (e.status === 400 && m.includes("api key")) return "Google rejected that API key. Check it for stray spaces.";
  if (e.status === 403 && /has not been used|is disabled|service_disabled/.test(m)) return "The Google Sheets API isn't enabled on this key's Cloud project. Enable it, wait a minute, then try again.";
  if (e.status === 403 && /referer|referrer|blocked/.test(m)) return "This key is restricted to other websites or APIs. Allow this site and the Google Sheets API in the key's restrictions.";
  if (e.status === 403) return "Google won't let this key open that sheet. Share it as 'Anyone with the link can view': an API key can't read private sheets.";
  if (e.status === 404) return "No spreadsheet found at that URL. Check the link.";
  if (e.status === 429) return "Google is rate limiting this key. Wait a minute and try again.";
  return e.message || "Google Sheets request failed.";
}
async function fetchAllSheets(spreadsheetId, apiKey, signal){
  const data = {}, found = [], missing = [];
  const results = await Promise.all(SHEET_NAMES.map(async name => {
    try { return {name, rows: await fetchSheet(spreadsheetId, name, apiKey, signal)}; }
    catch(e){ if (isMissingTab(e)) return {name, rows: null}; throw e; }
  }));
  for (const {name, rows} of results){
    if (rows && rows.length){ data[name] = rows; found.push(name); }
    else missing.push(name);
  }
  return {data, found, missing};
}

/* ---- step 1: topics ---- */
async function loadTopics(force){
  const url = $("spreadsheetUrl").value.trim(), key = $("sheetsApiKey").value.trim();
  if (!url || !key){
    if (force) setStatus("sheetStatus", "Add the sheet URL and your Google API key first.", "err");
    return;
  }
  const id = extractSpreadsheetId(url);
  if (!id){ setStatus("sheetStatus", "That doesn't look like a Google Sheets link. It should contain /spreadsheets/d/…", "err"); return; }
  const sig = id + "|" + key;
  if (!force && sig === loadedSig) return;
  $("loadTopics").disabled = true;
  setStatus("sheetStatus", "Loading topics…");
  try {
    const rows = await fetchSheet(id, "Topics and Descriptions", key);
    const topicCol = findColumnName(rows, ["Topic"]);
    const seen = new Set(), list = [];
    rows.forEach(r => {
      const name = String(r[topicCol] ?? "").trim();
      if (name && !seen.has(name)){ seen.add(name); list.push({name, description: val(r, "Description")}); }
    });
    if (!list.length){ setStatus("sheetStatus", "The Topics and Descriptions tab has no topics yet.", "err"); return; }
    const keep = new Set(selectedTopics());
    TOPICS = list; loadedSig = sig;
    renderTopics(keep);
    setStatus("sheetStatus", `Loaded ${list.length} topic${list.length===1?"":"s"}. Pick up to three in step 3.`, "ok");
  } catch(e){
    setStatus("sheetStatus", isMissingTab(e)
      ? "No 'Topics and Descriptions' tab in that sheet. This tool reads the Semantic Keyword Universe template, so the tab names need to match it."
      : explainSheetsError(e), "err");
  } finally {
    $("loadTopics").disabled = false;
  }
}
function renderTopics(keep){
  $("topicList").innerHTML = TOPICS.map((t,i) => `<label class="topic">
      <input type="checkbox" value="${esc(t.name)}" ${keep && keep.has(t.name) ? "checked" : ""}>
      <span><b>${esc(t.name)}</b>${t.description ? `<small title="${esc(t.description)}">${esc(t.description)}</small>` : ""}</span>
    </label>`).join("");
  $("topicList").querySelectorAll("input").forEach(cb => cb.addEventListener("change", onTopicChange));
  onTopicChange();
}
const selectedTopics = () => [...$("topicList").querySelectorAll("input:checked")].map(cb => cb.value);
function onTopicChange(){
  const chosen = selectedTopics();
  // Same 3-topic cap as before; boxes beyond it are disabled rather than refused with an alert.
  $("topicList").querySelectorAll("input").forEach(cb => { cb.disabled = !cb.checked && chosen.length >= MAX_TOPICS; });
  $("topicCount").textContent = `${chosen.length} of ${MAX_TOPICS} picked`;
}

/* ---- estimate ---- */
function briefCount(){ const n = Number($("numBriefs").value); return Number.isInteger(n) ? n : NaN; }
function refreshEstimate(){
  const n = briefCount(), ok = n >= 1 && n <= MAX_BRIEFS;
  const p = MODELS[$("model").value] || MODELS["gpt-5.6-terra"];
  const calls = ok ? n * CALLS_PER_BRIEF : 0;
  const cost = calls * (EST_IN * p.inP + EST_OUT * p.outP) / 1e6;
  $("e-briefs").textContent = ok ? n : "–";
  $("e-calls").textContent = ok ? calls : "–";
  $("e-cost").textContent = !ok ? "–" : cost < 0.01 ? "< $0.01" : "$" + cost.toFixed(2);
}

/* ---- keyword selection ---- */
function potential(row){
  const vol = num(val(row, "Search Volume")) || 0;
  const c = num(val(row, "Competition"));
  const comp = Number.isFinite(c) ? c : 100;   // missing or text competition counts as the worst case
  return vol / (comp + 1);                      // higher volume, lower competition = higher potential
}
function selectKeywordsAndTopics(allSheetData, numBriefs, topics){
  const keywordCat = allSheetData["Keyword Categorisation"] || [];
  const keywordsToTopics = allSheetData["Keywords to Topics with sBERT"] || [];
  if (!keywordCat.length) throw new Error("The Keyword Categorisation tab is missing or empty, and every brief starts from it.");
  if (!topics.length) throw new Error("Pick at least one topic.");

  const hasVolume = r => (num(val(r, "Search Volume")) || 0) > 0;
  const perTopic = Math.floor(numBriefs / topics.length), extra = numBriefs % topics.length;
  const used = new Set(), picked = [];

  topics.forEach((topic, i) => {
    const want = perTopic + (i < extra ? 1 : 0);
    const topicKeywords = keywordsToTopics
      .filter(r => lc(val(r, "Assigned Topic")) === lc(topic) && val(r, "Keywords"))
      .map(r => lc(val(r, "Keywords")));
    const candidates = keywordCat
      .filter(r => { const kw = lc(val(r, "Keyword Text")); return kw && topicKeywords.some(t => t.includes(kw)); })
      .filter(hasVolume)
      .sort((a,b) => potential(b) - potential(a));
    let got = 0;
    for (const r of candidates){
      if (got >= want) break;
      const kw = lc(val(r, "Keyword Text"));
      if (used.has(kw)) continue;
      used.add(kw); picked.push({row: r, topic, filled: false}); got++;
    }
  });

  // Not enough matched keywords: fill with the highest-potential keywords left, topics in turn.
  if (picked.length < numBriefs){
    const remaining = keywordCat
      .filter(r => { const kw = lc(val(r, "Keyword Text")); return kw && !used.has(kw) && hasVolume(r); })
      .sort((a,b) => potential(b) - potential(a));
    let idx = 0;
    for (const r of remaining){
      if (picked.length >= numBriefs) break;
      const kw = lc(val(r, "Keyword Text"));
      if (used.has(kw)) continue;
      used.add(kw);
      picked.push({row: r, topic: topics[idx % topics.length] || "General", filled: true}); idx++;
    }
  }
  return picked.slice(0, numBriefs);
}

/* ---- OpenAI ---- */
function buildPrompts(keyword, keywordData){
  const intent = val(keywordData, "Search Intent") || "informational";
  const format = val(keywordData, "Desired Content Format") || "article";
  return {
    queryAugmentations: `
You are an experienced SEO strategist. For the primary keyword "${keyword}", generate 6–8 related search queries that capture:
  • Long-tail variations
  • Different user intents (informational, commercial, transactional)
  • Persona-specific angles (e.g. "for beginners," "for professionals")
Return your answer as a JSON array of strings, e.g.:
["best ${keyword} tutorial", "affordable ${keyword} service", ...]`,

    querySequences: `
You are a UX researcher. For "${keyword}", map out the top 4 user journeys from awareness → consideration → decision → action. Present as a JSON array of objects with "stage" and "query", e.g.:
[{"stage":"awareness","query":"what is ${keyword}"}, …]`,

    personaAlignment: `
You are a marketing copywriter. Analyze the keyword "${keyword}" and its intent "${intent}". For each persona (novice, expert, decision-maker), describe:
  • Key pain points
  • Tone and style
  • Content format they prefer
Output as a JSON object:`,

    contentFormatRecommendations: `
You are a content strategist. Given the keyword "${keyword}", its intent "${intent}" and preferred format "${format}", recommend 2–3 content formats (e.g. "in-depth guide", "compare/contrast table") with a 1–sentence rationale for each. Return a JSON object:`,

    competitorGapAnalysis: `
You are a competitive analyst. For the keyword "${keyword}", review the top SERP competitors and suggest 4–5 unique angles or missing content gaps that our article could own. Return as a JSON array of strings:`,

    crossTopicNavigation: `
You are an internal linking specialist. For "${keyword}", recommend 3–4 internal linking strategies to related topics in our site to boost dwell time. Return as a JSON object with "anchorText" and "targetUrl" fields:`,

    titlesAndHeadings: `
You are a headline expert. For "${keyword}", generate:
  • 5 click-worthy title variants
  • 8 section headings (H2/H3)
Return as a JSON object with "titles" and "headings" arrays:`
  };
}

async function callOpenAI(prompt, apiKey, model, signal){
  const res = await fetch(OPENAI_URL, {
    method: "POST", signal,
    headers: {"Content-Type": "application/json", "Authorization": `Bearer ${apiKey}`},
    body: JSON.stringify({
      model,
      messages: [{role: "user", content: prompt}],
      reasoning_effort: "none",          // behave like the old non-reasoning model: fast, no hidden reasoning tokens
      max_completion_tokens: 1000
    })
  });
  if (!res.ok){
    let msg = "", code = "";
    try { const b = await res.json(); msg = b.error?.message || ""; code = b.error?.code || b.error?.type || ""; } catch {}
    const e = new Error(msg || `HTTP ${res.status}`); e.status = res.status; e.code = code;
    e.retryAfter = Number(res.headers.get("retry-after")) || 0;
    throw e;
  }
  const json = await res.json();
  return json.choices?.[0]?.message?.content ?? "";
}
const isFatalOpenAI = e => [400,401,403,404].includes(e.status) ||
  (e.status === 429 && /insufficient_quota|exceeded your current quota/i.test(`${e.code} ${e.message}`));
function explainOpenAIError(e, model){
  if (e.status === 401) return "OpenAI rejected that API key. Check it for stray spaces, or create a new one.";
  if (e.status === 404) return `Your OpenAI account can't use ${model}. Try the other model, or check your project's model access.`;
  if (e.status === 429) return "Your OpenAI account is out of credit. Add billing in the OpenAI dashboard, then try again.";
  if (e.status === 403) return "OpenAI refused the request: " + e.message;
  if (e.status === 400) return "OpenAI couldn't process the request: " + e.message;
  return e.message || "OpenAI request failed.";
}
// Models often wrap JSON in a code fence or add a sentence around it.
function parseAI(text){
  const t = String(text||"").trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
  try { return JSON.parse(t); } catch {}
  const start = t.search(/[\[{]/), end = Math.max(t.lastIndexOf("]"), t.lastIndexOf("}"));
  if (start >= 0 && end > start){ try { return JSON.parse(t.slice(start, end + 1)); } catch {} }
  return text;
}
async function generateAIContent(keyword, keywordData, apiKey, model, signal){
  const prompts = buildPrompts(keyword, keywordData);
  const aiResults = {}; let fallbacks = 0;
  await Promise.all(Object.entries(prompts).map(async ([key, prompt]) => {
    for (let attempt = 0; attempt < 2; attempt++){
      try {
        const content = await callOpenAI(prompt, apiKey, model, signal);
        if (!content.trim()) throw Object.assign(new Error("Empty reply"), {status: 0});
        aiResults[key] = parseAI(content);
        return;
      } catch(e){
        if (e.name === "AbortError") throw e;
        if (isFatalOpenAI(e)){ e.fatal = true; throw e; }
        if (attempt === 0){ await sleep(e.status === 429 ? (e.retryAfter * 1000 || 2500) : 1000); continue; }
        console.warn(`OpenAI request failed for ${key}:`, e.message);
      }
    }
    aiResults[key] = getFallbackContent(key, keyword); fallbacks++;
  }));
  return {aiResults, fallbacks};
}
function getFallbackContent(type, keyword){
  const fallbacks = {
    queryAugmentations: [`best ${keyword}`, `${keyword} guide`, `how to ${keyword}`, `${keyword} tips`, `professional ${keyword}`],
    querySequences: [
      {stage: "awareness", query: `what is ${keyword}`},
      {stage: "consideration", query: `best ${keyword} options`},
      {stage: "decision", query: `how to choose ${keyword}`}
    ],
    personaAlignment: {personas: ["beginners", "professionals", "decision-makers"], painPoints: ["lack of knowledge", "time constraints", "budget concerns"]},
    contentFormatRecommendations: {primary: "comprehensive article", secondary: "step-by-step guide", rationale: "matches informational intent"},
    competitorGapAnalysis: [`detailed ${keyword} comparison`, `${keyword} case studies`, `beginner-friendly ${keyword} guide`],
    crossTopicNavigation: {strategy: "topic clustering", suggestions: [`related ${keyword} topics`, `${keyword} tools and resources`]},
    titlesAndHeadings: {
      titles: [`Complete Guide to ${keyword}`, `${keyword}: Everything You Need to Know`, `Best ${keyword} Practices`],
      headings: [`What is ${keyword}?`, `Benefits of ${keyword}`, `How to use ${keyword}`]
    }
  };
  return fallbacks[type] || `Generated content for ${type}`;
}

/* ---- brief assembly ---- */
const isPlain = x => x === null || typeof x !== "object";
function inlineObj(o){
  return Object.entries(o).map(([k,v]) =>
    `${k}: ${Array.isArray(v) && v.every(isPlain) ? v.join(", ") : isPlain(v) ? v : JSON.stringify(v)}`).join(" · ");
}
function toMarkdown(v, depth){
  const pad = "  ".repeat(depth);
  if (Array.isArray(v)) return v.map(x => `${pad}• ${isPlain(x) ? x : Array.isArray(x) ? x.join(", ") : inlineObj(x)}`).join("\n");
  if (v && typeof v === "object") return Object.entries(v).map(([k, val]) => {
    if (isPlain(val)) return `${pad}**${k}:** ${val ?? ""}`;
    if (Array.isArray(val) && val.every(isPlain)) return `${pad}**${k}:** ${val.join(", ")}`;
    return `${pad}**${k}:**\n${toMarkdown(val, depth + 1)}`;
  }).join("\n");
  return pad + String(v);
}
function formatAIContent(content, type){
  if (content === undefined || content === null || content === "") return "AI content not generated.";
  try {
    if (type === "list" && Array.isArray(content))
      return content.map(item => `• ${isPlain(item) ? item : inlineObj(item)}`).join("\n");
    if (type === "sequence" && Array.isArray(content))
      return content.map((item, i) => isPlain(item) ? `${i + 1}. ${item}`
        : `${i + 1}. **${item.stage || "Stage"}:** ${isPlain(item.query) ? (item.query ?? "") : JSON.stringify(item.query)}`).join("\n");
    if (typeof content === "object") return toMarkdown(content, 0);
    return String(content);
  } catch(e){
    console.warn("Error formatting AI content:", e);
    return "Error formatting content.";
  }
}
const textOf = x => isPlain(x) ? String(x ?? "") : (x.title || x.text || x.heading || JSON.stringify(x));
function formatTitles(titles){
  if (!Array.isArray(titles)) return "No titles generated.";
  return titles.map((t, i) => `${i + 1}. ${textOf(t)}`).join("\n");
}
function formatHeadings(headings){
  // Some replies group headings by level: {"H2": [...], "H3": [...]}
  if (headings && !Array.isArray(headings) && typeof headings === "object")
    return Object.entries(headings).flatMap(([lvl, list]) => (Array.isArray(list) ? list : [list]).map(h => `${lvl}: ${textOf(h)}`)).join("\n");
  if (!Array.isArray(headings)) return "No headings generated.";
  return headings.map((h, i) => {
    if (!isPlain(h) && (h.level || h.type)) return `${h.level || h.type}: ${h.text || h.heading || h.title || ""}`;
    const s = textOf(h);
    return /^H[1-6]\b/i.test(s) ? s : `H${(i % 3) + 2}: ${s}`;
  }).join("\n");
}

function buildContentBrief(keyword, keywordData, topic, allSheetData, aiContent){
  const k = keyword || "Unknown";
  const na = name => val(keywordData, name) || "N/A";
  const content = [
    "# Content Brief",
    "",
    "## Primary Keyword Highlights",
    "**Keyword Text:** " + k,
    "**Search Volume:** " + na("Search Volume"),
    "**Competition:** " + na("Competition"),
    "**Short-Tail vs Long-Tail:** " + na("Short-Tail vs Long-Tail"),
    "**Branded vs Non-branded:** " + na("Branded vs Non-branded"),
    "**Search Intent:** " + na("Search Intent"),
    "**Desired Content Format:** " + na("Desired Content Format"),
    "**Desired Content Depth:** " + na("Desired content Depth"),
    "**User Persona:** " + na("User Persona (for query)"),
    "",
    "## Primary Semantic Cluster - Topic and its Description",
    getTopicAndDescription(topic, allSheetData),
    "",
    "## Additional Keyword Suggestions (Related Terms)",
    getKeywordSuggestions(k, allSheetData),
    "",
    "## Core Entity, Sub-entities, and their Attributes",
    getCoreEntityData(keywordData, allSheetData),
    "",
    "## Semantically-Related Entities",
    getSemanticEntityRelationships(keywordData, allSheetData),
    "",
    "## Core Uni-grams and Bi-grams",
    "**Core n-gram:** " + na("Core n-gram"),
    "**Core bi-gram:** " + na("Core bi-gram"),
    "",
    "## Search Intent Mapping",
    getSearchIntentMapping(k, keywordData, allSheetData),
    "",
    "## Related Questions & FAQs",
    getRelatedQuestionsAndFAQs(k, allSheetData),
    "",
    "## Query Augmentations / Query Fan Out",
    formatAIContent(aiContent.queryAugmentations, "list"),
    "",
    "## Query Sequence & Paths",
    formatAIContent(aiContent.querySequences, "sequence"),
    "",
    "## Session & Context Signals",
    getSessionContextSignals(k, allSheetData),
    "",
    "## Persona Alignment",
    formatAIContent(aiContent.personaAlignment, "object"),
    "",
    "## Content Format Recommendations",
    formatAIContent(aiContent.contentFormatRecommendations, "object"),
    "",
    "## SERP Competitors",
    getSERPCompetitors(k, allSheetData),
    "",
    "## Competitor Gap Analysis",
    formatAIContent(aiContent.competitorGapAnalysis, "list"),
    "",
    "## SERP Features",
    getSERPFeatures(k, allSheetData),
    "",
    "## Desired Content Formats",
    getDesiredContentFormats(k, allSheetData),
    "",
    "## Cross-Topic Navigation Plan (Internal Linking)",
    formatAIContent(aiContent.crossTopicNavigation, "object"),
    "",
    "## Title & Heading Suggestions",
    "### Suggested Titles:",
    formatTitles(aiContent.titlesAndHeadings?.titles),
    "",
    "### Suggested Headings:",
    formatHeadings(aiContent.titlesAndHeadings?.headings),
    "",
    "---",
    "Generated on: " + new Date().toLocaleDateString(),
    "Primary Keyword: " + k,
    "Brief ID: " + Date.now()
  ];
  return content.join("\n");
}

function getTopicAndDescription(topic, allSheetData){
  const td = allSheetData["Topics and Descriptions"] || [];
  const assigned = topic || "General";
  const topicCol = findColumnName(td, ["Topic"]);
  const match = td.find(r => topicCol && lc(r[topicCol]) === lc(assigned));
  return `**Topic:** ${assigned}
**Description:** ${match && val(match, "Description") ? val(match, "Description") : "Description not available for this topic"}`;
}
function getKeywordSuggestions(keyword, allSheetData){
  const suggestions = (allSheetData["Keyword Suggestions"] || []).filter(r => lc(val(r, "Seed Keyword")) === lc(keyword));
  if (!suggestions.length) return "No keyword suggestions found for this term.";
  return suggestions
    .filter(r => val(r, "Suggested keyword"))
    .sort((a,b) => (num(val(b, "Search Volume")) || 0) - (num(val(a, "Search Volume")) || 0))
    .slice(0, 10)
    .map(r => `• **${val(r, "Suggested keyword")}** - Volume: ${val(r, "Search Volume") || "N/A"}, Difficulty: ${val(r, "Keyword Difficulty") || "N/A"}, Intent: ${val(r, "Search Intent (main)") || "N/A"}, SERP Features: ${val(r, "SERP features") || "N/A"}`)
    .join("\n") || "No high-opportunity suggestions found.";
}
function entityAttributes(rows){
  let out = "";
  rows.forEach(r => Object.keys(r).forEach(key => {
    if (lc(key) !== "entity" && r[key]) out += `• ${key}: ${r[key]}\n`;
  }));
  return out;
}
function getCoreEntityData(keywordData, allSheetData){
  const core = val(keywordData, "Entity (Core)"), sub = val(keywordData, "Entity (Sub)");
  const sentiment = allSheetData["Entity Sentiment Data"] || [];
  let result = `**Core Entity:** ${core || "N/A"}\n**Sub-entity:** ${sub || "N/A"}\n\n`;
  const coreRows = core ? sentiment.filter(r => lc(val(r, "Entity")) === lc(core)) : [];
  if (coreRows.length) result += "**Core Entity Attributes:**\n" + entityAttributes(coreRows);
  const subRows = sub ? sentiment.filter(r => lc(val(r, "Entity")) === lc(sub)) : [];
  if (subRows.length) result += "\n**Sub-entity Attributes:**\n" + entityAttributes(subRows);
  return result;
}
function generateEntitySearchTerms(coreEntity){
  const words = coreEntity.toLowerCase().split(" ").filter(Boolean);
  const terms = [coreEntity];
  for (let i = 0; i < words.length - 1; i++) terms.push(words[i] + " " + words[i + 1]);          // bigrams
  if (words.length > 2) terms.push(words[0] + " " + words[words.length - 1]);                  // first + last
  for (let i = 0; i < words.length - 2; i++) terms.push(words[i] + " " + words[i + 1] + " " + words[i + 2]); // trigrams
  return [...new Set(terms)];
}
function getSemanticEntityRelationships(keywordData, allSheetData){
  const core = val(keywordData, "Entity (Core)");
  const relationships = allSheetData["Semantic Entity Relationships"] || [];
  if (!core) return "No core entity found.";
  const related = new Set();
  generateEntitySearchTerms(core).forEach(term => {
    const t = term.toLowerCase();
    relationships.forEach(r => {
      const ent = val(r, "Entity"), rel = val(r, "Related Entity");
      if (ent && ent.toLowerCase().includes(t) && rel) related.add(rel);
      if (rel && rel.toLowerCase().includes(t) && ent) related.add(ent);
    });
  });
  if (!related.size) return "No semantic entity relationships found.";
  return [...related].map(e => `• ${e}`).join("\n");
}
function serpRow(keyword, allSheetData){
  return (allSheetData["SERP Features Analysis"] || []).find(r =>
    lc(val(r, "Seed Keyword")) === lc(keyword) || lc(val(r, "Suggested keyword")) === lc(keyword));
}
function getSearchIntentMapping(keyword, keywordData, allSheetData){
  const na = name => val(keywordData, name) || "N/A";
  let result = `**From Keyword Categorisation:**
• Search Intent: ${na("Search Intent")}
• Desired Content Format: ${na("Desired Content Format")}
• Desired Content Depth: ${na("Desired content Depth")}
• User Persona: ${na("User Persona (for query)")}`;
  const s = serpRow(keyword, allSheetData);
  if (s) result += `

**From SERP Features Analysis:**
• Primary Search Intent: ${val(s, "Search Intent (main)") || "N/A"}
• Secondary Search Intent: ${val(s, "Search Intent (secondary)") || "N/A"}
• SERP Features: ${val(s, "SERP features") || "N/A"}
• Desired Content Formats: ${val(s, "Desired Content Formats") || "N/A"}`;
  return result;
}
function getRelatedQuestionsAndFAQs(keyword, allSheetData){
  let result = "";
  const suggestions = (allSheetData["Google/YouTube Autosuggest Terms"] || []).filter(r => lc(val(r, "Seed keyword")) === lc(keyword));
  if (suggestions.length){
    result += "**Auto-suggest Terms:**\n";
    suggestions.forEach(r => { result += `• ${val(r, "Common keyword from suggestions") || "N/A"} (Source: ${val(r, "Source") || "N/A"})\n`; });
  }
  const paa = (allSheetData["Query Paths - PAA"] || []).filter(r => lc(val(r, "Seed keyword")) === lc(keyword));
  if (paa.length){
    result += "\n**People Also Ask:**\n";
    paa.forEach(r => {
      result += `• **Q:** ${val(r, "question") || "N/A"}\n`;
      result += `  **Snippet:** ${val(r, "snippet") || "N/A"}\n`;
      result += `  **Source:** ${val(r, "title") || "N/A"} (${val(r, "link") || "N/A"})\n\n`;
    });
  }
  return result || "No related questions or FAQs found.";
}
function getSessionContextSignals(keyword, allSheetData){
  const rows = (allSheetData["Query Paths - Suggested Topics"] || []).filter(r => lc(val(r, "Keyword/Query")).includes(lc(keyword)));
  if (!rows.length) return "No session context signals found.";
  return rows.map(r => `• **Query:** ${val(r, "query") || "N/A"}\n  **Link:** ${val(r, "link") || "N/A"}\n`).join("\n");
}
function getSERPCompetitors(keyword, allSheetData){
  const rows = (allSheetData["Bulk Google SERP"] || []).filter(r => lc(val(r, "Keyword")) === lc(keyword)).slice(0, 5);
  if (!rows.length) return "No SERP competitor data found.";
  return rows.map((r, i) => `**${i + 1}. ${val(r, "Title") || "N/A"}**\n• URL: ${val(r, "URL") || "N/A"}\n• Description: ${val(r, "Description") || "N/A"}\n`).join("\n");
}
function getSERPFeatures(keyword, allSheetData){
  const s = serpRow(keyword, allSheetData);
  return s ? (val(s, "SERP features") || "No SERP features data available.") : "No SERP features found.";
}
function getDesiredContentFormats(keyword, allSheetData){
  const s = serpRow(keyword, allSheetData);
  return s ? (val(s, "Desired Content Formats") || "No content format data available.") : "No content formats found.";
}

/* ---- run ---- */
function validate(){
  const url = $("spreadsheetUrl").value.trim();
  if (!url) return ["Paste your Google Sheets URL in step 1.", "spreadsheetUrl"];
  if (!extractSpreadsheetId(url)) return ["That doesn't look like a Google Sheets link. It should contain /spreadsheets/d/…", "spreadsheetUrl"];
  if (!$("sheetsApiKey").value.trim()) return ["Add your Google Cloud API key in step 1.", "sheetsApiKey"];
  if (!$("openaiApiKey").value.trim()) return ["Add your OpenAI API key in step 2.", "openaiApiKey"];
  const n = briefCount();
  if (!(n >= 1 && n <= MAX_BRIEFS)) return ["Choose a whole number of briefs between 1 and 20.", "numBriefs"];
  if (!TOPICS.length) return ["Load your topics first: press Load topics in step 1.", "loadTopics"];
  if (!selectedTopics().length) return ["Pick at least one topic.", null];
  return null;
}
function setRunning(on){
  $("generateBtn").disabled = on; $("loadTopics").disabled = on;
  $("stopBtn").hidden = !on; $("prog").hidden = !on;
  if (on) $("prog").value = 0;
}
async function generate(){
  const problem = validate();
  if (problem){ setStatus("status", problem[0], "err"); if (problem[1]) $(problem[1]).focus(); return; }

  const id = extractSpreadsheetId($("spreadsheetUrl").value.trim());
  const sheetsKey = $("sheetsApiKey").value.trim(), openaiKey = $("openaiApiKey").value.trim();
  const model = $("model").value, n = briefCount(), topics = selectedTopics();
  const ctrl = new AbortController(); RUN = ctrl;
  BRIEFS = []; CURRENT = -1;
  LAST = {requested: n, found: [], missing: [], filled: 0, aiOk: 0, aiTotal: 0, model};
  setRunning(true);
  $("results").hidden = true; $("previewWrap").hidden = true;

  try {
    setStatus("status", "Reading your sheet…"); $("prog").value = 10;
    let sheets;
    try { sheets = await fetchAllSheets(id, sheetsKey, ctrl.signal); }
    catch(e){ if (e.name === "AbortError") throw e; throw new Error(explainSheetsError(e)); }
    LAST.found = sheets.found; LAST.missing = sheets.missing;
    $("prog").value = 30;

    setStatus("status", "Picking the highest-potential keywords…");
    const picks = selectKeywordsAndTopics(sheets.data, n, topics);
    if (!picks.length) throw new Error("No keywords with a search volume above zero were found. Check the Keyword Categorisation tab.");
    LAST.filled = picks.filter(p => p.filled).length;
    $("prog").value = 50;

    for (let i = 0; i < picks.length; i++){
      if (ctrl.signal.aborted) break;
      const {row, topic} = picks[i];
      const keyword = val(row, "Keyword Text") || "Unknown";
      setStatus("status", `Writing brief ${i + 1} of ${picks.length}: ${keyword}`);
      const {aiResults, fallbacks} = await generateAIContent(keyword, row, openaiKey, model, ctrl.signal);
      LAST.aiTotal += CALLS_PER_BRIEF; LAST.aiOk += CALLS_PER_BRIEF - fallbacks;
      BRIEFS.push({keyword, topic, row, fallbacks, content: buildContentBrief(keyword, row, topic, sheets.data, aiResults)});
      renderResults();
      $("prog").value = 50 + 40 * (i + 1) / picks.length;
    }

    if (BRIEFS.length){
      setStatus("status", "Packing the ZIP…"); $("prog").value = 95;
      const zipped = await downloadZip();
      $("prog").value = 100;
      const short = BRIEFS.length < n ? ` (${n} requested; the sheet had no more keywords with search volume)` : "";
      setStatus("status", `Done. ${BRIEFS.length} brief${BRIEFS.length === 1 ? "" : "s"} generated${short}.${zipped ? "" : " Download them one by one below."}`, "ok");
      if (CURRENT < 0) showPreview(0);
    }
  } catch(e){
    if (e.name === "AbortError" || ctrl.signal.aborted){
      setStatus("status", `Stopped. ${BRIEFS.length} brief${BRIEFS.length === 1 ? "" : "s"} finished${BRIEFS.length ? "; download them below" : ""}.`);
    } else {
      console.error(e);
      const msg = e.fatal ? explainOpenAIError(e, model) : e.message;
      setStatus("status", BRIEFS.length ? `${msg} ${BRIEFS.length} brief(s) finished before it stopped; they are below.` : msg, "err");
    }
    if (BRIEFS.length){ renderResults(); if (CURRENT < 0) showPreview(0); }
  } finally {
    RUN = null; setRunning(false);
  }
}

/* ---- results ---- */
function renderResults(){
  if (!BRIEFS.length || !LAST){ $("results").hidden = true; return; }
  $("results").hidden = false;
  const topicsCovered = new Set(BRIEFS.map(b => b.topic)).size;
  const aiDone = BRIEFS.length * CALLS_PER_BRIEF, aiOk = aiDone - BRIEFS.reduce((s,b) => s + b.fallbacks, 0);
  const tabsFound = LAST.found.length;
  $("tiles").innerHTML = [
    ["Briefs", BRIEFS.length, `of ${LAST.requested} requested`, BRIEFS.length < LAST.requested ? "warn" : ""],
    ["Topics covered", topicsCovered, "from your picks", ""],
    ["Sheet tabs read", `${tabsFound}/${SHEET_NAMES.length}`, LAST.missing.length ? `${LAST.missing.length} missing or empty` : "all tabs found", LAST.missing.length ? "warn" : "good"],
    ["AI sections", `${aiOk}/${aiDone}`, aiOk === aiDone ? `all from ${LAST.model}` : "some used template text", aiOk === aiDone ? "good" : "warn"]
  ].map(([k,v,d,c]) => `<div class="tile ${c}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${esc(d)}</div></div>`).join("");

  const notes = [];
  if (LAST.missing.length) notes.push(`<p><strong>Missing or empty tabs:</strong> ${esc(LAST.missing.join(", "))}. The sections that draw on them say nothing was found.</p>`);
  if (LAST.filled) notes.push(`<p><strong>${LAST.filled} keyword${LAST.filled === 1 ? "" : "s"} filled the gap.</strong> Your topics didn't have enough matched keywords in the Keywords to Topics with sBERT tab, so the next highest-potential keywords were added and given your topics in turn.</p>`);
  if (aiOk < aiDone) notes.push(`<p><strong>${aiDone - aiOk} AI section${aiDone - aiOk === 1 ? "" : "s"} used template text</strong> because OpenAI didn't answer after a retry. Those sections are generic placeholders; regenerate if you need them.</p>`);
  $("notes").innerHTML = notes.length ? `<div class="keynote warn">${notes.join("")}</div>` : "";

  $("briefTable").innerHTML = `<thead><tr>
      <th class="n">#</th><th>Keyword</th><th>Topic</th><th class="n">Volume</th><th class="n">Competition</th>
      <th>Intent</th><th class="n">Brief</th>
    </tr></thead><tbody>${BRIEFS.map((b, i) => `<tr${i === CURRENT ? ' aria-current="true"' : ""}>
      <td class="n">${i + 1}</td>
      <td class="canon">${esc(b.keyword)}</td>
      <td><span class="kind">${esc(b.topic)}</span></td>
      <td class="n">${esc(val(b.row, "Search Volume") || "–")}</td>
      <td class="n">${esc(val(b.row, "Competition") || "–")}</td>
      <td class="muted">${esc(val(b.row, "Search Intent") || "–")}</td>
      <td class="act"><button class="ghost sm" data-view="${i}">Preview</button><button class="ghost sm" data-dl="${i}">.txt</button></td>
    </tr>`).join("")}</tbody>`;
  $("briefTable").querySelectorAll("[data-view]").forEach(b => b.onclick = () => showPreview(+b.dataset.view));
  $("briefTable").querySelectorAll("[data-dl]").forEach(b => b.onclick = () => downloadOne(+b.dataset.dl));
}
function showPreview(i){
  const b = BRIEFS[i]; if (!b) return;
  CURRENT = i;
  $("previewWrap").hidden = false;
  $("previewTitle").textContent = `Preview: ${b.keyword}`;
  $("preview").textContent = b.content;
  $("briefTable").querySelectorAll("tbody tr").forEach((tr, j) => tr.toggleAttribute("aria-current", j === i));
  $("briefTable").querySelectorAll("tbody tr[aria-current]").forEach(tr => tr.setAttribute("aria-current", "true"));
}

/* ---- export ---- */
async function offerFile(filename, data, mime){
  const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(() => null) : null;
  if (api){
    try { await api.save({filename, data}); return "saved"; }
    catch(e){ if (e && e.code === "declined") return "declined"; }
  }
  const blob = data instanceof Blob ? data : new Blob([data], {type: mime});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  return "saved";
}
const safeName = s => String(s || "").replace(/[\\/:*?"<>|\u0000-\u001f]+/g, "-").replace(/\s+/g, " ").trim().slice(0, 80);
function briefFilenames(){
  const used = new Map();
  return BRIEFS.map(b => {
    const base = `Content brief - ${safeName(b.keyword)} - ${safeName(b.topic)}`;
    const k = base.toLowerCase(), c = (used.get(k) || 0) + 1; used.set(k, c);
    return (c > 1 ? `${base} (${c})` : base) + ".txt";
  });
}
async function downloadZip(){
  if (!BRIEFS.length) return false;
  if (typeof JSZip === "undefined"){
    setStatus("status", "The ZIP library didn't load (a blocker or the network). Download the briefs one by one from the table.", "err");
    return false;
  }
  const zip = new JSZip(), names = briefFilenames();
  BRIEFS.forEach((b, i) => zip.file(names[i], b.content));
  const blob = await zip.generateAsync({type: "blob"});
  const r = await offerFile(`Content_Briefs_${new Date().toISOString().slice(0, 10)}.zip`, blob, "application/zip");
  return r === "saved";
}
async function downloadOne(i){
  if (!BRIEFS[i]) return;
  await offerFile(briefFilenames()[i], BRIEFS[i].content, "text/plain");
}

/* ---- wiring ---- */
$("loadTopics").onclick = () => loadTopics(true);
["spreadsheetUrl", "sheetsApiKey"].forEach(id => $(id).addEventListener("change", () => loadTopics(false)));
["numBriefs", "model"].forEach(id => { $(id).addEventListener("input", refreshEstimate); $(id).addEventListener("change", refreshEstimate); });
$("generateBtn").onclick = generate;
$("stopBtn").onclick = () => { if (RUN){ RUN.abort(); setStatus("status", "Stopping…"); } };
$("dlZip").onclick = async () => { if (await downloadZip()) setStatus("status", "ZIP downloaded.", "ok"); };
$("dlOne").onclick = () => downloadOne(CURRENT);
refreshEstimate();
