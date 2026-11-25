"""Transcribe an audio/video file to timestamped text.

Usage: python transcribe.py <audio> <out.txt> [--language en|auto] [--words out.json]

Writes "[MM:SS] text" lines (HH:MM:SS for long files). --words also writes word timings
as [{"w", "s", "e"}]. Uses mlx-whisper on Apple Silicon, faster-whisper elsewhere.
Language defaults to podcast.json's "language" (or auto-detect).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_show, transcribe, word_list  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("audio")
p.add_argument("out")
p.add_argument("--language")
p.add_argument("--words")
p.add_argument("--model")
a = p.parse_args()

lang = a.language or load_show().get("language", "auto")
detected, segs = transcribe(a.audio, lang, words=bool(a.words), model=a.model)


def stamp(t):
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


with open(a.out, "w") as f:
    for s in segs:
        f.write(f"[{stamp(s['start'])}] {s['text']}\n")
if a.words:
    json.dump(word_list(segs), open(a.words, "w"), ensure_ascii=False)
print(f"{len(segs)} segments, language={detected} -> {a.out}")
