"""Print 50 ms RMS levels (dB) around cut points, to place cuts in silence.

Usage: python levels.py <audio> <t> [<t> ...]

For each t, prints the +-0.4 s window as time:dB pairs. Below about -35 dB is a pause.
"""
import subprocess
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
src = sys.argv[1]
for t in map(float, sys.argv[2:]):
    a = max(0.0, t - 0.4)
    out = subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-ss", str(a), "-t", "0.8", "-i", src, "-af",
        "aformat=channel_layouts=mono,aresample=48000,asetnsamples=2400,astats=metadata=1:reset=1,"
        "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f", "null", "-"], capture_output=True, text=True).stdout
    vals = [-99.0 if "inf" in l else float(l.split("=")[1]) for l in out.splitlines() if "RMS" in l]
    print(f"{t:7.2f}: " + " ".join(f"{a + i * 0.05:.2f}:{int(v)}" for i, v in enumerate(vals)))
