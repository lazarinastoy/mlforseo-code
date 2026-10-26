// Sentence embeddings with the same model and settings as the tool: Xenova/all-MiniLM-L6-v2,
// quantised (q8) ONNX weights, mean pooling, L2-normalised. Vectors are cached on disk by text.
import { pipeline, env } from '@huggingface/transformers';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
env.cacheDir = path.join(HERE, '..', '.hfcache');
let extractor = null;

export async function embedTexts(texts, cacheFile = path.join(HERE, '..', 'out', 'embeddings.cache.json')) {
  const cache = fs.existsSync(cacheFile) ? JSON.parse(fs.readFileSync(cacheFile, 'utf8')) : {};
  const todo = [...new Set(texts.filter(t => !(t in cache)))];
  if (todo.length) {
    extractor = extractor || await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2', { dtype: 'q8' });
    for (let i = 0; i < todo.length; i += 64) {
      const chunk = todo.slice(i, i + 64);
      const out = await extractor(chunk, { pooling: 'mean', normalize: true });
      const d = out.dims[1];
      chunk.forEach((t, j) => { cache[t] = Array.from(out.data.slice(j * d, (j + 1) * d)); });
    }
    fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
    fs.writeFileSync(cacheFile, JSON.stringify(cache));
  }
  return texts.map(t => Float32Array.from(cache[t]));
}
