// Compute the ensemble's features for a labelled CSV with the tool's own code.
//
//   node features.mjs --in out/generic.csv --out out/generic.features.json [--tool <path>] [--no-emb]
//
// The feature code is not copied here: lib/core.cjs cuts the CORE block out of the tool's HTML and runs it
// with the same compromise version the page loads, and embeddings come from the same model and settings
// (Xenova/all-MiniLM-L6-v2, quantised, mean pooling, normalised) through transformers.js for Node.
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { loadCore, readCSV, args, DEFAULT_TOOL } = require('./lib/core.cjs');
const { embedTexts } = await import('./lib/embed.mjs');

const a = args(process.argv.slice(2));
const CORE = loadCore(a.tool || DEFAULT_TOOL);
const rows = readCSV(CORE, a.in);
const queries = rows.map(r => r.query), labels = rows.map(r => +r.label);
const t0 = Date.now();
const base = [], emb = [];
queries.forEach(q => {
  const f = CORE.nb4Features(q, CORE.nlpAnalysis(q), null);
  base.push(CORE.FEATURES_BASE.map(k => f[k]));
});
if (!a['no-emb']) {
  const refTexts = [...CORE.SYN_REFS, ...CORE.HUM_REFS].map(r => r[0]);
  const vecs = await embedTexts([...refTexts, ...queries], a.cache);
  const nS = CORE.SYN_REFS.length;
  const refs = CORE.prepareRefs({
    syn: CORE.SYN_REFS.map((r, i) => ({ text: r[0], type: r[1], vec: vecs[i] })),
    hum: CORE.HUM_REFS.map((r, i) => ({ text: r[0], type: r[1], vec: vecs[nS + i] }))
  });
  queries.forEach((q, i) => {
    const f = CORE.nb4Features(q, null, CORE.embCompare(vecs[refTexts.length + i], refs));
    emb.push(CORE.FEATURES_EMB.map(k => f[k]));
  });
}
const out = { tool: path.resolve(a.tool || DEFAULT_TOOL), created: new Date().toISOString(), features_base: CORE.FEATURES_BASE,
  features_emb: CORE.FEATURES_EMB, queries, labels, sources: rows.map(r => r.source || ''), groups: rows.map(r => r.group || ''),
  base, emb: emb.length ? emb : null };
fs.mkdirSync(path.dirname(a.out), { recursive: true });
fs.writeFileSync(a.out, JSON.stringify(out));
console.log(`${queries.length} rows, ${CORE.FEATURES_BASE.length}${emb.length ? ' + ' + CORE.FEATURES_EMB.length : ''} features in ${((Date.now() - t0) / 1000).toFixed(1)}s -> ${a.out}`);
