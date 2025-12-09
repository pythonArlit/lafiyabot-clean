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

async def google_tts_hausa(text: str) -> str | None:
    try:
        payload = {
            "input": {"text": text + ". Lafiya lau."},
            "voice": {"languageCode": "ha-NG", "name": "ha-NG-Standard-A"},
            "audioConfig": {"audioEncoding": "MP3"}
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://texttospeech.googleapis.com/v1/text:synthesize?key=AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw",
                json=payload
            )
            if r.status_code == 200:
                audio_b64 = r.json()["audioContent"]
                audio_bytes = base64.b64decode(audio_b64)
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
    # Tu gardes ton Grok existant ou tu laisses cette version simple pour test
    return f"Sannu! Na ji tambayarka: \"{text}\". Za mu ba ka bayani da Hausa nan take."

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
            voice_url = await google_tts_hausa(reply_text)

            # Envoie le vocal (si réussi)
            if voice_url:
                httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    json={"messaging_product":"whatsapp","to":sender,"type":"audio","audio":{"link":voice_url}}
                )

            # Envoie le texte
            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply_text+DISCLAIMER}}
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
