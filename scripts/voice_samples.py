"""Fabrique un extrait pour chaque voix française prédéfinie de Mistral.
Publie docs/samples/index.html (page d'écoute) et docs/samples/voices.json (liste des voix).
"""
import json
import os
import subprocess
import sys
from html import escape

sys.path.insert(0, os.path.dirname(__file__))
import mistral_api as m  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = ("Bonjour, nous sommes le mardi 13 octobre, et voici votre revue du matin. "
        "Au sommaire : l'accord pétrolier entre Washington et Moscou, le budget 2027 qui arrive à l'Assemblée, "
        "et le premier grand modèle d'intelligence artificielle de Meta. C'est parti.")
MAX_VOICES = 16

out_dir = os.path.join(ROOT, "docs", "samples")
os.makedirs(out_dir, exist_ok=True)

model = m.tts_model("auto")
print("Modèle retenu :", model)
voices = m.list_voices()
fr = [v for v in voices if m.is_french(v)]
print(f"{len(voices)} voix prédéfinies, dont {len(fr)} en français")
if not fr:
    print("::error title=Voix::aucune voix française trouvée ; voix disponibles : "
          + ", ".join(f"{v.get('name')} {v.get('languages')}" for v in voices[:20]))
    sys.exit(1)

rows, meta, errors = [], [], []
for v in fr[:MAX_VOICES]:
    vid, name = v["id"], v.get("name", v["id"])
    fname = "".join(ch if ch.isalnum() else "_" for ch in (v.get("slug") or name)).strip("_") + ".mp3"
    try:
        audio = m.speech(TEXT, vid, model, "mp3")
    except m.MistralError as e:
        errors.append(f"{name} : {e}")
        print(f"::warning title=Voix {name}::{e}")
        continue
    raw = os.path.join(out_dir, "tmp_" + fname)
    open(raw, "wb").write(audio)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5",
                    "-b:a", "96k", os.path.join(out_dir, fname)], check=True)
    os.remove(raw)
    info = " · ".join(x for x in [v.get("gender") or "", ", ".join(v.get("tags") or []),
                                  v.get("description") or ""] if x)
    meta.append({"id": vid, "name": name, "slug": v.get("slug"), "gender": v.get("gender"),
                 "languages": v.get("languages"), "tags": v.get("tags"), "file": fname})
    rows.append(f'<li><strong>{escape(name)}</strong> <span>{escape(info)}</span><br>'
                f'<audio controls preload="none" src="{fname}"></audio></li>')
    print("ok", name)

json.dump({"model": model, "voices": meta, "errors": errors}, open(os.path.join(out_dir, "voices.json"), "w"),
          ensure_ascii=False, indent=1)
html = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voix Mistral</title>
<style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 16px;line-height:1.5}}
li{{margin:0 0 1.3rem}}span{{color:#5a6776;font-size:.9em}}audio{{width:100%;margin-top:.3rem}}</style>
<h1>Voix françaises de Mistral</h1>
<p>Même texte que pour les voix Gemini, lu par {len(rows)} voix Voxtral (modèle {escape(model)}).</p>
<ul style="list-style:none;padding:0">{''.join(rows)}</ul>"""
open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(html)
if not rows:
    print("::error title=Voix::aucun extrait n'a pu être fabriqué : " + " | ".join(errors)[:900])
    sys.exit(1)
print(f"Extraits prêts : {len(rows)}")
