from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")
ELEVEN_KEY = os.getenv("ELEVEN_KEY")

last_used = {}
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

async def text_to_voice_hausa(text: str) -> str | None:
    """Transforme le texte en vocal Hausa (ElevenLabs v3 2025)"""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Voix Hausa femme naturelle (ID officiel ElevenLabs 2025 pour Hausa)
            r = await client.post(
                "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM/stream",
                headers={
                    "xi-api-key": ELEVEN_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text + ". Lafiya lau.",
                    "model_id": "eleven_multilingual_v3",  # Modèle 2025 pour Hausa
                    "voice_settings": {
                        "stability": 0.7,
                        "similarity_boost": 0.9
                    }
                },
                stream=True
            )
            if r.status_code == 200:
                # Upload audio temporaire (stable, expire en 7 jours)
                audio_content = await r.aread()
                upload = await client.post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": ("audio.mp3", audio_content, "audio/mpeg")}
                )
                url = upload.json()["data"]["url"]
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        except Exception as e:
            print(f"Erreur TTS: {e}")
            return None
    return None

async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "Ka amsa a harshen Hausa na Kano da kyau da takaice."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.7
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return "Na ji tambayarka, amma na sami matsala a sadarwa."

@app.get("/webhook")
async def verify(r: Request):
    if r.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(r.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def receive(r: Request):
    data = await r.json()
    print("Webhook reçu →", data)
    try:
        for msg in data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", []):
            sender = msg["from"]
            text = msg["text"]["body"]
            now = time.time()
            if sender in last_used and now - last_used[sender] < 30:
                continue
            last_used[sender] = now
            reply_text = await ask_grok(text)
            voice_url = await text_to_voice_hausa(reply_text)
            if voice_url:
                # Envoie d'abord le vocal
                httpx.post(
                    f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": sender,
                        "type": "audio",
                        "audio": {"link": voice_url}
                    }
                )
            # Envoie le texte ensuite
            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "text",
                    "text": {"body": reply_text + DISCLAIMER}
                }
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status": "ok"}
