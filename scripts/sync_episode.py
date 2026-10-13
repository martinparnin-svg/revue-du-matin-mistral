"""Récupère le script du jour (ou d'une date donnée) dans le dépôt principal de la Revue du matin.

Usage : python scripts/sync_episode.py            (date du jour, heure de Paris)
        python scripts/sync_episode.py 2026-10-13
Sort sans erreur si le script n'existe pas encore.
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = yaml.safe_load(open(os.path.join(ROOT, "config.yml"), encoding="utf-8"))
date = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
dest = os.path.join(ROOT, "episodes", f"{date}.json")
url = f"https://raw.githubusercontent.com/{cfg['show']['source_repo']}/main/episodes/{date}.json"

r = requests.get(url, timeout=60)
if r.status_code != 200:
    print(f"Pas encore de script pour le {date} dans le dépôt principal (HTTP {r.status_code}).")
    sys.exit(0)
ep = r.json()
ep["title"] = ep.get("title", f"Revue du matin · {date}") + " (Mistral)"
json.dump(ep, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"Script du {date} récupéré : {len(ep.get('chapters', []))} chapitres.")
