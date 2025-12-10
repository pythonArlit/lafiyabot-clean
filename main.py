from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}

# Disclaimer par langue
DISCLAIMER = {
    "hausa": "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE",
    "french": "\n\nLafiyaBot n’est pas un médecin · Information générale uniquement · Consultez un médecin en cas de douleur grave",
    "english": "\n\nLafiyaBot is not a doctor · General information only · See a doctor if you have severe pain"
}

# Détection automatique de la langue (très précis)
def detect_language(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["sannu","ina kwana","lafiya","yaya","menene","ciwon","maganin","asibiti","garde","pharmacie"]):
        return "hausa"
    elif any(w in t for w in ["bonjour","salut","santé","docteur","maladie","pharmacie","comment","merci","svp"]):
        return "french"
    else:
        return "english"

# Prompts par langue
PROMPTS = {
    "hausa": "Ka amsa a harshen Hausa na Kano da kyau, a takaice, da ladabi. Ka yi amfani da kalmomi masu sauƙi.",
    "french": "Réponds en français clair, poli et simple. Utilise un ton rassurant.",
    "english": "Answer in clear, polite and simple English. Use a reassuring tone."
}

# Message d’accueil multilingue
WELCOME = {
    "hausa": "Sannu da zuwa! 😊\nNa LafiyaBot ne — mataimaki na lafiya a Hausa, Français da English.\nZa ka iya tambaya game da ciwon suga, zazzabi, haihuwa, rigakafi…\nZa mu amsa nan take!",
    "french": "Bonjour et bienvenue ! 😊\nJe suis LafiyaBot, votre assistant santé en français, anglais et hausa.\nPosez-moi toutes vos questions sur le diabète, paludisme, grossesse…\nJe réponds tout de suite !",
    "english": "Hello and welcome! 😊\nI am LafiyaBot, your health assistant in Hausa, French & English.\nAsk me anything about diabetes, malaria, pregnancy…\nI answer instantly!"
}

async def ask_grok(text: str) -> str:
    langue = detect_language(text)
    system = PROMPTS[langue]

    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 350
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            fallback = {
                "hausa": "Na ji tambayarka, za mu ba ka amsa nan take.",
                "french": "J’ai bien reçu votre question, je vous réponds tout de suite.",
                "english": "I received your question, answering right away."
            }
            return fallback[langue]

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
            text = msg["text"]["body"].strip()

            # Anti-spam 30 secondes
            now = time.time()
            if sender in last_used and now - last_used[sender] < 30:
                continue
            last_used[sender] = now

            langue = detect_language(text)

            # Message d’accueil automatique
            if text.lower() in ["sannu","hello","bonjour","salut","hi","menu"]:
                reply = WELCOME[langue]
            else:
                reply = await ask_grok(text)

            reply += DISCLAIMER[langue]

            httpx.post(
                f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "text",
                    "text": {"body": reply}
                }
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
