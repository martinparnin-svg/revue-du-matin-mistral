"""Accès à l'API Mistral : modèles, voix, synthèse (Voxtral TTS)."""
import os

import requests

API = "https://api.mistral.ai"
_model_cache = {}


class MistralError(RuntimeError):
    pass


def _headers():
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise MistralError("Secret MISTRAL_API_KEY absent")
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def _short(r):
    try:
        j = r.json()
        msg = j.get("message") or j.get("detail") or j.get("error") or j
        return f"HTTP {r.status_code} {str(msg)[:400]}"
    except Exception:
        return f"HTTP {r.status_code} {' '.join(r.text.split())[:400]}"


def tts_model(configured="auto"):
    """Renvoie le modèle de synthèse : celui configuré, ou le plus récent modèle « tts » du compte."""
    if configured and configured != "auto":
        return configured
    if "auto" in _model_cache:
        return _model_cache["auto"]
    r = requests.get(f"{API}/v1/models", headers=_headers(), timeout=60)
    if r.status_code != 200:
        raise MistralError("liste des modèles : " + _short(r))
    ids = [m.get("id", "") for m in r.json().get("data", [])]
    tts = sorted([i for i in ids if "tts" in i.lower()], reverse=True)
    if not tts:
        raise MistralError("aucun modèle de synthèse vocale disponible sur ce compte (modèles : "
                           + ", ".join(ids[:15]) + ")")
    print(f"Modèles de synthèse disponibles : {', '.join(tts)}", flush=True)
    _model_cache["auto"] = tts[0]
    return tts[0]


def list_voices():
    """Liste les voix prédéfinies (API v2, repli sur v1)."""
    out = []
    r = requests.get(f"{API}/v2/audio/voices", headers=_headers(), timeout=60,
                     params={"type": "preset", "page_size": 100})
    if r.status_code == 200:
        j = r.json()
        page = j.get("result", j)
        out = page.get("data") or page.get("items") or []
        token = page.get("next_page_token")
        while token:
            r2 = requests.get(f"{API}/v2/audio/voices", headers=_headers(), timeout=60,
                              params={"type": "preset", "page_size": 100, "page_token": token})
            if r2.status_code != 200:
                break
            p2 = r2.json().get("result", r2.json())
            out += p2.get("data") or []
            token = p2.get("next_page_token")
    else:
        print(f"::warning title=Voix::API v2 indisponible ({_short(r)}), essai de l'API v1", flush=True)
        r = requests.get(f"{API}/v1/audio/voices", headers=_headers(), timeout=60,
                         params={"type": "preset", "limit": 100})
        if r.status_code != 200:
            raise MistralError("liste des voix : " + _short(r))
        out = r.json().get("items") or r.json().get("data") or []
    return out


def is_french(v):
    langs = [str(x).lower() for x in (v.get("languages") or [])]
    slug = (v.get("slug") or "").lower()
    return any(l.startswith("fr") for l in langs) or slug.startswith("fr_")


def speech(text, voice_id, model, fmt="mp3"):
    body = {"model": model, "input": text, "response_format": fmt}
    if voice_id:
        body["voice_id"] = voice_id
    r = requests.post(f"{API}/v1/audio/speech", headers=_headers(), json=body, timeout=300)
    if r.status_code != 200:
        raise MistralError("synthèse : " + _short(r))
    ctype = r.headers.get("content-type", "")
    if ctype.startswith("audio/") or ctype == "application/octet-stream":
        return r.content
    import base64
    data = r.json().get("audio_data")
    if not data:
        raise MistralError("réponse sans audio : " + r.text[:300])
    return base64.b64decode(data)
