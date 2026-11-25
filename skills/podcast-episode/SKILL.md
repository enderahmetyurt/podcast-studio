---
name: podcast-episode
description: Prepare a podcast episode end to end - transcribes the recording, writes the episode description in the show's own format (intro paragraph, highlights, guest and contact links), suggests titles and chapter timestamps, and mixes intro voice + theme music + episode + outro into a loudness-normalized MP3. Use when the user wants to prepare a new episode, write show notes or an episode description, get chapters, or assemble the final episode audio. Usage /podcast-episode <recording> [intro-voice] [out.mp3].
argument-hint: <recording> [intro-voice] [out.mp3]
---

# Episode prep

Arguments: `$ARGUMENTS` → 1. episode recording, 2. (optional) spoken intro, 3. (optional) output name (default `<recording>-final.mp3`).
If something is missing, list audio files in the folder (`ls *.mp3 *.m4a *.wav`) and ask which is which.

Work in the episode folder. Talk to the user in their language; write the description in the show's `language`.

## 0. Scripts and config

Scripts: `PS="$(cd -P "<this skill's base directory>/../.." && pwd)/scripts"`; print it once and use the absolute path. Python: `${PODCAST_STUDIO_VENV:-~/.cache/podcast-studio-venv}/bin/python -I`; if it does not exist run `bash <scripts>/setup.sh`.

Read `podcast.json` (walk up from the episode folder). If there is none, run the `podcast-setup` skill first.

## 1. Transcript

Run in the background (`run_in_background: true`); 45 minutes of audio takes a few minutes on Apple Silicon, longer on CPU:

```bash
<python> -I <scripts>/transcribe.py <recording> <episode>-transcript.txt
```

Steps 1 and 3 are independent; start the mix while the transcript runs.

## 2. Description

Read the whole transcript. Write the description using `description.template` from `podcast.json` exactly: same structure, tone, tense and person. Fill placeholders from the transcript. Append `description.footer` verbatim. No headings, emojis, hashtags or timestamps unless the template has them.

Without a template, use:

```text
<One paragraph, present tense: who the guest is, what we start with, the central discussion, what else we touch on, a closing line that frames the main question.>

Highlights

* <Topic>: <1-2 sentences>
* ... (5-6 bullets in the order they come up)

Guest:
<Name>: <link>

<footer>
```

Rules:
- If the guest was on before (check `guests.json`), say so.
- Unknown guest link → write `[LINK]` and ask. If you can't be sure of the guest's full name from the transcript, ask.
- Add the guest to `guests.json` (`{"jane": {"name": "Jane Doe", "link": "...", "instagram": null, "x": null, "youtube": null}}`) once the user confirms the details.

Then add short notes for the user:
- Names and terms Whisper probably got wrong, with corrections
- Anything you guessed (job title, company) that needs checking
- Links promised on air ("we'll put it in the show notes")

Save as `<episode>-description.md`.

If asked: title ideas in the format the show uses (look at past episode folders), and chapters (`MM:SS Title`). Chapters must match the final mix: add the episode start offset that `mix.sh` prints to the raw transcript times; first line `00:00 Intro`.

## 3. Mix

```bash
MUSIC=<audio.theme_music> OUTRO=<audio.outro> <scripts>/mix.sh <intro-voice> <recording> <out.mp3>
```

Without a spoken intro pass `-` as the intro. Without `audio.theme_music` in `podcast.json`, ask the user for a file or skip the mix. Leave `OUTRO` unset if the show has none.

Tuning via environment: `MUSIC_LEAD` (6 s), `BED_LEVEL` (0.12), `MUSIC_TAIL` (5 s), `MUSIC_FADE` (3 s), `OUTRO_OVERLAP` (2.5 s), `LOUDNESS` (-16 LUFS).

Before running:
- Never overwrite an existing output without asking.
- Check the end of the recording for long silence; if the last words end well before the file does, raise `OUTRO_OVERLAP` accordingly:
  `ffmpeg -sseof -15 -i <recording> -af silencedetect=n=-45dB:d=0.4 -f null -`

When done, send the file to the user and list the transition times the script printed. Say plainly that you cannot listen to audio and the transitions need a listen.

## Notes

- zsh treats `$VAR[...]` and `$VAR:a` as modifiers; write `${VAR}` inside ffmpeg filters.
- Don't dump the raw transcript in chat; show the description and notes.
- Next: `/podcast-clips` for short clips, `/podcast-launch` for the launch-day montage.
