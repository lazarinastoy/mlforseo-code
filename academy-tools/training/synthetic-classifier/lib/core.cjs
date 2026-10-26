// Load the tool's CORE block (feature, scoring, model and analysis code) into Node.
// The block sits between "==== CORE START ====" and "==== CORE END ====" in the tool's single inline script.
const fs = require('fs');
const path = require('path');

const DEFAULT_TOOL = path.resolve(__dirname, '../../../tools/synthetic-vs-user-generated-queries-classifier.html');

function loadCore(file = DEFAULT_TOOL) {
  const src = fs.readFileSync(file, 'utf8');
  const a = src.indexOf('/* ==== CORE START ===='), b = src.indexOf('/* ==== CORE END ==== */');
  if (a < 0 || b < 0) throw new Error('CORE markers not found in ' + file);
  const nlp = require('compromise');
  return new Function('nlp', src.slice(a, b) + '\nreturn CORE;')(nlp);
}

// The model JSON the tool ships, between the MODEL-JSON markers.
function readModel(file = DEFAULT_TOOL) {
  const src = fs.readFileSync(file, 'utf8');
  const m = src.match(/\/\* MODEL-JSON-START \*\/([\s\S]*?)\/\* MODEL-JSON-END \*\//);
  if (!m) throw new Error('MODEL-JSON markers not found in ' + file);
  return JSON.parse(m[1]);
}

function readCSV(CORE, file) {
  const text = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  const rows = CORE.parseDelimited(text, CORE.detectDelimiter(text) || ',');
  const head = rows.shift().map(h => h.trim());
  return rows.map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith('--')) continue;
    const k = argv[i].slice(2), v = argv[i + 1];
    if (v === undefined || v.startsWith('--')) out[k] = true; else { out[k] = v; i++; }
  }
  return out;
}

module.exports = { loadCore, readModel, readCSV, args, DEFAULT_TOOL };
