from fastapi import FastAPI, Request
import httpx
import time
import base64

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}
DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

async def google_voice_hausa(text: str) -> str | None:
    try:
        payload = {
            "input": {"text": text},
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
            return "Na ji tambayarka, za mu ba ka bayani nan take."

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
            voice_url = await google_voice_hausa(reply)

            # 1. Vocal (priorité)
            if voice_url:
                httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                    json={"messaging_product":"whatsapp","to":sender,"type":"audio","audio":{"link":voice_url}}
                )

            # 2. Texte
            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply+DISCLAIMER}}
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
