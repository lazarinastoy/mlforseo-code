/**
 * NGRAMS custom function for Google Sheets.
 * Companion to the MLforSEO tutorial "4 ways to boost your SERP competitor
 * analysis with machine learning" by Lazarina Stoy.
 *
 * Install: Extensions > Apps Script, paste this file, save. Then in any cell:
 *   =NGRAMS(B2:B100, 2)           top bigrams in a column of titles
 *   =NGRAMS(C2:C100, 3, 20, TRUE) top 20 trigrams, stop words removed
 *
 * Returns a table: n-gram | count | rows (number of titles containing it).
 *
 * @param {A2:A100} range        Cells with titles or meta descriptions.
 * @param {2} n                  Words per n-gram (1, 2 or 3). Default 2.
 * @param {15} top               How many n-grams to return. Default 15.
 * @param {FALSE} removeStopWords TRUE to drop words like "the", "is", "what".
 *                               Keep them (FALSE) to see title patterns such
 *                               as "what is" or "how to".
 * @customfunction
 */
function NGRAMS(range, n, top, removeStopWords) {
  n = n || 2;
  top = top || 15;
  var STOP = ['a','an','and','are','as','at','be','by','for','from','how','in','is','it',
              'its','of','on','or','that','the','this','to','what','when','where','which',
              'who','why','with','you','your'];
  var stop = {};
  STOP.forEach(function (w) { stop[w] = true; });

  var cells = Array.isArray(range) ? [].concat.apply([], range) : [range];
  var counts = {};
  var rows = {};

  cells.forEach(function (cell) {
    if (cell === '' || cell === null) return;
    var words = String(cell).toLowerCase()
      .replace(/[^\p{L}\p{N}\s+#'-]/gu, ' ')
      .split(/\s+/)
      .filter(function (w) { return w && w !== '-' && !(removeStopWords && stop[w]); });
    var seen = {};
    for (var i = 0; i + n <= words.length; i++) {
      var gram = words.slice(i, i + n).join(' ');
      counts[gram] = (counts[gram] || 0) + 1;
      if (!seen[gram]) { rows[gram] = (rows[gram] || 0) + 1; seen[gram] = true; }
    }
  });

  var table = Object.keys(counts).map(function (g) { return [g, counts[g], rows[g]]; });
  table.sort(function (a, b) { return b[2] - a[2] || b[1] - a[1]; });
  if (!table.length) return [['(no n-grams found)', '', '']];
  return [['n-gram', 'count', 'rows']].concat(table.slice(0, top));
}
