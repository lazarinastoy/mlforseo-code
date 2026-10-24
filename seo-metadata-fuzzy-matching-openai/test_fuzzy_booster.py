"""Offline tests for fuzzy_booster.py and fuzzy_booster.ipynb (OpenAI is mocked).

    python -m unittest test_fuzzy_booster.py -v
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fuzzy_booster as fb  # noqa: E402


class FakeClient:
    """Stands in for openai.OpenAI(): records prompts, returns a quoted title."""

    def __init__(self):
        self.prompts = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, model, temperature, messages):
        self.prompts.append((model, temperature, messages[0]["content"]))
        msg = types.SimpleNamespace(content=' "Nuevo título SEO" ')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class ScriptTests(unittest.TestCase):
    def test_home_regex(self):
        self.assertEqual(fb.home_regex("https://www.example.com/"), r"^https://www\.example\.com/$")
        self.assertRegex("https://example.com/", fb.home_regex("sc-domain:example.com"))
        self.assertNotRegex("https://example.com/blog/", fb.home_regex("sc-domain:example.com"))

    def test_build_request(self):
        import datetime

        req = fb.build_request("https://www.example.com/", "acme|acme corp", today=datetime.date(2026, 10, 24))
        self.assertEqual(req["startDate"], "2025-06-24")
        self.assertEqual(req["dimensions"], ["page", "query"])
        self.assertEqual(len(req["dimensionFilterGroups"][0]["filters"]), 2)
        self.assertEqual(req["rowLimit"], 25000)

    def test_rows_to_dataframe_keeps_top_query(self):
        rows = [
            {"keys": ["/a", "q1"], "clicks": 5, "ctr": 0.05, "impressions": 100, "position": 3.456},
            {"keys": ["/a", "q2"], "clicks": 9, "ctr": 0.09, "impressions": 100, "position": 2.0},
            {"keys": ["/b", "q3"], "clicks": 1, "ctr": 0.01, "impressions": 100, "position": 7.0},
        ]
        df = fb.rows_to_dataframe(rows)
        self.assertEqual(df.set_index("page").loc["/a", "query"], "q2")
        self.assertAlmostEqual(df.set_index("page").loc["/a", "ctr"], 9.0)
        self.assertEqual(len(df), 2)
        self.assertEqual(len(fb.rows_to_dataframe([])), 0)

    def test_parse_meta(self):
        html = "<html><head><title> Hola </title><meta name='description' content=' Desc '></head><body><h1>H</h1></body></html>"
        self.assertEqual(fb.parse_meta(html), ("Hola", "Desc", "H"))
        self.assertEqual(fb.parse_meta("<p>x</p>"), ("No title", "No meta description", "No h1"))

    def test_clean_text_spanish(self):
        sw = fb.load_stopwords("spanish")
        self.assertEqual(fb.clean_text("Qué es el SEO técnico 2026?", sw), "seo tecnico")
        self.assertIn("mas", sw)  # accent-stripped stopword variant

    def test_similarity_scores(self):
        self.assertEqual(round(fb.fuzz.token_set_ratio("seo tecnico", "seo tecnico empezar example")), 100)
        self.assertLess(fb.fuzz.token_set_ratio("enlazado interno", "mejorar arquitectura web example"), 60)

    def test_strip_quotes(self):
        self.assertEqual(fb.strip_quotes('"Title"'), "Title")
        self.assertEqual(fb.strip_quotes("'Title'"), "Title")
        self.assertEqual(fb.strip_quotes('Say "hi"'), 'Say "hi"')
        self.assertEqual(fb.strip_quotes(float("nan")), "nan")

    def test_sample_end_to_end_with_mocked_openai(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(fb, "get_openai_client", return_value=client):
            out = os.path.join(tmp, "out.csv")
            df = fb.main(["--sample", "--out", out])
            saved = pd.read_csv(out, keep_default_na=False)
        self.assertEqual(len(df), 6)  # 8 rows, 6 unique pages
        for col in ["title_similarity", "meta_similarity", "h1_similarity", "new_title"]:
            self.assertIn(col, saved.columns)
        weak = df[df["title_similarity"] <= 60]
        self.assertGreater(len(weak), 0)
        self.assertEqual(len(client.prompts), len(weak))
        self.assertTrue((weak["new_title"] == "Nuevo título SEO").all())
        self.assertTrue((df[df["title_similarity"] > 60]["new_title"] == "").all())
        model, temperature, prompt = client.prompts[0]
        self.assertEqual((model, temperature), ("gpt-4o-mini", 0.0))
        self.assertIn("'spanish'", prompt)
        top = df.set_index("page").loc["https://www.example.com/blog/que-es-el-seo-tecnico/"]
        self.assertEqual(top["query"], "seo técnico")
        self.assertEqual(top["title_similarity"], 100)


class NotebookTests(unittest.TestCase):
    """Runs the notebook's code cells on the sample data (Steps 2-3 and the pip cell skipped)."""

    def test_notebook_runs_on_sample(self):
        nb = json.load(open(os.path.join(HERE, "fuzzy_booster.ipynb")))
        code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        skip = ("%pip", "uploaded = files.upload()", "HEADERS = {")
        client = FakeClient()
        fake_openai = types.SimpleNamespace(OpenAI=lambda: client)
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(sys.modules, {"openai": fake_openai}):
            shutil.copy(fb.SAMPLE_CSV, tmp)  # the sample cell reads the local copy before trying GitHub
            os.chdir(tmp)
            try:
                ns = {}
                for src in code:
                    if any(s in src for s in skip):
                        continue
                    src = "\n".join(l for l in src.splitlines() if l.strip() != "df")  # drop display lines
                    exec(compile(src, "<cell>", "exec"), ns)
                out = pd.read_csv("fuzzy_booster.csv", keep_default_na=False)
            finally:
                os.chdir(cwd)
        self.assertEqual(len(out), 6)
        self.assertIn("new_title", out.columns)
        self.assertFalse(any(c.endswith("_clean") for c in out.columns))
        script = fb.add_similarity(fb.top_query_per_page(pd.read_csv(fb.SAMPLE_CSV)), fb.load_stopwords("spanish"))
        merged = out.merge(script, on="page", suffixes=("_nb", "_py"))
        for col in ["title_similarity", "meta_similarity", "h1_similarity"]:
            self.assertTrue((merged[col + "_nb"] == merged[col + "_py"]).all(), col)
        self.assertEqual(ns["request"]["rowLimit"], 25000)


if __name__ == "__main__":
    unittest.main()
