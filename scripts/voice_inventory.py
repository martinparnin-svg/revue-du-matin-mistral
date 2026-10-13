"""Inventaire complet des voix et modèles de synthèse Mistral disponibles sur le compte.
Écrit docs/samples/inventory.json et fabrique, pour comparaison, quelques extraits de voix
non françaises lisant le texte français (Voxtral sait parler une autre langue que celle de la voix).
"""
import json
import os
import subprocess
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
import mistral_api as m  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "samples")
os.makedirs(OUT, exist_ok=True)
H = m._headers()
API = m.API
inv = {}

# 1. Modèles
r = requests.get(f"{API}/v1/models", headers=H, timeout=60)
ids = [x.get("id") for x in r.json().get("data", [])] if r.status_code == 200 else []
inv["models_audio"] = sorted(i for i in ids if any(k in i.lower() for k in ("tts", "voxtral", "speech", "audio")))
print("Modèles audio :", inv["models_audio"])


# 2. Voix : toutes les listes possibles (v2 preset / all, v1 preset / all)
def v2(params):
    out, token = [], None
    while True:
        p = dict(params, page_size=100)
        if token:
            p["page_token"] = token
        rr = requests.get(f"{API}/v2/audio/voices", headers=H, params=p, timeout=60)
        if rr.status_code != 200:
            return {"error": m._short(rr)}
        page = rr.json().get("result", rr.json())
        out += page.get("data") or []
        token = page.get("next_page_token")
        if not token:
            return out


def v1(params):
    out, off = [], 0
    while True:
        rr = requests.get(f"{API}/v1/audio/voices", headers=H, params=dict(params, limit=100, offset=off), timeout=60)
        if rr.status_code != 200:
            return {"error": m._short(rr)}
        j = rr.json()
        items = j.get("items") or []
        out += items
        if not items or len(out) >= j.get("total", 0):
            return out
        off += len(items)


lists = {"v2_preset": v2({"type": "preset"}), "v2_all": v2({"type": "all"}),
         "v1_preset": v1({"type": "preset"}), "v1_all": v1({"type": "all"})}
allv = {}
for k, lst in lists.items():
    if isinstance(lst, dict):
        inv[k] = lst
        print(k, lst)
        continue
    inv[k + "_count"] = len(lst)
    for v in lst:
        allv[v["id"]] = {f: v.get(f) for f in ("id", "name", "slug", "gender", "age", "languages", "tags", "type", "kind")}
inv["voices"] = sorted(allv.values(), key=lambda v: (str(v.get("languages")), v.get("name") or ""))
langs = {}
for v in inv["voices"]:
    for l in v.get("languages") or ["?"]:
        langs.setdefault(l, []).append(v["name"])
inv["by_language"] = langs
print(f"{len(allv)} voix distinctes")
for l, names in sorted(langs.items()):
    print(f"  {l} : {len(names)} — {', '.join(names)}")

# 3. Extraits de voix non françaises lisant le texte français (une par locuteur, de préférence « neutral »)
TEXT = ("Bonjour, nous sommes le mardi 13 octobre, et voici votre revue du matin. "
        "Au sommaire : l'accord pétrolier entre Washington et Moscou, le budget 2027 qui arrive à l'Assemblée, "
        "et le premier grand modèle d'intelligence artificielle de Meta. C'est parti.")
model = m.tts_model("auto")
speakers = {}
for v in inv["voices"]:
    if m.is_french(v):
        continue
    base = (v.get("name") or "").split(" - ")[0]
    if base not in speakers or "neutral" in (v.get("slug") or "").lower():
        speakers[base] = v
inv["cross_samples"] = []
for base, v in list(speakers.items())[:12]:
    fname = "x_" + "".join(c if c.isalnum() else "_" for c in (v.get("slug") or base)) + ".mp3"
    try:
        audio = m.speech(TEXT, v["id"], model, "mp3")
    except m.MistralError as e:
        print("échec", base, e)
        continue
    raw = os.path.join(OUT, "tmp.mp3")
    open(raw, "wb").write(audio)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5",
                    "-b:a", "96k", os.path.join(OUT, fname)], check=True)
    os.remove(raw)
    inv["cross_samples"].append({"name": v.get("name"), "gender": v.get("gender"),
                                 "languages": v.get("languages"), "file": fname})
    print("extrait", v.get("name"), v.get("gender"), v.get("languages"))

json.dump(inv, open(os.path.join(OUT, "inventory.json"), "w"), ensure_ascii=False, indent=1)
