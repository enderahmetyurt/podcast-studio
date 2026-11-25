---
name: podcast-clips
description: Turn a podcast episode into short vertical clips - finds the strongest 25-33 second moments, cuts them on clean sentence boundaries, renders 9:16 videos with cover, title, waveform and word-highlighted captions, and writes Instagram Reels / X / YouTube Shorts / TikTok copy tagging the guest. Also writes copy only for clips that already exist. Usage /podcast-clips <episode-audio> <cover> [guest-key] [platform=@handle ...], or /podcast-clips copy <folder> [guest-key]. Use when the user wants reels, shorts, clips, audiograms or social posts from an episode.
argument-hint: <episode-audio> <cover> [guest-key] [platform=@handle ...] | copy <folder> [guest-key]
---

# Episode clips

If the first argument is `copy`, go to **Copy-only mode** below.

Arguments: `$ARGUMENTS` → 1. episode audio, 2. cover image, 3. guest key in `guests.json`, then optional one-off handle overrides (`instagram=@..`, `x=@..`, `youtube=@..`, `tiktok=@..`).
If something is missing, list the audio and image files in the folder and ask.

Work in the episode folder. Talk to the user in their language; captions and copy are in the show's `language`.

## 0. Scripts and config

Scripts: `PS="$(cd -P "<this skill's base directory>/../.." && pwd)/scripts"`; print it once and use the absolute path. Python: `${PODCAST_STUDIO_VENV:-~/.cache/podcast-studio-venv}/bin/python -I`; if it does not exist run `bash <scripts>/setup.sh`. Use the scratchpad as the work folder.

Read `podcast.json` (walk up from the episode folder); none → run `podcast-setup` first.

## 1. Guest handles (first, while the transcript runs)

`guests.json` sits next to `podcast.json`:

```json
{ "jane": { "name": "Jane Doe", "link": "https://...", "instagram": "@..", "x": "@..", "youtube": null, "tiktok": null } }
```

- Guest known → show the handles and get confirmation ("Jane: IG @a · X @b · no YouTube. Still right?"). Don't write copy before that.
- User changes a handle → update the file.
- Argument overrides apply to this run only unless the user says to save them.
- Guest unknown → ask for name and handles, add them. Missing platform → `null`.
- Don't try to verify handles online (most platforms hide profiles from logged-out visitors); the user has the final say.

## 2. Transcript

Reuse `*-transcript.txt` in the episode folder if `podcast-episode` made one. Otherwise run in the background:

```bash
<python> -I <scripts>/transcribe.py <episode> <episode>-transcript.txt
```

## 3. Pick moments

Read the whole transcript. Pick 8-10 moments, each 25-33 s, understandable on its own, grabbing attention in the first 2 seconds. Prefer personal confessions and stories, bold claims, concrete numbers, strong closing lines. Skip the opening small talk, "we'll get to that" transitions, and anything that needs context.

Start and end on sentence boundaries, with 0.5 s of lead-in. Write `<scratch>/clips.txt`:

```text
00:39:19.5|00:39:51|08-burnout-at-night
```

Names: `NN-short-slug`, ASCII only.

## 4. Cut and check boundaries

```bash
mkdir -p clips && <python> -I <scripts>/cut.py <episode> <scratch>/clips.txt clips
```

Check each clip's START/END text. If a clip starts or ends mid-word, includes the tail of the previous sentence, or cuts a sentence short, shift that line 0.5-2 s and re-cut just that clip (append names: `... clips 03-x 07-y`). Repeat until clean. Transcript timestamps drift by a few seconds, so never skip this step.

Show a table: `# | file | length | topic (one line)`, recommend the strongest 3-4, and ask which to render.

## 5. Render videos

For each chosen clip write a short, curiosity-driven title (max ~35 characters, fits 2 lines; take it from the clip's own words). Read the clip's `.json` and put Whisper mistakes (names, technical terms, nonsense words) into `<scratch>/fixes.json`: `{"wrong": "right", "filler.": ""}`. Mention corrections you're unsure about.

Label: `<SHOW NAME> · <episode label> · <GUEST FIRST NAME>` in capitals, episode label from `podcast.json`'s `episode_label` with season/episode taken from the folder name (`s02e01-jane` → `S2E1`) or asked.

```bash
mkdir -p clips/video && <python> -I <scripts>/render_clip.py \
  --cover <cover> --audio clips/<name>.mp3 --words clips/<name>.json \
  --title "<title>" --label "<label>" --fixes <scratch>/fixes.json \
  --out clips/video/<name>.mp4 --work <scratch>/w_<name>
```

Check your own work: grab the frame at 8 s from each video and tile them, then look for title overflow and caption legibility:

```bash
ffmpeg -nostdin -v error -y -ss 8 -i clips/video/<name>.mp4 -frames:v 1 -vf scale=360:-1 <scratch>/f_<name>.png
ffmpeg -nostdin -v error -y -i f_1.png -i f_2.png ... -filter_complex hstack=<n> <scratch>/grid.png
```

Send one video to the user as a sample.

## 6. Post copy

Write all copy into one file next to the videos: `clips/video/clip-copy.md`. If it exists, ask before overwriting. If earlier episodes have a `clip-copy.md`, read one and match its tone exactly.

```markdown
# <episode label> Clip Copy - <Guest Name>

---

## 01 - <idea of the clip>

### Instagram

<hook: one line - question, bold claim or quote + 1 emoji>

<2-3 sentences of context; tag the guest with their IG handle>

<question to the viewer> 👇

🎧 <Show name> <episode label>, link in bio.

#tag1 #tag2 #tag3 #tag4 #tag5

### X

<under 280 chars: hook + "with @<x handle>" + question + `🎧 Full episode: [LINK]`, max 2 hashtags>

### YouTube Shorts

**Title:** <under 100 chars, ends with #shorts>

<hook + 1-2 sentences ("On <Show> <label>, @<youtube handle> ...") + `🎧 Full episode: [LINK]` + 3-5 hashtags, first is #shorts>

### TikTok

<hook line + 1 sentence + question, 3-5 hashtags>

---

(next clips...)

### Tips
- **Cover frame:** ...
- **Order:** strongest / main idea first, most controversial last.
```

Rules:
- Only the first line shows in the feed; keywords go in the first two lines (Instagram and TikTok search index the caption).
- Instagram: exactly 5 hashtags, 3-4 topical + 1 broad, varied per clip.
- Check the X character count.
- Platform with a `null` handle → use the guest's plain name. Unknown episode link → leave `[LINK]` and remind the user. Use the show's own handles from `podcast.json`.
- Skip platforms the show has no account on.

Do not post anything yourself; the user uploads.

## Copy-only mode

`/podcast-clips copy <folder> [guest-key] [platform=@handle ...]` - the videos exist already, only copy is needed. Skip steps 2-5:

1. List videos in the folder (`*.mp4 *.mov`) in name order. Ask about any that aren't guest clips (teasers, trailers).
2. Confirm handles as in step 1. Episode label from the folder name, else ask.
3. If `clip-copy.md` exists: back it up as `clip-copy.bak.md`, keep existing Instagram text, replace handle placeholders with real handles, add missing platform sections derived from the same content. Mention (don't fix) hashtag counts that aren't 5.
4. If it doesn't exist: transcribe each video (`transcribe.py <video> <scratch>/<name>.txt`, Whisper reads video files directly) and write the file from scratch using the template above.
5. List what changed and the placeholders left (`[LINK]`, unknown handles).

## Notes

- Always pass `-nostdin` to ffmpeg inside loops, or it swallows the loop's input.
- Captions are drawn with Pillow, so ffmpeg builds without libass/freetype work.
- zsh: write `${VAR}` inside ffmpeg filters.
