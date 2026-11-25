"""Cut clips from an episode, transcribe each with word timings, print start/end text to check boundaries.

Usage: python cut.py <episode> <clips.txt> <out-dir> [only-this-name ...]

clips.txt lines: START|END|name   (e.g. 00:39:20.6|00:39:46.6|08-burnout). Lines starting with # are skipped.
Writes <out-dir>/<name>.mp3 and <out-dir>/<name>.json (word timings).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import duration, ff, load_show, transcribe, word_list  # noqa: E402

if len(sys.argv) < 4:
    sys.exit(__doc__)
src, clips_file, out = sys.argv[1], sys.argv[2], sys.argv[3]
only = set(sys.argv[4:])
os.makedirs(out, exist_ok=True)
lang = load_show().get("language", "auto")

for line in open(clips_file):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    start, end, name = (x.strip() for x in line.split("|"))
    if only and name not in only:
        continue
    mp3 = f"{out}/{name}.mp3"
    ff("-ss", start, "-to", end, "-i", src,
       "-af", "afade=t=in:d=0.3,areverse,afade=t=in:d=0.8,areverse,loudnorm=I=-14:TP=-1.5:LRA=11",
       "-ar", "44100", "-b:a", "192k", mp3)
    _, segs = transcribe(mp3, lang, words=True)
    words = word_list(segs)
    json.dump(words, open(f"{out}/{name}.json", "w"), ensure_ascii=False)
    text = " ".join(w["w"] for w in words)
    print(f"== {name} ({duration(mp3):.1f}s)\n   START: {text[:80]}\n   END:   {text[-80:]}")
