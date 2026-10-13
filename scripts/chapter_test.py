"""Extrait de test long : un chapitre du script, lu par plusieurs voix, avec le jingle d'ouverture.

Usage : python scripts/chapter_test.py DATE INDEX_CHAPITRE slug1,slug2,...
  ex. python scripts/chapter_test.py 2026-10-13 1 fr_marie_happy,fr_marie_curious
Sortie : docs/samples/test_<slug>.mp3
"""
import os
import subprocess
import sys
import tempfile

import requests
import yaml

sys.path.insert(0, os.path.dirname(__file__))
import mistral_api as m  # noqa: E402
from build_episode import chunks, to_wav, silence  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
date, idx, slugs = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(",")
cfg = yaml.safe_load(open(os.path.join(ROOT, "config.yml"), encoding="utf-8"))
url = f"https://raw.githubusercontent.com/{cfg['show']['source_repo']}/main/episodes/{date}.json"
ep = requests.get(url, timeout=60).json()
ch = ep["chapters"][idx]
print("Chapitre :", ch["title"], f"({sum(len(p) for p in ch['paragraphs'])} caractères)")

model = m.tts_model(cfg["voice"]["mistral"].get("model", "auto"))
voices = {v.get("slug"): v for v in m.list_voices()}
out_dir = os.path.join(ROOT, "docs", "samples")
os.makedirs(out_dir, exist_ok=True)

for slug in slugs:
    v = voices.get(slug)
    if not v:
        print(f"::error title=Voix::{slug} introuvable")
        continue
    tmp = tempfile.mkdtemp()
    parts = []
    to_wav(os.path.join(ROOT, "assets", "jingle_intro.mp3"), os.path.join(tmp, "intro.wav"))
    silence(cfg["audio"]["pause_between_paragraphs_ms"], os.path.join(tmp, "gap.wav"))
    to_wav(os.path.join(ROOT, "assets", "jingle_transition.mp3"), os.path.join(tmp, "tr.wav"))
    parts += [os.path.join(tmp, "intro.wav")]
    # un paragraphe par appel, pour un rythme naturel entre les paragraphes
    for i, p in enumerate(ch["paragraphs"]):
        raw = os.path.join(tmp, f"p{i}.mp3")
        open(raw, "wb").write(m.speech(" ".join(p.split()), v["id"], model, "mp3"))
        wav = os.path.join(tmp, f"p{i}.wav")
        to_wav(raw, wav)
        parts += [wav, os.path.join(tmp, "gap.wav")]
    parts.append(os.path.join(tmp, "tr.wav"))
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    joined = os.path.join(tmp, "joined.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    out = os.path.join(out_dir, f"test_{slug}.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-b:a", "96k", out], check=True)
    print("prêt :", out)
