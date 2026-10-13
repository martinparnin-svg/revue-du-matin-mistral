"""Jingles v3 : trois directions modernes (A Signature, B Pulse, C Documentaire).
Synthèse originale (aucun échantillon externe) avec réverbération à convolution,
délai stéréo, compression « sidechain », saturation douce.

Usage : python tools/jingles_v3.py SORTIE/
  -> SORTIE/<A|B|C>/jingle_{intro,transition,outro}.mp3 + SORTIE/variante_<X>.mp3 (démo enchaînée)
"""
import os
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

SR = 44100
rng = np.random.default_rng(2026)


# ---------------------------------------------------------------- outils DSP

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def T(d):
    return np.arange(int(d * SR)) / SR


def bf(x, kind, f, order=2):
    wn = np.clip(np.asarray(f, float) / (SR / 2), 1e-4, 0.99)
    b, a = butter(order, wn if wn.ndim else float(wn), btype=kind)
    return lfilter(b, a, x)


def sweep_filter(x, kind, f0, f1, seg=0.015, curve=2.0):
    """Filtre dont la fréquence évolue de f0 à f1 (par segments courts)."""
    out = np.zeros_like(x)
    n = int(seg * SR)
    for i in range(0, len(x), n):
        p = (i / max(1, len(x))) ** curve
        f = f0 * (f1 / f0) ** p
        blk = x[max(0, i - 400): i + n]
        y = bf(blk, kind, f)
        out[i:i + n] = y[-len(out[i:i + n]):]
    return out


class St:
    """Piste stéréo."""

    def __init__(self, dur):
        self.x = np.zeros((int(dur * SR), 2))

    def add(self, sig, at, pan=0.0, gain=1.0):
        if sig.ndim == 1:
            sig = np.stack([sig * np.sqrt((1 - pan) / 2), sig * np.sqrt((1 + pan) / 2)], 1) * 1.414
        i = int(at * SR)
        if i >= len(self.x):
            return
        j = min(len(self.x), i + len(sig))
        self.x[i:j] += sig[: j - i] * gain

    def __iadd__(self, other):
        n = min(len(self.x), len(other.x))
        self.x[:n] += other.x[:n]
        return self


def impulse(decay=2.4, pre=0.015, damp=5500, bright=0.6):
    t = T(decay * 1.3)
    ir = np.zeros((len(t), 2))
    for c in range(2):
        n = rng.standard_normal(len(t)) * np.exp(-t * 6.9 / decay)
        lo = bf(n, "low", damp)
        ir[:, c] = bright * n * np.exp(-t * 4) + lo
    ir[: int(pre * SR)] = 0
    return ir / np.max(np.abs(ir))


def reverb(st, mix=0.3, **kw):
    ir = impulse(**kw)
    wet = np.stack([fftconvolve(st.x[:, c], ir[:, c])[: len(st.x)] for c in range(2)], 1)
    wet *= np.max(np.abs(st.x)) / (np.max(np.abs(wet)) + 1e-9)
    st.x = st.x * (1 - mix * 0.5) + wet * mix
    return st


def pingpong(st, delay, fb=0.4, mix=0.25, lp=4000):
    d = int(delay * SR)
    out = st.x.copy()
    tap = st.x.copy()
    for k in range(1, 7):
        tap = np.roll(tap, d, axis=0)
        tap[:d] = 0
        tap = tap[:, ::-1] * fb  # alterne gauche / droite
        tap[:, 0] = bf(tap[:, 0], "low", lp)
        tap[:, 1] = bf(tap[:, 1], "low", lp)
        out += tap * mix / fb
    st.x = out
    return st


def sidechain(st, hits, depth=0.65, release=0.22):
    t = np.arange(len(st.x)) / SR
    g = np.ones_like(t)
    for h in hits:
        m = t >= h
        g[m] = np.minimum(g[m], 1 - depth * np.exp(-(t[m] - h) / release))
    st.x *= g[:, None]
    return st


def finish(st, fade_in=0.0, fade_out=0.6):
    x = st.x
    if fade_in:
        n = int(fade_in * SR)
        x[:n] *= np.linspace(0, 1, n)[:, None]
    n = int(fade_out * SR)
    x[-n:] *= (np.linspace(1, 0, n) ** 2)[:, None]
    x = np.tanh(1.2 * x / (np.max(np.abs(x)) + 1e-9)) / np.tanh(1.2)
    # léger « air » : on rehausse un peu l'aigu
    air = np.stack([bf(x[:, c], "high", 9000) for c in range(2)], 1)
    x = x + 0.15 * air
    return x / np.max(np.abs(x)) * 0.95


def write(x, path):
    wav = path.replace(".mp3", ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-af", "loudnorm=I=-15:TP=-1.0:LRA=9",
                    "-ar", "44100", "-b:a", "192k", path], check=True)
    os.remove(wav)


# ---------------------------------------------------------------- sources sonores

def glass(m, dur=2.5, vel=1.0, ratio=3.5, index=2.6):
    """Cloche de verre en synthèse FM."""
    t = T(dur)
    f = midi(m)
    I = index * np.exp(-t * 7) + 0.25
    sig = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t))
    sig += 0.3 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 4)
    return vel * sig * np.exp(-t * 2.2) * np.minimum(1, t / 0.002)


def felt_piano(m, dur=2.2, vel=1.0):
    """Piano feutré : partiels légèrement inharmoniques, attaque douce, bruit de marteau."""
    t = T(dur)
    f = midi(m)
    B = 0.0004
    sig = np.zeros_like(t)
    for k in range(1, 12):
        fk = f * k * np.sqrt(1 + B * k * k)
        sig += np.sin(2 * np.pi * fk * t + rng.uniform(0, 6)) / (k ** 1.6) * np.exp(-t * (1.2 + 0.7 * k))
    sig = bf(sig, "low", 2600)
    hammer = bf(rng.standard_normal(len(t)), "band", [800, 3000]) * np.exp(-t * 90) * 0.15
    return vel * (sig + hammer) * np.minimum(1, t / 0.006)


def supersaw(notes, dur, vel=1.0, voices=5, spread=0.18):
    t = T(dur)
    sig = np.zeros_like(t)
    for m in notes:
        for v in range(voices):
            det = spread * (v - (voices - 1) / 2) / ((voices - 1) / 2)
            f = midi(m) * 2 ** (det / 12)
            ph = (f * t + rng.uniform()) % 1.0
            sig += 2 * ph - 1
    return vel * sig / (len(notes) * voices)


def sub808(m, dur=1.2, vel=1.0, glide=1.4):
    t = T(dur)
    f = midi(m) * (1 + (glide - 1) * np.exp(-t * 30))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vel * np.tanh(1.6 * np.sin(ph)) * np.exp(-t * 2.0) * np.minimum(1, t / 0.003)


def kick(vel=1.0):
    t = T(0.3)
    f = 48 + 140 * np.exp(-t * 40)
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = bf(rng.standard_normal(len(t)), "high", 3000) * np.exp(-t * 600) * 0.3
    return vel * (np.tanh(2 * np.sin(ph)) * np.exp(-t * 9) + click)


def hat(vel=1.0, dec=80):
    t = T(0.08)
    return vel * bf(rng.standard_normal(len(t)), "high", 8500) * np.exp(-t * dec)


def clap(vel=1.0):
    t = T(0.35)
    n = bf(rng.standard_normal(len(t)), "band", [1100, 5000])
    env = sum(np.where(t >= o, np.exp(-(t - o) * 60), 0) for o in (0, 0.007, 0.015)) + 0.4 * np.exp(-t * 11)
    return vel * n * env


def tick(vel=1.0):
    t = T(0.03)
    return vel * (np.sin(2 * np.pi * 3200 * t) + 0.5 * bf(rng.standard_normal(len(t)), "high", 6000)) * np.exp(-t * 300)


def boom(vel=1.0, dur=2.5):
    t = T(dur)
    f = 32 + 40 * np.exp(-t * 5)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 1.6)
    noise = bf(rng.standard_normal(len(t)), "low", 900) * np.exp(-t * 4) * 0.35
    return vel * np.tanh(1.5 * (body + noise)) * np.minimum(1, t / 0.004)


def whoosh(dur, vel=1.0, up=True):
    n = rng.standard_normal(int(dur * SR))
    f0, f1 = (300, 9000) if up else (9000, 300)
    s = sweep_filter(n, "band" if False else "low", f0, f1, curve=1.6)
    x = np.linspace(0, 1, len(s))
    env = x ** 2.5 if up else (1 - x) ** 1.5
    st = np.stack([s * env * (0.6 + 0.4 * x), s * env * (1 - 0.4 * x)], 1)  # mouvement stéréo
    return vel * st


def reverse_swell(sig_st, dur):
    """Prend un son, lui ajoute une longue réverbe, et le joue à l'envers (montée aspirée)."""
    tmp = St(dur)
    tmp.add(sig_st, 0)
    reverb(tmp, mix=0.9, decay=dur * 0.9, damp=4000)
    return tmp.x[::-1] * np.linspace(0, 1, len(tmp.x))[:, None] ** 1.5


def to_st(sig, pan=0.0):
    return np.stack([sig * np.sqrt((1 - pan) / 2), sig * np.sqrt((1 + pan) / 2)], 1) * 1.414


# ---------------------------------------------------------------- A : Signature

MOTIF_A = [62, 69, 76, 74]  # ré – la – mi – ré (quinte, neuvième : sonorité ouverte et actuelle)


def a_intro():
    hit = 1.3
    st = St(5.0)
    st.add(reverse_swell(to_st(glass(74, 1.0, 1.0) + glass(81, 1.0, 0.6)), hit), 0, gain=0.7)
    st.add(whoosh(hit, 0.35), 0)
    for i, m in enumerate(MOTIF_A):
        st.add(glass(m, 2.8, 0.9 if i < 3 else 0.7), hit + i * 0.16, pan=(-0.35, 0.35, 0, 0.15)[i])
    st.add(sub808(38, 1.6, 0.9, 1.6), hit)
    st.add(tick(0.35), hit)
    pingpong(st, 0.16 * 1.5, fb=0.38, mix=0.3)
    reverb(st, mix=0.45, decay=2.8)
    return finish(st, fade_out=1.0)


def a_transition():
    st = St(1.3)
    st.add(whoosh(0.4, 0.35), 0)
    st.add(glass(76, 1.2, 0.8), 0.4, pan=0.2)
    st.add(glass(81, 1.0, 0.45), 0.48, pan=-0.2)
    st.add(sub808(38, 0.7, 0.6), 0.4)
    pingpong(st, 0.18, fb=0.35, mix=0.25)
    reverb(st, mix=0.4, decay=1.6)
    return finish(st, fade_out=0.4)


def a_outro():
    st = St(4.2)
    for i, m in enumerate([76, 69, 62]):
        st.add(glass(m, 3.0, 0.85), 0.1 + i * 0.2, pan=(0.3, -0.3, 0)[i])
    st.add(glass(50, 3.2, 0.6, ratio=2.0, index=1.2), 0.5)
    st.add(sub808(38, 2.2, 0.8, 1.2), 0.5)
    pingpong(st, 0.24, fb=0.4, mix=0.3)
    reverb(st, mix=0.55, decay=3.2)
    return finish(st, fade_out=1.8)


# ---------------------------------------------------------------- B : Pulse

BPM_B = 122
QB = 60 / BPM_B
CH_B = [[50, 57, 62, 64, 65], [46, 53, 58, 62, 65], [43, 50, 55, 58, 62], [45, 52, 57, 61, 64]]  # Dm(9) Bb G-m A


def b_chords(st, t0, bars, f_from, f_to):
    dur = bars * 4 * QB
    seg = St(dur + 0.2)
    for i in range(bars * 2):
        notes = CH_B[i % 4]
        s = supersaw([n + 12 for n in notes[1:]], 2 * QB + 0.05, 0.9)
        seg.add(s, i * 2 * QB)
    for c in range(2):
        seg.x[:, c] = sweep_filter(seg.x[:, c], "low", f_from, f_to, curve=1.3)
    sidechain(seg, [k * QB for k in range(bars * 4)], depth=0.75, release=0.18)
    st.add(seg.x, t0)


def b_intro():
    bars = 2
    hit = bars * 4 * QB + QB / 2  # petit silence avant l'impact
    st = St(hit + 2.3)
    b_chords(st, 0, bars, 500, 6000)
    for q in range(bars * 4):
        st.add(kick(0.8), q * QB)
        st.add(hat(0.25), q * QB + QB / 2, pan=0.3)
        if q % 4 == 0:
            st.add(sub808(CH_B[(q // 2) % 4][0] - 12, 2 * QB, 0.7), q * QB)
        if q % 2 == 1:
            st.add(clap(0.35), q * QB, pan=-0.05)
    for r in range(8):  # roulement de charleston sur le dernier temps
        st.add(hat(0.12 + 0.03 * r, 120), (bars * 4 - 1) * QB + r * QB / 8, pan=-0.3)
    for i, m in enumerate([74, 77, 81, 79]):  # accroche en verre sur la 2e mesure
        st.add(glass(m, 1.0, 0.45), 4 * QB + i * QB / 2, pan=(-0.3, 0.3, -0.1, 0.2)[i])
    st.add(whoosh(2 * QB, 0.4), hit - 2 * QB)
    st.add(supersaw([62, 69, 74, 76, 81], 2.0, 1.1) * np.exp(-T(2.0) * 1.6), hit)
    st.add(sub808(38, 2.0, 1.0, 1.8), hit)
    st.add(kick(1.0), hit)
    st.add(clap(0.5), hit)
    st.add(glass(86, 2.0, 0.4), hit, pan=0.2)
    reverb(st, mix=0.25, decay=2.0)
    return finish(st, fade_out=1.2)


def b_transition():
    st = St(1.4)
    for r in range(6):
        st.add(hat(0.12 + 0.04 * r, 120), r * QB / 6, pan=-0.3 + 0.12 * r)
    st.add(whoosh(QB, 0.3), 0)
    hit = QB
    st.add(supersaw([62, 69, 76], 0.9, 0.9) * np.exp(-T(0.9) * 4), hit)
    st.add(sub808(38, 0.8, 0.8, 1.6), hit)
    st.add(kick(0.8), hit)
    st.add(glass(81, 0.9, 0.35), hit, pan=0.25)
    reverb(st, mix=0.25, decay=1.3)
    return finish(st, fade_out=0.45)


def b_outro():
    hit = 4 * QB
    st = St(hit + 2.6)
    b_chords(st, 0, 1, 2500, 7000)
    for q in range(4):
        st.add(kick(0.7), q * QB)
        st.add(hat(0.22), q * QB + QB / 2, pan=0.3)
    for i, m in enumerate([74, 77, 81]):
        st.add(glass(m, 1.0, 0.45), i * QB / 2 + QB, pan=(-0.3, 0.3, 0)[i])
    st.add(supersaw([50, 62, 66, 69, 74], 2.6, 1.0) * np.exp(-T(2.6) * 1.3), hit)
    st.add(sub808(38, 2.4, 0.9, 1.5), hit)
    st.add(glass(78, 2.4, 0.4), hit)
    reverb(st, mix=0.35, decay=2.6)
    return finish(st, fade_out=1.8)


# ---------------------------------------------------------------- C : Documentaire

BPM_C = 96
QC = 60 / BPM_C
OST_C = [62, 69, 65, 69, 62, 69, 64, 69]  # ostinato de piano feutré


def c_ticks(st, t0, beats, vel=0.12):
    for s in range(beats * 4):
        st.add(tick(vel * (1.0 if s % 4 == 0 else 0.55)), t0 + s * QC / 4, pan=0.45 if s % 2 else -0.45)


def c_intro():
    hit = 8 * QC
    st = St(hit + 2.6)
    c_ticks(st, 0, 8)
    for i in range(16):
        st.add(felt_piano(OST_C[i % 8], 1.4, 0.55 if i % 4 else 0.7), i * QC / 2, pan=-0.15)
    pad = supersaw([50, 57, 62], 8 * QC, 0.35, voices=3, spread=0.1)
    pad = bf(pad, "low", 900) * np.minimum(1, T(8 * QC) / (4 * QC))
    st.add(pad, 0)
    st.add(sub808(38, 4 * QC, 0.35, 1.0), 4 * QC)
    st.add(reverse_swell(to_st(felt_piano(74, 1.0) + felt_piano(81, 1.0, 0.6)), 2 * QC), hit - 2 * QC, gain=0.7)
    st.add(boom(1.0), hit)
    st.add(felt_piano(50, 2.5, 0.9), hit)
    st.add(felt_piano(74, 2.5, 0.5), hit, pan=0.2)
    st.add(glass(86, 2.4, 0.25, ratio=2.0, index=1.0), hit + 0.02, pan=0.3)
    reverb(st, mix=0.4, decay=2.8, damp=4500)
    return finish(st, fade_out=1.4)


def c_transition():
    st = St(2.0)
    c_ticks(st, 0, 1, 0.12)
    st.add(whoosh(QC, 0.22), 0)
    st.add(felt_piano(69, 1.2, 0.6), QC)
    st.add(felt_piano(74, 1.2, 0.45), QC + 0.03)
    st.add(boom(0.45, 1.0), QC)
    reverb(st, mix=0.45, decay=1.6, damp=4500)
    return finish(st, fade_out=0.7)


def c_outro():
    st = St(5.0)
    c_ticks(st, 0, 4, 0.14)
    for i, m in enumerate([62, 69, 65, 69, 62, 69]):
        st.add(felt_piano(m, 1.4, 0.6), i * QC / 2, pan=-0.15)
    hit = 4 * QC
    st.add(felt_piano(50, 3.0, 0.8), hit)
    st.add(felt_piano(66, 3.0, 0.5), hit + 0.02)   # fa dièse : fin en majeur, apaisée
    st.add(felt_piano(74, 3.0, 0.45), hit + 0.04)
    st.add(boom(0.7, 2.5), hit)
    reverb(st, mix=0.5, decay=3.0, damp=4500)
    return finish(st, fade_out=2.0)


# ---------------------------------------------------------------- export

VARIANTS = {"A": (a_intro, a_transition, a_outro), "B": (b_intro, b_transition, b_outro),
            "C": (c_intro, c_transition, c_outro)}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "jingles"
    only = sys.argv[2:] or list(VARIANTS)
    for v in only:
        d = os.path.join(out, v)
        os.makedirs(d, exist_ok=True)
        parts = []
        for name, fn in zip(("intro", "transition", "outro"), VARIANTS[v]):
            p = os.path.join(d, f"jingle_{name}.mp3")
            write(fn(), p)
            parts.append(p)
        # démo enchaînée : ouverture, 1,5 s, transition, 1,5 s, fin
        lst = os.path.join(d, "list.txt")
        sil = os.path.join(d, "sil.mp3")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-t", "1.5", "-b:a", "192k", sil], check=True)
        with open(lst, "w") as f:
            for p in (parts[0], sil, parts[1], sil, parts[2]):
                f.write(f"file '{os.path.abspath(p)}'\n")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-ar", "44100", "-b:a", "192k", os.path.join(out, f"variante_{v}.mp3")], check=True)
        os.remove(lst)
        os.remove(sil)
        print("variante", v, "ok")
