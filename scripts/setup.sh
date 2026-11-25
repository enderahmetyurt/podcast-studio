#!/usr/bin/env bash
# Create the Python environment podcast-studio uses and check for ffmpeg.
# Safe to re-run. Venv location: $PODCAST_STUDIO_VENV (default ~/.cache/podcast-studio-venv).
set -euo pipefail

VENV="${PODCAST_STUDIO_VENV:-$HOME/.cache/podcast-studio-venv}"

for tool in ffmpeg ffprobe; do
  command -v "$tool" >/dev/null || {
    echo "Missing $tool. Install it first: brew install ffmpeg (macOS), sudo apt install ffmpeg (Debian/Ubuntu), winget install ffmpeg (Windows)." >&2
    exit 1
  }
done

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating $VENV"
  python3 -m venv "$VENV"
fi

if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  WHISPER=mlx-whisper
else
  WHISPER=faster-whisper
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q pillow "$WHISPER"
echo "Ready: $VENV/bin/python (whisper backend: $WHISPER)"
