"""Launch-day montage: short punchy quotes over music, cover intro card, word-by-word text, branded end card.

Usage:
  python launch.py audio <config.json>                   # montage audio + words.json draft
  python launch.py video <config.json> [4x5|9x16|story]  # video (both 4x5 and 9x16 if no format given)

config.json:
{
  "name": "s2e4-launch",                 # outputs: <name>.mp3, <name>-4x5.mp4, <name>-9x16.mp4
  "out_dir": "/.../clips/video",
  "cover": "/.../cover.png",
  "title_lines": ["Domain-Driven Design", "in the Age of AI"],
  "guest": "Jane Doe",
  "clips": [{"src": "/.../05-hundreds-of-interviews.mp3", "ranges": [[3.59, 7.04]]}, ...]
}
Optional: "music", "music_offset", "logo", "site", "language". Defaults come from podcast.json
(audio.launch_music, audio.launch_music_offset, brand.logo, website, language).
Without music the quotes play over silence.

The "audio" step writes words.json next to config.json: per quote, a list of ["word", start, end]
(montage time, Whisper output). Edit it before the video step: fix wrong words, prefix key words
with "*" (accent color), add "|" to start a new page in long quotes.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import colors, ensure_sweep, ff, font_path, load_show, transcribe, upper  # noqa: E402

LEAD, GAP, BED, UP = 3.8, 0.6, 0.2, 0.85   # intro card length, gap between quotes, music under speech / between
END_CARD, FADE = 4.8, 1.8                  # end card length, music fade-out

# Layouts per format (y coordinates in pixels)
LAYOUT = {
    "4x5": dict(H=1350, logo=200, logo_y=40, text_mid=660, font=100, lh=120, maxw=960,
                name_y=1150, sub_y=1215, bar_y=1275, card_logo=180, card_logo_y=30, cover_w=880, cover_y=250, cover_h=720,
                title_font=66, title_lh=82, guest_font=58, site_y=1220),
    "9x16": dict(H=1920, logo=240, logo_y=170, text_mid=920, font=112, lh=132, maxw=940,
                 name_y=1600, sub_y=1670, bar_y=1760, card_logo=220, card_logo_y=260, cover_w=960, cover_y=540, cover_h=820,
                 title_font=76, title_lh=96, guest_font=68, site_y=1700),
    # Instagram story: 9:16 with the top ~250 px (profile bar) and bottom ~340 px (reply box) kept clear
    "story": dict(H=1920, logo=220, logo_y=280, text_mid=900, font=112, lh=132, maxw=940,
                  name_y=1400, sub_y=1465, bar_y=1530, card_logo=190, card_logo_y=275, cover_w=860, cover_y=500, cover_h=690,
                  title_font=72, title_lh=90, guest_font=64, site_y=1520),
}
W = 1080

if len(sys.argv) < 3 or sys.argv[1] not in ("audio", "video"):
    sys.exit(__doc__)
cmd, cfg_path = sys.argv[1], os.path.abspath(sys.argv[2])
C = json.load(open(cfg_path))
CFG_DIR = os.path.dirname(cfg_path)
SHOW = load_show()
COL = colors(SHOW)
BLACK, HEAVY = font_path(SHOW, "black"), font_path(SHOW, "heavy")
DARK = COL["dark"] + (255,)
LANG = C.get("language") or SHOW.get("language", "auto")
WORK = os.path.join(CFG_DIR, f".launch-{C['name']}")
os.makedirs(WORK, exist_ok=True)
os.makedirs(C["out_dir"], exist_ok=True)
MUSIC = C.get("music") or SHOW["audio"].get("launch_music") or SHOW["audio"].get("theme_music")
MUSIC_OFFSET = C.get("music_offset", SHOW["audio"].get("launch_music_offset", 0))
LOGO = C.get("logo") or SHOW["brand"].get("logo")
SITE = C.get("site", SHOW.get("website", ""))
AUDIO = os.path.join(C["out_dir"], f"{C['name']}.mp3")
WORDS = os.path.join(CFG_DIR, "words.json")
TIMELINE = os.path.join(WORK, "timeline.json")


# ---------------------------------------------------------------- audio

def build_audio():
    parts, timeline, t = [], [], LEAD
    for i, clip in enumerate(C["clips"]):
        start = t
        for j, (a, b) in enumerate(clip["ranges"]):
            p, d = f"{WORK}/p{i}_{j}.wav", b - a
            ff("-ss", str(a), "-t", str(d), "-i", clip["src"], "-af",
               f"aresample=44100,aformat=channel_layouts=stereo,afade=t=in:d=0.02,afade=t=out:st={d - 0.04}:d=0.04", p)
            parts.append((p, t))
            t += d + (0.12 if j < len(clip["ranges"]) - 1 else 0)   # gap at a splice
        timeline.append((round(start, 3), round(t, 3)))
        t += GAP
    speech_end = t - GAP
    total = speech_end + END_CARD

    # speech: normalized as one piece
    inputs, chains = [], []
    for k, (p, at) in enumerate(parts):
        inputs += ["-i", p]
        chains.append(f"[{k}:a]adelay={int(at * 1000)}:all=1[s{k}]")
    ff(*inputs, "-filter_complex",
       ";".join(chains) + ";" + "".join(f"[s{k}]" for k in range(len(parts))) +
       f"amix=inputs={len(parts)}:normalize=0:duration=longest,apad=whole_dur={total},atrim=0:{total},"
       "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,aformat=channel_layouts=stereo[o]",
       "-map", "[o]", f"{WORK}/speech.wav")

    # music: BED under quotes, UP between them, full at start and end; 0.25 s linear ramps
    if MUSIC:
        expr = ""
        for k, (a, b) in enumerate(timeline):
            prev = UP if k else 1.0
            nxt = UP if k + 1 < len(timeline) else 1.0
            expr += (f"if(between(t,{a - 0.25:.3f},{a:.3f}),{prev}+({BED}-{prev})*(t-{a - 0.25:.3f})/0.25,"
                     f"if(between(t,{a:.3f},{b:.3f}),{BED},"
                     f"if(between(t,{b:.3f},{b + 0.25:.3f}),{BED}+({nxt}-{BED})*(t-{b:.3f})/0.25,")
        expr += f"if(lt(t,{timeline[0][0] - 0.25:.3f}),1,if(gt(t,{timeline[-1][1]:.3f}),1,{UP}))" + ")))" * len(timeline)
        ff("-ss", str(MUSIC_OFFSET), "-t", str(total), "-i", MUSIC, "-af",
           f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,aformat=channel_layouts=stereo,volume='{expr}':eval=frame,"
           f"afade=t=in:d=0.05,afade=t=out:st={total - FADE}:d={FADE},apad=whole_dur={total}", f"{WORK}/music.wav")
    else:
        ff("-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total}", f"{WORK}/music.wav")

    # whoosh before every quote from the second one on
    sweep = ensure_sweep(WORK, SHOW)
    sw_in, sw_ch = [], []
    for k, (a, _) in enumerate(timeline[1:]):
        sw_in += ["-i", sweep]
        sw_ch.append(f"[{k + 2}:a]aformat=channel_layouts=stereo,volume=0.35,adelay={int((a - 0.45) * 1000)}:all=1[w{k}]")
    n = len(sw_ch)
    ff("-i", f"{WORK}/speech.wav", "-i", f"{WORK}/music.wav", *sw_in, "-filter_complex",
       (";".join(sw_ch) + ";" if sw_ch else "") + "[0:a][1:a]" + "".join(f"[w{k}]" for k in range(n)) +
       f"amix=inputs={n + 2}:normalize=0:duration=first,alimiter=limit=0.89[o]",
       "-map", "[o]", "-c:a", "libmp3lame", "-b:a", "192k", AUDIO)
    json.dump({"timeline": timeline, "speech_end": speech_end, "total": total}, open(TIMELINE, "w"), indent=1)

    # words draft
    # Transcribe the speech-only track: over the full-volume intro music Whisper hears
    # "no speech" for the first window and drops the opening quotes.
    _, segs = transcribe(f"{WORK}/speech.wav", LANG, words=True)
    ws = [(w["w"], w["s"], w["e"]) for s in segs for w in s["words"]]
    # Whisper can place words early at quote starts; assign each word to the quote nearest its midpoint
    draft = [[] for _ in timeline]
    for w, s, e in ws:
        mid = (s + e) / 2
        k = min(range(len(timeline)), key=lambda i: max(timeline[i][0] - mid, 0, mid - timeline[i][1]))
        draft[k].append([w, s, e])
    with open(WORDS, "w") as fh:   # one line per quote, easy to hand-edit
        fh.write("[\n" + ",\n".join(json.dumps(c, ensure_ascii=False) for c in draft) + "\n]\n")
    for (a, b), c in zip(timeline, draft):
        print(f"{a:6.2f}-{b:6.2f}  " + " ".join(w[0] for w in c))
    print(f"\n{AUDIO} ({total:.1f} s)\n{WORDS}")


# ---------------------------------------------------------------- video

def up(s):
    return upper(s, LANG)


def font(path, size):
    return ImageFont.truetype(path, size)


def logo(size):
    if not LOGO:
        return None
    im = Image.open(LOGO).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    im = im.crop(bbox) if bbox else im
    a = im.getchannel("A")
    round_logo = all(a.getpixel(c) < 32 for c in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)))
    inner = size if round_logo else int(size * 0.68)   # square logos fit inside the disc
    im.thumbnail((inner, inner), Image.LANCZOS)
    disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))   # white disc so dark logos stay visible on dark cards
    ImageDraw.Draw(disc).ellipse((0, 0, size - 1, size - 1), fill="white")
    disc.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return disc


def paste_logo(img, size, y):
    lg = logo(size)
    if lg:
        img.alpha_composite(lg, ((W - size) // 2, y))


def cover_card(img, cw, y0, max_h):
    src = Image.open(C["cover"]).convert("RGB")
    cw = min(cw, int(max_h * src.width / src.height))   # tall/square covers shrink so the text below fits
    card = src.resize((cw, int(src.height * cw / src.width)))
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, *card.size), 36, fill=255)
    x0 = (W - cw) // 2
    img.paste(card, (x0, y0), m)
    ImageDraw.Draw(img).rounded_rectangle((x0 - 4, y0 - 4, x0 + cw + 4, y0 + card.height + 4), 40,
                                          outline=COL["accent"], width=4)
    return y0 + card.height


def card_base(L):
    img = Image.new("RGBA", (W, L["H"]), DARK)
    paste_logo(img, L["card_logo"], L["card_logo_y"])
    return img, cover_card(img, L["cover_w"], L["cover_y"], L["cover_h"])


def render(fmt):
    L, H = LAYOUT[fmt], LAYOUT[fmt]["H"]
    F = os.path.join(WORK, fmt)
    os.makedirs(F, exist_ok=True)
    meta = json.load(open(TIMELINE))
    total, card_at = meta["total"], meta["speech_end"] + 0.35
    intro_end = meta["timeline"][0][0] - 0.3
    title = " ".join(C["title_lines"])

    # background: blurred cover + logo + guest/title + progress bar track
    src = Image.open(C["cover"]).convert("RGB")
    s = max(W / src.width, H / src.height)
    bg = src.resize((int(src.width * s), int(src.height * s)))
    l, t = (bg.width - W) // 2, (bg.height - H) // 2
    bg = ImageEnhance.Brightness(bg.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(50))).enhance(0.28).convert("RGBA")
    paste_logo(bg, L["logo"], L["logo_y"])
    d = ImageDraw.Draw(bg)
    d.text((W / 2, L["name_y"]), up(C["guest"]), font=font(BLACK, 58), fill="white", anchor="mm")
    sub = font(HEAVY, 36)
    while sub.size > 22 and d.textlength(title, font=sub) > W - 100:
        sub = font(HEAVY, sub.size - 2)
    d.text((W / 2, L["sub_y"]), title, font=sub, fill=COL["secondary"], anchor="mm")
    d.rounded_rectangle((90, L["bar_y"], W - 90, L["bar_y"] + 10), 5, fill=(70, 60, 90))
    bg.convert("RGB").save(f"{F}/bg.png")

    # intro card: logo, cover, episode title, guest
    img, y = card_base(L)
    d = ImageDraw.Draw(img)
    y += 60
    size = L["title_font"]   # shrink long titles until they fit
    while size > 30 and max(d.textlength(up(t), font=font(BLACK, size)) for t in C["title_lines"]) > W - 100:
        size -= 2
    for line in C["title_lines"]:
        d.text((W / 2, y), up(line), font=font(BLACK, size), fill="white", anchor="mt", stroke_width=4, stroke_fill="black")
        y += L["title_lh"] * size / L["title_font"]
    d.text((W / 2, y + 30), up(C["guest"]), font=font(BLACK, L["guest_font"]), fill=COL["accent"], anchor="mt")
    img.save(f"{F}/intro.png")

    # end card: logo, cover, guest, title, website
    img, y = card_base(L)
    d = ImageDraw.Draw(img)
    d.text((W / 2, y + 70), up(C["guest"]), font=font(BLACK, 62), fill="white", anchor="mt")
    end_sub = font(HEAVY, 40)
    while end_sub.size > 24 and d.textlength(title, font=end_sub) > W - 100:
        end_sub = font(HEAVY, end_sub.size - 2)
    d.text((W / 2, y + 150), title, font=end_sub, fill=COL["secondary"], anchor="mt")
    if SITE:
        d.text((W / 2, L["site_y"]), SITE, font=font(BLACK, 72), fill=COL["highlight"], anchor="mm")
    img.save(f"{F}/end.png")

    Image.new("RGBA", (W - 180, 10), COL["accent"] + (255,)).save(f"{F}/bar.png")
    Image.new("RGBA", (W - 180, 10), (0, 0, 0, 0)).save(f"{F}/track.png")

    # big word-by-word text
    f = font(BLACK, L["font"])
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    blank.save(f"{F}/blank.png")
    d0 = ImageDraw.Draw(blank)
    entries, t, n = [], 0.0, 0
    for clip in json.load(open(WORDS)):
        pages, cur = [], []
        for w in clip:
            if w == "|":
                pages.append(cur)
                cur = []
            else:
                cur.append((up(w[0].lstrip("*")), w[1], w[2], w[0].startswith("*")))
        pages.append(cur)
        pages = [pg for pg in pages if pg]
        for pi, page in enumerate(pages):
            # lay out the whole page first so words don't move as they appear
            lines, ln = [], []
            for w in page:
                if ln and d0.textlength(" ".join(x[0] for x in ln + [w]), font=f) > L["maxw"]:
                    lines.append(ln)
                    ln = []
                ln.append(w)
            lines.append(ln)
            top, pos = L["text_mid"] - len(lines) * L["lh"] / 2, []
            for i, ln in enumerate(lines):
                x = (W - d0.textlength(" ".join(w[0] for w in ln), font=f)) / 2
                for w in ln:
                    pos.append((x, top + i * L["lh"]))
                    x += d0.textlength(w[0] + " ", font=f)
            page_end = pages[pi + 1][0][1] if pi + 1 < len(pages) else page[-1][2] + 0.25
            for wi, (_, st, _, _) in enumerate(page):
                end = page[wi + 1][1] if wi + 1 < len(page) else page_end
                if st > t:
                    entries.append(("blank.png", st - t))
                img = blank.copy()
                d = ImageDraw.Draw(img)
                for k in range(wi + 1):
                    col = COL["highlight"] if k == wi else (COL["accent"] if page[k][3] else "white")
                    d.text(pos[k], page[k][0], font=f, fill=col, stroke_width=8, stroke_fill="black")
                name = f"t{n:04d}.png"
                img.save(f"{F}/{name}")
                entries.append((name, end - st))
                t, n = end, n + 1
    entries.append(("blank.png", total - t + 1))
    with open(f"{F}/text.txt", "w") as fh:
        fh.write("ffconcat version 1.0\n")
        for name, dur in entries:
            fh.write(f"file {name}\nduration {max(dur, 0.04):.3f}\n")
        fh.write("file blank.png\n")

    out = os.path.join(C["out_dir"], f"{C['name']}-{fmt}.mp4")
    loop = ["-loop", "1", "-framerate", "30", "-i"]
    ff(*loop, f"{F}/bg.png", "-i", AUDIO, "-f", "concat", "-safe", "0", "-i", f"{F}/text.txt",
       *loop, f"{F}/end.png", *loop, f"{F}/bar.png", *loop, f"{F}/track.png", *loop, f"{F}/intro.png",
       "-filter_complex",
       f"[5:v][4:v]overlay=x='-w*(1-t/{total:.3f})':y=0:format=auto[bar];"
       f"[0:v][bar]overlay=90:{L['bar_y']}[b];"
       "[2:v]fps=30,format=rgba[txt];[b][txt]overlay=0:0:eof_action=pass[v1];"
       f"[3:v]format=rgba,fade=t=in:st={card_at:.3f}:d=0.35:alpha=1[ec];"
       f"[v1][ec]overlay=0:0:enable='gte(t,{card_at:.3f})'[v2];"
       f"[6:v]format=rgba,fade=t=out:st={intro_end - 0.3:.3f}:d=0.3:alpha=1[ic];"
       f"[v2][ic]overlay=0:0:enable='lte(t,{intro_end:.3f})',format=yuv420p[v]",
       "-map", "[v]", "-map", "1:a", "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)
    print("ok", out)


if cmd == "audio":
    build_audio()
else:
    for fmt in sys.argv[3:] or ["4x5", "9x16"]:
        render(fmt)
