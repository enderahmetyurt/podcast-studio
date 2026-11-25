"""Shared helpers: show config, fonts, colors, language-aware uppercase, transcription backends."""
import json
import os
import platform
import re
import subprocess
import sys

DEFAULT_COLORS = {
    "accent": "#FF40A0",     # keywords, cover outline, guest name
    "secondary": "#3CDCFF",  # labels, episode title
    "highlight": "#FFD60A",  # the word being spoken, website
    "dark": "#080414",       # card background
}

# Bold display fonts we look for when the show config does not name one.
FONT_CANDIDATES = {
    "black": [
        "/Library/Fonts/SF-Pro-Display-Black.otf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    "heavy": [
        "/Library/Fonts/SF-Pro-Display-Heavy.otf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}

WHISPER_MLX = "mlx-community/whisper-large-v3-turbo"
WHISPER_FASTER = "large-v3-turbo"


# ------------------------------------------------------------------ show config

def find_show_config(start="."):
    """Walk up from `start` looking for podcast.json."""
    d = os.path.abspath(start)
    while True:
        p = os.path.join(d, "podcast.json")
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_show(path=None):
    """Load podcast.json; relative asset paths resolve against its folder. Missing file -> defaults."""
    path = path or find_show_config()
    show = json.load(open(path)) if path else {}
    base = os.path.dirname(os.path.abspath(path)) if path else os.getcwd()
    show["_dir"] = base

    def resolve(p):
        return p if not p or os.path.isabs(p) else os.path.join(base, os.path.expanduser(p))

    brand = show.setdefault("brand", {})
    brand["colors"] = {**DEFAULT_COLORS, **brand.get("colors", {})}
    for k in ("logo", "font_black", "font_heavy"):
        brand[k] = resolve(brand.get(k))
    audio = show.setdefault("audio", {})
    for k in ("theme_music", "outro", "launch_music", "sweep"):
        audio[k] = resolve(audio.get(k))
    show.setdefault("language", "auto")
    return show


def rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def colors(show):
    return {k: rgb(v) for k, v in show["brand"]["colors"].items()}


def font_path(show, kind="black"):
    explicit = show.get("brand", {}).get(f"font_{kind}")
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit(f"Font not found: {explicit} (brand.font_{kind} in podcast.json)")
        return explicit
    for p in FONT_CANDIDATES[kind]:
        if os.path.isfile(p):
            return p
    sys.exit(f"No bold font found. Set brand.font_{kind} in podcast.json to a .ttf/.otf file.")


def upper(text, lang):
    """Uppercase that respects Turkish/Azerbaijani dotted and dotless i."""
    if lang in ("tr", "az"):
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


# ------------------------------------------------------------------ transcription

def backend():
    forced = os.environ.get("PODCAST_WHISPER_BACKEND")
    if forced:
        return forced
    if sys.platform == "darwin" and platform.machine() == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "faster"


def transcribe(path, language=None, words=False, model=None):
    """Return (language, segments). Each segment: {"start", "end", "text", "words": [{"w","s","e"}]}."""
    lang = None if language in (None, "", "auto") else language
    # Not conditioning on the previous window keeps Whisper from locking into a repetition
    # loop ("eee, eee, ...") on long recordings and losing whole minutes of speech.
    if backend() == "mlx":
        import mlx_whisper
        r = mlx_whisper.transcribe(path, path_or_hf_repo=model or WHISPER_MLX, language=lang,
                                   word_timestamps=words, condition_on_previous_text=False)
        segs = [{"start": s["start"], "end": s["end"], "text": s["text"].strip(),
                 "words": [{"w": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2)}
                           for w in s.get("words", []) if w["word"].strip()]}
                for s in r["segments"]]
        return r.get("language", lang), clean_segments(segs)

    from faster_whisper import WhisperModel
    m = WhisperModel(model or WHISPER_FASTER, device="auto", compute_type="auto")
    it, info = m.transcribe(path, language=lang, word_timestamps=words, vad_filter=False,
                            condition_on_previous_text=False)
    segs = [{"start": s.start, "end": s.end, "text": s.text.strip(),
             "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                       for w in (s.words or []) if w.word.strip()]}
            for s in it]
    return info.language, clean_segments(segs)


# Lines Whisper invents over silence or music (it learned them from subtitle credits).
HALLUCINATIONS = re.compile(
    r"altyazı\s*m\.?\s*k\.?|abone olmayı unutmayın|subtitles? by|thanks? for watching|"
    r"please subscribe|untertitel|sous-titres|amara\.org|izlediğiniz için teşekkürler",
    re.IGNORECASE)


def clean_segments(segs):
    """Drop empty segments, subtitle-credit hallucinations and runs of the same filler."""
    out = []
    for s in segs:
        t = s["text"].strip()
        bare = re.sub(r"[\W_]+", "", t.lower())
        if not bare or HALLUCINATIONS.search(t):
            continue
        prev = [re.sub(r"[\W_]+", "", p["text"].lower()) for p in out[-2:]]
        if len(t) < 12 and prev.count(bare) == 2:  # third identical short line in a row
            continue
        out.append(s)
    return out


def word_list(segments):
    return [w for s in segments for w in s["words"]]


# ------------------------------------------------------------------ ffmpeg

def ff(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y", *args], check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def ensure_sweep(work_dir, show):
    """Return the show's whoosh effect, or synthesize a short one with ffmpeg."""
    custom = show.get("audio", {}).get("sweep")
    if custom:
        return custom
    out = os.path.join(work_dir, "sweep.wav")
    if not os.path.isfile(out):
        ff("-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.6:r=44100", "-af",
           "highpass=f=600,lowpass=f=9000,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.35:d=0.15,"
           "aformat=channel_layouts=stereo", out)
    return out
