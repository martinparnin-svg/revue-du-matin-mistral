"""Fabrique les épisodes MP3 à partir des scripts déposés dans episodes/AAAA-MM-JJ.json.

Format attendu du JSON :
{
  "date": "2026-10-14",
  "title": "Revue du matin · 14 octobre 2026",
  "summary": "Les sujets du jour en une ou deux phrases.",
  "links": {"note": "https://...", "page": "https://..."},
  "chapters": [{"title": "…", "paragraphs": ["…", "…"]}]
}

Usage : python scripts/build_episode.py            (épisodes pas encore fabriqués)
        python scripts/build_episode.py 2026-10-14 (refabrique cet épisode)
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from tts import synthesize  # noqa: E402
from feed import write_feed  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "docs", "audio")
MAX_CHARS = 3200  # taille maximale d'un appel de synthèse (≈ 3 à 4 min d'audio)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def to_wav(src, dst):
    """Normalise n'importe quel fichier audio en WAV 44,1 kHz stéréo pour l'assemblage."""
    run(["ffmpeg", "-y", "-i", src, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", dst])


def silence(ms, dst):
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{ms / 1000:.3f}",
         "-c:a", "pcm_s16le", dst])


def chunks(paragraphs):
    """Regroupe les paragraphes en blocs de taille raisonnable, sans couper une phrase."""
    out, cur = [], ""
    for p in paragraphs:
        p = " ".join(p.split())
        if cur and len(cur) + len(p) + 1 > MAX_CHARS:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        out.append(cur)
    return out


def build(ep_path, cfg):
    ep = json.load(open(ep_path, encoding="utf-8"))
    date = ep["date"]
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out_mp3 = os.path.join(AUDIO_DIR, f"{date}.mp3")
    tmp = tempfile.mkdtemp()
    parts = []

    def add(path):
        parts.append(path)

    a = cfg["audio"]
    j = os.path.join(ROOT, "assets")
    for name in ("intro", "transition", "outro"):
        to_wav(os.path.join(j, f"jingle_{name}.mp3"), os.path.join(tmp, f"j_{name}.wav"))
    silence(a["pause_between_paragraphs_ms"], os.path.join(tmp, "gap.wav"))
    silence(900, os.path.join(tmp, "gap_long.wav"))

    add(os.path.join(tmp, "j_intro.wav"))
    n = 0
    for ci, ch in enumerate(ep["chapters"]):
        if ci > 0:
            add(os.path.join(tmp, "j_transition.wav"))
        for block in chunks(ch["paragraphs"]):
            n += 1
            raw = os.path.join(tmp, f"tts_{n:03d}.audio")
            print(f"  synthèse {n} ({len(block)} caractères) — {ch['title']}", flush=True)
            synthesize(block, cfg, raw)
            wav = os.path.join(tmp, f"tts_{n:03d}.wav")
            to_wav(raw, wav)
            add(wav)
            add(os.path.join(tmp, "gap.wav"))
    add(os.path.join(tmp, "gap_long.wav"))
    add(os.path.join(tmp, "j_outro.wav"))

    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    joined = os.path.join(tmp, "joined.wav")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
    run(["ffmpeg", "-y", "-i", joined, "-af", f"loudnorm=I={a['target_lufs']}:TP=-1.5:LRA=11",
         "-ar", "44100", "-ac", "2", "-b:a", a["bitrate"],
         "-metadata", f"title={ep['title']}", "-metadata", f"artist={cfg['show']['author']}", out_mp3])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Épisode prêt : {out_mp3}")


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "config.yml"), encoding="utf-8"))
    eps = sorted(glob.glob(os.path.join(ROOT, "episodes", "*.json")))
    if len(sys.argv) > 1:
        todo = [os.path.join(ROOT, "episodes", f"{d}.json") for d in sys.argv[1:]]
    else:
        todo = [e for e in eps if not os.path.exists(
            os.path.join(AUDIO_DIR, os.path.basename(e).replace(".json", ".mp3")))]
    failed = False
    for e in todo:
        print(f"Fabrication de {os.path.basename(e)}")
        try:
            build(e, cfg)
        except Exception as exc:  # message visible dans le résumé du run
            print(f"::error title=Échec de {os.path.basename(e)}::{exc}", flush=True)
            failed = True
    write_feed(cfg, ROOT)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
