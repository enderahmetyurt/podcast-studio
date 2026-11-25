#!/usr/bin/env bash
# Assemble an episode: spoken intro over theme music, the episode, then the outro.
#
# Usage:
#   MUSIC=theme.mp3 OUTRO=outro.mp3 mix.sh <intro-voice> <episode> [out.mp3]
#
# Flow:
#   0 to MUSIC_LEAD s     theme music at full volume
#   intro voice           music ducks to BED_LEVEL underneath
#   end of intro          music rises over 1.5 s, starts a MUSIC_FADE s fade-out MUSIC_TAIL s later
#   fade-out start        episode begins
#   last OUTRO_OVERLAP s  outro fades in over the end of the episode
# Everything is normalized to LOUDNESS LUFS; output is 44.1 kHz stereo 192k MP3.
#
# MUSIC is required. OUTRO is optional (omit for no outro).
# Pass "-" as the intro to skip the spoken intro: the music plays MUSIC_LEAD s, then fades under the episode.

set -euo pipefail

MUSIC="${MUSIC:-}"
OUTRO="${OUTRO:-}"
MUSIC_LEAD="${MUSIC_LEAD:-6}"         # music before the intro voice (s)
BED_LEVEL="${BED_LEVEL:-0.12}"        # music level under the voice (0-1)
MUSIC_TAIL="${MUSIC_TAIL:-5}"         # from end of intro to start of fade-out (s)
MUSIC_FADE="${MUSIC_FADE:-3}"         # music fade-out length (s)
OUTRO_OVERLAP="${OUTRO_OVERLAP:-2.5}" # outro overlap with the end of the episode (s)
LOUDNESS="${LOUDNESS:--16}"           # target LUFS

if [[ $# -lt 2 ]]; then
  sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi

INTRO="$1"
EPISODE="$2"
OUT="${3:-${EPISODE%.*}-final.mp3}"

[[ -n "$MUSIC" ]] || { echo "Set MUSIC to the theme music file." >&2; exit 1; }
for f in "$EPISODE" "$MUSIC" ${OUTRO:+"$OUTRO"}; do
  [[ -f "$f" ]] || { echo "File not found: $f" >&2; exit 1; }
done
[[ "$INTRO" == "-" || -f "$INTRO" ]] || { echo "File not found: $INTRO" >&2; exit 1; }

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
calc() { echo "$1" | bc -l; }
ms() { printf '%.0f' "$(calc "($1) * 1000")"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

NORM="loudnorm=I=${LOUDNESS}:TP=-1.5:LRA=11"
if [[ "$INTRO" == "-" ]]; then
  ffmpeg -hide_banner -v error -y -f lavfi -i "anullsrc=r=44100:cl=stereo:d=0.1" "$TMP/silence.wav"
  INTRO="$TMP/silence.wav"
  MUSIC_TAIL=0
fi
INTRO_DUR="$(dur "$INTRO")"
EP_DUR="$(dur "$EPISODE")"

DUCK_START="$(calc "$MUSIC_LEAD - 1")"
DUCK_END="$(calc "$MUSIC_LEAD + 1")"
INTRO_END="$(calc "$MUSIC_LEAD + $INTRO_DUR")"
RISE_END="$(calc "$INTRO_END + 1.5")"
FADE_START="$(calc "$INTRO_END + $MUSIC_TAIL")"
MUSIC_LEN="$(calc "$FADE_START + $MUSIC_FADE")"
DROP="$(calc "1 - $BED_LEVEL")"

VOL="if(lt(t,${DUCK_START}),1,if(lt(t,${DUCK_END}),1-(t-${DUCK_START})/2*${DROP},if(lt(t,${INTRO_END}),${BED_LEVEL},if(lt(t,${RISE_END}),${BED_LEVEL}+(t-${INTRO_END})/1.5*${DROP},1))))"

echo "1/3 Intro + music..."
ffmpeg -hide_banner -v error -y -i "$INTRO" -i "$MUSIC" -filter_complex "
[0:a]aresample=44100,aformat=channel_layouts=stereo,${NORM},adelay=$(ms "$MUSIC_LEAD"):all=1,apad[voice];
[1:a]atrim=0:${MUSIC_LEN},${NORM},aresample=44100,aformat=channel_layouts=stereo,volume='${VOL}':eval=frame,afade=t=out:st=${FADE_START}:d=${MUSIC_FADE}[music];
[music][voice]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89,aresample=44100[mix]" \
  -map "[mix]" "$TMP/intro.wav"

echo "2/3 Normalizing episode and outro..."
ffmpeg -hide_banner -v error -y -i "$EPISODE" -af "${NORM},aresample=44100,afade=t=in:d=0.3" -ac 2 "$TMP/ep.wav"

echo "3/3 Mixing..."
if [[ -n "$OUTRO" ]]; then
  ffmpeg -hide_banner -v error -y -i "$OUTRO" -af "${NORM},aresample=44100,afade=t=in:d=1.5" -ac 2 "$TMP/outro.wav"
  ffmpeg -hide_banner -v error -y -i "$TMP/intro.wav" -i "$TMP/ep.wav" -i "$TMP/outro.wav" -filter_complex "
[1:a]adelay=$(ms "$FADE_START"):all=1[ep];
[2:a]adelay=$(ms "$FADE_START + $EP_DUR - $OUTRO_OVERLAP"):all=1[ot];
[0:a][ep][ot]amix=inputs=3:duration=longest:normalize=0,alimiter=limit=0.89[mix]" \
    -map "[mix]" -c:a libmp3lame -b:a 192k "$OUT"
else
  ffmpeg -hide_banner -v error -y -i "$TMP/intro.wav" -i "$TMP/ep.wav" -filter_complex "
[1:a]adelay=$(ms "$FADE_START"):all=1[ep];
[0:a][ep]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89[mix]" \
    -map "[mix]" -c:a libmp3lame -b:a 192k "$OUT"
fi

printf 'Done: %s (%.1f s)\n' "$OUT" "$(dur "$OUT")"
printf 'Intro voice ends %.1f s, episode starts %.1f s' "$INTRO_END" "$FADE_START"
[[ -n "$OUTRO" ]] && printf ', outro enters %.1f s' "$(calc "$FADE_START + $EP_DUR - $OUTRO_OVERLAP")"
echo
