"""Builds sentiment_analysis_methods.ipynb from the cells below.

Run `python build_notebook.py` to regenerate the notebook after editing a cell.
"""
import nbformat as nbf

cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))


def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip("\n")))


md(r"""
# Sentiment analysis methods, side by side

Companion notebook for the MLforSEO guide **Sentiment Analysis: A Deep Dive Into the Theory, Methods, and Applications** by Lazarina Stoy.

The guide explains the two big families of sentiment analysis: **lexicon-based** approaches (a hand-built dictionary of words with sentiment scores) and **machine learning** approaches (classic statistical models and deep learning). This notebook lets you run each one on the same text and see where they agree, where they break, and how accurate they are on a labelled dataset.

| Section | Method | Library / model |
|---|---|---|
| 1 | Lexicon-based | VADER, AFINN |
| 2 | Classic (shallow) machine learning | TF-IDF + logistic regression, trained on TweetEval |
| 3 | Deep learning (transformer) | `cardiffnlp/twitter-roberta-base-sentiment-latest` |
| 4 | Benchmark | Accuracy and macro-F1 of all of the above on the TweetEval test set |
| 5 | Document vs sentence level | Why one score per review hides mixed opinions |
| 6 | Pre-trained API (optional) | Google Cloud Natural Language API, v1 and v2 |
| 7 | Applied: brand SERP sentiment | Score the titles ranking for your branded queries and plot them by position |

No API key is needed for sections 1–5 and 7 (section 7 uses the transformer). Section 6 needs a Google Cloud API key with the Natural Language API enabled.

Runs in Google Colab (CPU is fine; a GPU runtime makes section 3–4 faster).
""")

code(r"""
# Colab already has pandas, scikit-learn, matplotlib, torch and transformers.
%pip install -q vaderSentiment afinn datasets
""")

code(r"""
import re
import pandas as pd
import matplotlib.pyplot as plt

pd.set_option("display.max_colwidth", 90)

# A few short texts that show the classic failure modes discussed in the guide:
# negation, mixed opinions, slang and emoji, sarcasm, and very short context.
samples = pd.DataFrame({"text": [
    "Absolutely love this course, the examples are so practical!",
    "The delivery was fast, but the product broke after two days.",
    "Not bad at all, honestly.",
    "This update is fire 🔥🔥 no cap",
    "Oh great, another password reset email. Just what I needed.",
    "Worst customer service I have ever dealt with.",
    "The meeting is on Tuesday at 3pm.",
    "meh",
]})
samples
""")

md(r"""
## 1. Lexicon-based sentiment analysis

Lexicon approaches look every word up in a pre-built sentiment dictionary and add the scores up. The guide lists the classic lexicons (Subjectivity Wordlist, WordNet-Affect, SentiWordNet, SenticNet, AFINN, SO-CAL…). Two that are easy to use in Python today:

* **AFINN**: about 3,300 English words rated from -5 to +5. Pure word counting.
* **VADER** (Valence Aware Dictionary and sEntiment Reasoner): a lexicon *plus* rules for negation ("not bad"), intensifiers ("very"), capitals, punctuation and emoji. It was built for social media text. Its `compound` score runs from -1 to +1; the authors suggest ≥ 0.05 is positive and ≤ -0.05 is negative.

Both are fast, free, transparent and need no training data. Both score sentiment from the writer's words only, which is the limitation the guide describes.
""")

code(r"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from afinn import Afinn

vader = SentimentIntensityAnalyzer()
afinn = Afinn(emoticons=True)

def vader_label(text):
    c = vader.polarity_scores(text)["compound"]
    return "positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral"

def afinn_label(text):
    s = afinn.score(text)
    return "positive" if s > 0 else "negative" if s < 0 else "neutral"

samples["vader_compound"] = samples.text.map(lambda t: vader.polarity_scores(t)["compound"])
samples["vader"] = samples.text.map(vader_label)
samples["afinn_score"] = samples.text.map(afinn.score)
samples["afinn"] = samples.text.map(afinn_label)
samples
""")

md(r"""
## 2. Classic machine learning: TF-IDF + logistic regression

A supervised model needs labelled examples. We use **TweetEval sentiment** (Barbieri et al., 2020): about 45,000 tweets labelled negative, neutral or positive, with a separate test set of about 12,000.

The combination of TF-IDF features with logistic regression is the one the guide mentions (Ahuja et al., 2019 found it the most efficient among the shallow options they compared). It trains in seconds on a laptop.
""")

code(r"""
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, f1_score, classification_report

ds = load_dataset("cardiffnlp/tweet_eval", "sentiment")
LABELS = ["negative", "neutral", "positive"]
train = ds["train"].to_pandas()
test = ds["test"].to_pandas()
train["label_name"] = train.label.map(lambda i: LABELS[i])
test["label_name"] = test.label.map(lambda i: LABELS[i])
print(len(train), "training tweets |", len(test), "test tweets")
print(train.label_name.value_counts(normalize=True).round(2).to_dict())
""")

code(r"""
tfidf_lr = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
    LogisticRegression(max_iter=2000, C=2.0),
)
tfidf_lr.fit(train.text, train.label_name)

samples["tfidf_lr"] = tfidf_lr.predict(samples.text)
samples[["text", "vader", "afinn", "tfidf_lr"]]
""")

md(r"""
## 3. Deep learning: a transformer fine-tuned for sentiment

`cardiffnlp/twitter-roberta-base-sentiment-latest` is a RoBERTa model pre-trained on about 124 million tweets and fine-tuned on TweetEval. It is the modern descendant of the CNN approaches in the guide: it reads the whole sentence in context, so it handles negation, slang and emoji far better than counting words.

Swap in `cardiffnlp/twitter-xlm-roberta-base-sentiment` for multilingual text.
""")

code(r"""
from transformers import pipeline

MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
roberta = pipeline("sentiment-analysis", model=MODEL, tokenizer=MODEL,
                   truncation=True, max_length=256)

def roberta_predict(texts, batch_size=64):
    out = roberta(list(texts), batch_size=batch_size)
    return [o["label"].lower() for o in out], [round(o["score"], 3) for o in out]

samples["roberta"], samples["roberta_conf"] = roberta_predict(samples.text)
samples[["text", "vader", "afinn", "tfidf_lr", "roberta", "roberta_conf"]]
""")

md(r"""
## 4. Benchmark on the TweetEval test set

Same test tweets for every method. Set `N` lower if you're on a slow CPU runtime (the transformer is the slow one: roughly 1–3 minutes per 1,000 tweets on CPU).
""")

code(r"""
N = 2000  # test tweets to score; len(test) for the full set
bench = test.sample(N, random_state=42).reset_index(drop=True)

preds = {
    "AFINN (lexicon)": bench.text.map(afinn_label),
    "VADER (lexicon + rules)": bench.text.map(vader_label),
    "TF-IDF + logistic regression": tfidf_lr.predict(bench.text),
    "RoBERTa (transformer)": roberta_predict(bench.text)[0],
}

rows = []
for name, p in preds.items():
    rows.append({
        "method": name,
        "accuracy": accuracy_score(bench.label_name, p),
        "macro_F1": f1_score(bench.label_name, p, average="macro"),
    })
results = pd.DataFrame(rows).round(3).sort_values("macro_F1")
results
""")

code(r"""
ax = results.plot.barh(x="method", y="macro_F1", legend=False, color="#8448ef", figsize=(8, 3.5))
ax.set_xlabel("Macro-F1 on TweetEval test sample (higher is better)")
ax.set_ylabel("")
ax.set_xlim(0, 1)
for i, v in enumerate(results.macro_F1):
    ax.text(v + 0.01, i, f"{v:.2f}", va="center")
plt.title("Sentiment methods compared")
plt.tight_layout()
plt.show()

print(classification_report(bench.label_name, preds["RoBERTa (transformer)"]))
""")

md(r"""
**Caveat:** the RoBERTa model was fine-tuned on TweetEval's *training* split, so it has a home advantage on this test. That's the point the guide makes about choosing a model suited to the data you have: a model trained on tweets will be strong on tweets and weaker on, say, long product reviews or legal text. Always spot-check on a sample of *your* data before trusting any model.
""")

md(r"""
## 5. Document level vs sentence level

Sentiment can be scored for a whole document, per sentence, or per aspect. A single document score averages away mixed opinions, which is exactly what you don't want when you analyse reviews.
""")

code(r"""
review = ("I've been using this tool for three months. The keyword clustering is brilliant "
          "and saves me hours every week. The interface, however, is confusing and slow. "
          "Customer support never replied to my ticket. Still, I'd recommend it for the clustering alone.")

sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", review) if s.strip()]
labels, conf = roberta_predict(sentences)
print("Whole review:", roberta_predict([review])[0][0])
pd.DataFrame({"sentence": sentences, "roberta": labels, "confidence": conf})
""")

md(r"""
## 6. (Optional) Google Cloud Natural Language API

The no-code Google Sheets route in the guide uses this API. Here is the same call in Python, for both API versions, so you can compare them. You need a Google Cloud project with the Natural Language API and billing enabled, and an API key. The first 5,000 units (1,000 characters each) of sentiment analysis per month are free.

* **v1** `documents:analyzeSentiment` returns a `score` (-1 to +1) and a `magnitude` (0 to infinity) for the document and each sentence. v1 also has `analyzeEntitySentiment`.
* **v2** `documents:analyzeSentiment` returns the same fields from a newer model. v2 has **no** entity sentiment method.

The two versions can disagree on the same text, so pick one and stay with it for anything you track over time.
""")

code(r"""
import os, requests, getpass

API_KEY = os.environ.get("GOOGLE_API_KEY") or getpass.getpass("Google Cloud API key (leave blank to skip): ")

def gcp_sentiment(text, version="v2"):
    url = f"https://language.googleapis.com/{version}/documents:analyzeSentiment"
    body = {"document": {"type": "PLAIN_TEXT", "content": text}, "encodingType": "UTF8"}
    r = requests.post(url, params={"key": API_KEY}, json=body, timeout=30)
    r.raise_for_status()
    d = r.json()["documentSentiment"]
    return d.get("score", 0.0), d.get("magnitude", 0.0)

def gcp_label(score, threshold=0.25):
    # Google suggests picking your own thresholds; 0.25 is a sensible start.
    return "positive" if score >= threshold else "negative" if score <= -threshold else "neutral"

if API_KEY:
    for v in ["v1", "v2"]:
        scored = samples.text.map(lambda t: gcp_sentiment(t, v))
        samples[f"gcp_{v}_score"] = [s for s, m in scored]
        samples[f"gcp_{v}_magnitude"] = [m for s, m in scored]
        samples[f"gcp_{v}"] = samples[f"gcp_{v}_score"].map(gcp_label)
    display(samples[["text", "roberta", "gcp_v1_score", "gcp_v1_magnitude", "gcp_v2_score", "gcp_v2_magnitude"]])
else:
    print("No key: skipped.")
""")

md(r"""
## 7. Applied: sentiment of the results ranking for your branded queries

This is the online reputation management project from the guide. Export the top 10 results (keyword, position, title, URL) for your branded queries from any SERP tool (DataForSEO, Semrush, Ahrefs, a Screaming Frog SERP crawl…) into a CSV with the columns `keyword, position, title, url`.

The example file `example_serp_titles.csv` uses a **fictional** brand so you can run the notebook straight away. Replace it with your own export.

We score each title with the transformer and turn its output into a signed score (positive probability minus negative probability, so -1 to +1). Then we plot titles by position and score, with bubble size showing how confident the model is: the same reading as the score and magnitude bubble chart in the guide.
""")

code(r"""
SERP_CSV = "example_serp_titles.csv"  # replace with your own export
try:
    serp = pd.read_csv(SERP_CSV)
except FileNotFoundError:
    serp = pd.read_csv("https://raw.githubusercontent.com/lazarinastoy/mlforseo-code/main/sentiment-analysis-methods/example_serp_titles.csv")

def signed_scores(texts):
    out = roberta(list(texts), top_k=None, batch_size=32)
    rows = []
    for o in out:
        p = {d["label"].lower(): d["score"] for d in o}
        rows.append((round(p["positive"] - p["negative"], 3), round(max(p.values()), 3)))
    return rows

scored = signed_scores(serp.title)
serp["score"] = [s for s, c in scored]
serp["confidence"] = [c for s, c in scored]
serp["sentiment"] = serp.score.map(lambda s: "positive" if s >= 0.25 else "negative" if s <= -0.25 else "neutral")
serp.sort_values(["keyword", "position"]).head(12)
""")

code(r"""
colors = serp.sentiment.map({"positive": "#2e9e6b", "neutral": "#9a8fb0", "negative": "#d64545"})
fig, ax = plt.subplots(figsize=(9, 5))
ax.scatter(serp.position, serp.score, s=serp.confidence * 400, c=colors, alpha=0.7, edgecolor="white")
ax.axhline(0, color="#999", lw=0.8)
ax.set_xticks(range(1, 11))
ax.set_xlabel("Ranking position")
ax.set_ylabel("Title sentiment (-1 negative … +1 positive)")
ax.set_title("Sentiment of titles ranking for branded queries")
plt.tight_layout()
plt.show()

# Where does negative content rank, and for which queries?
neg = serp[serp.sentiment == "negative"].sort_values("position")
print(f"{len(neg)} negative titles, {int((neg.position <= 3).sum())} of them in the top 3")
neg[["keyword", "position", "title", "url", "score"]]
""")

code(r"""
# Which domains publish negative (or positive) content about the brand most often?
serp["domain"] = serp.url.str.extract(r"https?://(?:www\.)?([^/]+)")
serp.pivot_table(index="domain", columns="sentiment", values="title", aggfunc="count", fill_value=0) \
    .sort_values(by=[c for c in ["negative", "positive"] if c in serp.sentiment.unique()], ascending=False)
""")

code(r"""
# Save everything
samples.to_csv("sentiment_method_comparison.csv", index=False)
results.to_csv("sentiment_benchmark.csv", index=False)
serp.to_csv("serp_title_sentiment.csv", index=False)
try:
    from google.colab import files
    for f in ["sentiment_method_comparison.csv", "sentiment_benchmark.csv", "serp_title_sentiment.csv"]:
        files.download(f)
except ImportError:
    print("Saved 3 CSV files to the working directory.")
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "name": "python3"},
    "language_info": {"name": "python"},
    "colab": {"provenance": []},
}
nbf.write(nb, "sentiment_analysis_methods.ipynb")
print("wrote sentiment_analysis_methods.ipynb with", len(cells), "cells")
