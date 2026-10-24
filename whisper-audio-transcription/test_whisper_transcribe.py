"""Offline tests for whisper_transcribe.py and the notebook (OpenAI and Colab are mocked).
Chunking tests need pydub + ffmpeg.

    python -m unittest test_whisper_transcribe.py -v
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import whisper_transcribe as wt  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


class FakeClient:
    def __init__(self):
        self.calls = []
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=self._create))

    def _create(self, model, file, **kwargs):
        name = os.path.basename(file.name)
        file.read()
        self.calls.append((model, name, kwargs))
        if kwargs.get("response_format") == "verbose_json":
            seg = lambda a, b, t: types.SimpleNamespace(start=a, end=b, text=t)  # noqa: E731
            return types.SimpleNamespace(segments=[seg(0.0, 2.5, f" hello {name} "), seg(2.5, 5.0, "world")])
        return types.SimpleNamespace(text=f"text of {name}")


def make_audio(path, seconds):
    from pydub import AudioSegment
    from pydub.generators import Sine

    Sine(440).to_audio_segment(duration=seconds * 1000).export(path, format=os.path.splitext(path)[1][1:])


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def small_file(self, name="clip.mp3"):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as f:
            f.write(b"\0" * 1024)
        return path

    def test_srt_timestamp(self):
        self.assertEqual(wt.srt_timestamp(0), "00:00:00,000")
        self.assertEqual(wt.srt_timestamp(3725.4567), "01:02:05,457")

    def test_segments_to_srt(self):
        srt = wt.segments_to_srt([(0, 1.5, "Hi"), (1.5, 3, "there")])
        self.assertEqual(srt, "1\n00:00:00,000 --> 00:00:01,500\nHi\n\n2\n00:00:01,500 --> 00:00:03,000\nthere\n")

    def test_small_file_text(self):
        client = FakeClient()
        self.assertEqual(wt.transcribe_text(client, self.small_file()), "text of clip.mp3")
        self.assertEqual(client.calls, [("whisper-1", "clip.mp3", {})])

    def test_size_guard(self):
        path = self.small_file()
        with mock.patch.object(wt, "MAX_FILE_SIZE", 10):
            with self.assertRaises(ValueError):
                wt.transcribe_file(FakeClient(), path)

    def test_cli_writes_txt_and_skips_unsupported(self):
        client = FakeClient()
        audio = self.small_file("a.m4a")
        bad = self.small_file("notes.pdf")
        out = wt.main([audio, bad, "--out-dir", os.path.join(self.tmp, "out"), "--language", "en"], client=client)
        self.assertEqual(len(out), 1)
        self.assertEqual(open(out[0], encoding="utf-8").read(), "text of a.m4a")
        self.assertEqual(client.calls[0][2], {"language": "en"})

    def test_cli_srt_requires_whisper1(self):
        with self.assertRaises(SystemExit):
            wt.main([self.small_file(), "--format", "srt", "--model", "gpt-4o-transcribe"], client=FakeClient())

    @unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
    def test_long_file_is_chunked_in_order(self):
        path = os.path.join(self.tmp, "long.wav")
        make_audio(path, 150)  # 2.5 minutes
        client = FakeClient()
        with mock.patch.object(wt, "MAX_FILE_SIZE", 1_000_000):
            text = wt.transcribe_text(client, path, chunk_minutes=1)
        self.assertEqual(text, "text of long_part001.mp3 text of long_part002.mp3 text of long_part003.mp3")

    @unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
    def test_long_file_srt_offsets(self):
        path = os.path.join(self.tmp, "long.wav")
        make_audio(path, 90)
        client = FakeClient()
        with mock.patch.object(wt, "MAX_FILE_SIZE", 1_000_000):
            srt = wt.transcribe_srt(client, path, chunk_minutes=1)
        self.assertIn("3\n00:01:00,000 --> 00:01:02,500\nhello long_part002.mp3", srt)
        self.assertTrue(all(c[2]["response_format"] == "verbose_json" for c in client.calls))


class NotebookTests(unittest.TestCase):
    """Runs every code cell of the notebook (except %pip) with fake Colab and OpenAI modules."""

    @unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
    def test_notebook_cells(self):
        nb = json.load(open(os.path.join(HERE, "whisper_audio_transcription.ipynb")))
        cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
        client = FakeClient()
        downloads = []
        uploads = iter([["single.mp3"], ["one.mp3", "two.wav", "big.mp3"]])

        def upload():
            names = next(uploads)
            return {n: open(n, "rb").read() for n in names}

        colab = types.ModuleType("google.colab")
        colab.files = types.SimpleNamespace(upload=upload, download=downloads.append)
        colab.userdata = types.SimpleNamespace(get=lambda k: "sk-test")
        google = types.ModuleType("google")
        google.colab = colab
        fake_openai = types.SimpleNamespace(OpenAI=lambda: client)
        modules = {"google": google, "google.colab": colab, "openai": fake_openai}

        cwd, tmp = os.getcwd(), tempfile.mkdtemp()
        try:
            os.chdir(tmp)
            for n in ["single.mp3", "one.mp3", "two.wav"]:
                with open(n, "wb") as f:
                    f.write(b"\0" * 2048)
            make_audio("big.mp3", 30)
            with mock.patch.dict(sys.modules, modules), mock.patch.dict(os.environ, {}, clear=False):
                ns = {}
                for src in cells:
                    if src.startswith("%pip"):
                        continue
                    exec(compile(src, "<cell>", "exec"), ns)
                    if "MAX_FILE_SIZE = " in src:
                        ns["MAX_FILE_SIZE"] = 200_000  # make big.mp3 count as "over the limit"
                self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test")
                self.assertEqual(ns["transcription"], "text of two.wav")
                self.assertEqual(downloads, ["one.txt", "two.txt"])  # big.mp3 skipped
                self.assertEqual(open("one.txt", encoding="utf-8").read(), "text of one.mp3")
                ns["CHUNK_MINUTES"] = 0.25
                ns["split_audio"].__defaults__ = (0.25,)
                self.assertEqual(ns["transcribe_long_audio"]("big.mp3"),
                                 "text of big_part001.mp3 text of big_part002.mp3")
                srt = ns["transcribe_to_srt"]("big.mp3")
                self.assertIn("00:00:15,000 --> 00:00:17,500", srt)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp)
        self.assertEqual(client.calls[0], ("whisper-1", "single.mp3", {}))


if __name__ == "__main__":
    unittest.main()
