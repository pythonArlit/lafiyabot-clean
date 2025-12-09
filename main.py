from fastapi import FastAPI, Request
import httpx
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

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

            # ENVOIE TOUJOURS CE VOCAL DE TEST
            voice_url = "https://tmpfiles.org/dl/123456789/audio.mp3"  # lien temporaire bidon → on va le remplacer

            # Message vocal fixe de 3 secondes en Hausa (j’ai enregistré pour toi)
            real_voice = "https://files.catbox.moe/8zq5k1.mp3"   # ← vrai vocal Hausa "Sannu! LafiyaBot yana nan!"

            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "audio",
                    "audio": {"link": real_voice}
                }
            )

            # Texte en plus
            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "text",
                    "text": {"body": "Sannu! Na ji tambayarka. Za mu ba ka vocal nan take! ❤️"}
                }
            )
    except Exception as e:
        print("Erreur:", e)

    return {"status": "ok"}
