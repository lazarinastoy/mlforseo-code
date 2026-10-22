"""AI transcript audit for a YouTube SEO audit (Claude API).

Companion to the "How to use AI to run your YouTube SEO audit" section of the
MLforSEO guide "How to do a YouTube SEO audit" by Lazarina Stoy.

It runs one structured prompt over a folder of video transcripts and saves one
row per video to a CSV: main topic, subtopics, entities, whether the title's
promise is delivered, the hook in the first 30 seconds, retention cues, the
first CTA timestamp and suggested chapters. Every finding must quote the
transcript as evidence, so you can spot-check it.

Input: a folder of transcripts (.txt, .srt or .vtt), one file per video. The
file name (without extension) is used as the video title, so name them after
your videos, e.g. "How to do a YouTube SEO audit.srt". Download captions for
your own videos from YouTube Studio, or transcribe the files with Whisper.

You need: an Anthropic API key in the ANTHROPIC_API_KEY environment variable
(or an `ant auth login` profile). Never paste keys into the script.

    pip install anthropic pandas
    export ANTHROPIC_API_KEY=...        # your own key
    python ai_transcript_audit.py transcripts/ --out transcript_audit.csv

Use --dry-run to see which files would be sent (and their size) without
calling the API.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

MODEL = "claude-opus-5-5"   # Anthropic's current default model
EFFORT = "medium"           # low | medium | high; "low" is cheaper for big catalogues
USE_FALLBACKS = True        # retry on another model if a request is declined
MAX_CHARS = 400_000         # skip (don't silently truncate) very long transcripts

SYSTEM_PROMPT = """You are auditing a YouTube video for search visibility and retention.
Use ONLY the transcript you are given. Quote the transcript (with timestamps
when the transcript has them) as evidence for every point. If something is not
in the transcript, write "not found" instead of guessing. Do not invent
timestamps."""

SCHEMA = {
    "type": "object",
    "properties": {
        "main_topic": {"type": "string"},
        "subtopics_covered": {"type": "array", "items": {"type": "string"}},
        "entities_mentioned": {"type": "array", "items": {"type": "string"}},
        "title_promise_delivered": {"type": "string", "enum": ["yes", "partly", "no"]},
        "title_promise_evidence": {"type": "string"},
        "hook_first_30s": {"type": "string"},
        "hook_has_clear_promise": {"type": "boolean"},
        "retention_cues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "type": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["timestamp", "type", "quote"],
                "additionalProperties": False,
            },
        },
        "first_cta_timestamp": {"type": "string"},
        "suggested_chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["timestamp", "title"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "main_topic", "subtopics_covered", "entities_mentioned",
        "title_promise_delivered", "title_promise_evidence", "hook_first_30s",
        "hook_has_clear_promise", "retention_cues", "first_cta_timestamp",
        "suggested_chapters",
    ],
    "additionalProperties": False,
}

SRT_INDEX = re.compile(r"^\d+\s*$")
SRT_TIME = re.compile(r"^(\d{1,2}:\d{2}:\d{2})[,.]\d{3}\s*-->")


def read_transcript(path):
    """Return plain text; SRT/VTT cue times become [hh:mm:ss] markers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() not in {".srt", ".vtt"}:
        return text.strip()
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or SRT_INDEX.match(line):
            continue
        m = SRT_TIME.match(line)
        if m:
            lines.append(f"[{m.group(1)}]")
        else:
            lines.append(line)
    # join each timestamp with the caption text that follows it
    return re.sub(r"\]\n", "] ", "\n".join(lines)).strip()


def audit_transcript(client, title, transcript):
    """Send one transcript to Claude and return the parsed JSON dict."""
    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": f"Title: {title}\n\nTranscript:\n{transcript}",
        }],
    )
    if USE_FALLBACKS:
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        )
    else:
        response = client.messages.create(**kwargs)

    if response.stop_reason == "refusal":
        raise RuntimeError("request declined (stop_reason=refusal)")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("output hit max_tokens; try a shorter transcript")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def flatten(title, result):
    """One CSV row per video; lists are joined so they fit in a sheet cell."""
    return {
        "title": title,
        "main_topic": result["main_topic"],
        "subtopics_covered": "; ".join(result["subtopics_covered"]),
        "entities_mentioned": "; ".join(result["entities_mentioned"]),
        "title_promise_delivered": result["title_promise_delivered"],
        "title_promise_evidence": result["title_promise_evidence"],
        "hook_first_30s": result["hook_first_30s"],
        "hook_has_clear_promise": result["hook_has_clear_promise"],
        "retention_cues": " | ".join(
            f'{c["timestamp"]} {c["type"]}: "{c["quote"]}"' for c in result["retention_cues"]
        ),
        "first_cta_timestamp": result["first_cta_timestamp"],
        "suggested_chapters": "\n".join(
            f'{c["timestamp"]} {c["title"]}' for c in result["suggested_chapters"]
        ),
    }


def main(argv=None, client=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", type=Path, help="folder of .txt / .srt / .vtt transcripts")
    parser.add_argument("--out", default="transcript_audit.csv")
    parser.add_argument("--dry-run", action="store_true", help="list files, don't call the API")
    args = parser.parse_args(argv)

    files = sorted(p for p in args.folder.iterdir()
                   if p.suffix.lower() in {".txt", ".srt", ".vtt"})
    if not files:
        sys.exit(f"No .txt, .srt or .vtt files in {args.folder}")

    if args.dry_run:
        for p in files:
            print(f"{p.name}: {len(read_transcript(p)):,} characters")
        return None

    if client is None:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY or your `ant` profile

    rows, errors = [], []
    for p in files:
        title, transcript = p.stem, read_transcript(p)
        if len(transcript) > MAX_CHARS:
            errors.append((p.name, f"transcript longer than {MAX_CHARS:,} characters, skipped"))
            continue
        try:
            rows.append(flatten(title, audit_transcript(client, title, transcript)))
            print(f"done: {title}")
        except Exception as e:  # keep going; report failures at the end
            errors.append((p.name, str(e)))

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"\nSaved {len(df)} rows to {args.out}")
    for name, err in errors:
        print(f"FAILED {name}: {err}")
    print("Spot-check the quotes against the transcripts before you use any finding.")
    return df


if __name__ == "__main__":
    main()
