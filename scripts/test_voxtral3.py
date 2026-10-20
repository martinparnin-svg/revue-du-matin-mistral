"""Essai Voxtral 3 (20 octobre 2026) : les quatre voix françaises du nouveau modèle et les balises d'émotion.
Écrit docs/samples/v3/ : un MP3 par extrait, deux compilations (voix.mp3, emotions.mp3) et index.html.
"""
import json, os, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__))
import mistral_api as m  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "samples", "v3")
os.makedirs(OUT, exist_ok=True)
NEW = "voxtral-mini-tts-3"
OLD = "voxtral-mini-tts-2603"

PASSAGE = ("Les chiffres d'abord, donnés par le ministre de l'Intérieur Laurent Nuñez. Cinq cent cinquante mille "
           "manifestants samedi, quand on en attendait deux cent mille. Soixante mille policiers et gendarmes déployés. "
           "Deux mille quatre cents interpellations. Hier matin, le ministre a reconnu un manque d'anticipation et une "
           "perte de contrôle. Il a présenté sa démission. Emmanuel Macron l'a refusée.")
COURT = "L'Ukraine est frappée dans son système électrique avant l'hiver. Des millions de foyers sont privés de courant."
EMOTIONS = [("neutre", ""), ("grave", "[emotion=sad][pace=slow] "), ("enlevee", "[emotion=excited][emphasis=high] ")]

voices = {v.get("name"): v for v in m.list_voices() if m.is_french(v)}
pvc = {n: v for n, v in voices.items() if (v.get("kind") == "pvc")}
fr = [(n, pvc[n]["id"]) for n in ("Camille", "Lea", "Manon", "Marie") if n in pvc]
print("Voix françaises du nouveau modèle :", [n for n, _ in fr], flush=True)

log, parts_v, parts_e = [], [], []
tmp = tempfile.mkdtemp()


def save(name, text, voice_id, model):
    path = os.path.join(OUT, name + ".mp3")
    try:
        audio = m.speech(text, voice_id, model)
        open(path, "wb").write(audio)
        log.append({"fichier": name + ".mp3", "modele": model, "ok": True})
        print("ok", name, flush=True)
        time.sleep(1)
        return path
    except Exception as exc:
        log.append({"fichier": name + ".mp3", "modele": model, "ok": False, "erreur": str(exc)[:300]})
        print("::warning title=" + name + "::" + str(exc)[:300], flush=True)
        return None


for n, vid in fr:
    p = save(f"voix-{n.lower()}", f"Ici {n}. " + PASSAGE, vid, NEW)
    if p:
        parts_v.append(p)
p = save("ancienne-marie-enthousiaste", "Ici l'ancienne Marie enthousiaste. " + PASSAGE, "fr_marie_excited", OLD)
if p:
    parts_v.append(p)

for n, vid in fr:
    for label, tag in EMOTIONS:
        p = save(f"emotion-{n.lower()}-{label}", tag + COURT, vid, NEW)
        if p:
            parts_e.append(p)


def compile_(parts, out):
    if not parts:
        return
    sil = os.path.join(tmp, "sil.wav")
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1.2", sil], check=True, capture_output=True)
    lst = os.path.join(tmp, out + ".txt")
    with open(lst, "w") as f:
        for i, p in enumerate(parts):
            w = os.path.join(tmp, f"{out}{i}.wav")
            subprocess.run(["ffmpeg", "-y", "-i", p, "-ar", "44100", "-ac", "2", w], check=True, capture_output=True)
            f.write(f"file '{w}'\nfile '{sil}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-af", "loudnorm=I=-16:TP=-1.5",
                    "-b:a", "96k", os.path.join(OUT, out + ".mp3")], check=True, capture_output=True)


compile_(parts_v, "voix")
compile_(parts_e, "emotions")
json.dump(log, open(os.path.join(OUT, "journal.json"), "w"), ensure_ascii=False, indent=1)
rows = "".join(f'<li>{x["fichier"]} — {x["modele"]}<br><audio controls preload="none" src="{x["fichier"]}"></audio></li>'
               if x["ok"] else f'<li>{x["fichier"]} : échec ({x["erreur"]})</li>' for x in log)
open(os.path.join(OUT, "index.html"), "w").write(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Essai Voxtral 3</title><body style="font-family:system-ui;max-width:640px;margin:auto;padding:16px">'
    '<h1>Essai Voxtral 3</h1><p><a href="voix.mp3">Compilation des voix</a> · <a href="emotions.mp3">Compilation des émotions</a></p>'
    f'<ul>{rows}</ul>')
fails = [x for x in log if not x["ok"]]
print(f"{len(log) - len(fails)} extraits réussis, {len(fails)} échecs")
