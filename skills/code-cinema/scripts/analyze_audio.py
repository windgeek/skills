"""分析音频：拍点、能量、频段、onset → audio.js（window.AUDIO），并打印段落能量概况。
用法: python analyze_audio.py audio.wav audio.js [--fps 30]"""
import sys, json, numpy as np, librosa
wav, out = sys.argv[1], sys.argv[2]
FPS = int(sys.argv[sys.argv.index('--fps') + 1]) if '--fps' in sys.argv else 30
y, sr = librosa.load(wav, sr=44100, mono=True)
hop = sr // FPS
S = np.abs(librosa.stft(y, n_fft=4096, hop_length=hop)); fr = librosa.fft_frequencies(sr=sr, n_fft=4096)
band = lambda a, b: np.log1p(S[(fr >= a) & (fr < b)].mean(0) * 50)
rms = librosa.feature.rms(y=y, frame_length=4096, hop_length=hop)[0]
on = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
def norm(x, sm=1):
    x = np.convolve(x, np.ones(sm) / sm, 'same'); lo, hi = np.percentile(x, 5), np.percentile(x, 98)
    return np.clip((x - lo) / max(hi - lo, 1e-9), 0, 1)
n = int(len(y) / sr * FPS)
A = {k: [round(float(v), 3) for v in norm(a, s)[:n]] for k, a, s in
     [("rms", rms, 9), ("low", band(30, 160), 2), ("mid", band(300, 3000), 5), ("high", band(5000, 14000), 2), ("onset", on, 1), ("energy", rms, 45)]}
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
A["beats"] = [round(float(b), 3) for b in librosa.frames_to_time(beats, sr=sr, hop_length=hop)]
A["bpm"] = float(np.atleast_1d(tempo)[0]); A["dur"] = round(len(y) / sr, 3)
open(out, "w").write("window.AUDIO=" + json.dumps(A) + ";")
e = np.array(A["energy"])
print(f"时长 {A['dur']}s  BPM {A['bpm']:.1f}  拍点 {len(A['beats'])} 个，首拍 {A['beats'][0] if A['beats'] else '-'}s")
print("能量（每 5 秒，0-9）：")
for i in range(0, len(e), 150 * 6):
    print(f"  {i // FPS:4d}s  " + " ".join(str(int(v * 9)) for v in e[i:i + 150 * 6:150]))
