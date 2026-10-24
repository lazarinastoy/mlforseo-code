# Transcribe audio with OpenAI's Whisper API

Companion code for the MLforSEO tutorial **[How to transcribe audio with OpenAI's Whisper API in Google Colab (Python)](https://www.mlforseo.com/machine-learning-tutorials/audio-transcription/how-to-transcribe-audio-with-openais-whisper-api-in-google-colab-python/)**.

## What it does

Turns podcasts, interviews, webinars and videos into text you can repurpose as blog posts, captions or research notes.

| Part | What you get |
|---|---|
| Single file (steps 1-6) | Upload one file in Colab and print its transcript |
| Files over 25 MB | Split into 10-minute chunks with `pydub` and transcribe them in order |
| SRT captions | `.srt` file built from `whisper-1` segment timestamps, offsets corrected across chunks |
| Bulk | Upload several files, get and download one `.txt` per file |

The API accepts `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `wav` and `webm` up to 25 MB per request.

## Files

| File | What it is |
|---|---|
| `whisper_audio_transcription.ipynb` | The Colab notebook, following the steps in the post |
| `whisper_transcribe.py` | Command-line version: any number of files, txt or srt, automatic chunking |
| `test_whisper_transcribe.py` | Offline tests for the script and the notebook (OpenAI and Colab mocked; chunking tests need ffmpeg) |
| `requirements.txt` | `openai`, `pydub` |

## Run it

**Google Colab**
1. Open `whisper_audio_transcription.ipynb` in Colab (File > Open notebook > GitHub, or upload it).
2. Click the key icon in the left sidebar, add a secret named `OPENAI_API_KEY` with your key, and switch on notebook access. Your OpenAI account needs credits.
3. Run the cells in order. Use the bulk cell at the end for several files.

**Locally**
```bash
pip install -r requirements.txt          # plus ffmpeg for files over 25 MB (brew install ffmpeg / apt install ffmpeg)
export OPENAI_API_KEY=sk-...

python whisper_transcribe.py interview.mp3                       # interview.txt next to the file
python whisper_transcribe.py episodes/*.m4a --out-dir transcripts
python whisper_transcribe.py webinar.mp4 --format srt            # captions
python whisper_transcribe.py talk.wav --model gpt-4o-transcribe --language en
```

**Tests:** `python -m unittest test_whisper_transcribe.py -v`

## Models

| Model | Notes |
|---|---|
| `whisper-1` | The model in the tutorial. Supports `srt`, `vtt` and `verbose_json` with timestamps |
| `gpt-4o-transcribe`, `gpt-4o-mini-transcribe` | Newer speech-to-text models on the same endpoint. Text or JSON output only, so no SRT |

## What changed from the original 2024 notebook

- The original imported `openai` but called `OpenAI()` (a `NameError`), and mixed in the retired `openai.api_key = ...` pattern. It now uses `from openai import OpenAI` and `client = OpenAI()`.
- The key is read from a Colab secret or the `OPENAI_API_KEY` environment variable instead of being typed into the notebook.
- The single-file function returns the transcript text, not the response object.
- Files over 25 MB get a clear message instead of an API error, and there's a chunking helper for them. Transcripts are written as UTF-8, so non-English text saves correctly.

## Privacy

Audio is uploaded to OpenAI. Don't send recordings with confidential or personal information unless your agreement with OpenAI covers it.

## Tested with

Python 3.9, openai 2.48 (mocked), pydub 0.25.1, ffmpeg 9 (October 2026). Chunking and SRT offsets were tested on generated audio; live API calls were not executed in testing.
