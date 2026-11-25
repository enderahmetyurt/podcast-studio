---
name: podcast-setup
description: Set up podcast-studio for a show - installs the transcription environment, then interviews the user and writes podcast.json (show name, language, host, links, brand colors, logo, fonts, theme music, outro, description template) and an empty guests.json. Use when the user wants to start using podcast-studio, configure their podcast, change show branding or links, or when another podcast-studio skill finds no podcast.json.
argument-hint: "[show-folder]"
---

# Podcast setup

Talk to the user in the language they write in. Everything this plugin produces for the audience (descriptions, captions, posts) uses the show's `language`.

## 0. Locate the scripts

This skill's base directory is shown when it loads. The scripts are two levels up:

```bash
PS="$(cd -P "<base directory>/../.." && pwd)/scripts"; echo "$PS"
```

Use the printed absolute path in later commands (shell variables do not persist between calls). Python is `${PODCAST_STUDIO_VENV:-~/.cache/podcast-studio-venv}/bin/python`, always run with `-I`.

## 1. Environment

```bash
bash <scripts>/setup.sh
```

Installs Pillow plus mlx-whisper (Apple Silicon) or faster-whisper (everything else) into the venv and checks for ffmpeg. If ffmpeg is missing, give the user the install command the script printed; do not install system packages yourself. The first transcription downloads the Whisper model (~1.5 GB).

## 2. Show folder

The show folder holds `podcast.json`, `guests.json`, an `assets/` folder, and one folder per episode (e.g. `s01e04-jane-doe/`). Skills find `podcast.json` by walking up from the episode folder. Use the argument, else the current folder; confirm with the user. If `podcast.json` already exists, show it and ask what to change rather than starting over.

## 3. Interview

Ask in one or two short rounds, not field by field. Only `name` and `language` are required; leave out what the user does not have.

- Show name, host name, website
- Language of the episodes (ISO code: `en`, `tr`, `es`, `de`...; `auto` if mixed)
- Social handles: Instagram, X, YouTube, LinkedIn page, TikTok
- Episode label format, default `S{season}E{episode}`
- Brand: logo file (PNG with transparent background works best), 4 colors (`accent`, `secondary`, `highlight`, `dark`; offer the defaults), optional bold fonts (`font_black`, `font_heavy`; without them a system bold font is used)
- Audio: theme music for the intro, outro sting, music for launch-day montages (+ start offset in seconds), optional whoosh effect. Remind the user to use music they have the rights to.
- Description: ask for one or two past episode descriptions (paste or file). Derive `description.template` and `description.footer` (the fixed contact block) from them, so new descriptions match their format. If they have none, use the default structure in `examples/podcast.json`.

Copy asset files the user points to into `assets/` and reference them with relative paths.

## 4. Write the files

Write `podcast.json` following the structure of `examples/podcast.json` in the plugin root, and `guests.json` as `{}` if it does not exist. Show the result and point out anything left empty.

## 5. Next steps

Tell the user the three workflows:
- `/podcast-episode <recording> [intro-voice]` - transcript, description, title ideas, final mix
- `/podcast-clips <episode-audio> <cover>` - short vertical clips with captions + post copy
- `/podcast-launch <episode-folder>` - launch-day montage video (4:5 and 9:16) + post copy
