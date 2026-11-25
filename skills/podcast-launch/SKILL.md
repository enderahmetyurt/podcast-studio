---
name: podcast-launch
description: Make the launch-day post for a podcast episode - cuts 6-8 short punchy quotes, montages them over music with a cover intro card, big word-by-word text and a branded end card, renders 4:5 (Instagram/X/LinkedIn feed) and 9:16 (Shorts/Reels/TikTok) videos, and writes copy for each platform including LinkedIn. Usage /podcast-launch <episode-folder>. Use when the user wants a launch-day post, release announcement, trailer-style montage or evergreen promo video for an episode.
argument-hint: <episode-folder>
---

# Launch-day montage

The post stays on the profile for good: no "out now", "new episode", dates or times in the video or copy (stories are a separate job).

Talk to the user in their language; on-screen text and copy use the show's `language`.

## 0. Scripts and config

Scripts: `PS="$(cd -P "<this skill's base directory>/../.." && pwd)/scripts"`; print it once and use the absolute path. Python: `${PODCAST_STUDIO_VENV:-~/.cache/podcast-studio-venv}/bin/python -I`; if it does not exist run `bash <scripts>/setup.sh`.

Read `podcast.json`; none → run `podcast-setup` first. Music comes from `audio.launch_music` (or `theme_music`), starting at `audio.launch_music_offset` seconds. No music configured → ask for a file; the montage also works over silence.

## Inputs

Find in the episode folder, ask for what's missing:
- Cover image
- Episode title and guest name (from `*-description.md` or the user). Split the title into two balanced lines for the intro card.
- Quote source: `clips/*.mp3` + `clips/*.json` from `podcast-clips` (word timings `[{"w","s","e"}]`). If there are none, transcribe the full episode with `--words` and cut from it.
- If a trailer was made, ask which lines it used and don't reuse them.

## 1. Pick quotes

6-8 quotes, each 2-6 s, one punchy sentence; ~25-30 s of speech in total. Cover different topics and build an arc: hook → main idea → striking examples → hard-hitting close. You may drop the middle of a sentence by using two ranges (`ranges` with two pairs); tell the user where the splice is.

Place cuts in silence, not on word timestamps (they drift 0.1-0.3 s):

```bash
<python> -I <scripts>/levels.py <clip.mp3> <t1> <t2> ...
```

Prints 50 ms RMS (dB) around each point; below -35 dB is a pause. Start at the end of a pause, end at the start of one.

## 2. Audio

Write `<episode>/clips/launch/config.json`:

```json
{
  "name": "s02e04-launch",
  "out_dir": "<episode>/clips/video",
  "cover": "<episode>/cover.png",
  "title_lines": ["Domain-Driven Design", "in the Age of AI"],
  "guest": "Jane Doe",
  "clips": [
    {"src": "<episode>/clips/05-hundreds-of-interviews.mp3", "ranges": [[3.59, 7.04]]},
    {"src": "<episode>/clips/09-button-color.mp3", "ranges": [[12.27, 13.87], [16.55, 17.62]]}
  ]
}
```

Optional overrides: `music`, `music_offset`, `logo`, `site`, `language`.

```bash
<python> -I <scripts>/launch.py audio <config.json>
```

Flow: 3.8 s cover card with music at full volume → quotes (music at 20%, rising for 0.6 s between quotes, whoosh before each) → 4.8 s end card, music fades. All at -16 LUFS.

The command re-transcribes the montage and prints the text per quote. Check: did the next sentence's first word leak into the end of a quote ("So", "But")? Half a word at the start? Fix the range and re-run.

Send the audio to the user with a table (quote, source, length) and the splice points, and ask for approval. Say that you cannot listen to audio.

## 3. On-screen text

The audio step writes `words.json` next to the config: per quote, a list of `["word", start, end]`. Edit it before the video:
- Fix Whisper mistakes (names, technical terms). Merge split words; add missing words using neighboring times.
- Prefix 1-2 key words per quote with `*` (accent color).
- In long quotes (10+ words) insert `"|"` at a sentence break to start a new page.
- End a cut-off sentence with `…`.

## 4. Video

```bash
<python> -I <scripts>/launch.py video <config.json>
```

Produces `<name>-4x5.mp4` (Instagram, X, LinkedIn feed) and `<name>-9x16.mp4` (Shorts, Reels, TikTok). Add `story` for an Instagram-story-safe 9:16. Design: dark intro card (logo, cover, title, guest in accent color) → blurred cover with big words appearing one by one (current word in highlight color, key words in accent), logo on top, guest + title + progress bar at the bottom → end card (logo, cover, guest, title, website).

Grab frames from the intro, a few quotes and the end card (`ffmpeg -ss <t> -i <mp4> -frames:v 1`) and look at them; move page breaks in `words.json` if text overflows. Send both videos.

## 5. Copy

Add a `## 00 - Launch montage` section at the top of `clips/video/clip-copy.md` (create the file if needed). Match the tone of earlier episodes' copy if there is any.
- **Instagram** (4:5 post): first line is the strongest quote from the montage, then 2 sentences tagging the guest with their IG handle and naming the montage topics, a question that invites comments, "🎧 Full episode: link in bio.", 5 hashtags.
- **X** (4:5 video): quote + one sentence + `🎧 <Show> <label>: [LINK]` + 2 hashtags.
- **YouTube Shorts** (9:16): `**Title:** <episode title> #shorts`, 2-3 sentence description, `🎧 Full episode: [LINK]`, 4 hashtags.
- **TikTok** (9:16): quote hook + 1 sentence + question + 3-5 hashtags.
- **LinkedIn - show page** (4:5): brand voice, third person ("<Host> sits down with <guest>", "the episode covers..."), no "I". Two-line hook built on a contrast → short paragraph introducing the guest → "Highlights:" with 5-6 `→` takeaways (from the montage and the description highlights, 1-2 sentences each) → question for readers → `🎧 Full episode: [LINK]` → 5 CamelCase hashtags. Remind the user to @-mention the guest from the page.
- **LinkedIn - host repost**: a 2-3 sentence first-person note for the host to "Repost with your thoughts", including their favorite quote; no link, no hashtags.

Handles from `guests.json`; unknown → `@guest` and remind the user. The user fills in `[LINK]`. Skip platforms the show doesn't use.

Don't propose a posting schedule unless asked.

## Notes

- zsh: build filters in Python, write `${VAR}` in shell.
- All text is drawn with Pillow, so ffmpeg builds without drawtext/libass work.
- Logos are placed on a white disc so dark logos stay visible on dark cards.
