"""Transcribe audio files with OpenAI's speech-to-text API (Whisper).

Script version of whisper_audio_transcription.ipynb (MLforSEO tutorial "How to transcribe
audio with OpenAI's Whisper API in Google Colab (Python)").

    export OPENAI_API_KEY=sk-...
    python whisper_transcribe.py interview.mp3                    # -> interview.txt
    python whisper_transcribe.py *.m4a --out-dir transcripts      # bulk
    python whisper_transcribe.py webinar.mp4 --format srt         # -> webinar.srt captions
    python whisper_transcribe.py talk.wav --model gpt-4o-transcribe

Files over 25 MB are split into 10-minute chunks with pydub (needs ffmpeg) and transcribed in order.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

MAX_FILE_SIZE = 25 * 1024 * 1024  # API upload limit
CHUNK_MINUTES = 10
SUPPORTED = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}


def get_client():
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        try:  # Colab secret named OPENAI_API_KEY
            from google.colab import userdata

            os.environ["OPENAI_API_KEY"] = userdata.get("OPENAI_API_KEY")
        except ImportError:
            sys.exit("Set the OPENAI_API_KEY environment variable first.")
    return OpenAI()


def split_audio(file_path: str, chunk_minutes: int = CHUNK_MINUTES, out_dir: str | None = None):
    """Cut audio into mono 64 kbps MP3 chunks. Returns [(chunk_path, start_seconds), ...]."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(file_path).set_channels(1)
    chunk_ms = int(chunk_minutes * 60 * 1000)
    out_dir = out_dir or tempfile.mkdtemp(prefix="whisper_chunks_")
    base = os.path.splitext(os.path.basename(file_path))[0]
    chunks = []
    for i, start in enumerate(range(0, len(audio), chunk_ms), start=1):
        chunk_path = os.path.join(out_dir, f"{base}_part{i:03d}.mp3")
        audio[start:start + chunk_ms].export(chunk_path, format="mp3", bitrate="64k")
        chunks.append((chunk_path, start / 1000))
    return chunks


def parts_for(file_path: str, chunk_minutes: int = CHUNK_MINUTES):
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        return split_audio(file_path, chunk_minutes)
    return [(file_path, 0.0)]


def transcribe_file(client, file_path: str, model: str = "whisper-1", language: str | None = None) -> str:
    """Plain-text transcript of one file under 25 MB."""
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        raise ValueError(f"{file_path} is over 25 MB; use transcribe_text() to split it")
    kwargs = {"language": language} if language else {}
    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(model=model, file=audio_file, **kwargs)
    return response.text


def transcribe_text(client, file_path: str, model: str = "whisper-1", language: str | None = None,
                    chunk_minutes: int = CHUNK_MINUTES) -> str:
    """Plain-text transcript of a file of any size."""
    return " ".join(
        transcribe_file(client, part, model, language) for part, _ in parts_for(file_path, chunk_minutes)
    ).strip()


def srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(entries) -> str:
    return "\n".join(
        f"{i}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n"
        for i, (start, end, text) in enumerate(entries, start=1)
    )


def transcribe_srt(client, file_path: str, language: str | None = None, chunk_minutes: int = CHUNK_MINUTES) -> str:
    """SRT captions (whisper-1 only: the gpt-4o transcribe models have no segment timestamps)."""
    kwargs = {"language": language} if language else {}
    entries = []
    for part, offset in parts_for(file_path, chunk_minutes):
        with open(part, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                **kwargs,
            )
        for seg in response.segments:
            entries.append((seg.start + offset, seg.end + offset, seg.text.strip()))
    return segments_to_srt(entries)


def main(argv=None, client=None) -> list[str]:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+", help="audio/video files (mp3, mp4, mpeg, mpga, m4a, wav, webm)")
    p.add_argument("--format", choices=["txt", "srt"], default="txt")
    p.add_argument("--model", default="whisper-1", help="whisper-1 (default), gpt-4o-transcribe or gpt-4o-mini-transcribe")
    p.add_argument("--language", help="ISO-639-1 code, e.g. en, es, bg (optional; auto-detected otherwise)")
    p.add_argument("--chunk-minutes", type=int, default=CHUNK_MINUTES)
    p.add_argument("--out-dir", help="where to write transcripts (default: next to each file)")
    args = p.parse_args(argv)
    if args.format == "srt" and args.model != "whisper-1":
        p.error("--format srt needs --model whisper-1")

    client = client or get_client()
    written = []
    for path in args.files:
        if os.path.splitext(path)[1].lower() not in SUPPORTED:
            print(f"Skipped {path}: unsupported file type")
            continue
        if args.format == "srt":
            output = transcribe_srt(client, path, args.language, args.chunk_minutes)
        else:
            output = transcribe_text(client, path, args.model, args.language, args.chunk_minutes)
        out_dir = args.out_dir or os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + "." + args.format)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Transcription saved to {out_path}")
        written.append(out_path)
    return written


if __name__ == "__main__":
    main()
