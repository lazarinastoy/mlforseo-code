// Score a labelled CSV with every method in the tool, using the tool's own code and shipped model, and
// print the comparison the tool's Evaluate tab shows (accuracy, precision, recall, F1 at a threshold, the
// best-F1 threshold, AUC), next to the word-count-only baseline.
//
//   node evaluate.mjs --in out/external_test.csv [--tool <path>] [--thr 0.5] [--no-emb] [--refs-from-labels] [--out scores.csv]
//
// --refs-from-labels draws Notebook 3's references from the labelled rows (40 per class, as the notebook
// does) and leaves those rows out of the embeddings method's metrics.
import fs from 'fs';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { loadCore, readModel, readCSV, args, DEFAULT_TOOL } = require('./lib/core.cjs');

const a = args(process.argv.slice(2));
const toolPath = a.tool || DEFAULT_TOOL;
const CORE = loadCore(toolPath), MODEL = readModel(toolPath);
const thr = a.thr ? +a.thr : 0.5;
const rows = readCSV(CORE, a.in).map(r => ({ q: r.query ?? r.keyword, y: CORE.mapLabel(r.label ?? r.Type) })).filter(r => r.q && r.y !== null);
const t0 = Date.now();
rows.forEach(r => {
  const A = CORE.nlpAnalysis(r.q);
  r.nb1 = CORE.nb1(r.q).score;
  r.nb2 = CORE.nb2(r.q, A).score;
  r.f = CORE.nb4Features(r.q, A, null);
  r.ensBase = CORE.lrScore(MODEL.sets.base, r.f).p;
  r.wc = CORE.wordCountScore(r.q);
});
const methods = [['Rule-based (NB1)', 'nb1'], ['Entity & linguistic (NB2)', 'nb2'], ['Ensemble, no embeddings', 'ensBase']];
let skipNb3 = new Set();
if (!a['no-emb']) {
  const { embedTexts } = await import('./lib/embed.mjs');
  const vecs = await embedTexts(rows.map(r => r.q));
  const def = [...CORE.SYN_REFS, ...CORE.HUM_REFS];
  const dv = await embedTexts(def.map(r => r[0]));
  const nS = CORE.SYN_REFS.length;
  const refs = CORE.prepareRefs({ syn: CORE.SYN_REFS.map((r, i) => ({ text: r[0], type: r[1], vec: dv[i] })), hum: CORE.HUM_REFS.map((r, i) => ({ text: r[0], type: r[1], vec: dv[nS + i] })) });
  let nb3Refs = refs;
  if (a['refs-from-labels']) {
    const rand = CORE.rng(42);
    const pick = c => { const idx = rows.map((r, i) => r.y === c ? i : -1).filter(i => i >= 0); return CORE.sampleIdx(idx.length, Math.min(40, idx.length), rand).map(k => idx[k]); };
    const s = pick(1), h = pick(0);
    skipNb3 = new Set([...s, ...h]);
    nb3Refs = CORE.prepareRefs({ syn: s.map(i => ({ text: rows[i].q, type: 'data', vec: vecs[i] })), hum: h.map(i => ({ text: rows[i].q, type: 'data', vec: vecs[i] })) });
  }
  rows.forEach((r, i) => {
    r.nb3 = CORE.nb3(vecs[i], nb3Refs).score;
    const cmp = CORE.embCompare(vecs[i], refs);
    r.ensEmb = CORE.lrScore(MODEL.sets.emb, Object.assign({}, r.f, CORE.embFeatures(cmp))).p;
  });
  methods.splice(2, 0, ['Embeddings (NB3)', 'nb3']);
  methods.push(['Ensemble, with embeddings', 'ensEmb']);
}
methods.push(['Word count only', 'wc']);
const pad = (s, n) => String(s).padEnd(n);
console.log(`${rows.length} labelled rows (${rows.filter(r => r.y === 1).length} synthetic, ${rows.filter(r => r.y === 0).length} user), scored in ${((Date.now() - t0) / 1000).toFixed(1)}s; threshold ${thr}`);
console.log(pad('method', 28) + 'acc    prec   rec    F1     | best thr  F1     | AUC');
for (const [name, k] of methods) {
  const use = rows.filter((r, i) => !(k === 'nb3' && skipNb3.has(i)));
  const s = use.map(r => r[k]), y = use.map(r => r.y);
  const m = CORE.confusion(s, y, thr), b = CORE.bestThreshold(s, y), auc = CORE.auc(s, y);
  const words = k === 'wc' ? ` (${Math.ceil(b.thr * CORE.WC_SCALE - 1e-9)}+ words)` : '';
  console.log(pad(name, 28) + [m.accuracy, m.precision, m.recall, m.f1].map(v => v.toFixed(3)).join('  ') + ` | ${b.thr.toFixed(3)}${words}  ${b.f1.toFixed(3)} | ${auc.toFixed(3)}`);
}
if (a.out) {
  const keys = methods.map(m => m[1]);
  fs.writeFileSync(a.out, ['query,label,' + keys.join(',')].concat(rows.map(r => [JSON.stringify(r.q), r.y, ...keys.map(k => r[k] === undefined ? '' : r[k])].join(','))).join('\n'));
}
