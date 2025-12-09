from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")  # tu gardes ta clé Grok

last_used = {}

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

async def ask_grok(text: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "Ka amsa a harshen Hausa na Kano da kyau, a takaice, da ladabi."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.7
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return "Na ji tambayarka, za mu ba ka amsa nan take."

@app.get("/webhook")
async def verify(r: Request):
    if r.query_params.get("hub.verify_token") == "lafiyabot123":
        return int(r.query_params.get("hub.challenge"))
    return "Wrong token", 403

@app.post("/webhook")
async def receive(r: Request):
    data = await r.json()
    print("Message →", data)
    try:
        for msg in data.get("entry",[{}])[0].get("changes",[{}])[0].get("value",{}).get("messages",[]):
            sender = msg["from"]
            text = msg["text"]["body"]
            if sender in last_used and time.time() - last_used[sender] < 30: continue
            last_used[sender] = time.time()

            reply = await ask_grok(text)
            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "text",
                    "text": {"body": reply + DISCLAIMER}
                }
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
