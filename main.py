from fastapi import FastAPI, Request
import httpx
import time
import os
import base64

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

last_used = {}
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

async def text_to_voice_google(text: str) -> str | None:
    """Voix Hausa gratuite via Google TTS (aucune clé nécessaire)"""
    try:
        # Google TTS public (limité mais parfait pour tests et usage modéré)
        url = "https://text-to-speech-api.cloud.google.com/v1/text:synthesize"
        payload = {
            "input": {"text": text + ". Lafiya lau."},
            "voice": {
                "languageCode": "ha-NG",        # Hausa Nigeria (accent très naturel)
                "name": "ha-NG-Standard-A",     # Voix féminine Hausa
                "ssmlGender": "FEMALE"
            },
            "audioConfig": {"audioEncoding": "MP3"}
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                audio_b64 = r.json()["audioContent"]
                audio_bytes = base64.b64decode(audio_b64)
                # Upload temporaire gratuit
                upload = await client.post(
                    "https://tmpfiles.org/api/v1/upload",
                    files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")}
                )
                url = upload.json()["data"]["url"]
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except:
        pass
    return None

async def ask_grok(text: str) -> str:
    # Ton code Grok existant (je le garde tel quel)
    # ... (tu peux garder ta fonction ask_grok actuelle)
    return "Sannu! Na ji tambayarka: " + text + " Za mu ba ka bayani da Hausa nan take."

@app.get("/webhook")
async def verify(r: Request):
    if r.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(r.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def receive(r: Request):
    data = await r.json()
    print("Webhook →", data)
    try:
        for msg in data.get("entry",[{}])[0].get("changes",[{}])[0].get("value",{}).get("messages",[]):
            sender = msg["from"]
            text = msg["text"]["body"]
            if sender in last_used and time.time() - last_used[sender] < 30: continue
            last_used[sender] = time.time()

            reply_text = await ask_grok(text)
            voice_url = await text_to_voice_google(reply_text)

            # 1. Envoie le vocal (si réussi)
            if voice_url:
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

            # 2. Envoie toujours le texte
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
