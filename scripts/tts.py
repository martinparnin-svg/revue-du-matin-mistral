"""Synthèse vocale interchangeable.

Chaque service expose la même fonction : synthesize(text, cfg, out_path) -> écrit un fichier audio.
Pour changer de voix, modifier `voice.provider` dans config.yml et ajouter la clé
correspondante dans les secrets GitHub (GEMINI_API_KEY, ELEVENLABS_API_KEY ou GOOGLE_TTS_API_KEY).
"""
import base64
import json
import os
import time

import requests


class TTSError(RuntimeError):
    pass


def _short(text):
    """Message d'erreur lisible sur une ligne (jamais la clé, qui n'est pas dans la réponse)."""
    try:
        err = json.loads(text).get("error", {})
        return f"{err.get('status', '')} {err.get('message', '')}".strip()[:400] or text[:400]
    except Exception:
        return " ".join(text.split())[:400]


def _post_with_retry(url, headers, body, tries=5, wait=20):
    last = None
    for attempt in range(tries):
        try:
            r = requests.post(url, headers=headers, data=json.dumps(body), timeout=300)
        except requests.RequestException as e:
            last = f"réseau : {e}"
            print(f"::warning title=Synthèse vocale::essai {attempt + 1} : {last}", flush=True)
            time.sleep(wait)
            continue
        if r.status_code == 200:
            return r
        last = f"HTTP {r.status_code} {_short(r.text)}"
        print(f"::warning title=Synthèse vocale::essai {attempt + 1} : {last}", flush=True)
        if r.status_code in (429, 500, 502, 503, 504):
            if r.status_code == 429 and "per day" in r.text.lower():
                break  # quota quotidien épuisé : inutile d'insister
            delay = r.headers.get("Retry-After")
            time.sleep(int(delay) if delay and delay.isdigit() else wait * (attempt + 1))
            continue
        break
    raise TTSError(last)


# --- Gemini TTS -------------------------------------------------------------

def gemini(text, cfg, out_path):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise TTSError("Secret GEMINI_API_KEY absent")
    g = cfg["voice"]["gemini"]
    content = {"type": "text", "text": text}
    if g.get("style"):
        content["annotations"] = [{"type": "speech_metadata", "style": g["style"]}]
    body = {
        "model": g["model"],
        "input": [{"type": "user_input", "content": [content]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": g["voice"]}]},
    }
    r = _post_with_retry(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        {"x-goog-api-key": key, "Content-Type": "application/json"},
        body,
    )
    data = r.json()
    audio = None
    for step in data.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for c in step.get("content", []):
            if c.get("type") == "audio" and c.get("data"):
                audio = c["data"]
    if not audio:
        raise TTSError("Réponse Gemini sans audio : " + json.dumps(data)[:500])
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(audio))
    time.sleep(g.get("pause_between_calls_s", 0))
    return out_path


# --- ElevenLabs -------------------------------------------------------------

def elevenlabs(text, cfg, out_path):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise TTSError("Secret ELEVENLABS_API_KEY absent")
    e = cfg["voice"]["elevenlabs"]
    r = _post_with_retry(
        f"https://api.elevenlabs.io/v1/text-to-speech/{e['voice_id']}?output_format=mp3_44100_128",
        {"xi-api-key": key, "Content-Type": "application/json"},
        {"text": text, "model_id": e["model"], "language_code": "fr"},
    )
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


# --- Google Cloud TTS (Chirp 3 HD) ------------------------------------------

def google_chirp(text, cfg, out_path):
    key = os.environ.get("GOOGLE_TTS_API_KEY")
    if not key:
        raise TTSError("Secret GOOGLE_TTS_API_KEY absent")
    v = cfg["voice"]["google_chirp"]["voice"]
    r = _post_with_retry(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
        {"Content-Type": "application/json"},
        {
            "input": {"text": text},
            "voice": {"languageCode": "fr-FR", "name": v},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
        },
    )
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(r.json()["audioContent"]))
    return out_path


# --- Mistral (Voxtral TTS) ---------------------------------------------------

_mistral_voice = {}


def mistral(text, cfg, out_path):
    import mistral_api as m
    c = cfg["voice"]["mistral"]
    model = m.tts_model(c.get("model", "auto"))
    voice = c.get("voice_id") or _mistral_voice.get("id")
    if not voice:
        fr = [v for v in m.list_voices() if m.is_french(v)]
        if not fr:
            raise TTSError("aucune voix française prédéfinie trouvée chez Mistral")
        _mistral_voice["id"] = voice = fr[0]["id"]
        print(f"Voix par défaut : {fr[0].get('name')} ({voice})", flush=True)
    last = None
    for attempt in range(5):
        try:
            audio = m.speech(text, voice, model, "mp3")
            with open(out_path, "wb") as f:
                f.write(audio)
            time.sleep(c.get("pause_between_calls_s", 0))
            return out_path
        except m.MistralError as e:
            last = str(e)
            print(f"::warning title=Synthèse vocale::essai {attempt + 1} : {last}", flush=True)
            if not any(code in last for code in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")):
                break
            time.sleep(15 * (attempt + 1))
    raise TTSError(last)


PROVIDERS = {"gemini": gemini, "elevenlabs": elevenlabs, "google_chirp": google_chirp, "mistral": mistral}


def synthesize(text, cfg, out_path):
    name = cfg["voice"]["provider"]
    if name not in PROVIDERS:
        raise TTSError(f"Service inconnu : {name}")
    return PROVIDERS[name](text, cfg, out_path)
