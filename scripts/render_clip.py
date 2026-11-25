"""Render a 9:16 clip video: blurred cover background, cover card, title, waveform, word-highlighted captions.

Usage:
  python render_clip.py --cover cover.png --audio clip.mp3 --words clip.json \
      --title "I almost burned out" --label "MY SHOW · S2E1 · JANE" \
      --out clip.mp4 --work /tmp/work [--fixes fixes.json] [--show podcast.json]

--fixes: {"wrong": "right"} map that corrects Whisper mistakes; "" deletes the word.
Colors, fonts and language come from podcast.json (found by walking up from the current folder).
Captions are drawn with Pillow, so ffmpeg does not need libass or freetype.
"""
import argparse
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import colors, font_path, load_show, upper  # noqa: E402

W, H = 1080, 1920

p = argparse.ArgumentParser()
for a in ("cover", "audio", "words", "title", "label", "out", "work"):
    p.add_argument(f"--{a}", required=True)
p.add_argument("--fixes")
p.add_argument("--show")
p.add_argument("--language", help="overrides podcast.json, used for uppercasing")
args = p.parse_args()
os.makedirs(args.work, exist_ok=True)

SHOW = load_show(args.show)
LANG = args.language or SHOW.get("language", "auto")
C = colors(SHOW)
FONT, FONT_LABEL = font_path(SHOW, "black"), font_path(SHOW, "heavy")
fixes = json.load(open(args.fixes)) if args.fixes else {}


def load_words():
    words = []
    for w in json.load(open(args.words)):
        t = fixes.get(w["w"], w["w"])
        if not t:
            continue
        # Whisper splits suffixes and punctuation off as separate words ("data center 'larda", "5 -10")
        if words and (t[0] in "'’-" or t in ".,?!"):
            words[-1]["w"] += t
            words[-1]["e"] = w["e"]
        else:
            words.append(dict(w, w=t))
    for w in words:
        w["w"] = upper(w["w"], LANG)
    return words


def chunk(words, max_words=3, max_chars=16):
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(x["w"] for x in cur + [w])) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w["w"][-1] in ".,?!":
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def wrap(text, font, maxw, d):
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if d.textlength(test, font=font) > maxw and cur:
            lines.append(cur)
            cur = word
        else:
            cur = test
    return lines + [cur]


def background():
    src = Image.open(args.cover).convert("RGB")
    scale = max(W / src.width, H / src.height)
    bg = src.resize((int(src.width * scale), int(src.height * scale)))
    left, top = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(40))).enhance(0.35)

    cw = 1000
    card = src.resize((cw, int(src.height * cw / src.width)))
    if card.height > 820:
        card = card.crop((0, (card.height - 820) // 2, cw, (card.height - 820) // 2 + 820))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), 36, fill=255)
    cy = 560
    bg.paste(card, ((W - cw) // 2, cy), mask)
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle(((W - cw) // 2 - 4, cy - 4, (W + cw) // 2 + 4, cy + card.height + 4), 40,
                        outline=C["accent"], width=4)

    # The show name is a brand: plain uppercase (Enderinko → ENDERINKO, not ENDERİNKO).
    label_text = " · ".join(x.upper() if x.strip() == SHOW.get("name", "").strip() else upper(x, LANG)
                             for x in args.label.split(" · "))
    d.text((W / 2, 250), label_text, font=ImageFont.truetype(FONT_LABEL, 34), fill=C["secondary"], anchor="mm")
    tf = ImageFont.truetype(FONT, 76)
    y = 330
    for line in wrap(args.title, tf, 960, d)[:2]:
        d.text((W / 2, y), line, font=tf, fill="white", anchor="ma", stroke_width=4, stroke_fill="black")
        y += 92
    bg.save(f"{args.work}/bg.png")
    return cy + card.height


def caption_frames(chunks, cap_y):
    f = ImageFont.truetype(FONT, 88)
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    blank.save(f"{args.work}/blank.png")
    entries, t, n = [], 0.0, 0
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else ch[-1]["e"] + 0.4
        for wi, w in enumerate(ch):
            start = w["s"]
            end = ch[wi + 1]["s"] if wi + 1 < len(ch) else min(nxt, ch[-1]["e"] + 0.6)
            if start > t:
                entries.append(("blank.png", start - t))
            img = blank.copy()
            d = ImageDraw.Draw(img)
            words = [x["w"] for x in ch]
            size = 88
            while size > 48 and d.textlength(" ".join(words), font=f) > W - 80:   # long words: shrink to fit
                size -= 4
                f = ImageFont.truetype(FONT, size)
            x = (W - d.textlength(" ".join(words), font=f)) / 2
            for k, word in enumerate(words):
                d.text((x, cap_y), word, font=f, fill=C["highlight"] if k == wi else "white",
                       stroke_width=7, stroke_fill="black")
                x += d.textlength(word + " ", font=f)
            f = ImageFont.truetype(FONT, 88)
            name = f"c{n:04d}.png"
            img.save(f"{args.work}/{name}")
            entries.append((name, end - start))
            t, n = max(t, end), n + 1
    entries.append(("blank.png", 1.0))
    with open(f"{args.work}/captions.txt", "w") as fh:
        fh.write("ffconcat version 1.0\n")
        for name, dur in entries:
            fh.write(f"file {name}\nduration {max(dur, 0.04):.3f}\n")
        fh.write(f"file {entries[-1][0]}\n")


def hexc(c):
    return "0x%02X%02X%02X" % c


card_bottom = background()
caption_frames(chunk(load_words()), 1560)

subprocess.run([
    "ffmpeg", "-nostdin", "-v", "error", "-y",
    "-loop", "1", "-framerate", "30", "-i", f"{args.work}/bg.png",
    "-i", args.audio,
    "-f", "concat", "-safe", "0", "-i", f"{args.work}/captions.txt",
    "-filter_complex",
    f"[1:a]volume=2.5,showwaves=s=900x160:mode=cline:scale=sqrt:rate=30:colors={hexc(C['accent'])}|{hexc(C['secondary'])},"
    "format=rgba,colorchannelmixer=aa=0.9[wave];"
    f"[0:v][wave]overlay=(W-w)/2:{card_bottom + 40}[v1];"
    "[2:v]fps=30,format=rgba[cap];[v1][cap]overlay=0:0:eof_action=pass,format=yuv420p[v]",
    "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out,
], check=True)
print("ok", args.out)
