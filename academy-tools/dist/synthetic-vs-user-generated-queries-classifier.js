
/* ==== CORE START ====
   Pure feature, scoring, model and analysis code: no DOM in here. The training scripts in
   academy-tools/training/synthetic-classifier/ cut this block out of this file and run it in Node,
   so the model is trained on exactly the features the tool computes. */
const CORE = (() => {
"use strict";
const NLP = (typeof nlp === "function") ? nlp : null;

/* ---------- Python-compatible text helpers (the notebooks are Python) ---------- */
// Python 3 str patterns treat \b, \w and \d as Unicode-aware; JavaScript's are ASCII-only.
const WCH = "[\\p{L}\\p{N}_]";
const WB = `(?:(?<=${WCH})(?!${WCH})|(?<!${WCH})(?=${WCH}))`;
function pyre(src, flags = "") {
  const out = src.replace(/\\b/g, WB).replace(/\\w/g, WCH).replace(/\\d/g, "\\p{Nd}");
  return new RegExp(out, flags.includes("u") ? flags : flags + "u");
}
const pySplit = s => String(s).split(/\s+/).filter(Boolean);           // str.split()
const pyLen = s => [...String(s)].length;                                // len() counts code points
const isUpperCh = c => c !== c.toLowerCase() && c === c.toUpperCase();   // str.isupper() on one char
const isCased = c => c.toLowerCase() !== c.toUpperCase();
function pyTitle(s) {                                                   // str.title()
  let out = "", prev = false;
  for (const c of s) { out += prev ? c.toLowerCase() : c.toUpperCase(); prev = isCased(c); }
  return out;
}
const clamp01 = x => Math.max(0, Math.min(1, x));
function countRe(rx, s) {
  rx.lastIndex = 0; let n = 0, m;
  while ((m = rx.exec(s))) { n++; if (m[0] === "") rx.lastIndex++; }
  return n;
}
function confidence(score, thr, hi, mid) {
  const d = Math.abs(score - thr);
  return d > hi ? "high" : d > mid ? "medium" : "low";
}

/* =====================================================================================
   Notebook 1: rule-based heuristics (ported line by line)
   ===================================================================================== */
const QUESTION_STARTERS = ["what", "how", "why", "when", "where", "which", "who", "is", "are", "can", "does", "do", "should"];
const startsWithQuestion = ql => QUESTION_STARTERS.some(w => ql.startsWith(w + " "));

function nb1Length(query) {
  const wc = pySplit(query).length;
  if (wc <= 3) return 0.1;
  if (wc <= 5) return 0.25;
  if (wc <= 12) return 0.7;
  if (wc <= 20) return 0.6;
  return 0.3;
}

const RX_ARTICLES = pyre("\\b(a|an|the)\\b", "g");
const RX_PREPS_NB1 = pyre("\\b(for|with|about|between|from|into|during|without)\\b", "g");
function nb1Structure(query) {
  let score = 0.0;
  const ql = query.toLowerCase().trim();
  if (startsWithQuestion(ql)) score += 0.3;
  const articles = countRe(RX_ARTICLES, ql);
  if (articles >= 1) score += 0.15;
  if (articles >= 2) score += 0.1;
  const preps = countRe(RX_PREPS_NB1, ql);
  if (preps >= 1) score += 0.15;
  if (preps >= 2) score += 0.1;
  const t = query.trim();
  if (t.endsWith("?") || t.endsWith(".")) score += 0.15;
  if (ql === t && !/[.?!,;:]/.test(query)) score -= 0.1;
  return clamp01(score);
}

// The five query-variant families Notebook 1 has text patterns for, in its order and weights.
const NB1_TYPES = [
  {key: "comparative", add: 0.25, pats: ["\\bvs\\.?\\b", "\\bversus\\b", "\\bcompared to\\b", "\\bcomparison\\b",
    "\\bdifference between\\b", "\\b\\w+ or \\w+\\b", "\\bbetter than\\b", "\\balternatives? to\\b", "\\bpros and cons\\b"]},
  {key: "specialization", add: 0.25, pats: ["\\bbest .+ for\\b", "\\btop .+ for\\b", "\\b\\w+ for (small|large|enterprise|startup|beginner)",
    "\\baffordable\\b", "\\bbudget[- ]friendly\\b", "\\b(enterprise|professional|beginner)[- ](?:grade|level)\\b"]},
  {key: "implicit", add: 0.2, pats: ["\\bhow much does .+ cost\\b", "\\bpricing\\b", "\\breviews?\\b", "\\bpros and cons\\b",
    "\\bis .+ worth\\b", "\\bsafety\\b", "\\breliability\\b", "\\bside effects\\b", "\\brisks? of\\b"]},
  {key: "follow_up", add: 0.15, pats: ["^how (to|do|does|can|should)", "^what (happens|is the|are the)",
    "^why (does|do|is|are|should)", "^when (should|to|is the best)"]},
  {key: "generalization", add: 0.15, pats: ["\\b(types? of|categories of|kinds? of)\\b",
    "\\b(overview|guide|introduction|basics|fundamentals)\\b", "\\b(everything you need to know|complete guide|comprehensive)\\b"]}
].map(t => Object.assign(t, {rx: t.pats.map(p => pyre(p))}));
const RX_YEAR = pyre("\\b20(2[4-9]|3[0-9])\\b");

// Hints for the three patent types Notebook 1 has no pattern for. Shown, never scored.
const TYPE_HINTS = {
  equivalent: pyre("\\b(available today|options to consider|most recommended|highest rated|top rated|best rated|well[- ]reviewed|most popular|top picks?)\\b"),
  canonicalization: pyre("\\b(buying guide|definition of|meaning of|explained)\\b"),
  translation: /[^\u0000-\u024F\u2000-\u206F\u20A0-\u20CF]|(?:^|\s)(?:para|por|los|las|und|der|die|das|für|mit|pour|avec|dans|della|per|não|como|qué|quel|wie)(?=\s|$)/iu
};

function nb1Templates(query) {
  const ql = query.toLowerCase().trim();
  let score = 0.0;
  const types = [], matches = {};
  for (const t of NB1_TYPES) {
    for (const rx of t.rx) {
      const m = ql.match(rx);
      if (m) { score += t.add; types.push(t.key); matches[t.key] = m[0]; break; }
    }
  }
  const year = RX_YEAR.test(ql);
  if (year) score += 0.1;
  const hints = [];
  for (const [k, rx] of Object.entries(TYPE_HINTS)) { const m = query.match(rx); if (m) hints.push([k, m[0].trim()]); }
  return {score: clamp01(score), types, matches, year, hints};
}

const FUNCTION_WORDS = new Set(["a", "an", "the", "is", "are", "was", "were", "for", "to", "in", "on", "at", "by", "with", "from", "of"]);
const RX_ABBREV_NB1 = pyre("\\b(govt|dept|mgmt|dev|impl|config|admin|auth|bc|b/c|w/|w/o|tbh|imo|fwiw|lmk|idk|rn)\\b", "g");
function nb1Messiness(query) {
  let score = 0.0;
  const q = query.trim();
  if (q.includes("  ")) score += 0.2;
  const words = pySplit(q);
  if (words.length >= 2) {
    const ratio = words.filter(w => FUNCTION_WORDS.has(w.toLowerCase())).length / words.length;
    if (ratio < 0.1 && words.length <= 6) score += 0.3;
  }
  if (countRe(RX_ABBREV_NB1, q.toLowerCase()) > 0) score += 0.25;
  if (q !== q.toLowerCase() && q !== q.toUpperCase() && q !== pyTitle(q)) {
    const first = [...q][0], rest = [...q].slice(1).join("");
    if (!(isUpperCh(first) && rest === rest.toLowerCase())) score += 0.1;
  }
  if (/[{}|\\<>]/.test(q)) score += 0.2;
  if (words.length === 1) score += 0.4;
  return clamp01(score);
}

const FORMAL_MARKERS = new Set(["comprehensive", "implementation", "comparison", "evaluation", "assessment",
  "strategies", "optimization", "integration", "methodology", "considerations", "recommendations", "alternatives",
  "specification", "requirements", "functionality", "scalability", "reliability", "performance", "efficiency",
  "capabilities", "certification", "compliance", "infrastructure", "architecture", "deployment"]);
const RX_AZ_WORDS = pyre("\\b[a-z]+\\b", "g");
function nb1Vocabulary(query) {
  const words = query.toLowerCase().match(RX_AZ_WORDS) || [];
  if (!words.length) return 0.5;
  const formal = words.filter(w => FORMAL_MARKERS.has(w)).length;
  if (formal >= 2) return 0.8;
  if (formal === 1) return 0.6;
  const avg = words.reduce((s, w) => s + w.length, 0) / words.length;
  if (avg > 7) return 0.6;
  if (avg > 5.5) return 0.45;
  if (avg < 4) return 0.2;
  return 0.35;
}

const NB1_WEIGHTS = {length: 0.20, structure: 0.20, template: 0.25, messiness: 0.20, vocabulary: 0.15};
function nb1(query) {
  const L = nb1Length(query), S = nb1Structure(query), T = nb1Templates(query);
  const H = nb1Messiness(query), V = nb1Vocabulary(query);
  const score = NB1_WEIGHTS.length * L + NB1_WEIGHTS.structure * S + NB1_WEIGHTS.template * T.score +
    NB1_WEIGHTS.messiness * (1.0 - H) + NB1_WEIGHTS.vocabulary * V;
  return {score, signals: {length: L, structure: S, template: T.score, messiness: H, vocabulary: V},
    types: T.types, matches: T.matches, year: T.year, hints: T.hints, wordCount: pySplit(query).length};
}

/* =====================================================================================
   Notebook 2: entity and linguistic features. spaCy and textstat are Python-only, so POS tags and
   entities come from compromise, mapped onto spaCy's tag and entity names, and the readability
   formula is reimplemented with a rule-based syllable counter.
   ===================================================================================== */
const CLOSED_POS = {
  a: "DET", an: "DET", the: "DET", some: "DET", any: "DET", all: "DET", each: "DET", every: "DET",
  both: "DET", either: "DET", neither: "DET", another: "DET", no: "DET",
  for: "ADP", in: "ADP", with: "ADP", under: "ADP", of: "ADP", on: "ADP", at: "ADP", by: "ADP", from: "ADP",
  into: "ADP", onto: "ADP", about: "ADP", between: "ADP", without: "ADP", during: "ADP", over: "ADP", after: "ADP",
  before: "ADP", through: "ADP", against: "ADP", across: "ADP", near: "ADP", around: "ADP", along: "ADP",
  among: "ADP", within: "ADP", toward: "ADP", towards: "ADP", upon: "ADP", via: "ADP", per: "ADP", than: "ADP",
  vs: "ADP", "vs.": "ADP", versus: "ADP", out: "ADP", up: "ADP", down: "ADP", off: "ADV", like: "ADP",
  and: "CCONJ", or: "CCONJ", but: "CCONJ", nor: "CCONJ", "&": "CCONJ", plus: "CCONJ",
  how: "SCONJ", when: "SCONJ", where: "SCONJ", why: "SCONJ", if: "SCONJ", because: "SCONJ", while: "SCONJ",
  although: "SCONJ", though: "SCONJ", whether: "SCONJ", unless: "SCONJ", since: "SCONJ",
  what: "PRON", which: "PRON", who: "PRON", whom: "PRON", whose: "PRON", that: "PRON", there: "PRON",
  i: "PRON", me: "PRON", my: "PRON", mine: "PRON", you: "PRON", your: "PRON", yours: "PRON", he: "PRON",
  him: "PRON", his: "PRON", she: "PRON", her: "PRON", it: "PRON", its: "PRON", we: "PRON", us: "PRON",
  our: "PRON", they: "PRON", them: "PRON", their: "PRON", myself: "PRON", yourself: "PRON", itself: "PRON",
  themselves: "PRON", someone: "PRON", anyone: "PRON", everyone: "PRON", something: "PRON", anything: "PRON",
  everything: "PRON", nothing: "PRON", somebody: "PRON", anybody: "PRON",
  is: "AUX", are: "AUX", was: "AUX", were: "AUX", be: "AUX", been: "AUX", being: "AUX", am: "AUX",
  can: "AUX", could: "AUX", should: "AUX", would: "AUX", will: "AUX", shall: "AUX", may: "AUX", might: "AUX",
  must: "AUX", not: "PART", "n't": "PART", "'s": "PART", "’s": "PART", much: "ADJ", many: "ADJ", more: "ADJ", most: "ADV"
};
// open-class words compromise often tags as verbs in keyword-style queries, where they are nouns or adjectives
const OPEN_POS = {top: "ADJ", tips: "NOUN", guide: "NOUN", guides: "NOUN", review: "NOUN", reviews: "NOUN", price: "NOUN",
  prices: "NOUN", cost: "NOUN", size: "NOUN", sizes: "NOUN", features: "NOUN", needs: "NOUN", ideas: "NOUN", deals: "NOUN"};
const HAVE_FORMS = new Set(["have", "has", "had"]);
const DEMONSTRATIVES = new Set(["this", "these", "those"]);

function nlpTerms(query) {
  if (!NLP) return null;
  const out = [];
  try {
    const doc = NLP(String(query));
    for (const sent of doc.docs) for (const t of sent) out.push(t);
  } catch (e) { return null; }
  return out;
}
const hasTag = (t, tag) => !!(t && t.tags && t.tags.has(tag));
const termWord = t => (t.text || t.implicit || "").toLowerCase();

function uposFor(terms, i) {
  const t = terms[i], w = termWord(t), next = terms[i + 1];
  if (!t.text && t.implicit) return hasTag(t, "Negative") ? "PART" : (CLOSED_POS[t.implicit.toLowerCase()] || "AUX");
  if (!/[\p{L}\p{N}&]/u.test(w)) return null;                                  // punctuation: skipped, as spaCy's is_punct
  if (w === "to") return next && hasTag(next, "Verb") && !hasTag(next, "Gerund") ? "PART" : "ADP";
  if (w === "does" || w === "did") return "AUX";
  if (w === "do") return i > 0 && hasTag(terms[i - 1], "QuestionWord") ? "AUX" : "VERB";
  if (HAVE_FORMS.has(w)) return next && (hasTag(next, "PastTense") || hasTag(next, "Participle")) ? "AUX" : "VERB";
  if (DEMONSTRATIVES.has(w)) return next && (hasTag(next, "Noun") || hasTag(next, "Adjective")) ? "DET" : "PRON";
  if (hasTag(t, "Hyphenated") && next && hasTag(next, "Hyphenated") && w === "no") return "NOUN";
  if (CLOSED_POS[w]) return CLOSED_POS[w];
  if (OPEN_POS[w]) return OPEN_POS[w];
  if (hasTag(t, "Demonym")) return "ADJ";
  if (hasTag(t, "Auxiliary") || hasTag(t, "Copula") || hasTag(t, "Modal")) return "AUX";
  if (hasTag(t, "Negative")) return "PART";
  if (hasTag(t, "Ordinal")) return "ADJ";
  if (hasTag(t, "Value") || hasTag(t, "Cardinal") || hasTag(t, "NumericValue")) return "NUM";
  if (hasTag(t, "Determiner")) return "DET";
  if (hasTag(t, "Preposition")) return "ADP";
  if (hasTag(t, "Conjunction")) return "CCONJ";
  if (hasTag(t, "Pronoun")) return "PRON";
  if (hasTag(t, "Expression") || hasTag(t, "Interjection")) return "INTJ";
  if (hasTag(t, "Verb")) return "VERB";
  if (hasTag(t, "Adjective")) return "ADJ";
  if (hasTag(t, "Adverb")) return "ADV";
  if (hasTag(t, "ProperNoun") || hasTag(t, "Acronym")) return "PROPN";
  if (hasTag(t, "Noun")) return "NOUN";
  return /\p{N}/u.test(w) ? "NUM" : "NOUN";
}

const RX_YEAR_TOKEN = /^(19|20)\d{2}s?$/;
const LEFTOVER_PROPER = "PERSON";   // spaCy's small model labels most unknown capitalised names PERSON
function nerFor(t, prev, next) {
  const w = t.text || "";
  if (!w) return null;
  if (hasTag(t, "Money") || hasTag(t, "Currency")) return "MONEY";
  if (hasTag(t, "Percent")) return "PERCENT";
  if (RX_YEAR_TOKEN.test(w.replace(/[^\w]/g, "")) || hasTag(t, "Date") || hasTag(t, "Month") || hasTag(t, "WeekDay") || hasTag(t, "Year")) return "DATE";
  if (hasTag(t, "Ordinal")) return "ORDINAL";
  if (hasTag(t, "Value") || hasTag(t, "Cardinal") || hasTag(t, "NumericValue")) return "CARDINAL";
  if (hasTag(t, "Unit")) return "UNIT";
  if (hasTag(t, "Person")) return "PERSON";
  if (hasTag(t, "Organization")) return "ORG";
  if (hasTag(t, "Place")) return "GPE";
  if (hasTag(t, "Demonym")) return "NORP";
  const capital = /^\p{Lu}/u.test(w) && !CLOSED_POS[w.toLowerCase()];
  const proper = hasTag(t, "ProperNoun") || hasTag(t, "Acronym") ||
    (capital && next && (hasTag(next, "ProperNoun") || hasTag(next, "Organization")) && /^\p{Lu}/u.test(next.text || ""));
  if (proper) return prev && hasTag(prev, "Demonym") ? null : LEFTOVER_PROPER;
  return null;
}
function entitiesFrom(terms) {
  const spans = [];
  let cur = null;
  terms.forEach((t, i) => {
    let lab = nerFor(t, terms[i - 1], terms[i + 1]);
    if (lab === "UNIT") lab = cur && (cur.label === "CARDINAL" || cur.label === "QUANTITY" || cur.label === "MONEY") ? cur.label === "MONEY" ? "MONEY" : "QUANTITY" : null;
    const joinable = cur && lab && (cur.label === lab || (lab === "QUANTITY" && cur.label === "CARDINAL")) && !/[,;:]/.test(terms[i - 1].post || "");
    if (joinable) { cur.text += " " + t.text; if (lab === "QUANTITY") cur.label = "QUANTITY"; }
    else if (lab) { cur = {text: t.text, label: lab}; spans.push(cur); }
    else cur = null;
  });
  return spans;
}

function nlpAnalysis(query) {
  const terms = nlpTerms(query);
  if (!terms) return null;
  const pos = [];
  terms.forEach((t, i) => { const p = uposFor(terms, i); if (p) pos.push([t.text || t.implicit, p]); });
  return {pos, ents: entitiesFrom(terms)};
}

/* ---- textstat 0.7: Flesch Reading Ease and syllables (CMU-dictionary lookups replaced by rules) ---- */
const SYL_EXCEPTIONS = {vs: 2, being: 2, seeing: 2, doing: 2, going: 2, every: 3, everyday: 3, everything: 3,
  everyone: 3, business: 2, different: 3, average: 3, area: 3, idea: 3, ideas: 3, create: 2, created: 3,
  science: 2, quiet: 2, diet: 2, real: 1, really: 2, senior: 2, seniors: 2, medium: 3, reactive: 3, safety: 2,
  wireless: 2, movement: 2, lovely: 2, someone: 2, something: 2, sometimes: 2, therefore: 2, whereas: 2,
  recipe: 3, recipes: 3, people: 2, little: 2, simple: 2, table: 2, apple: 2, google: 2, youtube: 2, iphone: 2,
  coupon: 2, coupons: 2, naive: 2, poem: 2, lion: 2, giant: 2, client: 2, clients: 2, via: 2, fuel: 2,
  video: 3, videos: 3, radio: 3, studio: 3, audio: 3, stereo: 3, react: 2, reaction: 3, ohio: 3, hawaii: 3};
function syllables(word) {
  let w = String(word).toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 1;
  if (SYL_EXCEPTIONS[w] !== undefined) return SYL_EXCEPTIONS[w];
  if (w.length <= 3) return 1;
  let core = w;
  if (/[^aeiouy]e$/.test(core) && !/[^aeiouy]le$/.test(core)) core = core.slice(0, -1);
  else if (/[^aeiouy]es$/.test(core) && !/(s|x|z|ch|sh|ce|ge|se|ze)es$/.test(w)) core = core.slice(0, -2);
  else if (/[^aeiouy]ed$/.test(core) && !/[td]ed$/.test(core)) core = core.slice(0, -2);
  let n = (core.match(/[aeiouy]+/g) || []).length;
  n += (core.match(/(?<=[^aeiouy]|^)(?:ia|io|iu|ua|uo|eo|ii)(?!u)/g) || []).length;
  n -= (core.match(/(?:tion|sion|cian|tial|cial|cious|tious|gion|geous|ious$)/g) || []).length;
  n += (core.match(/[aeiou]ings?$/g) || []).length;
  n += (core.match(/[^aeiouy]ier$|[^aeiouy]iest$/g) || []).length;
  n -= (core.match(/[^aeiouy]e(?=(?:ly|ment|ments|ful|less|ness|ty|day|way|proof|board|ware|wear|line|time|life|style|side|bone)$)/g) || []).length;
  if (/^y[aeiou]/.test(core)) n--;
  return Math.max(1, n);
}
const RX_NONCONTRACTION_APOS = /'(?![tsd]|ve|ll|re)/g;
const RX_PUNCT_KEEP_APOS = /[^\p{L}\p{N}_\s']/gu;
function tsWords(text) {                                    // textstat list_words(rm_punctuation=True)
  return String(text).replace(RX_NONCONTRACTION_APOS, "").replace(RX_PUNCT_KEEP_APOS, "").split(/\s+/).filter(Boolean);
}
const RX_SENTENCES = pyre("\\b[^.!?]+[.!?]*", "g");
function tsSentences(text) {
  if (!text.length) return 0;
  const sents = text.match(RX_SENTENCES) || [];
  const ignore = sents.filter(s => tsWords(s).length <= 2).length;
  return Math.max(1, sents.length - ignore);
}
function tsSyllables(text) {
  if (!text) return 0;
  return tsWords(text.toLowerCase()).reduce((s, w) => s + syllables(w), 0);
}
function fleschReadingEase(text) {
  const nw = tsWords(text).length, ns = tsSentences(text);
  const wps = ns ? nw / ns : 0;
  const spw = nw ? tsSyllables(text) / nw : 0;
  if (wps === 0 || spw === 0) return 0.0;
  return 206.835 - 1.015 * wps - 84.6 * spw;
}

const RX_ALPHA_WORDS = pyre("\\b[a-zA-Z]+\\b", "g");
const alphaWords = s => String(s).match(RX_ALPHA_WORDS) || [];

function nb2Entity(query, A) {
  const ents = A ? A.ents : [];
  const wc = pySplit(query).length;
  const types = new Set(ents.map(e => e.label));
  const has = l => types.has(l) ? 1 : 0;
  const hasOrg = has("ORG"), hasProduct = has("PRODUCT"), hasDate = (types.has("DATE") || types.has("CARDINAL")) ? 1 : 0, hasGpe = has("GPE");
  return {entity_count: ents.length, entity_density: ents.length / Math.max(wc, 1), entity_type_count: types.size,
    entity_type_diversity: ents.length ? types.size / Math.max(ents.length, 1) : 0,
    has_org: hasOrg, has_product: hasProduct, has_date: hasDate, has_gpe: hasGpe,
    multi_type_score: Math.min(1.0, (hasOrg + hasProduct + hasDate + hasGpe) / 3.0), entities: ents};
}
function nb2Pos(A) {
  const tags = A ? A.pos.map(p => p[1]) : [];
  if (!tags.length) return {pos_entropy: 0, noun_ratio: 1.0, verb_ratio: 0, adj_ratio: 0, det_ratio: 0, adp_ratio: 0, pos_diversity: 0, n: 0};
  const total = tags.length, c = {};
  tags.forEach(t => { c[t] = (c[t] || 0) + 1; });
  let entropy = 0;
  for (const k in c) { const p = c[k] / total; if (p > 0) entropy -= p * Math.log2(p); }
  const g = k => c[k] || 0;
  return {pos_entropy: entropy, noun_ratio: (g("NOUN") + g("PROPN")) / total, verb_ratio: (g("VERB") + g("AUX")) / total,
    adj_ratio: g("ADJ") / total, det_ratio: g("DET") / total, adp_ratio: g("ADP") / total,
    pos_diversity: Object.keys(c).length / total, n: total};
}
function nb2Lexical(query) {
  const words = alphaWords(query.toLowerCase());
  if (!words.length) return {ttr: 0, avg_word_length: 0, flesch_reading_ease: 50, syllable_ratio: 0, hapax_ratio: 0, long_word_ratio: 0};
  const uniq = new Set(words), freq = {};
  words.forEach(w => { freq[w] = (freq[w] || 0) + 1; });
  return {ttr: uniq.size / words.length,
    avg_word_length: words.reduce((s, w) => s + w.length, 0) / words.length,
    flesch_reading_ease: fleschReadingEase(query),
    syllable_ratio: tsSyllables(query) / Math.max(words.length, 1),
    hapax_ratio: Object.values(freq).filter(n => n === 1).length / Math.max(uniq.size, 1),
    long_word_ratio: words.filter(w => w.length > 7).length / Math.max(words.length, 1)};
}
const NB2_BIGRAMS = new Set(["best for", "how to", "what are", "what is", "compared to", "pros and", "types of", "guide to",
  "vs comparison", "top rated", "how does", "is worth", "how much", "should i", "why is", "why does", "when to",
  "difference between", "alternatives to", "reviews and", "pricing and", "features and"]);
const NB2_TRIGRAMS = new Set(["how to choose", "what is the", "what are the", "best for small", "pros and cons", "how does it",
  "is it worth", "compared to other", "top rated for", "how much does", "everything you need", "complete guide to", "step by step"]);
function nb2Ngram(query) {
  const w = pySplit(query.toLowerCase());
  if (w.length < 2) return {synthetic_bigram_count: 0, synthetic_trigram_count: 0, bigram_score: 0, trigram_score: 0, hits: []};
  const hits = [];
  let bi = 0, tri = 0;
  for (let i = 0; i < w.length - 1; i++) { const b = w[i] + " " + w[i + 1]; if (NB2_BIGRAMS.has(b)) { bi++; hits.push(b); } }
  for (let i = 0; i < w.length - 2; i++) { const t = w[i] + " " + w[i + 1] + " " + w[i + 2]; if (NB2_TRIGRAMS.has(t)) { tri++; hits.push(t); } }
  const nb = w.length - 1, nt = Math.max(w.length - 2, 0);
  return {synthetic_bigram_count: bi, synthetic_trigram_count: tri,
    bigram_score: Math.min(1.0, bi / Math.max(nb, 1) * 3), trigram_score: nt ? Math.min(1.0, tri / Math.max(nt, 1) * 4) : 0, hits};
}
const NB2_WEIGHTS = {entity: 0.20, pos: 0.25, lexical: 0.25, ngram: 0.30};
function nb2(query, A) {
  if (A === undefined) A = nlpAnalysis(query);
  const e = nb2Entity(query, A), p = nb2Pos(A), l = nb2Lexical(query), n = nb2Ngram(query);
  const entity = Math.min(1.0, e.entity_density * 2 + e.multi_type_score * 0.5);
  const pos = Math.min(1.0, p.pos_entropy / 3.5 * 0.4 + (1.0 - p.noun_ratio) * 0.3 + p.verb_ratio * 0.15 + p.det_ratio * 0.15);
  const fre = Math.max(0, Math.min(100, l.flesch_reading_ease));
  const freScore = 1.0 - Math.abs(fre - 55) / 55;
  const lexical = Math.min(1.0, freScore * 0.3 + l.long_word_ratio * 0.3 + Math.min(1.0, l.syllable_ratio / 2.5) * 0.2 + Math.min(1.0, l.avg_word_length / 8) * 0.2);
  const ngram = Math.min(1.0, n.bigram_score * 0.6 + n.trigram_score * 0.4);
  const score = NB2_WEIGHTS.entity * entity + NB2_WEIGHTS.pos * pos + NB2_WEIGHTS.lexical * lexical + NB2_WEIGHTS.ngram * ngram;
  return {score, available: !!A, components: {entity, pos, lexical, ngram}, entity: e, posf: p, lexical: l, ngramf: n,
    tags: A ? A.pos : [], wordCount: pySplit(query).length};
}

/* =====================================================================================
   Notebook 3: embeddings (all-MiniLM-L6-v2). Vectors arrive L2-normalised from the model.
   ===================================================================================== */
// The notebook's domain-agnostic reference corpus, tagged with the patent type each anchor stands for.
const SYN_REFS = [
  ["product A versus product B detailed comparison for buyers", "comparative"],
  ["how does option one compare to option two for everyday use", "comparative"],
  ["top rated alternatives compared by features and price", "comparative"],
  ["pros and cons of the two most popular choices in this category", "comparative"],
  ["which option is better for beginners versus advanced users", "comparative"],
  ["best rated option for small households under a tight budget", "specialization"],
  ["most durable choice for heavy daily use by professionals", "specialization"],
  ["affordable entry-level pick for first-time buyers this year", "specialization"],
  ["top recommendation for large-scale or commercial use cases", "specialization"],
  ["best option for people with specific accessibility needs", "specialization"],
  ["what is the average cost of this product for a typical household", "implicit"],
  ["customer satisfaction ratings for the most popular brands", "implicit"],
  ["what are the common problems reported with this type of product", "implicit"],
  ["how long does this product usually last with regular use", "implicit"],
  ["is the premium version actually worth the extra money", "implicit"],
  ["how to choose the right option for your needs and situation", "follow_up"],
  ["what to look for when evaluating products in this category", "follow_up"],
  ["how to get started with this product as a complete beginner", "follow_up"],
  ["what are the next steps after making an initial purchase", "follow_up"],
  ["how to maintain this product to extend its useful life", "follow_up"],
  ["overview of the main types of products in this category", "generalization"],
  ["complete guide to choosing the right product this year", "generalization"],
  ["different categories of options explained for new buyers", "generalization"],
  ["comprehensive comparison of materials quality and durability", "generalization"],
  ["everything you need to know before buying for the first time", "generalization"],
  ["highest rated and most recommended options available today", "equivalent"],
  ["most reliable and well-reviewed choices for regular use", "equivalent"],
  ["best value picks balancing quality and affordable pricing", "equivalent"],
  ["top performing products preferred by experienced users", "equivalent"],
  ["recommended options for comfort safety and ease of use", "equivalent"]
];
const HUM_REFS = [
  ["amazon", "navigational"], ["google", "navigational"], ["youtube", "navigational"], ["facebook", "navigational"],
  ["reddit", "navigational"], ["ebay", "navigational"], ["walmart", "navigational"], ["chewy", "navigational"],
  ["etsy", "navigational"], ["target", "navigational"],
  ["weather today", "informational"], ["how fix wifi", "informational"], ["recipe pasta", "informational"],
  ["near me", "informational"], ["best price", "informational"], ["reviews", "informational"], ["size chart", "informational"],
  ["how to measure", "informational"], ["what is", "informational"], ["instructions", "informational"], ["vs", "informational"],
  ["cheap", "informational"],
  ["buy online cheap", "transactional"], ["best deals sale", "transactional"], ["free shipping", "transactional"],
  ["discount code", "transactional"], ["where to buy", "transactional"], ["in stock near me", "transactional"],
  ["help me pick something good for my situation on a budget", "conversational"],
  ["whats the best option for someone like me just starting out", "conversational"],
  ["explain the difference simply i dont know much about this", "conversational"],
  ["best chep option", "messy"], ["how to mesure correctly", "messy"], ["wich one better", "messy"],
  ["revews for this brand", "messy"], ["durable and good qualaty", "messy"], ["size guide help", "messy"]
];

function dot(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
function norm(a) { return Math.sqrt(dot(a, a)); }
function meanVec(vs) {
  const out = new Float64Array(vs[0].length);
  for (const v of vs) for (let i = 0; i < v.length; i++) out[i] += v[i];
  for (let i = 0; i < out.length; i++) out[i] /= vs.length;
  return out;
}
function cosine(a, b) { const na = norm(a), nb = norm(b); return na && nb ? dot(a, b) / (na * nb) : 0; }

// refs: {syn:[{text,type,vec}], hum:[{text,type,vec}]} -> adds the centroids the scores need
function prepareRefs(refs) {
  refs.synCentroid = meanVec(refs.syn.map(r => r.vec));
  refs.humCentroid = meanVec(refs.hum.map(r => r.vec));
  refs.corpusCentroid = meanVec(refs.syn.concat(refs.hum).map(r => r.vec));
  return refs;
}
function topKMean(sims, k) { const s = Array.from(sims).sort((a, b) => b - a).slice(0, k); return s.reduce((a, b) => a + b, 0) / s.length; }
function argMax(a) { let j = 0; for (let i = 1; i < a.length; i++) if (a[i] > a[j]) j = i; return j; }

function embCompare(vec, refs) {
  const synSims = refs.syn.map(r => cosine(vec, r.vec)), humSims = refs.hum.map(r => cosine(vec, r.vec));
  const simSyn = cosine(vec, refs.synCentroid), simHum = cosine(vec, refs.humCentroid);
  return {simSyn, simHum, synSims, humSims, top5Syn: topKMean(synSims, 5), top5Hum: topKMean(humSims, 5),
    maxSyn: Math.max(...synSims), maxHum: Math.max(...humSims), iSyn: argMax(synSims), iHum: argMax(humSims)};
}
const NB3_WEIGHTS = {centroid: 0.25, knn: 0.35, max_similarity: 0.25, norm: 0.15};
function nb3(vec, refs) {
  const c = embCompare(vec, refs);
  const centroid = (c.simSyn - c.simHum + 1) / 2;
  const knn = (c.top5Syn - c.top5Hum + 1) / 2;
  const maxs = (c.maxSyn - c.maxHum + 1) / 2;
  const distCenter = 1.0 - cosine(vec, refs.corpusCentroid);
  const normScore = 1.0 - Math.min(1.0, distCenter * 3);
  const score = NB3_WEIGHTS.centroid * centroid + NB3_WEIGHTS.knn * knn + NB3_WEIGHTS.max_similarity * maxs + NB3_WEIGHTS.norm * normScore;
  return {score, signals: {centroid, knn, max_similarity: maxs, norm: normScore},
    nearestSyn: {text: refs.syn[c.iSyn].text, type: refs.syn[c.iSyn].type, sim: c.maxSyn},
    nearestHum: {text: refs.hum[c.iHum].text, type: refs.hum[c.iHum].type, sim: c.maxHum}};
}

/* =====================================================================================
   Notebook 4: the ensemble's feature set (45 features, same names and order as the notebook)
   and a logistic regression on standardised features.
   ===================================================================================== */
const RX_PREPS_NB4 = pyre("\\b(for|with|about|between|from|into|during|without|of|in|on|at|to|by)\\b", "g");
const RX_COMPARATIVE_NB4 = pyre("\\b(vs\\.?|versus|compared to|comparison|difference between|better than|alternatives? to|pros and cons)\\b");
const RX_SPECIALIZATION_NB4 = pyre("\\b(best .+ for|top .+ for|affordable|budget[- ]friendly|enterprise[- ]grade)\\b");
const RX_IMPLICIT_NB4 = pyre("\\b(how much|cost|pricing|reviews?|worth|safety|reliability|side effects|risks?)\\b");
const RX_FOLLOWUP_NB4 = pyre("^(how (to|do|does|can|should)|what (happens|is the|are the)|why (does|do|is|are))");
const RX_GENERAL_NB4 = pyre("\\b(types? of|overview|guide|introduction|basics|comprehensive|complete guide)\\b");
const RX_ABBREV_NB4 = pyre("\\b(govt|dept|mgmt|dev|impl|config|bc|w/|tbh|imo|idk|rn)\\b");
const NB4_BIGRAMS = new Set(["best for", "how to", "what are", "what is", "compared to", "pros and", "types of", "vs comparison",
  "how much", "should i", "difference between", "alternatives to", "pricing and", "features and"]);

const FEATURES_BASE = ["word_count", "char_count", "avg_word_length", "has_question_mark", "has_period", "uppercase_ratio",
  "starts_with_question", "article_count", "preposition_count", "function_word_ratio", "has_year",
  "has_comparative", "has_specialization", "has_implicit", "has_followup", "has_generalization",
  "has_double_space", "has_abbreviation", "is_single_word",
  "entity_count", "entity_density", "entity_type_count", "has_org_entity", "has_product_entity", "has_date_entity",
  "pos_entropy", "noun_ratio", "verb_ratio", "adj_ratio", "det_ratio", "adp_ratio", "pos_diversity",
  "type_token_ratio", "hapax_ratio", "long_word_ratio", "flesch_reading_ease", "syllable_per_word", "synthetic_bigram_hits"];
const FEATURES_EMB = ["emb_sim_synthetic_centroid", "emb_sim_human_centroid", "emb_centroid_diff",
  "emb_top5_syn_sim", "emb_top5_hum_sim", "emb_max_syn_sim", "emb_max_hum_sim"];
const FEATURE_GROUP = {};
FEATURES_BASE.forEach((f, i) => { FEATURE_GROUP[f] = i < 11 ? "structure" : i < 16 ? "pattern" : i < 19 ? "messiness" :
  i < 25 ? "entity" : i < 32 ? "pos" : i < 37 ? "lexical" : "ngram"; });
FEATURES_EMB.forEach(f => { FEATURE_GROUP[f] = "embedding"; });

function nb4Features(query, A, embCmp) {
  if (A === undefined) A = nlpAnalysis(query);
  const ql = query.toLowerCase().trim();
  const words = pySplit(query), aw = alphaWords(ql), wc = words.length;
  const f = {};
  f.word_count = wc;
  f.char_count = pyLen(query);
  f.avg_word_length = aw.reduce((s, w) => s + w.length, 0) / Math.max(aw.length, 1);
  f.has_question_mark = query.includes("?") ? 1 : 0;
  f.has_period = query.trim().endsWith(".") ? 1 : 0;
  f.uppercase_ratio = [...query].filter(isUpperCh).length / Math.max(pyLen(query), 1);
  f.starts_with_question = startsWithQuestion(ql) ? 1 : 0;
  f.article_count = countRe(RX_ARTICLES, ql);
  f.preposition_count = countRe(RX_PREPS_NB4, ql);
  f.function_word_ratio = aw.filter(w => FUNCTION_WORDS.has(w)).length / Math.max(aw.length, 1);
  f.has_year = RX_YEAR.test(query) ? 1 : 0;
  f.has_comparative = RX_COMPARATIVE_NB4.test(ql) ? 1 : 0;
  f.has_specialization = RX_SPECIALIZATION_NB4.test(ql) ? 1 : 0;
  f.has_implicit = RX_IMPLICIT_NB4.test(ql) ? 1 : 0;
  f.has_followup = RX_FOLLOWUP_NB4.test(ql) ? 1 : 0;
  f.has_generalization = RX_GENERAL_NB4.test(ql) ? 1 : 0;
  f.has_double_space = query.includes("  ") ? 1 : 0;
  f.has_abbreviation = RX_ABBREV_NB4.test(ql) ? 1 : 0;
  f.is_single_word = wc === 1 ? 1 : 0;
  const e = nb2Entity(query, A);
  f.entity_count = e.entity_count;
  f.entity_density = e.entity_count / Math.max(wc, 1);
  f.entity_type_count = e.entity_type_count;
  f.has_org_entity = e.has_org;
  f.has_product_entity = e.has_product;
  f.has_date_entity = e.has_date;
  const p = nb2Pos(A);
  if (p.n) {
    f.pos_entropy = p.pos_entropy; f.noun_ratio = p.noun_ratio; f.verb_ratio = p.verb_ratio; f.adj_ratio = p.adj_ratio;
    f.det_ratio = p.det_ratio; f.adp_ratio = p.adp_ratio; f.pos_diversity = p.pos_diversity;
  } else {
    ["pos_entropy", "noun_ratio", "verb_ratio", "adj_ratio", "det_ratio", "adp_ratio", "pos_diversity"].forEach(k => { f[k] = 0; });
  }
  if (aw.length) {
    f.type_token_ratio = new Set(aw).size / aw.length;
    const freq = {}; aw.forEach(w => { freq[w] = (freq[w] || 0) + 1; });
    f.hapax_ratio = Object.values(freq).filter(n => n === 1).length / Math.max(new Set(aw).size, 1);
    f.long_word_ratio = aw.filter(w => w.length > 7).length / aw.length;
  } else { f.type_token_ratio = 0; f.hapax_ratio = 0; f.long_word_ratio = 0; }
  f.flesch_reading_ease = fleschReadingEase(query);
  f.syllable_per_word = tsSyllables(query) / Math.max(aw.length, 1);
  const lw = pySplit(ql);
  let hits = 0;
  for (let i = 0; i < lw.length - 1; i++) if (NB4_BIGRAMS.has(lw[i] + " " + lw[i + 1])) hits++;
  f.synthetic_bigram_hits = hits;
  if (embCmp) Object.assign(f, embFeatures(embCmp));
  return f;
}
function embFeatures(c) {
  return {emb_sim_synthetic_centroid: c.simSyn, emb_sim_human_centroid: c.simHum, emb_centroid_diff: c.simSyn - c.simHum,
    emb_top5_syn_sim: c.top5Syn, emb_top5_hum_sim: c.top5Hum, emb_max_syn_sim: c.maxSyn, emb_max_hum_sim: c.maxHum};
}

const sigmoid = z => z >= 0 ? 1 / (1 + Math.exp(-z)) : Math.exp(z) / (1 + Math.exp(z));
// model: {features, mean, scale, coef, intercept}. Contribution = coefficient x standardised value (log-odds).
function lrScore(model, f) {
  let z = model.intercept;
  const contrib = new Array(model.features.length);
  for (let i = 0; i < model.features.length; i++) {
    const v = f[model.features[i]];
    const s = Number.isFinite(v) ? (v - model.mean[i]) / (model.scale[i] || 1) : 0;
    contrib[i] = model.coef[i] * s;
    z += contrib[i];
  }
  return {p: sigmoid(z), z, contrib};
}

// L2-regularised logistic regression fitted by Newton's method (the same objective as scikit-learn's
// LogisticRegression: 0.5*|w|^2 + C*sum(sample_weight*logloss), intercept not penalised).
function standardise(X) {
  const n = X.length, p = X[0].length, mean = new Array(p).fill(0), scale = new Array(p).fill(0);
  for (const r of X) for (let j = 0; j < p; j++) mean[j] += r[j];
  for (let j = 0; j < p; j++) mean[j] /= n;
  for (const r of X) for (let j = 0; j < p; j++) scale[j] += (r[j] - mean[j]) ** 2;
  for (let j = 0; j < p; j++) { scale[j] = Math.sqrt(scale[j] / n); if (!(scale[j] > 1e-12)) scale[j] = 1; }
  return {mean, scale};
}
function choleskySolve(H, g) {
  const n = g.length, L = H.map(r => r.slice());
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let s = L[i][j];
      for (let k = 0; k < j; k++) s -= L[i][k] * L[j][k];
      if (i === j) L[i][i] = Math.sqrt(Math.max(s, 1e-12)); else L[i][j] = s / L[j][j];
    }
    for (let j = i + 1; j < n; j++) L[i][j] = 0;
  }
  const y = new Array(n);
  for (let i = 0; i < n; i++) { let s = g[i]; for (let k = 0; k < i; k++) s -= L[i][k] * y[k]; y[i] = s / L[i][i]; }
  const x = new Array(n);
  for (let i = n - 1; i >= 0; i--) { let s = y[i]; for (let k = i + 1; k < n; k++) s -= L[k][i] * x[k]; x[i] = s / L[i][i]; }
  return x;
}
function lrFit(Xraw, y, opts = {}) {
  const C = opts.C || 1.0, lambda = 1 / C, n = Xraw.length, p = Xraw[0].length;
  const {mean, scale} = standardise(Xraw);
  const Z = Xraw.map(r => r.map((v, j) => (v - mean[j]) / scale[j]));
  let w = new Array(n).fill(1);
  if (opts.balanced) {
    const n1 = y.reduce((a, b) => a + b, 0), n0 = n - n1;
    w = y.map(v => v ? n / (2 * Math.max(n1, 1)) : n / (2 * Math.max(n0, 1)));
  }
  let beta = new Array(p + 1).fill(0);
  const objective = b => {
    let o = 0;
    for (let i = 0; i < n; i++) {
      let z = b[0]; for (let j = 0; j < p; j++) z += b[j + 1] * Z[i][j];
      o += w[i] * (Math.max(z, 0) - z * y[i] + Math.log1p(Math.exp(-Math.abs(z))));
    }
    let r = 0; for (let j = 1; j <= p; j++) r += b[j] * b[j];
    return o + 0.5 * lambda * r;
  };
  let obj = objective(beta);
  for (let iter = 0; iter < 100; iter++) {
    const g = new Array(p + 1).fill(0), H = Array.from({length: p + 1}, () => new Array(p + 1).fill(0));
    for (let i = 0; i < n; i++) {
      const zi = Z[i];
      let z = beta[0]; for (let j = 0; j < p; j++) z += beta[j + 1] * zi[j];
      const pr = sigmoid(z), r = w[i] * (pr - y[i]), h = w[i] * pr * (1 - pr);
      g[0] += r; for (let j = 0; j < p; j++) g[j + 1] += r * zi[j];
      H[0][0] += h;
      for (let j = 0; j < p; j++) {
        const hj = h * zi[j];
        H[0][j + 1] += hj;
        for (let k = 0; k <= j; k++) H[j + 1][k + 1] += hj * zi[k];
      }
    }
    for (let j = 1; j <= p; j++) { g[j] += lambda * beta[j]; H[j][j] += lambda; }
    for (let j = 0; j <= p; j++) for (let k = j + 1; k <= p; k++) H[j][k] = H[k][j];
    for (let j = 1; j <= p; j++) H[0][j] = H[j][0];
    const d = choleskySolve(H, g);
    let t = 1, next, nobj;
    for (let ls = 0; ls < 30; ls++) {
      next = beta.map((b, j) => b - t * d[j]);
      nobj = objective(next);
      if (nobj <= obj + 1e-12) break;
      t /= 2;
    }
    const step = Math.max(...d.map(v => Math.abs(v * t)));
    beta = next; const improved = obj - nobj; obj = nobj;
    if (step < 1e-8 || improved < 1e-10 * Math.max(1, Math.abs(obj))) break;
  }
  return {features: opts.features || null, mean, scale, coef: beta.slice(1), intercept: beta[0], C, balanced: !!opts.balanced};
}

/* =====================================================================================
   Batch analyses: slot-mask templates (Notebook 1), fan-out batches (Notebook 3)
   ===================================================================================== */
const RX_MASK_YEAR = pyre("\\b(19|20)\\d{2}\\b", "g");
const RX_MASK_PRICE = pyre("\\$\\s?\\d[\\d,]*(?:\\.\\d+)?k?", "g");
const RX_MASK_NUM = pyre("\\b\\d[\\d,]*(?:\\.\\d+)?\\b", "g");
function slotMask(query) {
  let q = query.toLowerCase().trim();
  q = q.replace(RX_MASK_YEAR, "{YEAR}");
  q = q.replace(RX_MASK_PRICE, "{PRICE}");
  q = q.replace(RX_MASK_NUM, "{NUM}");
  return q.replace(/\s+/g, " ").trim();
}
// Counter.most_common order: count descending, ties in order of first appearance.
function templates(queries, minCount = 3) {
  const map = new Map();
  queries.forEach((q, i) => {
    const t = slotMask(q);
    if (!map.has(t)) map.set(t, {template: t, rows: [], first: i});
    map.get(t).rows.push(i);
  });
  const all = [...map.values()];
  const recurring = all.filter(t => t.rows.length >= minCount).sort((a, b) => b.rows.length - a.rows.length || a.first - b.first);
  return {unique: all.length, recurring, countOf: q => (map.get(slotMask(q)) || {rows: []}).rows.length};
}

// Seeded random numbers, so the same list always gives the same baseline and split.
function rng(seed) {
  let a = seed >>> 0;
  return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
function sampleIdx(n, k, rand) {
  const idx = Array.from({length: n}, (_, i) => i);
  for (let i = 0; i < k; i++) { const j = i + Math.floor(rand() * (n - i)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
  return idx.slice(0, k);
}

// yield to the page between chunks of work (a message, unlike a timer, is not throttled in background tabs)
const tick = () => new Promise(r => {
  if (typeof MessageChannel === "function") { const ch = new MessageChannel(); ch.port1.onmessage = () => r(); ch.port2.postMessage(0); }
  else setTimeout(r, 0);
});
// HDBSCAN (as hdbscan / scikit-learn: min_samples = min_cluster_size, excess-of-mass selection, no single
// cluster) on L2-normalised vectors with Euclidean distance. vecs: array of Float32Array.
async function hdbscan(vecs, minClusterSize, hooks = {}) {
  const n = vecs.length, mcs = Math.max(2, minClusterSize | 0), minSamples = mcs;
  const labels = new Int32Array(n).fill(-1);
  if (n < mcs * 2 || n < 4) return {labels, clusters: []};
  const tri = new Float32Array(n * (n - 1) / 2);
  const rowStart = i => i * (2 * n - i - 1) / 2;
  const D = (i, j) => i === j ? 0 : i < j ? tri[rowStart(i) + j - i - 1] : tri[rowStart(j) + i - j - 1];
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    const a = vecs[i], base = rowStart(i) - i - 1;
    for (let j = i + 1; j < n; j++) {
      const b = vecs[j]; let s = 0;
      for (let k = 0; k < a.length; k++) s += a[k] * b[k];
      tri[base + j] = Math.sqrt(Math.max(0, 2 - 2 * s));
    }
    if (Date.now() - t0 > 40 && i % 16 === 0) {
      if (hooks.progress) hooks.progress(0.75 * (1 - ((n - i) * (n - i)) / (n * n)), "Measuring distances");
      await tick();
      if (hooks.stopped && hooks.stopped()) return null;
    }
  }
  // core distance: distance to the min_samples-th nearest point, counting the point itself
  const core = new Float32Array(n), buf = new Float32Array(n - 1), kth = minSamples - 1;
  for (let i = 0; i < n; i++) {
    let c = 0; for (let j = 0; j < n; j++) if (j !== i) buf[c++] = D(i, j);
    core[i] = kth <= 0 ? 0 : quickSelect(buf, kth - 1);
    if (i % 200 === 0) { if (hooks.progress) hooks.progress(0.75 + 0.1 * i / n, "Finding dense regions"); await tick(); }
  }
  // Prim's minimum spanning tree over mutual reachability distance
  const inTree = new Uint8Array(n), best = new Float64Array(n).fill(Infinity), from = new Int32Array(n).fill(-1);
  const edges = [];
  let cur = 0; inTree[0] = 1;
  for (let step = 1; step < n; step++) {
    let next = -1, nd = Infinity;
    for (let j = 0; j < n; j++) {
      if (inTree[j]) continue;
      const mr = Math.max(core[cur], core[j], D(cur, j));
      if (mr < best[j]) { best[j] = mr; from[j] = cur; }
      if (best[j] < nd) { nd = best[j]; next = j; }
    }
    edges.push([from[next], next, nd]);
    inTree[next] = 1; cur = next;
    if (step % 400 === 0) { if (hooks.progress) hooks.progress(0.85 + 0.12 * step / n, "Building the cluster tree"); await tick(); }
  }
  edges.sort((a, b) => a[2] - b[2]);
  // single-linkage hierarchy
  const parent = new Int32Array(n), node = new Int32Array(n), hier = [];
  for (let i = 0; i < n; i++) { parent[i] = i; node[i] = i; }
  const find = x => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  const size = x => x < n ? 1 : hier[x - n][3];
  for (const [a, b, d] of edges) {
    const ra = find(a), rb = find(b);
    const left = node[ra], right = node[rb];
    hier.push([left, right, d, size(left) + size(right)]);
    parent[rb] = ra; node[ra] = n + hier.length - 1;
  }
  const root = 2 * n - 2;
  const bfs = start => {
    const out = []; let q = [start];
    while (q.length) { out.push(...q); q = q.filter(x => x >= n).flatMap(x => [hier[x - n][0], hier[x - n][1]]); }
    return out;
  };
  // condensed tree
  const relabel = new Int32Array(2 * n - 1), ignore = new Uint8Array(2 * n - 1), rows = [];
  relabel[root] = n; let nextLabel = n + 1;
  for (const x of bfs(root)) {
    if (x < n || ignore[x]) continue;
    const [left, right, dist] = hier[x - n];
    const lambda = 1 / Math.max(dist, 1e-6);
    const lc = size(left), rc = size(right);
    const dropAll = sub => { for (const s of bfs(sub)) { if (s < n) rows.push([relabel[x], s, lambda, 1]); ignore[s] = 1; } };
    if (lc >= mcs && rc >= mcs) {
      relabel[left] = nextLabel++; rows.push([relabel[x], relabel[left], lambda, lc]);
      relabel[right] = nextLabel++; rows.push([relabel[x], relabel[right], lambda, rc]);
    } else if (lc < mcs && rc < mcs) { dropAll(left); dropAll(right); }
    else if (lc < mcs) { relabel[right] = relabel[x]; dropAll(left); }
    else { relabel[left] = relabel[x]; dropAll(right); }
  }
  // stability and excess-of-mass selection
  const birth = new Map([[n, 0]]), stab = new Map(), kids = new Map(), up = new Map();
  for (const [p, c, l, s] of rows) {
    if (s > 1) { birth.set(c, l); if (!kids.has(p)) kids.set(p, []); kids.get(p).push(c); }
    up.set(c, p);
  }
  for (const [p, , l, s] of rows) stab.set(p, (stab.get(p) || 0) + (l - (birth.get(p) || 0)) * s);
  const clusterIds = [...birth.keys()].filter(c => c !== n).sort((a, b) => b - a);
  const selected = new Map(clusterIds.map(c => [c, true]));
  for (const c of clusterIds) {
    const sub = (kids.get(c) || []).reduce((s, k) => s + (stab.get(k) || 0), 0);
    if (sub > (stab.get(c) || 0)) { selected.set(c, false); stab.set(c, sub); }
    else {
      const stack = [...(kids.get(c) || [])];
      while (stack.length) { const k = stack.pop(); selected.set(k, false); stack.push(...(kids.get(k) || [])); }
    }
  }
  const chosen = clusterIds.filter(c => selected.get(c)).sort((a, b) => a - b);
  const labelOf = new Map(chosen.map((c, i) => [c, i]));
  for (let i = 0; i < n; i++) {
    let c = up.get(i);
    while (c !== undefined && c !== n) { if (labelOf.has(c)) { labels[i] = labelOf.get(c); break; } c = up.get(c); }
  }
  const clusters = chosen.map((c, i) => ({id: i, members: []}));
  for (let i = 0; i < n; i++) if (labels[i] >= 0) clusters[labels[i]].members.push(i);
  if (hooks.progress) hooks.progress(1, "Done");
  return {labels, clusters};
}
function quickSelect(arr, k) {          // k-th smallest (0-based) of a Float32Array, in place
  let lo = 0, hi = arr.length - 1;
  while (lo < hi) {
    const pivot = arr[(lo + hi) >> 1];
    let i = lo, j = hi;
    while (i <= j) {
      while (arr[i] < pivot) i++;
      while (arr[j] > pivot) j--;
      if (i <= j) { const t = arr[i]; arr[i] = arr[j]; arr[j] = t; i++; j--; }
    }
    if (k <= j) hi = j; else if (k >= i) lo = i; else return arr[k];
  }
  return arr[k];
}

// Notebook 3's centroid cohesion. For unit vectors it equals the length of the mean vector.
function cohesion(vecs, idx) {
  const m = new Float64Array(vecs[idx[0]].length);
  for (const i of idx) { const v = vecs[i]; for (let k = 0; k < m.length; k++) m[k] += v[k]; }
  let s = 0; for (let k = 0; k < m.length; k++) s += (m[k] / idx.length) ** 2;
  return Math.sqrt(s);
}
// Notebook 3's inter-child spread (1 - mean pairwise cosine) follows from cohesion: n(1-c^2)/(n-1).
const nb3Spread = (c, n) => n < 2 ? 0 : n * (1 - c * c) / (n - 1);
const STOP = new Set(["a", "an", "the", "of", "for", "to", "in", "on", "at", "by", "with", "from", "and", "or", "is", "are",
  "be", "do", "does", "can", "how", "what", "which", "why", "when", "where", "i", "my", "your", "it", "this", "that", "vs"]);
const contentWords = q => new Set(pySplit(q.toLowerCase().replace(/[^\p{L}\p{N}\s'-]/gu, " ")).filter(w => !STOP.has(w)));
// Facet spread: how differently the members are worded (1 - mean pairwise word overlap).
function facetSpread(queries, idx, rand) {
  const pick = idx.length > 60 ? sampleIdx(idx.length, 60, rand).map(i => idx[i]) : idx;
  const sets = pick.map(i => contentWords(queries[i]));
  let s = 0, n = 0;
  for (let a = 0; a < sets.length; a++) for (let b = a + 1; b < sets.length; b++) {
    const A = sets[a], B = sets[b]; let inter = 0;
    for (const w of A) if (B.has(w)) inter++;
    const uni = A.size + B.size - inter;
    s += uni ? inter / uni : 1; n++;
  }
  return n ? 1 - s / n : 0;
}
function starReport(vecs, queries, clusters, synFlags, seed = 42) {
  const rand = rng(seed), n = vecs.length, baseCache = new Map();
  const baseline = size => {
    if (!baseCache.has(size)) {
      let s = 0; for (let r = 0; r < 50; r++) s += cohesion(vecs, sampleIdx(n, Math.min(size, n), rand));
      baseCache.set(size, s / 50);
    }
    return baseCache.get(size);
  };
  const out = clusters.map(c => {
    const m = c.members, coh = cohesion(vecs, m), base = baseline(m.length);
    const spread = facetSpread(queries, m, rand);
    const lift = coh - base;
    const nb3s = nb3Spread(coh, m.length), nb3StarBase = base * nb3Spread(base, m.length);
    return {id: c.id, members: m, size: m.length, cohesion: coh, baseline: base, lift, facetSpread: spread,
      score: Math.max(0, lift) * spread, nb3Spread: nb3s, nb3Star: coh * nb3s, nb3StarLift: coh * nb3s - nb3StarBase,
      synShare: synFlags ? m.filter(i => synFlags[i]).length / m.length : null};
  });
  out.sort((a, b) => b.score - a.score || b.lift - a.lift);
  out.forEach((c, r) => { c.rank = r + 1; c.candidate = r === 0 && c.lift > 0 && (c.synShare === null || c.synShare >= 0.5) && c.size >= 3; });
  return out;
}
// 2D projection for the batch map: the first two principal components (power iteration).
function pca2(vecs) {
  const n = vecs.length, d = vecs[0].length, mean = new Float64Array(d);
  for (const v of vecs) for (let k = 0; k < d; k++) mean[k] += v[k] / n;
  const comps = [];
  for (let c = 0; c < 2; c++) {
    let w = new Float64Array(d); const r = rng(7 + c); for (let k = 0; k < d; k++) w[k] = r() - 0.5;
    for (let it = 0; it < 60; it++) {
      const nw = new Float64Array(d);
      for (const v of vecs) {
        let s = 0; for (let k = 0; k < d; k++) s += (v[k] - mean[k]) * w[k];
        for (let k = 0; k < d; k++) nw[k] += s * (v[k] - mean[k]);
      }
      for (const pc of comps) { let s = 0; for (let k = 0; k < d; k++) s += nw[k] * pc[k]; for (let k = 0; k < d; k++) nw[k] -= s * pc[k]; }
      let nn = 0; for (let k = 0; k < d; k++) nn += nw[k] * nw[k]; nn = Math.sqrt(nn) || 1;
      for (let k = 0; k < d; k++) nw[k] /= nn;
      w = nw;
    }
    comps.push(w);
  }
  return vecs.map(v => comps.map(pc => { let s = 0; for (let k = 0; k < d; k++) s += (v[k] - mean[k]) * pc[k]; return s; }));
}

/* =====================================================================================
   Evaluation
   ===================================================================================== */
function confusion(scores, labels, thr) {
  let tp = 0, fp = 0, tn = 0, fn = 0;
  for (let i = 0; i < scores.length; i++) {
    if (labels[i] === null || labels[i] === undefined || !Number.isFinite(scores[i])) continue;
    const p = scores[i] >= thr;
    if (p && labels[i] === 1) tp++; else if (p) fp++; else if (labels[i] === 1) fn++; else tn++;
  }
  return metrics({tp, fp, tn, fn});
}
function metrics(c) {
  const n = c.tp + c.fp + c.tn + c.fn;
  const precision = c.tp + c.fp ? c.tp / (c.tp + c.fp) : 0, recall = c.tp + c.fn ? c.tp / (c.tp + c.fn) : 0;
  return Object.assign(c, {n, accuracy: n ? (c.tp + c.tn) / n : 0, precision, recall,
    f1: precision + recall ? 2 * precision * recall / (precision + recall) : 0});
}
function auc(scores, labels) {
  const pts = [];
  for (let i = 0; i < scores.length; i++) if ((labels[i] === 0 || labels[i] === 1) && Number.isFinite(scores[i])) pts.push([scores[i], labels[i]]);
  const pos = pts.filter(p => p[1] === 1).length, neg = pts.length - pos;
  if (!pos || !neg) return null;
  pts.sort((a, b) => a[0] - b[0]);
  let rankSum = 0;
  for (let i = 0; i < pts.length;) {
    let j = i; while (j < pts.length && pts[j][0] === pts[i][0]) j++;
    const avg = (i + j + 1) / 2;
    for (let k = i; k < j; k++) if (pts[k][1] === 1) rankSum += avg;
    i = j;
  }
  return (rankSum - pos * (pos + 1) / 2) / (pos * neg);
}
function bestThreshold(scores, labels) {
  const pts = [];
  for (let i = 0; i < scores.length; i++) if ((labels[i] === 0 || labels[i] === 1) && Number.isFinite(scores[i])) pts.push([scores[i], labels[i]]);
  const pos = pts.filter(p => p[1] === 1).length;
  if (!pts.length || !pos) return null;
  pts.sort((a, b) => b[0] - a[0]);
  let tp = 0, fp = 0, best = {f1: -1, thr: 0.5};
  for (let i = 0; i < pts.length;) {
    let j = i; while (j < pts.length && pts[j][0] === pts[i][0]) { if (pts[j][1] === 1) tp++; else fp++; j++; }
    const prec = tp / (tp + fp), rec = tp / pos, f1 = prec + rec ? 2 * prec * rec / (prec + rec) : 0;
    if (f1 > best.f1 + 1e-12) best = {f1, thr: pts[i][0]};
    i = j;
  }
  return best;
}
const WC_SCALE = 20;            // word-count baseline: score = min(words, 20) / 20, so 0.5 means 10+ words
const wordCountScore = q => Math.min(pySplit(q).length, WC_SCALE) / WC_SCALE;

/* =====================================================================================
   Input: delimited text, column and label detection
   ===================================================================================== */
function detectDelimiter(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim()).slice(0, 20);
  const count = (l, d) => { let n = 0, q = false; for (const c of l) { if (c === '"') q = !q; else if (c === d && !q) n++; } return n; };
  let best = null, bestScore = 0;
  for (const d of ["\t", ",", ";"]) {
    const cs = lines.map(l => count(l, d));
    const first = cs[0] || 0;
    if (!first) continue;
    const consistent = cs.filter(c => c === first).length / cs.length;
    if (consistent < (d === "\t" ? 0.6 : 0.8)) continue;
    const score = consistent * (d === "\t" ? 1.2 : d === "," ? 1.1 : 1);
    if (score > bestScore) { best = d; bestScore = score; }
  }
  return best;
}
function parseDelimited(text, delim) {
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; }
      else cell += c;
    } else if (c === '"' && cell.trim() === "") { q = true; cell = ""; }
    else if (c === delim) { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; }
    else if (c !== "\r") cell += c;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(v => v.trim() !== ""));
}
const QUERY_HEADERS = ["keyword", "keywords", "query", "queries", "search term", "search terms", "search query", "search_query",
  "term", "terms", "phrase", "phrases", "question", "questions", "prompt", "prompts", "fan-out", "fan-outs", "fanout", "query fan-outs", "top queries"];
const LABEL_HEADERS = ["label", "labels", "type", "class", "category", "source", "origin", "is_synthetic", "synthetic", "y",
  "target", "ground_truth", "ground truth", "truth", "annotation", "kind", "generated_by", "query_type", "query type"];
function mapLabel(v) {
  const s = String(v ?? "").trim().toLowerCase();
  if (!s) return null;
  if (/^(1|1\.0|true|yes|synthetic|synth|ai|llm|bot|machine|generated|fan-?out|s)$/.test(s)) return 1;
  if (/^(0|0\.0|false|no|user|human|real|organic|person|people|u|h)$/.test(s)) return 0;
  if (/(^|[^a-z])(user|human|real|organic|people|person|typed|customer)([^a-z]|$)/.test(s) || /^user[ _-]?generated/.test(s)) return 0;
  if (/(synthetic|synth|llm|(^|[^a-z])ai([^a-z]|$)|gpt|machine|generated|fan-?out|model|bot|artificial)/.test(s)) return 1;
  return null;
}
function labelColumnScore(values) {
  const vals = values.map(v => String(v ?? "").trim()).filter(Boolean);
  if (vals.length < 2) return 0;
  const distinct = new Set(vals.map(v => v.toLowerCase()));
  if (distinct.size > 12) return 0;
  const mapped = vals.map(mapLabel);
  const ok = mapped.filter(m => m !== null).length / vals.length;
  const classes = new Set(mapped.filter(m => m !== null));
  return classes.size === 2 ? ok : 0;
}
// rows: array of arrays. Returns {header, queryCol, labelCol, confident, columns}
function detectColumns(rows) {
  const width = Math.max(...rows.slice(0, 50).map(r => r.length));
  const first = rows[0].map(c => c.trim().toLowerCase());
  const named = first.some(c => QUERY_HEADERS.includes(c) || LABEL_HEADERS.includes(c) || /keyword|query/.test(c));
  const header = width > 1 ? (named || first.every(c => c && !/^-?[\d.,]+$/.test(c))) : /^(keywords?|quer(y|ies)|search terms?|terms?|phrases?)$/.test(first[0] || "");
  const body = header ? rows.slice(1) : rows;
  const names = header ? rows[0].map((c, i) => c.trim() || `Column ${i + 1}`) : Array.from({length: width}, (_, i) => `Column ${i + 1}`);
  let queryCol = -1, confident = false;
  if (header) {
    for (const h of QUERY_HEADERS) { const i = first.indexOf(h); if (i >= 0) { queryCol = i; confident = true; break; } }
    if (queryCol < 0) { const i = first.findIndex(c => /keyword|query/.test(c)); if (i >= 0) { queryCol = i; confident = true; } }
  }
  // spread the sample over the whole file: exports are often sorted, with all of one label first
  const step = Math.max(1, Math.floor(body.length / 600)), sample = body.filter((_, i) => i % step === 0);
  if (queryCol < 0) {
    let best = -1;
    for (let c = 0; c < width; c++) {
      const vals = sample.map(r => (r[c] || "").trim()).filter(Boolean);
      const textual = vals.filter(v => /\p{L}/u.test(v) && !/^-?[\d.,%$€£]+$/.test(v)).length;
      const avgWords = vals.reduce((s, v) => s + pySplit(v).length, 0) / Math.max(vals.length, 1);
      const sc = textual / Math.max(sample.length, 1) + Math.min(avgWords, 6) / 60 - labelColumnScore(vals);
      if (sc > best) { best = sc; queryCol = c; }
    }
    confident = width === 1;
  }
  let labelCol = -1, bestL = 0;
  for (let c = 0; c < width; c++) {
    if (c === queryCol) continue;
    const vals = sample.map(r => r[c]);
    let sc = labelColumnScore(vals);
    if (sc > 0 && header && LABEL_HEADERS.includes(first[c])) sc += 0.5;
    if (sc >= 0.9 && sc > bestL) { bestL = sc; labelCol = c; }
  }
  return {header, names, queryCol, labelCol, confident, width, body};
}

return {
  // notebook 1
  nb1, nb1Length, nb1Structure, nb1Templates, nb1Messiness, nb1Vocabulary, NB1_WEIGHTS, NB1_TYPES, confidence,
  // notebook 2
  nlpAnalysis, nb2, fleschReadingEase, syllables, tsSyllables, NB2_WEIGHTS, hasNLP: () => !!NLP,
  // notebook 3
  SYN_REFS, HUM_REFS, prepareRefs, embCompare, nb3, NB3_WEIGHTS, cosine,
  // notebook 4
  FEATURES_BASE, FEATURES_EMB, FEATURE_GROUP, nb4Features, embFeatures, lrScore, lrFit, standardise, sigmoid,
  // batch analyses
  slotMask, templates, hdbscan, tick, starReport, cohesion, pca2, rng, sampleIdx,
  // evaluation and input
  confusion, metrics, auc, bestThreshold, wordCountScore, WC_SCALE, pySplit,
  detectDelimiter, parseDelimited, detectColumns, mapLabel, labelColumnScore
};
})();
/* ==== CORE END ==== */

/* The shipped ensemble weights (written by training/synthetic-classifier/embed_model.py). */
const SHIPPED_MODEL = /* MODEL-JSON-START */{"version":1,"created":"2026-10-26","note":"Generated queries (Notebook 4's generator plus an extension) and 30% of a labelled test set, split by template family","trained_on":{"rows":2463,"synthetic":1488,"user":975,"by_source":{"extension":1254,"external":796,"notebook4":413}},"sets":{"base":{"features":["word_count","char_count","avg_word_length","has_question_mark","has_period","uppercase_ratio","starts_with_question","article_count","preposition_count","function_word_ratio","has_year","has_comparative","has_specialization","has_implicit","has_followup","has_generalization","has_double_space","has_abbreviation","is_single_word","entity_count","entity_density","entity_type_count","has_org_entity","has_product_entity","has_date_entity","pos_entropy","noun_ratio","verb_ratio","adj_ratio","det_ratio","adp_ratio","pos_diversity","type_token_ratio","hapax_ratio","long_word_ratio","flesch_reading_ease","syllable_per_word","synthetic_bigram_hits"],"mean":[7.16971,43.1275,5.22734,0.0,0.0,0.0202009,0.256192,0.289484,0.928542,0.136422,0.0840438,0.103126,0.0982542,0.101908,0.116525,0.0613073,0.00203004,0.0,0.0174584,0.707674,0.0872039,0.535932,0.0393829,0.0,0.146975,1.68714,0.526198,0.120318,0.0992906,0.0279208,0.102562,0.596567,0.991412,0.990263,0.181248,59.0714,1.67145,0.235079],"scale":[3.51882,20.6628,1.12139,1.0,1.0,0.0498201,0.436529,0.596579,0.94841,0.127768,0.277454,0.304124,0.297658,0.302528,0.320853,0.239893,0.0450103,1.0,0.130972,1.03247,0.124773,0.703385,0.194504,1.0,0.354081,0.799021,0.233939,0.138687,0.118899,0.0568872,0.103985,0.183337,0.0302086,0.0353538,0.187303,35.3652,0.435266,0.514069],"coef":[-6.01916,2.71726,0.514285,0.0,0.0,0.593086,0.266099,0.662209,0.159561,1.12861,1.36575,0.579256,0.238561,-0.201275,0.0356718,0.552356,-0.167455,0.0,-0.200891,0.414217,-1.53501,0.748895,-0.184077,0.0,-0.61464,7.03417,0.419328,-0.533779,-0.385542,-0.896085,-0.738094,-3.70065,0.218526,-0.0607465,0.289417,-0.645447,-0.524701,-0.318462],"intercept":0.1448,"C":1.0},"emb":{"features":["word_count","char_count","avg_word_length","has_question_mark","has_period","uppercase_ratio","starts_with_question","article_count","preposition_count","function_word_ratio","has_year","has_comparative","has_specialization","has_implicit","has_followup","has_generalization","has_double_space","has_abbreviation","is_single_word","entity_count","entity_density","entity_type_count","has_org_entity","has_product_entity","has_date_entity","pos_entropy","noun_ratio","verb_ratio","adj_ratio","det_ratio","adp_ratio","pos_diversity","type_token_ratio","hapax_ratio","long_word_ratio","flesch_reading_ease","syllable_per_word","synthetic_bigram_hits","emb_sim_synthetic_centroid","emb_sim_human_centroid","emb_centroid_diff","emb_top5_syn_sim","emb_top5_hum_sim","emb_max_syn_sim","emb_max_hum_sim"],"mean":[7.16971,43.1275,5.22734,0.0,0.0,0.0202009,0.256192,0.289484,0.928542,0.136422,0.0840438,0.103126,0.0982542,0.101908,0.116525,0.0613073,0.00203004,0.0,0.0174584,0.707674,0.0872039,0.535932,0.0393829,0.0,0.146975,1.68714,0.526198,0.120318,0.0992906,0.0279208,0.102562,0.596567,0.991412,0.990263,0.181248,59.0714,1.67145,0.235079,0.219447,0.1855,0.0339479,0.23776,0.217318,0.295823,0.279654],"scale":[3.51882,20.6628,1.12139,1.0,1.0,0.0498201,0.436529,0.596579,0.94841,0.127768,0.277454,0.304124,0.297658,0.302528,0.320853,0.239893,0.0450103,1.0,0.130972,1.03247,0.124773,0.703385,0.194504,1.0,0.354081,0.799021,0.233939,0.138687,0.118899,0.0568872,0.103985,0.183337,0.0302086,0.0353538,0.187303,35.3652,0.435266,0.514069,0.118258,0.0905707,0.110627,0.0897179,0.0698558,0.110332,0.102988],"coef":[-5.20815,1.75855,0.869586,0.0,0.0,0.500259,0.393675,0.675787,0.0837181,0.71717,1.44912,0.261557,0.218415,-0.425356,-0.0936879,0.397645,-0.161973,0.0,0.046438,0.571576,-1.56394,0.820253,-0.175049,0.0,-0.643589,6.56171,0.401082,-0.74873,-0.620546,-0.677488,-0.442798,-3.44522,0.306184,-0.147057,0.155568,-0.707647,-0.806219,-0.0455852,0.0225757,-0.683633,0.583827,0.52827,0.034104,0.449415,-0.0880229],"intercept":0.0134545,"C":1.0}},"heldout":{"base":{"rows":1653,"accuracy":0.9758,"precision":0.9923,"recall":0.97,"f1":0.9811,"auc":0.9969},"emb":{"rows":1653,"accuracy":0.9679,"precision":0.9913,"recall":0.9588,"f1":0.9748,"auc":0.9969},"word_count":{"k":6,"f1":0.978,"accuracy":0.971,"auc":0.9982}}}/* MODEL-JSON-END */;

/* =====================================================================================
   Interface
   ===================================================================================== */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fx = (v, d = 2) => Number.isFinite(v) ? v.toFixed(d) : "n/a";
const pct = (v, d = 1) => Number.isFinite(v) ? (v * 100).toFixed(d) + "%" : "n/a";
const nf = n => Number(n).toLocaleString("en-GB");
const w100 = v => (Math.max(0, Math.min(1, v)) * 100).toFixed(1) + "%";
const tick = CORE.tick;
const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1/dist/transformers.min.js";
const MODEL_ID = "Xenova/all-MiniLM-L6-v2";
const MAX_ROWS = 20000, CLUSTER_CAP = 6000, PAGE = 500;

const METHODS = {
  ens: {name: "Ensemble model", nb: "NB4", conf: [0.25, 0.1]},
  nb1: {name: "Rule-based heuristics", nb: "NB1", conf: [0.2, 0.1]},
  nb3: {name: "Embeddings", nb: "NB3", conf: [0.15, 0.07]},
  nb2: {name: "Entity & linguistic", nb: "NB2", conf: [0.2, 0.1]},
  wc: {name: "Word count only", nb: "baseline", conf: [0.2, 0.1]}
};
const ORDER = ["ens", "nb1", "nb3", "nb2"];
const TYPE_NAMES = {equivalent: "Equivalent", follow_up: "Follow-up", generalization: "Generalization",
  canonicalization: "Canonicalization", translation: "Language translation", comparative: "Comparative",
  implicit: "Implicit", specialization: "Specialization"};
const PATENT_ORDER = ["equivalent", "follow_up", "generalization", "canonicalization", "translation", "comparative", "implicit", "specialization"];
const KIND_NAMES = {navigational: "navigational", informational: "short informational", transactional: "transactional",
  conversational: "conversational prompt", messy: "typo or messy", data: "from your labels", custom: "your reference"};
const GROUP_NAMES = {structure: "Structure and length", pattern: "Patent-type patterns", messiness: "Messiness",
  entity: "Entities", pos: "Parts of speech", lexical: "Readability and vocabulary", ngram: "Fan-out n-grams", embedding: "Embeddings"};
const FEATURE_NAMES = {word_count: "Word count", char_count: "Characters", avg_word_length: "Average word length",
  has_question_mark: "Question mark", has_period: "Ends with a full stop", uppercase_ratio: "Share of capital letters",
  starts_with_question: "Starts with a question word", article_count: "Articles (a, an, the)", preposition_count: "Prepositions",
  function_word_ratio: "Share of function words", has_year: "Mentions a year 2024-2039", has_comparative: "Comparative pattern",
  has_specialization: "Specialization pattern", has_implicit: "Implicit pattern", has_followup: "Follow-up pattern",
  has_generalization: "Generalization pattern", has_double_space: "Double space", has_abbreviation: "Abbreviation",
  is_single_word: "Single word", entity_count: "Entities", entity_density: "Entities per word", entity_type_count: "Entity types",
  has_org_entity: "Organisation entity", has_product_entity: "Product entity", has_date_entity: "Date or number entity",
  pos_entropy: "Part-of-speech entropy", noun_ratio: "Share of nouns", verb_ratio: "Share of verbs", adj_ratio: "Share of adjectives",
  det_ratio: "Share of determiners", adp_ratio: "Share of prepositions (tagged)", pos_diversity: "Part-of-speech variety",
  type_token_ratio: "Distinct words share", hapax_ratio: "Words used once", long_word_ratio: "Words over 7 letters",
  flesch_reading_ease: "Flesch reading ease", syllable_per_word: "Syllables per word", synthetic_bigram_hits: "Fan-out word pairs",
  emb_sim_synthetic_centroid: "Similarity to synthetic centre", emb_sim_human_centroid: "Similarity to user centre",
  emb_centroid_diff: "Synthetic minus user centre", emb_top5_syn_sim: "5 nearest synthetic", emb_top5_hum_sim: "5 nearest user",
  emb_max_syn_sim: "Nearest synthetic", emb_max_hum_sim: "Nearest user"};

const S = {
  thr: {ens: 0.5, nb1: 0.5, nb2: 0.5, nb3: 0.5, wc: 0.5}, perMethod: false,
  show: {nb1: true, nb2: true, ens: true},
  emb: {on: false, ready: false, loading: null, extractor: null, defaultRefs: null, activeRefs: null, refMode: "default", refRows: null},
  model: {custom: null, useCustom: false},
  list: null, busy: false, stop: false, pending: null,
  filter: "all", sort: "score-desc", shown: PAGE, evalMethod: "ens",
  clusters: null, clBusy: false, clStop: false, clSel: 0, clAll: false, inspect: null
};

/* ---------- method helpers ---------- */
const avail = m => m === "nb3" ? S.emb.on && S.emb.ready : (m === "nb2" || m === "ens") ? CORE.hasNLP() : true;
const visible = m => avail(m) && (m === "nb3" || m === "wc" || S.show[m]);
const shownMethods = () => ORDER.filter(visible);
const primary = () => shownMethods()[0] || "nb1";
function scoreOf(r, m) {
  if (m === "ens") return r.ens ? r.ens.p : NaN;
  if (m === "nb1") return r.nb1.score;
  if (m === "nb2") return r.nb2 ? r.nb2.score : NaN;
  if (m === "nb3") return r.nb3 ? r.nb3.score : NaN;
  return CORE.wordCountScore(r.q);
}
const isSyn = (r, m) => scoreOf(r, m) >= S.thr[m];
const confOf = (r, m) => { const s = scoreOf(r, m); return Number.isFinite(s) ? CORE.confidence(s, S.thr[m], ...METHODS[m].conf) : ""; };
const wcWords = thr => Math.ceil(thr * CORE.WC_SCALE - 1e-9);

/* ---------- scoring ---------- */
function analyseBase(q) {
  const A = CORE.hasNLP() ? CORE.nlpAnalysis(q) : null;
  const nb1 = CORE.nb1(q);
  return {q, wc: nb1.wordCount, nb1, nb2: A ? CORE.nb2(q, A) : null, feats: A ? CORE.nb4Features(q, A, null) : null,
    vec: null, cmp: null, nb3: null, ens: null, mask: CORE.slotMask(q), label: null, tpl: 1};
}
function addEmbedding(r, vec) {
  r.vec = vec;
  r.cmp = CORE.embCompare(vec, S.emb.defaultRefs);
  r.nb3 = CORE.nb3(vec, S.emb.activeRefs || S.emb.defaultRefs);
  if (r.feats) Object.assign(r.feats, CORE.embFeatures(r.cmp));
}
function currentModel(useEmb) {
  if (S.model.useCustom && S.model.custom) {
    const s = S.model.custom.sets;
    if (useEmb && s.emb) return {set: s.emb, emb: true, who: "yours"};
    if (s.base) return {set: s.base, emb: false, who: "yours"};
  }
  const s = SHIPPED_MODEL.sets;
  return useEmb && s.emb ? {set: s.emb, emb: true, who: "shipped"} : {set: s.base, emb: false, who: "shipped"};
}
function scoreEnsemble(r) {
  if (!r.feats) { r.ens = null; return; }
  const m = currentModel(!!(r.cmp && S.emb.on && S.emb.ready));
  const s = CORE.lrScore(m.set, r.feats);
  r.ens = {p: s.p, z: s.z, contrib: s.contrib, set: m.set, emb: m.emb, who: m.who};
}

/* ---------- embeddings (Notebook 3), loaded only when switched on ---------- */
const mb = b => (b / 1048576).toFixed(1);
function embStatus(html) { $("emb-status").innerHTML = html; }
function embProgress(v) { const p = $("emb-prog"); if (v === null) { p.hidden = true; return; } p.hidden = false; p.value = v; }
function loadEmbedder() {
  if (S.emb.extractor && S.emb.defaultRefs) return Promise.resolve(S.emb.extractor);
  if (!S.emb.loading) {
    S.emb.loading = (async () => {
      embStatus("Loading the embeddings library&hellip;"); embProgress(0);
      const T = await import(TRANSFORMERS_URL);
      T.env.allowLocalModels = false;
      const files = new Map();
      S.emb.extractor = await T.pipeline("feature-extraction", MODEL_ID, {dtype: "q8", device: "wasm", progress_callback: p => {
        if (p && p.status === "progress" && p.total) {
          files.set(p.file, [p.loaded, p.total]);
          let l = 0, t = 0; files.forEach(([a, b]) => { l += a; t += b; });
          embProgress(l / t);
          embStatus(`Downloading the model: ${mb(l)} of ${mb(t)} MB. Your browser keeps a copy for next time.`);
        }
      }});
      embStatus("Embedding the reference queries&hellip;");
      const refs = [...CORE.SYN_REFS, ...CORE.HUM_REFS];
      const vecs = await embedTexts(refs.map(r => r[0]));
      const nS = CORE.SYN_REFS.length;
      S.emb.defaultRefs = CORE.prepareRefs({syn: CORE.SYN_REFS.map((r, i) => ({text: r[0], type: r[1], vec: vecs[i]})),
        hum: CORE.HUM_REFS.map((r, i) => ({text: r[0], type: r[1], vec: vecs[nS + i]}))});
      if (!S.emb.activeRefs) S.emb.activeRefs = S.emb.defaultRefs;
      return S.emb.extractor;
    })().catch(e => { S.emb.loading = null; S.emb.extractor = null; throw e; });
  }
  return S.emb.loading;
}
async function embedTexts(texts, onStep, stopped) {
  const out = [];
  for (let i = 0; i < texts.length; i += 32) {
    if (stopped && stopped()) break;
    const chunk = texts.slice(i, i + 32);
    const t = await S.emb.extractor(chunk, {pooling: "mean", normalize: true});
    const d = t.dims[t.dims.length - 1];
    for (let j = 0; j < chunk.length; j++) out.push(t.data.slice(j * d, (j + 1) * d));
    if (t.dispose) t.dispose();
    if (onStep) onStep(Math.min(i + 32, texts.length), texts.length);
    await tick();
  }
  return out;
}
function embReadyText() {
  return `On. ${S.emb.refMode === "default" ? "Notebook 3&rsquo;s default references" : S.emb.refMode === "labels" ? "References drawn from your labels" : "Your own references"} are in use. Queries are embedded in this tab.`;
}
async function setEmbeddings(on) {
  S.emb.on = on;
  if (!on) { embStatus("Off. Scores use the methods that need no model download."); embProgress(null); rescoreAll(); return; }
  try {
    await loadEmbedder();
    S.emb.ready = true;
    embProgress(null);
    embStatus(embReadyText());
    if (S.list && !S.busy) await embedList();
    if (S.inspect && !S.inspect.vec) await inspect(S.inspect.q, true);
    $("iq-status").textContent = "";
    rescoreAll();
  } catch (e) {
    S.emb.on = false; $("emb-toggle").checked = false; embProgress(null);
    embStatus(`<strong>The embedding model did not load</strong> (${esc(e && e.message || e)}). Check the connection or an ad blocker; the other methods still work.`);
    rescoreAll();
  }
}

/* ---------- reference corpus (Notebook 3) ---------- */
function refsToText(list) { return list.map(r => r[0]).join("\n"); }
function fillRefBoxes() {
  $("ref-syn").value = refsToText(CORE.SYN_REFS); $("ref-hum").value = refsToText(CORE.HUM_REFS);
  countRefs();
}
function countRefs() {
  const n = id => $(id).value.split("\n").map(s => s.trim()).filter(Boolean).length;
  $("ref-syn-n").textContent = `(${n("ref-syn")})`; $("ref-hum-n").textContent = `(${n("ref-hum")})`;
}
async function useRefs(syn, hum, mode, rows) {
  if (syn.length < 3 || hum.length < 3) { $("ref-status").innerHTML = "<strong>Add at least three examples on each side.</strong>"; return; }
  if (!S.emb.on || !S.emb.ready) { $("ref-status").innerHTML = "<strong>Switch embeddings on first.</strong> The references are embedded with the same model."; return; }
  $("ref-status").textContent = "Embedding the references…";
  const vecs = await embedTexts([...syn, ...hum]);
  const kind = mode === "labels" ? "data" : "custom";
  S.emb.activeRefs = CORE.prepareRefs({syn: syn.map((t, i) => ({text: t, type: kind, vec: vecs[i]})), hum: hum.map((t, i) => ({text: t, type: kind, vec: vecs[syn.length + i]}))});
  S.emb.refMode = mode; S.emb.refRows = rows || null;
  $("ref-status").textContent = mode === "labels" ? `Using ${syn.length} synthetic and ${hum.length} user rows from your labels. Those rows are left out of the embeddings method's evaluation.` : `Using your ${syn.length} synthetic and ${hum.length} user references.`;
  embStatus(embReadyText());
  renewNb3();
}
function renewNb3() {
  const refs = S.emb.activeRefs || S.emb.defaultRefs;
  if (S.list) S.list.rows.forEach(r => { if (r.vec) r.nb3 = CORE.nb3(r.vec, refs); });
  if (S.inspect && S.inspect.vec) S.inspect.nb3 = CORE.nb3(S.inspect.vec, refs);
  refreshViews();
}
$("ref-syn").addEventListener("input", countRefs);
$("ref-hum").addEventListener("input", countRefs);
$("ref-apply").onclick = () => {
  const lines = id => [...new Set($(id).value.split("\n").map(s => s.trim()).filter(Boolean))];
  const same = lines("ref-syn").join("\n") === refsToText(CORE.SYN_REFS) && lines("ref-hum").join("\n") === refsToText(CORE.HUM_REFS);
  if (same) { $("ref-reset").click(); return; }
  useRefs(lines("ref-syn"), lines("ref-hum"), "custom");
};
$("ref-reset").onclick = () => {
  fillRefBoxes();
  S.emb.activeRefs = S.emb.defaultRefs; S.emb.refMode = "default"; S.emb.refRows = null;
  $("ref-status").innerHTML = "Using Notebook 3&rsquo;s defaults.";
  if (S.emb.ready) { embStatus(embReadyText()); renewNb3(); }
};
$("ref-labels").onclick = () => {
  if (!S.list || !S.list.labelInfo) return;
  const rand = CORE.rng(42);
  const pick = cls => { const idx = S.list.rows.filter(r => r.label === cls).map(r => r.i); return CORE.sampleIdx(idx.length, Math.min(40, idx.length), rand).map(k => idx[k]); };
  const s = pick(1), h = pick(0);
  $("ref-syn").value = s.map(i => S.list.rows[i].q).join("\n"); $("ref-hum").value = h.map(i => S.list.rows[i].q).join("\n");
  countRefs();
  useRefs(s.map(i => S.list.rows[i].q), h.map(i => S.list.rows[i].q), "labels", new Set([...s, ...h]));
};

/* ---------- tabs ---------- */
const tabButtons = [...document.querySelectorAll(".modes [role=tab]")];
function switchTab(name) {
  tabButtons.forEach(b => { const on = b.dataset.tab === name; b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1; });
  ["inspect", "list", "eval", "batch"].forEach(t => { $("view-" + t).hidden = t !== name; });
  if (name === "eval") renderEval();
  if (name === "batch") renderBatch();
}
tabButtons.forEach((b, i) => {
  b.addEventListener("click", () => switchTab(b.dataset.tab));
  b.addEventListener("keydown", e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const next = tabButtons[(i + (e.key === "ArrowRight" ? 1 : tabButtons.length - 1)) % tabButtons.length];
    next.focus(); switchTab(next.dataset.tab);
  });
});

/* ---------- shared bits of markup ---------- */
const lvl = syn => syn ? "is-synth" : "is-user";
const badge = (syn, text) => `<span class="cls ${lvl(syn)}">${text || (syn ? "Synthetic" : "User")}</span>`;
function meterCell(r, m) {
  const s = scoreOf(r, m);
  if (!Number.isFinite(s)) return `<span class="hint">n/a</span>`;
  return `<span class="mbar ${lvl(s >= S.thr[m])}" title="${esc(METHODS[m].name)}: ${fx(s, 3)}"><i><b style="width:${w100(s)}"></b><em style="left:${w100(S.thr[m])}"></em></i>${fx(s)}</span>`;
}
const typeChips = types => types.map(t => `<span class="type">${TYPE_NAMES[t] || t}</span>`).join("");
const tiles = list => list.map(([k, v, d, cls]) => `<div class="tile ${cls || ""}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join("");
const share = (n, t) => t ? `${nf(n)} of ${nf(t)} (${(n / t * 100).toFixed(1)}%)` : "0";

/* =====================================================================================
   Inspect a query
   ===================================================================================== */
const EXAMPLES = ["espresso machine", "why is my espresso sour", "best espresso machine for small kitchens under 300 dollars in 2025",
  "Breville Barista Express vs De'Longhi Dedica comparison for home baristas", "is a dual boiler espresso machine worth the extra money",
  "whats the best espresso machine for a beginner who doesnt want to spend a lot"];
$("iq-examples").innerHTML = EXAMPLES.map(q => `<button type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("");
$("iq-examples").addEventListener("click", e => { const b = e.target.closest("button[data-q]"); if (b) { $("iq").value = b.dataset.q; inspect(b.dataset.q); } });
$("iq-run").onclick = () => { const q = $("iq").value.trim(); if (!q) { $("iq-status").innerHTML = "<strong>Type a query first.</strong>"; $("iq").focus(); return; } inspect(q); };
$("iq").addEventListener("keydown", e => { if (e.key === "Enter") $("iq-run").click(); });

async function inspect(q, quiet) {
  const r = analyseBase(q);
  S.inspect = r;
  scoreEnsemble(r);
  renderInspect();
  $("iq-status").textContent = "";
  if (!S.emb.on) return;
  if (!S.emb.ready) { if (!quiet) $("iq-status").textContent = "The embedding scores appear here once the model has loaded."; return; }
  try {
    const [v] = await embedTexts([q]);
    if (S.inspect !== r) return;
    addEmbedding(r, v); scoreEnsemble(r); renderInspect();
  } catch (e) { if (!quiet) $("iq-status").textContent = "Embeddings are not available, so this shows the other methods."; }
}

function renderInspect() {
  const r = S.inspect; if (!r) return;
  const box = $("iq-result"), pm = primary(), syn = isSyn(r, pm);
  const methods = shownMethods();
  const rows = methods.concat(["wc"]).map(m => {
    const s = scoreOf(r, m), y = s >= S.thr[m];
    const lab = m === "wc" ? `${r.wc} word${r.wc === 1 ? "" : "s"}` : `${badge(y)} <span class="conf">${confOf(r, m)}</span>`;
    return `<li class="${lvl(y)}"><span class="name">${esc(METHODS[m].name)} <span class="nbtag">${METHODS[m].nb}</span></span>
      <span class="meter"><span style="width:${w100(s)}"></span><i class="tick" style="left:${w100(S.thr[m])}" title="Threshold ${fx(S.thr[m])}"></i></span>
      <span class="n">${fx(s)}</span><span class="lab">${lab}</span></li>`;
  }).join("");
  const parts = [`<div class="panel result ${lvl(syn)}">
    <div class="rhead"><div><div class="eyebrow">Query</div><div class="qtext">${esc(r.q)}</div></div>${badge(syn, (syn ? "Synthetic" : "User") + " &middot; " + esc(METHODS[pm].name.toLowerCase()))}</div>
    <div class="figures"><span>Words <b>${r.wc}</b></span><span>Slot-mask template <b class="mono">${esc(r.mask)}</b></span>${r.ens ? `<span>Ensemble weights <b>${r.ens.who === "yours" ? "your model" : "shipped"}, ${r.ens.emb ? "with" : "without"} embeddings</b></span>` : ""}</div>
    <ul class="scores">${rows}</ul>
    <div class="hint" data-gap="8">The word-count row is the baseline: the score is words &divide; ${CORE.WC_SCALE}, so the threshold ${fx(S.thr.wc)} means ${wcWords(S.thr.wc)} or more words.</div>
  </div>`];
  const cards = [];
  if (r.ens && visible("ens")) cards.push(ensembleCard(r));
  if (visible("nb1")) cards.push(nb1Card(r), patentCard(r));
  if (visible("nb2") && r.nb2) cards.push(nb2Card(r));
  cards.push(nb3Card(r));
  box.innerHTML = parts.join("") + `<div class="dgrid">${cards.join("")}</div>`;
  box.hidden = false;
}

function nb1Card(r) {
  const s = r.nb1.signals, W = CORE.NB1_WEIGHTS;
  const row = (name, v, w, why, inv) => `<tr><td>${name}<span class="why">${why}</span></td><td class="n">${fx(v)} &times; ${w.toFixed(2)}${inv ? " (1 &minus; value)" : ""}</td><td class="n">${fx(w * (inv ? 1 - v : v), 3)}</td></tr>`;
  return `<div class="panel"><h3>Rule-based signals <span class="nbtag">NB1</span></h3>
    <table class="kv"><tbody>
      ${row("Length", s.length, W.length, "0.1 at 1&ndash;3 words, 0.25 at 4&ndash;5, 0.7 at 6&ndash;12, 0.6 at 13&ndash;20, 0.3 above")}
      ${row("Structure", s.structure, W.structure, "question word first, articles, prepositions, final punctuation")}
      ${row("Patent patterns", s.template, W.template, r.nb1.types.length ? "matched: " + r.nb1.types.map(t => TYPE_NAMES[t]).join(", ") + (r.nb1.year ? ", plus a year" : "") : r.nb1.year ? "a recent year only" : "no pattern matched")}
      ${row("Human messiness", s.messiness, W.messiness, "typos, abbreviations, telegraphic style, odd capitals; counts against synthetic", true)}
      ${row("Vocabulary", s.vocabulary, W.vocabulary, "formal words and longer words push it up")}
      <tr><td><b>Score</b></td><td class="n"></td><td class="n">${fx(r.nb1.score, 3)}</td></tr>
    </tbody></table></div>`;
}
function patentCard(r) {
  const on = new Set(r.nb1.types), hints = new Map(r.nb1.hints);
  if (r.nb3 && r.nb3.nearestSyn && TYPE_NAMES[r.nb3.nearestSyn.type]) hints.set("nearest:" + r.nb3.nearestSyn.type, r.nb3.nearestSyn.text);
  const chips = PATENT_ORDER.map(t => on.has(t) ? `<span class="type on" title="Matched: ${esc(r.nb1.matches[t])}">${TYPE_NAMES[t]}</span>`
    : hints.has(t) ? `<span class="type off" title="Hint only, not scored">${TYPE_NAMES[t]}?</span>` : `<span class="type off">${TYPE_NAMES[t]}</span>`).join("");
  const matched = r.nb1.types.map(t => `<li><b>${TYPE_NAMES[t]}</b>: &ldquo;${esc(r.nb1.matches[t])}&rdquo;</li>`).join("");
  const hintList = [...hints].filter(([k]) => !k.startsWith("nearest:")).map(([k, v]) => `<li>${TYPE_NAMES[k]}? &ldquo;${esc(v)}&rdquo; (hint, not scored)</li>`).join("");
  const near = r.nb3 ? `<li>Nearest synthetic reference is a ${TYPE_NAMES[r.nb3.nearestSyn.type] || KIND_NAMES[r.nb3.nearestSyn.type] || "reference"} example.</li>` : "";
  return `<div class="panel"><h3>Patent query types <span class="nbtag">NB1</span></h3>
    <div class="tags">${chips}</div>
    <ul class="members" data-gap="8">${matched || "<li class='hint'>No Notebook 1 pattern matched.</li>"}${hintList}${near}</ul>
    <div class="hint" data-gap="8">Google&rsquo;s patent US20240289407A1 names eight variant types. Notebook 1 has text patterns for five; Equivalent, Canonicalization and Language translation get hints here but never change the score.</div></div>`;
}
function nb2Card(r) {
  const n = r.nb2, c = n.components, W = CORE.NB2_WEIGHTS;
  const ents = n.entity.entities.length ? n.entity.entities.map(e => `<span class="tok">${esc(e.text)}<small>${e.label}</small></span>`).join("") : `<span class="hint">none found</span>`;
  const toks = n.tags.map(([t, p]) => `<span class="tok">${esc(t)}<small>${p}</small></span>`).join("");
  const row = (name, v, w, why) => `<tr><td>${name}<span class="why">${why}</span></td><td class="n">${fx(v)} &times; ${w.toFixed(2)}</td><td class="n">${fx(v * w, 3)}</td></tr>`;
  return `<div class="panel"><h3>Entity &amp; linguistic features <span class="nbtag">NB2</span></h3>
    <table class="kv"><tbody>
      ${row("Entities", c.entity, W.entity, `${n.entity.entity_count} found, ${fx(n.entity.entity_density)} per word, type mix ${fx(n.entity.multi_type_score)}`)}
      ${row("Parts of speech", c.pos, W.pos, `entropy ${fx(n.posf.pos_entropy)} bits, nouns ${pct(n.posf.noun_ratio, 0)}, verbs ${pct(n.posf.verb_ratio, 0)}, determiners ${pct(n.posf.det_ratio, 0)}`)}
      ${row("Readability", c.lexical, W.lexical, `Flesch reading ease ${fx(n.lexical.flesch_reading_ease, 1)}, ${fx(n.lexical.syllable_ratio)} syllables per word, ${pct(n.lexical.long_word_ratio, 0)} long words`)}
      ${row("Fan-out n-grams", c.ngram, W.ngram, n.ngramf.hits.length ? "matched: " + esc(n.ngramf.hits.join(", ")) : "none of the notebook's word pairs or triples")}
      <tr><td><b>Score</b></td><td class="n"></td><td class="n">${fx(n.score, 3)}</td></tr>
    </tbody></table>
    <div class="lbl" data-gap="12">Entities</div><div class="tags">${ents}</div>
    <div class="lbl" data-gap="10">Part-of-speech tags</div><div class="tags">${toks || '<span class="hint">no words</span>'}</div></div>`;
}
function nb3Card(r) {
  if (!S.emb.on || !S.emb.ready || !r.nb3) {
    return `<div class="panel"><h3>Embeddings <span class="nbtag">NB3</span></h3>
      <p class="hint">${S.emb.on ? "The model is still loading; this card fills in when it is ready." : "Switch on embeddings in the settings to see this query&rsquo;s nearest synthetic and user reference queries and its embedding score."}</p></div>`;
  }
  const n = r.nb3, s = n.signals, W = CORE.NB3_WEIGHTS;
  const row = (name, v, w, why) => `<tr><td>${name}<span class="why">${why}</span></td><td class="n">${fx(v)} &times; ${w.toFixed(2)}</td><td class="n">${fx(v * w, 3)}</td></tr>`;
  const kind = t => TYPE_NAMES[t] ? TYPE_NAMES[t] + " anchor" : (KIND_NAMES[t] || t);
  return `<div class="panel"><h3>Embeddings <span class="nbtag">NB3</span></h3>
    <table class="kv"><tbody>
      ${row("Centroids", s.centroid, W.centroid, "similarity to the synthetic centre minus the user centre, mapped to 0&ndash;1")}
      ${row("5 nearest", s.knn, W.knn, "mean of the 5 closest synthetic minus the 5 closest user references")}
      ${row("Nearest", s.max_similarity, W.max_similarity, "closest synthetic minus closest user reference")}
      ${row("Typicality", s.norm, W.norm, "closeness to the centre of all references")}
      <tr><td><b>Score</b></td><td class="n"></td><td class="n">${fx(n.score, 3)}</td></tr>
    </tbody></table>
    <div class="refq is-synth"><span class="lbl">Nearest synthetic reference</span><br><b>${esc(n.nearestSyn.text)}</b><span class="hint">${kind(n.nearestSyn.type)} &middot; cosine ${fx(n.nearestSyn.sim, 3)}</span></div>
    <div class="refq is-user"><span class="lbl">Nearest user reference</span><br><b>${esc(n.nearestHum.text)}</b><span class="hint">${kind(n.nearestHum.type)} &middot; cosine ${fx(n.nearestHum.sim, 3)}</span></div></div>`;
}
function ensembleCard(r) {
  const e = r.ens, feats = e.set.features, groups = {};
  feats.forEach((f, i) => { const g = CORE.FEATURE_GROUP[f] || "structure"; groups[g] = (groups[g] || 0) + e.contrib[i]; });
  const gl = Object.entries(groups).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const single = feats.map((f, i) => [f, e.contrib[i]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 10);
  const maxAbs = Math.max(0.5, ...gl.map(g => Math.abs(g[1])), ...single.map(x => Math.abs(x[1])));
  const bar = v => { const w = Math.abs(v) / maxAbs * 50; return `<span class="dbar"><span class="${v >= 0 ? "syn" : "usr"}" style="left:${v >= 0 ? 50 : 50 - w}%;width:${w.toFixed(2)}%"></span></span>`; };
  const sign = v => (v >= 0 ? "+" : "") + fx(v);
  const fval = f => { const v = r.feats[f]; return Number.isInteger(v) ? String(v) : fx(v); };
  const groupRows = gl.map(([g, v]) => `<li class="grp"><span class="lab">${GROUP_NAMES[g]}</span>${bar(v)}<span class="n">${sign(v)}</span></li>`).join("");
  const singleRows = single.map(([f, v]) => `<li class="sub"><span class="lab">${esc(FEATURE_NAMES[f] || f)}<small>value ${fval(f)} &middot; ${GROUP_NAMES[CORE.FEATURE_GROUP[f]].toLowerCase()}</small></span>${bar(v)}<span class="n">${sign(v)}</span></li>`).join("");
  return `<div class="panel wide"><h3>Ensemble: why this score <span class="nbtag">NB4</span></h3>
    <div class="sub" data-gapb="6">Logistic regression on standardised features, so each push is exactly coefficient &times; standardised value, in log-odds: the linear-model version of Notebook 4&rsquo;s per-prediction SHAP chart. With the starting point ${sign(e.set.intercept)} they add up to ${fx(e.z)}, a probability of ${fx(e.p, 3)}. Word count and part-of-speech entropy rise together, so the model leans on one and corrects with the other; read the group totals first.</div>
    <div class="evgrid"><div><div class="lbl">By feature group</div><ul class="contrib">${groupRows}</ul></div>
    <div><div class="lbl">Largest single pushes</div><ul class="contrib">${singleRows}</ul></div></div>
    <div class="legend"><span class="is-synth"><i class="sw"></i>towards synthetic</span><span class="is-user"><i class="sw"></i>towards user</span><span>${feats.length} features, ${e.who === "yours" ? "your model" : "shipped weights"}</span></div></div>`;
}

/* =====================================================================================
   Classify a list
   ===================================================================================== */
document.querySelectorAll("#view-list .seg [data-in]").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll("#view-list .seg [data-in]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  ["paste", "file", "sample"].forEach(k => { $("in-" + k).hidden = k !== b.dataset.in; });
}));

const SAMPLE = `query,label
espresso machine,user
breville barista express,user
delonghi dedica vs breville bambino,user
best espresso machine under 300,user
espresso machine descaling,user
how to descale delonghi,user
coffee grinder burr,user
baratza encore review,user
cold brew ratio,user
nespresso pods cheap,user
moka pot instructions,user
why is my espresso sour,user
aeropress recipe,user
milk frother,user
espresso machine sale,user
gaggia classic pro mods,user
lavazza beans,user
coffee machine with grinder,user
how to clean breville portafilter,user
whats the best espresso machine for a beginner who doesnt want to spend a lot,user
de longhi magnifica s manual,user
single dose grinder reddit,user
What are the best espresso machines for beginners in 2026?,synthetic
Breville Barista Express vs De'Longhi Dedica comparison for home baristas,synthetic
how to choose the right burr grinder for espresso at home,synthetic
average cost of a home espresso setup for beginners,synthetic
is a dual boiler espresso machine worth the extra money,synthetic
common problems reported with entry-level espresso machines,synthetic
best espresso machine for small kitchens under 300 dollars in 2025,synthetic
best espresso machine for small kitchens under 500 dollars in 2025,synthetic
best espresso machine for small kitchens under 300 dollars in 2026,synthetic
best espresso machine for small kitchens under 800 dollars in 2026,synthetic
overview of the different types of home espresso machines,synthetic
how does a heat exchanger espresso machine compare to a dual boiler for milk drinks,synthetic
pros and cons of super-automatic espresso machines for busy households,synthetic
what to look for when evaluating espresso grinders for consistency,synthetic
how long does a home espresso machine usually last with regular use,synthetic
complete guide to dialling in espresso for beginners,synthetic
affordable espresso machines designed specifically for small apartments,synthetic
customer satisfaction ratings for popular home espresso machine brands,synthetic
which is better for latte art a steam wand or an automatic milk frother,synthetic
how to maintain an espresso machine to extend its useful life,synthetic
espresso machine buying guide 2026,synthetic`;

// Read text into {queries, labels, labelInfo}. Detects a delimiter and header, or treats it as one query per line.
function tableFrom(text) {
  text = String(text).replace(/^\uFEFF/, "");
  const delim = CORE.detectDelimiter(text);
  const rows = delim ? CORE.parseDelimited(text, delim) : text.split(/\r?\n/).filter(l => l.trim()).map(l => [l]);
  if (!rows.length) return null;
  const det = CORE.detectColumns(rows);
  return Object.assign(det, {delim});
}
function extract(tab, qCol, lCol) {
  const queries = [], labels = [], raw = [];
  let skipped = 0;
  for (const r of tab.body) {
    let q = (r[qCol] || "").trim();
    if (tab.width === 1 && /^"(?:[^"]|"")*"$/.test(q)) q = q.slice(1, -1).replace(/""/g, '"');
    if (!q) { skipped++; continue; }
    queries.push(q);
    if (lCol >= 0) { const v = (r[lCol] || "").trim(); raw.push(v); labels.push(CORE.mapLabel(v)); }
  }
  let labelInfo = null;
  if (lCol >= 0) {
    const map = new Map();
    raw.forEach((v, i) => { const k = v || "(empty)"; if (!map.has(k)) map.set(k, {value: k, cls: labels[i], n: 0}); map.get(k).n++; });
    labelInfo = {column: tab.names[lCol], values: [...map.values()].sort((a, b) => b.n - a.n), swapped: false};
  }
  return {queries, labels: lCol >= 0 ? labels : null, labelInfo, skipped};
}

$("paste-run").onclick = () => {
  const text = $("paste").value;
  if (!text.trim()) { status("<strong>Paste at least one query.</strong>"); return; }
  const first = text.split(/\r?\n/).find(l => l.trim()) || "";
  const tabular = /\t/.test(text) || /\b(keywords?|quer(y|ies)|search terms?|label|type|class)\b/i.test(first) && /[,;\t]/.test(first);
  const tab = (tabular && tableFrom(text)) || {body: text.split(/\r?\n/).filter(l => l.trim()).map(l => [l]), width: 1, names: ["Query"], queryCol: 0, labelCol: -1, header: false};
  const data = extract(tab, tab.queryCol, tab.labelCol);
  startList(data, "pasted list");
};
$("sample-run").onclick = () => {
  const tab = tableFrom(SAMPLE);
  startList(extract(tab, tab.queryCol, tab.labelCol), "sample");
};
$("eval-sample").onclick = () => { switchTab("list"); document.querySelector('#view-list .seg [data-in="sample"]').click(); $("sample-run").click(); };

let FILE_TAB = null, FILE_NAME = "";
async function readFileText(f) {
  const buf = new Uint8Array(await f.arrayBuffer());
  if (buf[0] === 0xFF && buf[1] === 0xFE) return new TextDecoder("utf-16le").decode(buf);
  if (buf[0] === 0xFE && buf[1] === 0xFF) return new TextDecoder("utf-16be").decode(buf);
  return new TextDecoder("utf-8").decode(buf);
}
$("file").onchange = async e => {
  const f = e.target.files[0]; e.target.value = "";
  if (!f) return;
  let tab;
  try { tab = tableFrom(await readFileText(f)); } catch (err) { tab = null; }
  if (!tab || !tab.body.length) { $("file-info").innerHTML = "<strong>No rows found in that file.</strong>"; $("file-run").disabled = true; $("colpick").hidden = true; return; }
  FILE_TAB = tab; FILE_NAME = f.name;
  const opts = tab.names.map((n, i) => `<option value="${i}">${esc(n)}</option>`).join("");
  $("col-q").innerHTML = opts; $("col-q").value = String(tab.queryCol);
  $("col-l").innerHTML = `<option value="-1">No labels</option>` + opts; $("col-l").value = String(tab.labelCol);
  $("colpick").hidden = tab.width < 2;
  $("file-info").innerHTML = `Read <strong>${nf(tab.body.length)}</strong> row${tab.body.length === 1 ? "" : "s"} from ${esc(f.name)}${tab.header ? ", with a header row" : ""}.`;
  $("col-note").innerHTML = tab.width > 1 && !tab.confident ? "<strong>Check the query column.</strong> No column is called keyword or query, so the one with the most text was picked." : "";
  $("file-run").disabled = false;
};
$("file-run").onclick = () => {
  if (!FILE_TAB) return;
  const q = +$("col-q").value, l = +$("col-l").value;
  if (l === q) { $("col-note").innerHTML = "<strong>Pick different columns for the queries and the labels.</strong>"; return; }
  const data = extract(FILE_TAB, q, l);
  if (data.labels && data.labels.every(v => v === null)) {
    $("col-note").innerHTML = "<strong>That label column has no values this tool recognises</strong> (User / Synthetic, human / AI, 0 / 1). Classifying without labels.";
    data.labels = null; data.labelInfo = null;
  }
  startList(data, FILE_NAME);
};
$("stop").onclick = () => { S.stop = true; status("Stopping after this chunk&hellip;"); };

function status(html) { $("run-status").innerHTML = html; }
function progress(v) { $("prog").value = v; }

async function startList(data, source) {
  if (S.busy) return;
  if (!data.queries.length) { status("<strong>No queries found.</strong>"); $("runbar").hidden = false; return; }
  let {queries, labels} = data;
  let capped = 0;
  if (queries.length > MAX_ROWS) { capped = queries.length - MAX_ROWS; queries = queries.slice(0, MAX_ROWS); if (labels) labels = labels.slice(0, MAX_ROWS); }
  S.busy = true; S.stop = false; S.clusters = null; S.shown = PAGE;
  $("runbar").hidden = false; $("stop").hidden = false; progress(0);
  const n = queries.length, rows = [], embShare = S.emb.on ? 0.55 : 0;
  try {
    for (let i = 0; i < n; i++) {
      const r = analyseBase(queries[i]); r.i = i; r.label = labels ? labels[i] : null;
      rows.push(r);
      if (i % 50 === 49 || i === n - 1) {
        progress((i + 1) / n * (1 - embShare));
        status(`Scoring ${nf(i + 1)} of ${nf(n)} queries&hellip;`);
        await tick();
        if (S.stop) break;
      }
    }
    S.list = {rows, labelInfo: data.labelInfo, source, total: n, capped, skipped: data.skipped || 0, stopped: S.stop, embStopped: false};
    if (S.emb.on && !S.stop) await embedList(embShare);
    S.list.stopped = S.stop;
    finishList();
  } catch (e) {
    status(`<strong>Something went wrong:</strong> ${esc(e && e.message || e)}`);
  } finally {
    S.busy = false; $("stop").hidden = true;
  }
  if (S.pending) { const p = S.pending; S.pending = null; p(); }
}
async function embedList(share = 1) {
  const L = S.list; if (!L) return;
  const todo = L.rows.filter(r => !r.vec);
  if (!todo.length) { rescoreAll(); return; }
  const standalone = !S.busy;
  if (standalone) { S.busy = true; S.stop = false; $("runbar").hidden = false; $("stop").hidden = false; }
  try {
    status(S.emb.extractor ? "Embedding the queries&hellip;" : "Loading the embedding model&hellip;");
    await loadEmbedder();
    S.emb.ready = true;
    const base = 1 - share;
    const vecs = await embedTexts(todo.map(r => r.q), (d, t) => { progress(base + share * d / t); status(`Embedding ${nf(d)} of ${nf(t)} queries&hellip;`); }, () => S.stop);
    vecs.forEach((v, i) => addEmbedding(todo[i], v));
    if (vecs.length < todo.length) L.embStopped = true;
  } catch (e) {
    status(`<strong>Embeddings failed</strong> (${esc(e && e.message || e)}); the other methods are shown.`);
  } finally {
    if (standalone) { S.busy = false; $("stop").hidden = true; finishList(); }
  }
}
function finishList() {
  const L = S.list;
  L.rows.forEach(scoreEnsemble);
  L.tpl = CORE.templates(L.rows.map(r => r.q), 2);
  L.rows.forEach(r => { r.tpl = L.tpl.countOf(r.q); });
  progress(1);
  const done = L.rows.length, notes = [];
  if (L.stopped) notes.push(`Stopped after ${nf(done)} of ${nf(L.total)} queries`);
  else notes.push(`Scored ${nf(done)} quer${done === 1 ? "y" : "ies"} from the ${esc(L.source)}`);
  if (L.embStopped) notes.push("embeddings only for part of the list");
  if (L.capped) notes.push(`the last ${nf(L.capped)} rows were left out (limit ${nf(MAX_ROWS)})`);
  if (L.skipped) notes.push(`${nf(L.skipped)} empty row${L.skipped === 1 ? "" : "s"} skipped`);
  if (!CORE.hasNLP()) notes.push("the language library did not load, so the linguistic method and the ensemble are off");
  status(notes.join("; ") + ".");
  $("count-list").textContent = nf(done);
  $("ref-labels").hidden = !L.labelInfo;
  refreshViews();
}

function rescoreAll() {
  if (S.list && !S.busy) S.list.rows.forEach(scoreEnsemble);
  if (S.inspect) scoreEnsemble(S.inspect);
  refreshViews();
}
function refreshViews() {
  renderInspect();
  renderList();
  if (!$("view-eval").hidden) renderEval();
  if (!$("view-batch").hidden) renderBatch();
}

function filteredRows() {
  const L = S.list, pm = primary(), ms = shownMethods();
  let rows = L.rows;
  if (S.filter === "syn") rows = rows.filter(r => isSyn(r, pm));
  else if (S.filter === "user") rows = rows.filter(r => !isSyn(r, pm));
  else if (S.filter === "split") rows = rows.filter(r => { const v = ms.map(m => scoreOf(r, m)).filter(Number.isFinite); return v.length > 1 && new Set(ms.filter(m => Number.isFinite(scoreOf(r, m))).map(m => isSyn(r, m))).size > 1; });
  else if (S.filter === "wrong") rows = rows.filter(r => r.label !== null && isSyn(r, pm) !== (r.label === 1));
  const key = {"score-desc": r => -scoreOf(r, pm), "score-asc": r => scoreOf(r, pm), order: r => r.i, words: r => -r.wc, template: r => -r.tpl}[S.sort];
  return [...rows].sort((a, b) => (key(a) - key(b)) || (a.i - b.i));
}
function renderList() {
  const L = S.list;
  if (!L) return;
  $("list-results").hidden = false;
  const pm = primary(), n = L.rows.length, ms = shownMethods();
  const syn = L.rows.filter(r => isSyn(r, pm)).length;
  const rec = L.tpl ? L.tpl.recurring.filter(t => t.rows.length >= 3) : [];
  const disagree = L.rows.filter(r => new Set(ms.filter(m => Number.isFinite(scoreOf(r, m))).map(m => isSyn(r, m))).size > 1).length;
  const t = [["Queries", nf(n), L.stopped ? `stopped early, ${nf(L.total)} in the input` : `from the ${esc(L.source)}`, ""],
    ["Synthetic", nf(syn), `${pct(n ? syn / n : 0)} by the ${esc(METHODS[pm].name.toLowerCase())}`, "is-synth"],
    ["User", nf(n - syn), `${pct(n ? (n - syn) / n : 0)} at threshold ${fx(S.thr[pm])}`, "is-user"],
    ["Repeated templates", nf(rec.length), `3+ times, covering ${nf(rec.reduce((s, x) => s + x.rows.length, 0))} queries`, ""],
    ["Methods disagree", nf(disagree), `of ${nf(n)} queries, across ${ms.length} method${ms.length === 1 ? "" : "s"}`, ""]];
  if (L.labelInfo) { const k = L.rows.filter(r => r.label !== null).length; t.push(["Labelled rows", nf(k), "open Evaluate &amp; train for the scores", ""]); }
  $("list-tiles").innerHTML = tiles(t);
  $("f-wrong").hidden = !L.labelInfo;
  if (!L.labelInfo && S.filter === "wrong") S.filter = "all";
  document.querySelectorAll(".filters [data-filter]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.filter === S.filter)));
  const rows = filteredRows(), page = rows.slice(0, S.shown);
  const head = `<thead><tr><th>Query</th><th class="n">Words</th>${L.labelInfo ? "<th>Your label</th>" : ""}${ms.map(m => `<th>${esc(METHODS[m].name)}</th>`).join("")}<th>Patent types</th><th class="n">Template</th></tr></thead>`;
  const body = page.map(r => `<tr><td class="q"><button type="button" class="link" data-i="${r.i}" title="Inspect this query">${esc(r.q)}</button></td>
    <td class="n">${r.wc}</td>${L.labelInfo ? `<td>${r.label === null ? '<span class="cls none">none</span>' : badge(r.label === 1)}</td>` : ""}
    ${ms.map(m => `<td>${meterCell(r, m)}</td>`).join("")}
    <td class="why">${r.nb1.types.map(x => TYPE_NAMES[x]).join(", ")}</td><td class="n">${r.tpl > 1 ? "&times;" + r.tpl : ""}</td></tr>`).join("");
  $("list-table").innerHTML = head + `<tbody>${body || `<tr><td colspan="9" class="hint">No queries match this filter.</td></tr>`}</tbody>`;
  $("more").hidden = rows.length <= S.shown;
  $("shown").textContent = rows.length ? `Showing ${nf(page.length)} of ${nf(rows.length)}. The CSV export has every row.` : "";
  $("dl-clusters").disabled = !S.clusters;
}
document.querySelectorAll(".filters [data-filter]").forEach(b => b.addEventListener("click", () => { S.filter = b.dataset.filter; S.shown = PAGE; renderList(); }));
$("sort").onchange = e => { S.sort = e.target.value; renderList(); };
$("more").onclick = () => { S.shown += PAGE; renderList(); };
$("list-table").addEventListener("click", e => {
  const b = e.target.closest("button[data-i]"); if (!b) return;
  const r = S.list.rows[+b.dataset.i];
  $("iq").value = r.q; S.inspect = r; switchTab("inspect"); renderInspect();
  $("iq-result").scrollIntoView({behavior: "smooth", block: "start"});
});

/* =====================================================================================
   Evaluate & train
   ===================================================================================== */
function evalRows(m) {
  const L = S.list;
  return L.rows.filter(r => r.label !== null && Number.isFinite(scoreOf(r, m)) && !(m === "nb3" && S.emb.refRows && S.emb.refRows.has(r.i)));
}
function evalOf(m, thr = S.thr[m]) {
  const rows = evalRows(m), s = rows.map(r => scoreOf(r, m)), y = rows.map(r => r.label);
  const at = CORE.confusion(s, y, thr), best = CORE.bestThreshold(s, y);
  return {rows, s, y, at, best, bestM: best ? CORE.confusion(s, y, best.thr) : null, auc: CORE.auc(s, y)};
}
const evalMethods = () => shownMethods().concat(["wc"]);
function thrText(m, t) { return m === "wc" ? `${fx(t)} (${wcWords(t)}+ words)` : fx(t, 3); }

function renderEval() {
  const L = S.list, has = !!(L && L.labelInfo && L.rows.some(r => r.label !== null));
  $("eval-empty").hidden = has; $("eval-body").hidden = !has;
  if (!has) return;
  const li = L.labelInfo, nU = L.rows.filter(r => r.label === 0).length, nS = L.rows.filter(r => r.label === 1).length, nN = L.rows.filter(r => r.label === null).length;
  $("label-summary").innerHTML = `Column <b>${esc(li.column)}</b>: ` + li.values.slice(0, 6).map(v => `&ldquo;${esc(v.value)}&rdquo; &rarr; ${v.cls === null ? "ignored" : v.cls === 1 ? "synthetic" : "user"} (${nf(v.n)})`).join(", ") +
    (li.values.length > 6 ? `, and ${li.values.length - 6} more values` : "") + `. <b>${nf(nU)}</b> user and <b>${nf(nS)}</b> synthetic rows are scored${nN ? `; ${nf(nN)} without a usable label are left out` : ""}.`;
  $("eval-note").textContent = S.emb.refRows ? "Notebook 3 references are drawn from these labels, so those 80 rows are left out of the embeddings method's scores." : "";
  const ms = evalMethods();
  if (!ms.includes(S.evalMethod)) S.evalMethod = ms[0];
  const E = Object.fromEntries(ms.map(m => [m, evalOf(m)]));
  const bestF1 = Math.max(...ms.map(m => E[m].at.f1));
  $("cmp").innerHTML = `<thead><tr><th>Method</th><th class="n">Threshold</th><th class="n">Accuracy</th><th class="n">Precision</th><th class="n">Recall</th><th class="n">F1</th><th class="n">Best-F1 threshold</th><th class="n">F1 there</th><th class="n">AUC</th><th class="n">Rows</th></tr></thead><tbody>` +
    ms.map(m => { const e = E[m]; const name = m === "ens" && L.rows[0] && L.rows[0].ens ? `${METHODS[m].name} <span class="hint">(${L.rows[0].ens.who === "yours" ? "your model" : "shipped"}, ${L.rows[0].ens.emb ? "with" : "without"} embeddings)</span>` : esc(METHODS[m].name);
      return `<tr class="${e.at.f1 === bestF1 ? "best" : ""}"><td>${name} <span class="nbtag">${METHODS[m].nb}</span></td><td class="n">${thrText(m, S.thr[m])}</td>
      <td class="n">${fx(e.at.accuracy, 3)}</td><td class="n">${fx(e.at.precision, 3)}</td><td class="n">${fx(e.at.recall, 3)}</td><td class="n"><b>${fx(e.at.f1, 3)}</b></td>
      <td class="n">${e.best ? thrText(m, e.best.thr) : "n/a"}</td><td class="n">${e.best ? fx(e.best.f1, 3) : "n/a"}</td><td class="n">${e.auc === null ? "n/a" : fx(e.auc, 3)}</td><td class="n">${nf(e.rows.length)}</td></tr>`; }).join("") + "</tbody>";
  $("cmp-note").textContent = S.perMethod ? "Each method uses its own threshold." : `All methods at threshold ${fx(S.thr.ens)}.`;
  const wc = E.wc, beat = ms.filter(m => m !== "wc" && E[m].best && wc.best && E[m].best.f1 > wc.best.f1 + 0.005).map(m => METHODS[m].name);
  $("wc-note").innerHTML = `<p><strong>Read these next to the word-count row.</strong> On this list, labelling every query with ${wc.best ? wcWords(wc.best.thr) : "n"} or more words as synthetic reaches F1 ${wc.best ? fx(wc.best.f1, 3) : "n/a"} (AUC ${wc.auc === null ? "n/a" : fx(wc.auc, 3)}). ${beat.length ? `At their best thresholds, ${beat.join(" and ")} ${beat.length === 1 ? "beats" : "beat"} it.` : "No method beats it at its best threshold, so on this list the scores add little beyond length."} If your synthetic queries are simply longer, any method that reads length will look good here and may not on another list.</p>
    <p>The best-F1 thresholds are picked with the labels, so they flatter every method a little. The shipped ensemble was trained on generated queries plus 30% of the course&rsquo;s dog-harness test set; scores on that set include rows it has seen.</p>`;
  // detail
  $("ev-methods").innerHTML = ms.map(m => `<button type="button" data-m="${m}" aria-pressed="${m === S.evalMethod}">${esc(METHODS[m].name)}</button>`).join("");
  renderEvalDetail(E[S.evalMethod]);
}
function renderEvalDetail(e) {
  const m = S.evalMethod, t = S.thr[m];
  if (!e) e = evalOf(m);
  $("ev-thr").value = String(t);
  $("ev-thr-out").textContent = thrText(m, t);
  const a = e.at;
  $("ev-cm").innerHTML = `<div class="h"></div><div class="h">Predicted user</div><div class="h">Predicted synthetic</div>
    <div class="h rh">Labelled user</div><div class="c ok"><b>${nf(a.tn)}</b>true negative</div><div class="c bad"><b>${nf(a.fp)}</b>false positive</div>
    <div class="h rh">Labelled synthetic</div><div class="c bad"><b>${nf(a.fn)}</b>false negative</div><div class="c ok"><b>${nf(a.tp)}</b>true positive</div>`;
  $("ev-metrics").innerHTML = [["Accuracy", a.accuracy], ["Precision", a.precision], ["Recall", a.recall], ["F1", a.f1], ["AUC", e.auc]]
    .map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v === null ? "n/a" : fx(v, 3)}</div></div>`).join("") + `<div><div class="k">Best F1 at</div><div class="v">${e.best ? fx(e.best.thr, 2) : "n/a"}</div></div>`;
  const s0 = e.s.filter((_, i) => e.y[i] === 0), s1 = e.s.filter((_, i) => e.y[i] === 1);
  $("ev-hist").innerHTML = histogram([{values: s0, cls: "bar-usr", name: "User"}, {values: s1, cls: "bar-syn", name: "Synthetic"}],
    {width: widthOf($("ev-hist")), min: 0, max: 1, bins: 25, markers: [{x: t, cls: "thr", label: "threshold"}], xlabel: m === "wc" ? `score (words ÷ ${CORE.WC_SCALE})` : "score", aria: `${METHODS[m].name} scores by true label`});
}
$("ev-methods").addEventListener("click", e => { const b = e.target.closest("button[data-m]"); if (!b) return; S.evalMethod = b.dataset.m; renderEval(); });
$("ev-thr").addEventListener("input", e => { S.thr[S.evalMethod] = +e.target.value; S.perMethod = true; syncThrNote(); renderEvalDetail(); });
$("ev-thr").addEventListener("change", () => { refreshViews(); });
$("ev-best").onclick = () => { const e = evalOf(S.evalMethod); if (e.best) { S.thr[S.evalMethod] = Math.round(e.best.thr * 1e4) / 1e4; S.perMethod = true; syncThrNote(); refreshViews(); } };
$("ev-apply-all").onclick = () => { evalMethods().forEach(m => { const e = evalOf(m); if (e.best) S.thr[m] = Math.round(e.best.thr * 1e4) / 1e4; }); S.perMethod = true; syncThrNote(); refreshViews(); };
$("ev-reset").onclick = () => { setAllThr(+$("thr").value); refreshViews(); };
$("swap").onclick = () => {
  const L = S.list; if (!L || !L.labelInfo) return;
  L.rows.forEach(r => { if (r.label !== null) r.label = 1 - r.label; });
  L.labelInfo.values.forEach(v => { if (v.cls !== null) v.cls = 1 - v.cls; });
  L.labelInfo.swapped = !L.labelInfo.swapped;
  refreshViews();
};

/* ---- training in the browser ---- */
$("tr-share").addEventListener("input", e => { $("tr-share-out").textContent = Math.round(e.target.value * 100) + "%"; });
function splitRows(rows, share, grouped, seed = 11) {
  const rand = CORE.rng(seed), test = new Set();
  if (grouped) {
    const groups = new Map();
    rows.forEach(r => { const k = r.mask; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); });
    const keys = [...groups.keys()];
    const order = CORE.sampleIdx(keys.length, keys.length, rand).map(i => keys[i]);
    const target = [0, 1].map(c => share * rows.filter(r => r.label === c).length), got = [0, 0];
    for (const k of order) {
      const g = groups.get(k), c = g.filter(r => r.label === 1).length >= g.length / 2 ? 1 : 0;
      if (got[c] < target[c]) { g.forEach(r => test.add(r)); g.forEach(r => { got[r.label]++; }); }
    }
  } else {
    [0, 1].forEach(c => { const cls = rows.filter(r => r.label === c); CORE.sampleIdx(cls.length, Math.round(share * cls.length), rand).forEach(i => test.add(cls[i])); });
  }
  return {train: rows.filter(r => !test.has(r)), test: rows.filter(r => test.has(r))};
}
$("tr-run").onclick = async () => {
  const L = S.list;
  const rows = L ? L.rows.filter(r => r.label !== null && r.feats) : [];
  const n1 = rows.filter(r => r.label === 1).length, n0 = rows.length - n1;
  if (n1 < 10 || n0 < 10) { $("tr-status").innerHTML = "<strong>Training needs at least 10 labelled rows of each kind.</strong>"; return; }
  const useEmb = S.emb.on && S.emb.ready && rows.every(r => r.cmp);
  const names = useEmb ? CORE.FEATURES_BASE.concat(CORE.FEATURES_EMB) : CORE.FEATURES_BASE.slice();
  const share = +$("tr-share").value, C = +$("tr-c").value, balanced = $("tr-bal").checked;
  let sp = splitRows(rows, share, $("tr-group").checked);
  if (!sp.test.some(r => r.label === 1) || !sp.test.some(r => r.label === 0) || sp.train.filter(r => r.label === 1).length < 5 || sp.train.filter(r => r.label === 0).length < 5) sp = splitRows(rows, share, false);
  $("tr-status").textContent = `Fitting on ${nf(sp.train.length)} rows…`;
  await tick();
  const X = rs => rs.map(r => names.map(f => r.feats[f]));
  const held = CORE.lrFit(X(sp.train), sp.train.map(r => r.label), {C, balanced, features: names});
  held.features = names;
  const pHeld = sp.test.map(r => CORE.lrScore(held, r.feats).p), yT = sp.test.map(r => r.label);
  const shippedSet = useEmb ? SHIPPED_MODEL.sets.emb : SHIPPED_MODEL.sets.base;
  const pShip = sp.test.map(r => CORE.lrScore(shippedSet, r.feats).p);
  const pWc = sp.test.map(r => CORE.wordCountScore(r.q));
  const wcTrain = CORE.bestThreshold(sp.train.map(r => CORE.wordCountScore(r.q)), sp.train.map(r => r.label));
  $("tr-status").textContent = `Refitting on all ${nf(rows.length)} labelled rows…`;
  await tick();
  const full = CORE.lrFit(X(rows), rows.map(r => r.label), {C, balanced, features: names});
  full.features = names;
  const r6 = v => Number(v.toPrecision(6));
  const set = {features: names, mean: full.mean.map(r6), scale: full.scale.map(r6), coef: full.coef.map(r6), intercept: r6(full.intercept), C, balanced};
  S.model.custom = {version: 1, created: new Date().toISOString().slice(0, 10), source: "trained in the browser", note: `Trained on ${rows.length} labelled rows from ${L.source}`,
    trained_on: {rows: rows.length, synthetic: n1, user: n0}, sets: {[useEmb ? "emb" : "base"]: set}};
  const line = (name, p, thr) => { const a = CORE.confusion(p, yT, thr), b = CORE.bestThreshold(p, yT), u = CORE.auc(p, yT);
    return `<tr><td>${name}</td><td class="n">${fx(a.accuracy, 3)}</td><td class="n">${fx(a.precision, 3)}</td><td class="n">${fx(a.recall, 3)}</td><td class="n"><b>${fx(a.f1, 3)}</b></td><td class="n">${b ? fx(b.f1, 3) : "n/a"}</td><td class="n">${u === null ? "n/a" : fx(u, 3)}</td></tr>`; };
  const top = names.map((f, i) => [f, full.coef[i]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 8);
  $("tr-result").innerHTML = `<div class="tablewrap" data-gap="14"><table class="data"><thead><tr><th>On the ${nf(sp.test.length)} held-out rows</th><th class="n">Accuracy</th><th class="n">Precision</th><th class="n">Recall</th><th class="n">F1 at 0.5</th><th class="n">Best F1</th><th class="n">AUC</th></tr></thead><tbody>
      ${line("Your model", pHeld, 0.5)}${line("Shipped ensemble", pShip, 0.5)}${line(`Word count only (${wcTrain ? wcWords(wcTrain.thr) : "?"}+ words, cut-off from the training rows)`, pWc, wcTrain ? wcTrain.thr : 0.5)}
    </tbody></table></div>
    <div class="keynote"><p>${useEmb ? "45 features, embeddings included" : "38 features without embeddings (switch embeddings on to add 7 more)"}; C = ${C}${balanced ? ", classes balanced" : ""}. The held-out rows were never used for fitting${$("tr-group").checked ? ", and rows sharing a slot-mask template stayed on one side" : ""}. The model you use and export was then refitted on all ${nf(rows.length)} labelled rows, so its scores on this list are no longer a fair test.</p>
    <p>Largest weights: ${top.map(([f, c]) => `${esc(FEATURE_NAMES[f] || f)} ${c >= 0 ? "+" : ""}${fx(c)}`).join(", ")}.</p></div>`;
  $("tr-result").hidden = false;
  $("tr-use").hidden = false; $("tr-export").hidden = false;
  $("tr-status").textContent = "Done.";
  setUseCustom(false);
};
function setUseCustom(on) {
  S.model.useCustom = on && !!S.model.custom;
  $("tr-use").setAttribute("aria-pressed", String(S.model.useCustom));
  $("tr-use").textContent = S.model.useCustom ? "Using your model (switch back)" : "Use my model for the list";
  rescoreAll();
}
$("tr-use").onclick = () => setUseCustom(!S.model.useCustom);
$("tr-export").onclick = () => { if (S.model.custom) offerFile("synthetic-query-model.json", JSON.stringify(S.model.custom, null, 1), "application/json"); };
$("tr-import").onchange = async e => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  try {
    const m = JSON.parse(await f.text());
    const known = new Set(CORE.FEATURES_BASE.concat(CORE.FEATURES_EMB));
    const ok = m && m.sets && Object.keys(m.sets).length && Object.entries(m.sets).every(([k, s]) => (k === "base" || k === "emb") && Array.isArray(s.features) &&
      s.features.every(x => known.has(x)) && [s.mean, s.scale, s.coef].every(a => Array.isArray(a) && a.length === s.features.length && a.every(Number.isFinite)) && Number.isFinite(s.intercept) &&
      (k === "emb" || s.features.every(x => CORE.FEATURES_BASE.includes(x))));
    if (!ok) throw new Error("this is not a weights file from this tool");
    S.model.custom = m;
    $("tr-use").hidden = false; $("tr-export").hidden = false;
    $("tr-status").textContent = `Imported ${esc(f.name)}${m.note ? ": " + m.note : ""}.`;
    setUseCustom(true);
  } catch (err) { $("tr-status").innerHTML = `<strong>Could not import:</strong> ${esc(err.message)}.`; }
};

/* =====================================================================================
   Batch patterns
   ===================================================================================== */
function renderBatch() {
  const L = S.list;
  $("batch-empty").hidden = !!L; $("batch-body").hidden = !L;
  if (!L) return;
  renderTemplates(); renderClusters(); renderPos(); renderDists();
}
function renderTemplates() {
  const L = S.list, min = +$("tpl-min").value, pm = primary();
  const rec = L.tpl.recurring.filter(t => t.rows.length >= min);
  const covered = rec.reduce((s, t) => s + t.rows.length, 0);
  if (!rec.length) { $("tpl-out").innerHTML = `<p class="hint">${nf(L.tpl.unique)} distinct templates across ${nf(L.rows.length)} queries, and none repeats ${min} or more times.</p>`; return; }
  const max = rec[0].rows.length;
  $("tpl-out").innerHTML = `<p class="hint">${nf(L.tpl.unique)} distinct templates across ${nf(L.rows.length)} queries; <b>${nf(rec.length)}</b> repeat ${min}+ times and cover ${nf(covered)} queries (${pct(covered / L.rows.length)}).</p>
    <div class="tablewrap"><table class="data"><thead><tr><th>Template</th><th>Repeats</th><th class="n">Synthetic share</th><th>Members</th></tr></thead><tbody>` +
    rec.slice(0, 100).map(t => { const syn = t.rows.filter(i => isSyn(L.rows[i], pm)).length / t.rows.length;
      return `<tr><td class="mono">${esc(t.template)}</td><td><span class="mbar"><i><b style="width:${w100(t.rows.length / max)}"></b></i>${t.rows.length}</span></td><td class="n">${pct(syn, 0)}</td>
      <td class="mem">${membersHtml(t.rows.map(i => L.rows[i].q), 2)}</td></tr>`; }).join("") + `</tbody></table></div>` +
    (rec.length > 100 ? `<p class="hint">Showing the top 100; the templates CSV has all ${nf(rec.length)}.</p>` : "");
}
function membersHtml(list, k) {
  const first = list.slice(0, k).map(q => `<li>${esc(q)}</li>`).join("");
  const rest = list.slice(k);
  return `<ul class="members">${first}</ul>` + (rest.length ? `<details class="more"><summary>${nf(rest.length)} more</summary><ul class="members">${rest.slice(0, 200).map(q => `<li>${esc(q)}</li>`).join("")}${rest.length > 200 ? `<li class="hint">and ${nf(rest.length - 200)} more in the CSV</li>` : ""}</ul></details>` : "");
}
$("tpl-min").onchange = () => renderTemplates();

$("cl-run").onclick = async () => {
  const L = S.list; if (!L || S.clBusy) return;
  if (!S.emb.on || !S.emb.ready) { $("cl-status").innerHTML = "<strong>Switch on embeddings first</strong> (settings at the top). Batches are found in embedding space."; return; }
  if (S.busy) { $("cl-status").textContent = "Wait for the list to finish scoring."; return; }
  if (L.rows.some(r => !r.vec)) await embedList();
  const rows = L.rows.filter(r => r.vec).slice(0, CLUSTER_CAP);
  const min = Math.max(2, Math.min(500, +$("cl-min").value || 5));
  S.clBusy = true; S.clStop = false; $("cl-stop").hidden = false; $("cl-prog").hidden = false; $("cl-prog").value = 0;
  $("cl-status").textContent = "Clustering…";
  try {
    const vecs = rows.map(r => r.vec);
    const res = await CORE.hdbscan(vecs, min, {progress: (v, label) => { $("cl-prog").value = v; $("cl-status").textContent = `${label}…`; }, stopped: () => S.clStop});
    if (!res) { $("cl-status").textContent = "Stopped."; return; }
    const pm = primary();
    const report = CORE.starReport(vecs, rows.map(r => r.q), res.clusters, rows.map(r => isSyn(r, pm)));
    $("cl-status").textContent = "Projecting the map…"; await tick();
    const coords = rows.length >= 3 ? CORE.pca2(vecs) : null;
    S.clusters = {rows, labels: res.labels, report, coords, min, capped: L.rows.length > CLUSTER_CAP ? L.rows.length - CLUSTER_CAP : 0, method: pm};
    S.clSel = report.length ? report[0].id : -1;
    $("cl-status").textContent = "";
    renderClusters(); renderList();
  } catch (e) {
    $("cl-status").innerHTML = `<strong>Clustering failed:</strong> ${esc(e && e.message || e)}`;
  } finally { S.clBusy = false; $("cl-stop").hidden = true; $("cl-prog").hidden = true; }
};
$("cl-stop").onclick = () => { S.clStop = true; };
function renderClusters() {
  const C = S.clusters, out = $("cl-out");
  if (!C) { out.innerHTML = S.emb.on && S.emb.ready ? "" : `<p class="hint">Needs embeddings: switch them on in the settings, then press Find fan-out batches.</p>`; return; }
  const noise = C.labels.filter(l => l < 0).length;
  if (!C.report.length) { out.innerHTML = `<p class="hint">No dense batches of ${C.min}+ queries in ${nf(C.rows.length)} queries; all ${nf(noise)} are scattered. Try a smaller batch size, or a list that holds a whole fan-out.</p>`; return; }
  const sel = C.report.find(c => c.id === S.clSel) || C.report[0];
  out.innerHTML = `<p class="hint" data-gap="12">${nf(C.report.length)} batch${C.report.length === 1 ? "" : "es"} of ${C.min}+ queries in ${nf(C.rows.length)} queries; ${nf(noise)} scattered queries belong to none.${C.capped ? ` Only the first ${nf(CLUSTER_CAP)} queries were clustered.` : ""} Random groups of the same size have a cohesion of about ${fx(C.report[0].baseline, 2)}.</p>
    <div class="evgrid">
      <div>${clusterMap(C, sel)}<div class="legend"><span><i class="sw scat"></i>scattered</span><span class="is-synth"><i class="sw"></i>in a batch</span><span><i class="sw sel"></i>selected batch, spokes to its hub</span></div><div class="hint">First two principal components of the embeddings; distances are only roughly kept.</div></div>
      <div><div class="lbl">Batch ${sel.rank}${sel.candidate ? " &middot; strongest fan-out candidate" : ""}</div>
        <div class="mt"><div><div class="k">Queries</div><div class="v">${sel.size}</div></div><div><div class="k">Cohesion</div><div class="v">${fx(sel.cohesion)}</div></div><div><div class="k">Above random</div><div class="v">${sel.lift >= 0 ? "+" : ""}${fx(sel.lift)}</div></div><div><div class="k">Facet spread</div><div class="v">${fx(sel.facetSpread)}</div></div><div><div class="k">Synthetic</div><div class="v">${pct(sel.synShare, 0)}</div></div></div>
        <ul class="members" data-gap="10">${sel.members.slice(0, 12).map(i => `<li>${esc(C.rows[i].q)}</li>`).join("")}</ul>${sel.size > 12 ? `<details class="more"><summary>${sel.size - 12} more</summary><ul class="members">${sel.members.slice(12, 300).map(i => `<li>${esc(C.rows[i].q)}</li>`).join("")}</ul></details>` : ""}
      </div>
    </div>
    <div class="tablewrap" data-gap="14"><table class="data"><thead><tr><th class="n">Rank</th><th class="n">Queries</th><th class="n">Cohesion</th><th class="n">Above random</th><th class="n">Facet spread</th><th class="n">Fan-out score</th><th class="n">Synthetic</th><th>Members</th></tr></thead><tbody>` +
    C.report.slice(0, S.clAll ? 200 : 15).map(c => `<tr class="${c.id === sel.id ? "best" : ""}"><td class="n">${c.rank}${c.candidate ? " &#9733;" : ""}</td><td class="n">${c.size}</td><td class="n">${fx(c.cohesion)}</td><td class="n">${c.lift >= 0 ? "+" : ""}${fx(c.lift)}</td><td class="n">${fx(c.facetSpread)}</td><td class="n"><b>${fx(c.score, 3)}</b></td><td class="n">${pct(c.synShare, 0)}</td>
      <td class="mem"><button type="button" class="link small" data-c="${c.id}">Show on the map</button>${membersHtml(c.members.map(i => C.rows[i].q), 2)}</td></tr>`).join("") + `</tbody></table></div>` +
    (C.report.length > 15 ? `<div class="actions"><button type="button" class="ghost small" id="cl-all">${S.clAll ? "Show the top 15" : `Show all ${nf(Math.min(C.report.length, 200))} batches`}</button><span class="hint">The batches CSV has every batch and member.</span></div>` : "");
}
$("cl-out").addEventListener("click", e => { if (e.target.id === "cl-all") { S.clAll = !S.clAll; renderClusters(); return; } const b = e.target.closest("button[data-c]"); if (!b) return; S.clSel = +b.dataset.c; renderClusters(); $("cl-out").scrollIntoView({behavior: "smooth", block: "start"}); });
function clusterMap(C, sel) {
  const box = $("cl-out"), full = widthOf(box, 1000), W = full >= 700 ? Math.floor((full - 18) / 2) : full, H = Math.round(Math.min(420, Math.max(260, W * 0.72))), pad = 14, pts = C.coords;
  if (!pts) return "";
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = v => pad + (v - x0) / ((x1 - x0) || 1) * (W - 2 * pad), Y = v => H - pad - (v - y0) / ((y1 - y0) || 1) * (H - 2 * pad);
  const inSel = new Set(sel ? sel.members : []);
  let back = "", mid = "", front = "";
  pts.forEach((p, i) => {
    const lab = C.labels[i];
    if (inSel.has(i)) return;
    if (lab < 0) back += `<circle class="pt" cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.2"/>`;
    else mid += `<circle class="pt-c" cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.6"/>`;
  });
  if (sel) {
    const hx = sel.members.reduce((s, i) => s + X(pts[i][0]), 0) / sel.size, hy = sel.members.reduce((s, i) => s + Y(pts[i][1]), 0) / sel.size;
    sel.members.forEach(i => { front += `<line class="spoke" x1="${hx.toFixed(1)}" y1="${hy.toFixed(1)}" x2="${X(pts[i][0]).toFixed(1)}" y2="${Y(pts[i][1]).toFixed(1)}"/>`; });
    sel.members.forEach(i => { front += `<circle class="pt-sel" cx="${X(pts[i][0]).toFixed(1)}" cy="${Y(pts[i][1]).toFixed(1)}" r="3.6"></circle>`; });
    front += `<rect class="hub" x="${(hx - 4).toFixed(1)}" y="${(hy - 4).toFixed(1)}" width="8" height="8" transform="rotate(45 ${hx.toFixed(1)} ${hy.toFixed(1)})"/>`;
  }
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of the queries in embedding space, with the selected batch and its hub highlighted"><rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" fill="none" class="axis"/>${back}${mid}${front}</svg>`;
}
function splitBy(m) {
  const L = S.list, labelled = !!L.labelInfo && L.rows.some(r => r.label !== null);
  return labelled ? {by: "your labels", user: r => r.label === 0, syn: r => r.label === 1}
    : {by: `the ${METHODS[m].name.toLowerCase()}'s labels`, user: r => !isSyn(r, m), syn: r => isSyn(r, m)};
}
function renderPos() {
  const L = S.list;
  if (!CORE.hasNLP()) { $("pos-out").innerHTML = `<p class="hint">The language library did not load, so part-of-speech tags are not available.</p>`; return; }
  const sp = splitBy(primary());
  const u = L.rows.filter(sp.user).map(r => r.nb2.posf.pos_entropy), s = L.rows.filter(sp.syn).map(r => r.nb2.posf.pos_entropy);
  const all = u.concat(s), hi = Math.max(3, ...all), mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : NaN;
  const mu = mean(u), ms = mean(s), marks = [];
  if (Number.isFinite(mu)) marks.push({x: mu, cls: "mean-usr", label: `user mean ${fx(mu)}`});
  if (Number.isFinite(ms)) marks.push({x: ms, cls: "mean-syn", label: `synthetic mean ${fx(ms)}`});
  if (Number.isFinite(mu) && Number.isFinite(ms)) marks.push({x: (mu + ms) / 2, cls: "mid", label: `midpoint ${fx((mu + ms) / 2)}`});
  const sep = ms - mu;
  $("pos-out").innerHTML = histogram([{values: u, cls: "bar-usr"}, {values: s, cls: "bar-syn"}], {width: widthOf($("pos-out")), min: 0, max: hi, bins: 24, markers: marks, height: 230,
      xlabel: "POS entropy in bits (low: noun-heavy, telegraphic; high: balanced, well-formed)", aria: "Part-of-speech entropy by class"}) +
    `<div class="legend"><span class="is-user"><i class="sw"></i>User (${nf(u.length)})</span><span class="is-synth"><i class="sw"></i>Synthetic (${nf(s.length)})</span><span>split by ${esc(sp.by)}</span></div>` +
    (Number.isFinite(sep) ? `<p class="hint" data-gap="8">Class means ${fx(mu)} and ${fx(ms)} bits, ${fx(Math.abs(sep))} apart. ${Math.abs(sep) > 0.3 ? "A clear gap: entropy alone separates much of this list." : "A modest gap: read it together with the other signals."} Notebook 2 reported 1.88 and 2.05 on the course&rsquo;s test set with spaCy&rsquo;s tags; compromise tags give somewhat different values.</p>` : "");
}
function renderDists() {
  const L = S.list, ms = shownMethods(), labelled = !!L.labelInfo && L.rows.some(r => r.label !== null);
  $("dist-note").textContent = labelled ? "Split by your labels." : "Split by each method's own labels.";
  const dw = widthOf($("dists"), 1000), cols = Math.max(1, Math.floor((dw + 14) / (330 + 14))), cw = Math.max(260, Math.floor((dw - 14 * (cols - 1)) / cols) - 42);
  $("dists").innerHTML = ms.map(m => {
    const sp = labelled ? {user: r => r.label === 0, syn: r => r.label === 1} : {user: r => !isSyn(r, m), syn: r => isSyn(r, m)};
    const u = L.rows.filter(sp.user).map(r => scoreOf(r, m)).filter(Number.isFinite), s = L.rows.filter(sp.syn).map(r => scoreOf(r, m)).filter(Number.isFinite);
    return `<div class="panel"><h3>${esc(METHODS[m].name)} <span class="nbtag">${METHODS[m].nb}</span></h3>${histogram([{values: u, cls: "bar-usr"}, {values: s, cls: "bar-syn"}], {width: cw, height: 170, min: 0, max: 1, bins: 20, markers: [{x: S.thr[m], cls: "thr", label: "threshold"}], aria: `${METHODS[m].name} score distribution`})}
      <div class="legend"><span class="is-user"><i class="sw"></i>User (${nf(u.length)})</span><span class="is-synth"><i class="sw"></i>Synthetic (${nf(s.length)})</span></div></div>`;
  }).join("");
}

/* ---------- SVG histogram in the house colours ---------- */
// Charts are drawn at the width they are shown at, so their text stays at its real size.
function widthOf(el, fallback = 520) { const w = el && el.clientWidth; return w > 0 ? Math.max(260, Math.min(1100, Math.round(w))) : fallback; }
function histogram(series, o) {
  const W = o.width || 520, H = o.height || 200, m = {l: 40, r: 12, t: 18, b: o.xlabel ? 38 : 24};
  const bins = o.bins || 20, lo = o.min, hi = o.max, bw = (hi - lo) / bins;
  const counts = series.map(s => { const c = new Array(bins).fill(0); s.values.forEach(v => { if (!Number.isFinite(v)) return; c[Math.max(0, Math.min(bins - 1, Math.floor((v - lo) / bw)))]++; }); return c; });
  const ymax = Math.max(1, ...counts.flat());
  const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r), Y = c => H - m.b - c / ymax * (H - m.t - m.b);
  let g = "";
  [0, 0.5, 1].forEach(f => { const v = Math.round(ymax * f); g += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text x="${m.l - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${v}</text>`; });
  counts.forEach((c, si) => c.forEach((n, k) => {
    if (!n) return;
    const x0 = X(lo + k * bw) + 0.5, x1 = X(lo + (k + 1) * bw) - 0.5;
    g += `<rect class="${series[si].cls}" x="${x0.toFixed(1)}" y="${Y(n).toFixed(1)}" width="${Math.max(0.5, x1 - x0).toFixed(1)}" height="${(H - m.b - Y(n)).toFixed(1)}"></rect>`;
  }));
  g += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/>`;
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; g += `<text x="${X(v).toFixed(1)}" y="${H - m.b + 14}" text-anchor="middle">${fx(v, hi - lo > 2 ? 1 : 2)}</text>`; }
  (o.markers || []).forEach((mk, i) => {
    if (!Number.isFinite(mk.x)) return;
    const x = X(Math.max(lo, Math.min(hi, mk.x)));
    g += `<line class="${mk.cls}" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${m.t - 6}" y2="${H - m.b}"/>`;
    if (mk.label) g += `<text class="t" x="${(x + 4).toFixed(1)}" y="${m.t - 6 + 11 * i}" text-anchor="${x > W * 0.7 ? "end" : "start"}" dx="${x > W * 0.7 ? -8 : 0}">${esc(mk.label)}</text>`;
  });
  if (o.xlabel) g += `<text x="${(m.l + W - m.r) / 2}" y="${H - 4}" text-anchor="middle">${esc(o.xlabel)}</text>`;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || "histogram")}">${g}</svg>`;
}

/* =====================================================================================
   Exports
   ===================================================================================== */
function csvCell(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "number") return Number.isFinite(v) ? String(Math.round(v * 10000) / 10000) : "";
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
const toCSV = (head, rows) => [head.map(csvCell).join(",")].concat(rows.map(r => r.map(csvCell).join(","))).join("\r\n");
async function offerFile(filename, text, mime) {
  const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(() => null) : null;
  if (api) { try { await api.save({filename, data: text}); return "saved"; } catch (e) { return e && e.code === "declined" ? "declined" : "failed"; } }
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([(mime === "text/csv" ? "\uFEFF" : "") + text], {type: mime + ";charset=utf-8"}));
  a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000); return "saved";
}
const lab = (r, m) => { const s = scoreOf(r, m); return Number.isFinite(s) ? (s >= S.thr[m] ? "synthetic" : "user") : ""; };
$("dl-results").onclick = () => {
  const L = S.list; if (!L) return;
  const emb = L.rows.some(r => r.nb3), batch = new Map();
  if (S.clusters) S.clusters.report.forEach(c => c.members.forEach(i => batch.set(S.clusters.rows[i].i, c.rank)));
  const head = ["query", "words"].concat(L.labelInfo ? ["your_label"] : [],
    ["ensemble_score", "ensemble_label", "ensemble_confidence", "ensemble_model", "ensemble_threshold"],
    ["rule_score", "rule_label", "rule_confidence", "rule_length", "rule_structure", "rule_patterns", "rule_messiness", "rule_vocabulary", "patent_types", "type_hints"],
    ["linguistic_score", "linguistic_label", "linguistic_confidence", "ling_entity", "ling_pos", "ling_lexical", "ling_ngram", "entity_count", "entities", "pos_entropy", "flesch_reading_ease", "ngram_hits"],
    emb ? ["embedding_score", "embedding_label", "embedding_confidence", "emb_centroid", "emb_knn", "emb_max_similarity", "emb_typicality", "nearest_synthetic_ref", "nearest_synthetic_sim", "nearest_user_ref", "nearest_user_sim"] : [],
    ["word_count_score", "template", "template_count"], S.clusters ? ["fanout_batch_rank"] : []);
  const rows = L.rows.map(r => [r.q, r.wc].concat(L.labelInfo ? [r.label === null ? "" : r.label ? "synthetic" : "user"] : [],
    r.ens ? [r.ens.p, lab(r, "ens"), confOf(r, "ens"), `${r.ens.who}, ${r.ens.emb ? "with" : "without"} embeddings`, S.thr.ens] : ["", "", "", "", ""],
    [r.nb1.score, lab(r, "nb1"), confOf(r, "nb1"), r.nb1.signals.length, r.nb1.signals.structure, r.nb1.signals.template, r.nb1.signals.messiness, r.nb1.signals.vocabulary,
      r.nb1.types.map(t => TYPE_NAMES[t]).join("; "), r.nb1.hints.map(h => TYPE_NAMES[h[0]]).join("; ")],
    r.nb2 ? [r.nb2.score, lab(r, "nb2"), confOf(r, "nb2"), r.nb2.components.entity, r.nb2.components.pos, r.nb2.components.lexical, r.nb2.components.ngram,
      r.nb2.entity.entity_count, r.nb2.entity.entities.map(e => `${e.text} (${e.label})`).join("; "), r.nb2.posf.pos_entropy, r.nb2.lexical.flesch_reading_ease, r.nb2.ngramf.hits.join("; ")] : new Array(12).fill(""),
    emb ? (r.nb3 ? [r.nb3.score, lab(r, "nb3"), confOf(r, "nb3"), r.nb3.signals.centroid, r.nb3.signals.knn, r.nb3.signals.max_similarity, r.nb3.signals.norm,
      r.nb3.nearestSyn.text, r.nb3.nearestSyn.sim, r.nb3.nearestHum.text, r.nb3.nearestHum.sim] : new Array(11).fill("")) : [],
    [CORE.wordCountScore(r.q), r.mask, r.tpl], S.clusters ? [batch.get(r.i) || ""] : []));
  offerFile("synthetic-query-classification.csv", toCSV(head, rows), "text/csv");
};
$("dl-templates").onclick = () => {
  const L = S.list; if (!L) return;
  const pm = primary();
  const rows = L.tpl.recurring.map(t => [t.template, t.rows.length, t.rows.filter(i => isSyn(L.rows[i], pm)).length / t.rows.length, t.rows.map(i => L.rows[i].q).join(" | ")]);
  offerFile("synthetic-query-templates.csv", toCSV(["template", "count", `synthetic_share_${pm}`, "members"], rows), "text/csv");
};
$("dl-clusters").onclick = () => {
  const C = S.clusters; if (!C) return;
  const rows = C.report.map(c => [c.rank, c.size, c.cohesion, c.baseline, c.lift, c.facetSpread, c.score, c.synShare, c.candidate ? "yes" : "", c.nb3Spread, c.nb3Star, c.nb3StarLift, c.members.map(i => C.rows[i].q).join(" | ")]);
  offerFile("synthetic-query-fanout-batches.csv", toCSV(["rank", "size", "cohesion", "random_cohesion", "cohesion_above_random", "facet_spread", "fanout_score", `synthetic_share_${C.method}`, "strongest_candidate", "nb3_embedding_spread", "nb3_star_score", "nb3_star_lift", "members"], rows), "text/csv");
};

/* =====================================================================================
   Settings
   ===================================================================================== */
function setAllThr(v) { Object.keys(S.thr).forEach(k => { S.thr[k] = v; }); S.perMethod = false; $("thr").value = String(v); syncThrNote(); }
function syncThrNote() {
  $("thr-out").textContent = S.perMethod ? "per method" : fx(+$("thr").value);
  $("thr-note").innerHTML = S.perMethod ? `Each method has its own cut-off: ${["ens", "nb1", "nb3", "nb2"].filter(avail).map(m => `${esc(METHODS[m].name)} ${fx(S.thr[m])}`).join(", ")}. Moving this slider sets them all again.`
    : "One cut-off for every method. Evaluate &amp; train can set one per method.";
}
let rafPending = false;
function refreshSoon() { if (rafPending) return; rafPending = true; requestAnimationFrame(() => { rafPending = false; refreshViews(); }); }
$("thr").addEventListener("input", e => { setAllThr(+e.target.value); refreshSoon(); });
["nb1", "nb2", "ens"].forEach(m => $("m-" + m).addEventListener("change", e => { S.show[m] = e.target.checked; refreshViews(); }));
$("emb-toggle").addEventListener("change", e => {
  if (S.busy) {
    S.pending = e.target.checked ? () => setEmbeddings(true) : null;
    if (e.target.checked) { embStatus("Loads when the current list has finished&hellip;"); return; }
  }
  setEmbeddings(e.target.checked);
});

fillRefBoxes();
syncThrNote();
if (!CORE.hasNLP()) {
  $("m-nb2").disabled = true; $("m-ens").disabled = true;
  embStatus("<strong>The language library (compromise) did not load</strong>, so the linguistic method and the ensemble are unavailable. Rule-based scoring and embeddings still work.");
}
$("iq").value = EXAMPLES[2];
inspect(EXAMPLES[2]);
