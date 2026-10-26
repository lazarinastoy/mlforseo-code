
/* ===== Classification logic: unchanged from the original tool ===== */
// Enhanced NLP utilities
const stopWords = new Set(['a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the', 'to', 'was', 'will', 'with', 'the', 'this', 'but', 'they', 'have', 'had', 'what', 'when', 'where', 'who', 'which', 'why', 'how']);

const questionWords = new Set(['who', 'what', 'where', 'when', 'why', 'how', 'whose', 'whom', 'which']);

const technicalTerms = {
    medical: ['diagnosis', 'symptoms', 'treatment', 'syndrome', 'pathology', 'etiology', 'prognosis', 'therapeutic', 'clinical', 'metabolic', 'physiological'],
    technical: ['architecture', 'implementation', 'optimization', 'configuration', 'methodology', 'paradigm', 'infrastructure', 'algorithm', 'protocol'],
    scientific: ['biomechanical', 'metabolic', 'cellular', 'physiological', 'mechanism', 'process', 'molecular', 'organic', 'chemical'],
    business: ['stakeholder', 'leverage', 'synergy', 'utilization', 'implementation', 'strategic', 'operational', 'organizational']
};

const prepositions = new Set(['in', 'on', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'from', 'up', 'down', 'over', 'under']);

// Simple entity detection
function detectEntities(query) {
    const words = query.split(/\s+/);
    const entities = [];

    // Detect capitalized words (excluding first word)
    words.forEach((word, i) => {
        if (i > 0 && /^[A-Z]/.test(word)) {
            entities.push(word);
        }
    });

    // Detect common entity patterns
    const commonEntities = /\b(iPhone|Android|Python|JavaScript|Google|Amazon|Apple|Microsoft|Tesla|COVID|DNA|RNA|SQL|API|CPU|GPU)\b/gi;
    const matches = query.match(commonEntities);
    if (matches) {
        entities.push(...matches);
    }

    return [...new Set(entities)]; // Remove duplicates
}

// Calculate reading grade level (Flesch-Kincaid approximation)
function calculateReadingGrade(query) {
    const words = query.split(/\s+/).filter(w => w.length > 0);
    const sentences = query.split(/[.!?]+/).filter(s => s.trim().length > 0).length || 1;
    const syllables = words.reduce((sum, word) => sum + countSyllables(word), 0);

    const avgWordsPerSentence = words.length / sentences;
    const avgSyllablesPerWord = syllables / (words.length || 1);

    const grade = 0.39 * avgWordsPerSentence + 11.8 * avgSyllablesPerWord - 15.59;
    return Math.max(0, Math.min(20, grade)); // Clamp between 0-20
}

function countSyllables(word) {
    word = word.toLowerCase();
    if (word.length <= 3) return 1;
    word = word.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '');
    word = word.replace(/^y/, '');
    const matches = word.match(/[aeiouy]{1,2}/g);
    return matches ? matches.length : 1;
}

// Feature extraction
function extractFeatures(query) {
    const tokens = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);
    const entities = detectEntities(query);
    const words = query.split(/\s+/).filter(w => w.length > 0);

    const stopWordCount = tokens.filter(t => stopWords.has(t)).length;
    const hasQuestionWord = tokens.some(t => questionWords.has(t));
    const prepositionCount = tokens.filter(t => prepositions.has(t)).length;

    // Find technical terms
    const techTermsFound = [];
    const queryLower = query.toLowerCase();
    Object.values(technicalTerms).forEach(terms => {
        terms.forEach(term => {
            if (queryLower.includes(term)) {
                techTermsFound.push(term);
            }
        });
    });

    return {
        char_count: query.length,
        word_count: words.length,
        avg_word_length: tokens.reduce((sum, t) => sum + t.length, 0) / (tokens.length || 1),
        stop_word_ratio: stopWordCount / (tokens.length || 1),
        has_question_word: hasQuestionWord,
        unique_word_ratio: new Set(tokens).size / (tokens.length || 1),
        entity_count: entities.length,
        entity_density: entities.length / (tokens.length || 1),
        reading_grade: calculateReadingGrade(query),
        is_question: query.trim().endsWith('?'),
        preposition_count: prepositionCount,
        capitalized_words: words.filter(w => /^[A-Z]/.test(w)).length,
        tech_terms_found: techTermsFound,
        tech_term_count: techTermsFound.length
    };
}

// Rule-based classification
function classifyRuleBased(query, options = {}) {
    const features = extractFeatures(query);

    const lengthThreshold = options.lengthThreshold || 5;
    const gradeThreshold = options.gradeThreshold || 10;
    const entityThreshold = options.entityThreshold || 0.35;
    const classThreshold = options.classThreshold || 4;

    let syntheticScore = 0;
    const reasons = [];

    // Rule 1: Length
    if (features.word_count >= lengthThreshold) {
        syntheticScore += 1;
        reasons.push(`Long query (${features.word_count} words ≥ ${lengthThreshold})`);
    }

    // Rule 2: Low stop word ratio
    if (features.stop_word_ratio < 0.2) {
        syntheticScore += 1;
        reasons.push(`Low stop word usage (${(features.stop_word_ratio * 100).toFixed(1)}%)`);
    }

    // Rule 3: High reading grade
    if (features.reading_grade > gradeThreshold) {
        syntheticScore += 2;
        reasons.push(`High reading complexity (Grade ${features.reading_grade.toFixed(1)})`);
    }

    // Rule 4: High entity density
    if (features.entity_density > entityThreshold) {
        syntheticScore += 2;
        reasons.push(`High entity density (${(features.entity_density * 100).toFixed(1)}%)`);
    }

    // Rule 5: Technical vocabulary
    if (features.tech_term_count > 0) {
        syntheticScore += 1;
        reasons.push(`Technical terms: ${features.tech_terms_found.join(', ')}`);
    }

    // Rule 6: No question words
    if (!features.has_question_word && features.word_count > 3) {
        syntheticScore += 0.5;
        reasons.push('No question words in multi-word query');
    }

    // Rule 7: Multiple entities
    if (features.entity_count >= 2) {
        syntheticScore += 1;
        reasons.push(`Multiple entities (${features.entity_count})`);
    }

    const maxScore = 8.5;
    const confidence = syntheticScore / maxScore;
    const classification = syntheticScore >= classThreshold ? 'SYNTHETIC' : 'USER';

    return {
        classification,
        confidence,
        score: syntheticScore,
        maxScore,
        reasons,
        features
    };
}

// Enhanced ML classification
function classifyML(query, options = {}) {
    const features = extractFeatures(query);
    const featureWeight = options.featureWeight || 'balanced';
    const sensitivity = parseFloat(options.sensitivity) || 0.5;

    // Feature weights based on importance
    let weights = {
        reading_grade: 0.25,
        entity_density: 0.20,
        stop_word_ratio: 0.15,
        word_count: 0.12,
        tech_term_count: 0.10,
        avg_word_length: 0.08,
        unique_word_ratio: 0.05,
        preposition_count: 0.05
    };

    // Adjust weights based on strategy
    if (featureWeight === 'semantic') {
        weights.reading_grade = 0.30;
        weights.entity_density = 0.30;
        weights.tech_term_count = 0.15;
    } else if (featureWeight === 'lexical') {
        weights.word_count = 0.25;
        weights.avg_word_length = 0.20;
        weights.stop_word_ratio = 0.20;
    }

    // Normalize features and calculate weighted score
    const normalized = {
        reading_grade: Math.min(features.reading_grade / 15, 1),
        entity_density: Math.min(features.entity_density / 0.6, 1),
        stop_word_ratio: 1 - Math.min(features.stop_word_ratio / 0.5, 1), // Inverted
        word_count: Math.min(features.word_count / 10, 1),
        tech_term_count: Math.min(features.tech_term_count / 3, 1),
        avg_word_length: Math.min(features.avg_word_length / 8, 1),
        unique_word_ratio: features.unique_word_ratio,
        preposition_count: Math.min(features.preposition_count / 3, 1)
    };

    // Calculate probability
    let probability = 0;
    for (const [key, weight] of Object.entries(weights)) {
        probability += (normalized[key] || 0) * weight;
    }

    // Apply question word penalty
    if (features.has_question_word) {
        probability *= 0.7;
    }

    // Determine classification based on sensitivity threshold
    const classification = probability >= sensitivity ? 'SYNTHETIC' : 'USER';

    // Feature importance for this query
    const featureImportance = Object.entries(weights)
        .map(([name, weight]) => ({
            name,
            weight,
            value: normalized[name] || 0,
            contribution: (normalized[name] || 0) * weight
        }))
        .sort((a, b) => b.contribution - a.contribution);

    return {
        classification,
        probability,
        confidence: Math.abs(probability - 0.5) * 2, // Distance from decision boundary
        features,
        featureImportance: featureImportance.slice(0, 5) // Top 5 features
    };
}

/* ===== CSV input =====
   Same rules as the original: a first line containing "keyword", "query" or a comma
   is a header; with columns, the first header containing "keyword" or "query" is
   used (else the first column); otherwise every line is one query. The only change
   is that quoted fields are read properly, so "shoes, cheap" stays one query. */
function readRecords(text) {
    const records = [];
    let raw = '', cells = [], cell = '', q = false;
    const end = () => { cells.push(cell); records.push({raw, cells}); raw = ''; cells = []; cell = ''; };
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (q) {
            if (c === '"') { if (text[i + 1] === '"') { cell += '"'; raw += '""'; i++; continue; } q = false; }
            else cell += c;
            raw += c;
        } else if (c === '"' && cell.trim() === '') { q = true; cell = ''; raw += c; }
        else if (c === ',') { cells.push(cell); cell = ''; raw += c; }
        else if (c === '\n') end();
        else if (c !== '\r') { cell += c; raw += c; }
    }
    if (raw.trim()) end();
    return records.filter(r => r.raw.trim());
}
const unquote = s => /^"(?:[^"]|"")*"$/.test(s) ? s.slice(1, -1).replace(/""/g, '"') : s;

function parseCSV(text) {
    const lines = readRecords(String(text).replace(/^﻿/, ''));
    if (!lines.length) return [];

    // Check if first line is a header
    const firstLine = lines[0].raw.trim().toLowerCase();
    const hasHeader = firstLine.includes('keyword') || firstLine.includes('query') || firstLine.includes(',');

    if (hasHeader && lines[0].raw.includes(',')) {
        // CSV with columns
        const headers = lines[0].cells.map(h => h.trim().toLowerCase());
        const keywordIndex = headers.findIndex(h => h.includes('keyword') || h.includes('query'));
        return lines.slice(1).map(line => {
            const columns = line.cells.map(c => c.trim());
            return keywordIndex >= 0 ? columns[keywordIndex] : columns[0];
        }).filter(q => q && q.length > 0);
    }
    // One query per line
    return (hasHeader ? lines.slice(1) : lines).map(l => unquote(l.raw.trim())).filter(q => q.length > 0);
}

/* ===== Interface ===== */
const byId = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const pct = v => (v * 100).toFixed(1) + '%';
const width = v => (Math.max(0, Math.min(1, v)) * 100).toFixed(1) + '%';
const MAX_ROWS = 1000;
const TABS = ['features', 'rules', 'ml'];
const LAST = {features: null, rules: null, ml: null};     // what is on screen, so a settings change can re-run it
const EXPORT = {features: null, rules: null, ml: null};   // rows behind the export button

/* analysis-mode tabs */
const tabButtons = [...document.querySelectorAll('.modes [role=tab]')];
function switchTab(name) {
    tabButtons.forEach(b => {
        const on = b.dataset.tab === name;
        b.setAttribute('aria-selected', String(on));
        b.tabIndex = on ? 0 : -1;
    });
    TABS.forEach(t => { byId(`${t}-tab`).hidden = t !== name; });
}
tabButtons.forEach((b, i) => {
    b.addEventListener('click', () => switchTab(b.dataset.tab));
    b.addEventListener('keydown', e => {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        const next = tabButtons[(i + (e.key === 'ArrowRight' ? 1 : tabButtons.length - 1)) % tabButtons.length];
        next.focus(); switchTab(next.dataset.tab);
    });
});

/* single query vs CSV */
function setInputMode(tab, mode) {
    byId(`${tab}-single-input`).hidden = mode !== 'single';
    byId(`${tab}-csv-input`).hidden = mode !== 'csv';
    document.querySelectorAll(`.seg[data-for="${tab}"] [data-mode]`)
        .forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
}
document.querySelectorAll('.seg').forEach(g => g.querySelectorAll('[data-mode]')
    .forEach(b => b.addEventListener('click', () => setInputMode(g.dataset.for, b.dataset.mode))));

function ruleOptions() {
    return {
        lengthThreshold: parseInt(byId('rules-length-threshold').value),
        gradeThreshold: parseFloat(byId('rules-grade-threshold').value),
        entityThreshold: parseFloat(byId('rules-entity-threshold').value),
        classThreshold: parseFloat(byId('rules-class-threshold').value)
    };
}
function mlOptions() {
    return {featureWeight: byId('ml-feature-weight').value, sensitivity: byId('ml-sensitivity').value};
}

function runSingle(tab) {
    const input = byId(`${tab}-query-input`);
    const query = input.value.trim();
    if (!query) { byId(`${tab}-status`).innerHTML = '<strong>Enter a query first.</strong>'; input.focus(); return; }
    byId(`${tab}-status`).textContent = '';
    LAST[tab] = {kind: 'single', query};
    render(tab);
}

async function handleCSV(tab, e) {
    const file = e.target.files[0]; if (!file) return;
    const info = byId(`${tab}-csv-info`);
    let queries;
    try { queries = parseCSV(await file.text()); }
    catch { info.innerHTML = '<strong>That file could not be read as CSV.</strong>'; return; }
    finally { e.target.value = ''; }
    if (!queries.length) { info.innerHTML = '<strong>No queries found in that file.</strong> Use one query per line, or a column named keyword or query.'; return; }
    info.innerHTML = `Read <strong>${queries.length.toLocaleString()}</strong> ${queries.length === 1 ? 'query' : 'queries'} from ${esc(file.name)}.`;
    LAST[tab] = {kind: 'csv', queries};
    render(tab);
}

TABS.forEach(tab => {
    byId(`${tab}-run`).addEventListener('click', () => runSingle(tab));
    byId(`${tab}-query-input`).addEventListener('keydown', e => { if (e.key === 'Enter') runSingle(tab); });
    byId(`${tab}-csv-file`).addEventListener('change', e => handleCSV(tab, e));
});
['rules-length-threshold', 'rules-grade-threshold', 'rules-entity-threshold', 'rules-class-threshold']
    .forEach(id => byId(id).addEventListener('change', () => render('rules')));
byId('ml-feature-weight').addEventListener('change', () => render('ml'));
byId('ml-sensitivity').addEventListener('input', () => { sensitivityLabel(); render('ml'); });

function sensitivityLabel() {
    const v = parseFloat(byId('ml-sensitivity').value);
    const lean = v < 0.4 ? 'more synthetic' : v > 0.6 ? 'more user' : 'balanced';
    byId('ml-sensitivity-value').textContent = `${v.toFixed(2)} · ${lean}`;
}

function render(tab) {
    const last = LAST[tab]; if (!last) return;
    const box = byId(`${tab}-results`);
    if (last.kind === 'single') { EXPORT[tab] = null; box.innerHTML = SINGLE[tab](last.query); }
    else {
        box.innerHTML = BATCH[tab](last.queries);
        byId(`${tab}-export`).addEventListener('click', () => exportCSV(tab));
    }
    box.hidden = false;
}

/* ---- shared bits ---- */
const lvl = c => c === 'SYNTHETIC' ? 'is-synth' : 'is-user';
const badge = c => `<span class="cls ${lvl(c)}" data-class="${c}">${c === 'SYNTHETIC' ? 'Synthetic' : 'User'}</span>`;
const head = (query, c) => `<div class="rhead"><div><div class="eyebrow">Query</div>
    <div class="qtext">${esc(query)}</div></div>${c ? badge(c) : ''}</div>`;
const tiles = list => `<div class="tiles">${list.map(([k, v, d, cls]) =>
    `<div class="tile ${cls || ''}"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join('')}</div>`;
const batchHead = (tab, n) => `<div class="section-head"><h2>Results</h2><div class="actions">
    ${n > MAX_ROWS ? `<span class="hint">Showing the first ${MAX_ROWS.toLocaleString()} of ${n.toLocaleString()}. The export has them all.</span>` : ''}
    <button type="button" class="ghost" id="${tab}-export">Export results CSV</button></div></div>`;
const table = (cols, body) => `<div class="tablewrap"><table><thead><tr>${cols.map(([t, n]) =>
    `<th${n ? ' class="n"' : ''}>${t}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>`;
const share = (n, total) => `${n.toLocaleString()} of ${total.toLocaleString()} (${(n / total * 100).toFixed(1)}%)`;
const nice = s => s.replace(/_/g, ' ');

/* ---- single-query results ---- */
const SINGLE = {
    features(query) {
        const f = extractFeatures(query);
        const ents = detectEntities(query);
        const items = [
            ['Word count', f.word_count],
            ['Character count', f.char_count],
            ['Avg word length', f.avg_word_length.toFixed(2)],
            ['Stop-word ratio', pct(f.stop_word_ratio)],
            ['Entity count', f.entity_count],
            ['Entity density', pct(f.entity_density)],
            ['Reading grade', f.reading_grade.toFixed(1)],
            ['Unique word ratio', pct(f.unique_word_ratio)],
            ['Has question word', f.has_question_word ? 'Yes' : 'No'],
            ['Prepositions', f.preposition_count],
            ['Technical terms', f.tech_term_count],
            ['Is a question', f.is_question ? 'Yes' : 'No']
        ];
        return `<div class="panel result">${head(query)}
            <div class="fgrid">${items.map(([k, v]) => `<div class="fitem" data-k="${k}"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}</div>
            ${ents.length ? `<div class="keynote"><strong>Entities detected:</strong> ${esc(ents.join(', '))}</div>` : ''}
            ${f.tech_terms_found.length ? `<div class="keynote"><strong>Technical terms found:</strong> ${esc(f.tech_terms_found.join(', '))}</div>` : ''}
        </div>`;
    },
    rules(query) {
        const o = ruleOptions();
        const r = classifyRuleBased(query, o);
        const thr = o.classThreshold || 4;   // the same fallback classifyRuleBased uses
        return `<div class="panel result ${lvl(r.classification)}" data-class="${r.classification}">${head(query, r.classification)}
            <div class="figures">
              <span>Synthetic score <b data-v="score">${r.score.toFixed(1)} / ${r.maxScore}</b></span>
              <span>Confidence <b data-v="confidence">${pct(r.confidence)}</b></span>
              <span>Labelled synthetic at <b>${thr}</b></span>
            </div>
            <div class="meter"><span style="width:${width(r.confidence)}"></span><i class="tick" style="left:${width(thr / r.maxScore)}" title="Classification threshold"></i></div>
            <h3>Why</h3>
            ${r.reasons.length ? `<ul class="reasons">${r.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`
                : '<p class="hint">No rule fired, so the score is 0.</p>'}
        </div>`;
    },
    ml(query) {
        const o = mlOptions();
        const r = classifyML(query, o);
        const thr = parseFloat(o.sensitivity) || 0.5;
        const top = Math.max(...r.featureImportance.map(f => f.contribution)) || 1;
        return `<div class="panel result ${lvl(r.classification)}" data-class="${r.classification}">${head(query, r.classification)}
            <div class="figures">
              <span>Synthetic probability <b data-v="probability">${pct(r.probability)}</b></span>
              <span>Confidence <b data-v="confidence">${pct(r.confidence)}</b></span>
              <span>Threshold <b>${thr.toFixed(2)}</b></span>
            </div>
            <div class="meter"><span style="width:${width(r.probability)}"></span><i class="tick" style="left:${width(thr)}" title="Classification threshold"></i></div>
            <h3>Top contributing features</h3>
            <ul class="contrib">${r.featureImportance.map(f => `<li>
                <span class="name">${nice(f.name)}</span>
                <span class="calc">${f.value.toFixed(2)} &times; ${f.weight.toFixed(2)}</span>
                <span class="track"><span style="width:${width(f.contribution / top)}"></span></span>
                <span class="n">${pct(f.contribution)}</span></li>`).join('')}</ul>
            ${r.features.has_question_word ? '<p class="hint">The query has a question word, so the total was multiplied by 0.7 after these contributions.</p>' : ''}
        </div>`;
    }
};

/* ---- CSV results ---- */
const BATCH = {
    features(queries) {
        const rows = queries.map(q => ({query: q, ...extractFeatures(q)}));
        EXPORT.features = rows;
        const n = rows.length;
        const avg = k => rows.reduce((s, r) => s + r[k], 0) / n;
        const tech = rows.filter(r => r.tech_term_count > 0).length;
        return tiles([
            ['Queries', n.toLocaleString(), 'read from your file', 'plain'],
            ['Average words', avg('word_count').toFixed(1), 'per query'],
            ['Average reading grade', avg('reading_grade').toFixed(1), 'Flesch-Kincaid approximation'],
            ['With technical terms', tech.toLocaleString(), `${(tech / n * 100).toFixed(1)}% of queries`]
        ]) + batchHead('features', n) + table(
            [['Query'], ['Words', 1], ['Grade', 1], ['Entities', 1], ['Entity density', 1], ['Stop words', 1], ['Question word'], ['Technical terms']],
            rows.slice(0, MAX_ROWS).map(r => `<tr>
                <td class="q">${esc(r.query)}</td><td class="n">${r.word_count}</td>
                <td class="n">${r.reading_grade.toFixed(1)}</td><td class="n">${r.entity_count}</td>
                <td class="n">${pct(r.entity_density)}</td><td class="n">${pct(r.stop_word_ratio)}</td>
                <td>${r.has_question_word ? 'Yes' : 'No'}</td>
                <td class="why">${r.tech_term_count ? esc(r.tech_terms_found.join(', ')) : ''}</td></tr>`).join(''));
    },
    rules(queries) {
        const o = ruleOptions();
        const rows = queries.map(q => ({query: q, ...classifyRuleBased(q, o)}));
        EXPORT.rules = rows;
        const n = rows.length;
        const user = rows.filter(r => r.classification === 'USER').length;
        const synth = rows.filter(r => r.classification === 'SYNTHETIC').length;
        return tiles([
            ['Total queries', n.toLocaleString(), 'read from your file', 'plain'],
            ['User queries', user.toLocaleString(), share(user, n), 'is-user'],
            ['Synthetic queries', synth.toLocaleString(), share(synth, n), 'is-synth']
        ]) + batchHead('rules', n) + table(
            [['Query'], ['Label'], ['Score', 1], ['Confidence', 1], ['Why']],
            rows.slice(0, MAX_ROWS).map(r => `<tr data-class="${r.classification}">
                <td class="q">${esc(r.query)}</td><td>${badge(r.classification)}</td>
                <td class="n">${r.score.toFixed(1)} / ${r.maxScore}</td>
                <td class="n">${pct(r.confidence)}</td>
                <td class="why">${esc(r.reasons.join(' · '))}</td></tr>`).join(''));
    },
    ml(queries) {
        const o = mlOptions();
        const rows = queries.map(q => ({query: q, ...classifyML(q, o)}));
        EXPORT.ml = rows;
        const n = rows.length;
        const user = rows.filter(r => r.classification === 'USER').length;
        const synth = rows.filter(r => r.classification === 'SYNTHETIC').length;
        const avgP = rows.reduce((s, r) => s + r.probability, 0) / n;
        return tiles([
            ['Total queries', n.toLocaleString(), 'read from your file', 'plain'],
            ['User queries', user.toLocaleString(), share(user, n), 'is-user'],
            ['Synthetic queries', synth.toLocaleString(), share(synth, n), 'is-synth'],
            ['Avg synthetic probability', pct(avgP), 'across all queries']
        ]) + batchHead('ml', n) + table(
            [['Query'], ['Label'], ['Synthetic probability', 1], ['Confidence', 1], ['Top feature']],
            rows.slice(0, MAX_ROWS).map(r => `<tr data-class="${r.classification}">
                <td class="q">${esc(r.query)}</td><td>${badge(r.classification)}</td>
                <td class="n"><span class="mbar ${lvl(r.classification)}"><span style="width:${width(r.probability)}"></span></span>${pct(r.probability)}</td>
                <td class="n">${pct(r.confidence)}</td>
                <td class="why">${nice(r.featureImportance[0].name)}</td></tr>`).join(''));
    }
};

/* ---- export: same columns as the original, now quoted so the file opens cleanly ---- */
async function offerFile(filename, text, mime) {
    const api = (typeof claude !== "undefined" && claude.use) ? await claude.use("downloads").catch(() => null) : null;
    if (api) { try { await api.save({filename, data: text}); return "saved"; }
        catch (e) { return e && e.code === "declined" ? "declined" : "failed"; } }
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type: mime}));
    a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000); return "saved";
}
async function exportCSV(tab) {
    const rows = EXPORT[tab]; if (!rows || !rows.length) return;
    const headers = Object.keys(rows[0]);
    const cell = v => {
        if (v === null || v === undefined) return '';
        if (typeof v === 'object') v = JSON.stringify(v);
        v = String(v);
        return /[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
    };
    const csv = [headers.map(cell).join(','), ...rows.map(r => headers.map(h => cell(r[h])).join(','))].join('\n');
    await offerFile(`query-analysis-${tab}-${new Date().toISOString().slice(0, 10)}.csv`, csv, 'text/csv');
}
