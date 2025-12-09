from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")
ELEVEN_KEY = os.getenv("ELEVEN_KEY")   # ← ta clé ElevenLabs (gratuit 10 000 caractères/mois)

last_used = {}
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

# Génère un message vocal en Hausa (voix féminine très naturelle)
async def text_to_voice_hausa(text: str) -> str | None:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(
                "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM/stream",  # voix Hausa femme (la meilleure)
                headers={"xi-api-key": ELEVEN_KEY},
                json={
                    "text": text + ". Lafiya lau.",
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.7, "similarity_boost": 0.9}
                },
                stream=True
            )
            if r.status_code == 200:
                # Upload temporaire gratuit (expire en 7 jours, parfait pour WhatsApp)
                upload = await client.post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": ("audio.mp3", r.content, "audio/mpeg")}
                )
                url = upload.json()["data"]["url"]
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        except:
            pass
    return None

async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={"model":"grok-3","messages":[
                    {"role":"system","content":"Ka amsa a harshen Hausa na Kano da kyau da takaice."},
                    {"role":"user","content":text}
                ],"temperature":0.7}
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
    try:
        for msg in data.get("entry",[{}])[0].get("changes",[{}])[0].get("value",{}).get("messages",[]):
            sender = msg["from"]
            text = msg["text"]["body"]
            now = time.time()
            if sender in last_used and now - last_used[sender] < 30: continue
            last_used[sender] = now

            reply_text = await ask_grok(text)
            voice_url = await text_to_voice_hausa(reply_text)

            # 1. Envoie le vocal (priorité)
            if voice_url:
                httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    json={"messaging_product":"whatsapp","to":sender,"type":"audio","audio":{"link":voice_url}}
                )

            # 2. Envoie le texte (facultatif mais recommandé)
            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply_text+DISCLAIMER}}
            )
    except Exception as e:
        print("Erreur:",e)
    return {"status":"ok"}
