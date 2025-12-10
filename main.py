from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

# Mémoire de la langue de chaque utilisateur (WhatsApp ID → langue)
user_language = {}

# Disclaimer par langue
DISCLAIMER = {
    "fr": "\n\nLafiyaBot n’est pas un médecin · Information générale uniquement · Consultez un médecin en cas de douleur grave.",
    "en": "\n\nLafiyaBot is not a doctor · General information only · See a doctor if you have severe pain.",
    "ha": "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"
}

# Prompts Grok par langue
PROMPTS = {
    "fr": "Réponds en français clair, poli et simple. Utilise un ton rassurant.",
    "en": "Answer in clear, polite and simple English. Use a reassuring tone.",
    "ha": "Ka amsa a harshen Hausa na Kano da kyau, a takaice, da ladabi."
}

# Menu de bienvenue
WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

Choisissez votre langue / Zaɓi harshenku / Choose your language:

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* pour English
🇳🇪 Tapez *3* pour Hausa

(ou tapez 1, 2, 3 à tout moment pour changer de langue)"""

# Fonction Grok
async def ask_grok(text: str, langue: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": PROMPTS[langue]},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 350
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print("Erreur Grok:", e)
            return {"fr": "Je n’ai pas pu répondre.", "en": "I couldn’t answer.", "ha": "Na kasa amsawa."}[langue]

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
            text = msg["text"]["body"].strip().lower()

            # Anti-spam 25 secondes
            now = time.time()
            if sender in last_used and now - last_used[sender] < 25:
                continue
            last_used[sender] = now

            # === CHANGEMENT DE LANGUE À TOUT MOMENT ===
            if text in ["1", "fr", "français", "francais", "french"]:
                user_language[sender] = "fr"
                reply = "Parfait ! 😊 Je parle maintenant en français.\nComment puis-je vous aider ?"
            elif text in ["2", "en", "english", "anglais"]:
                user_language[sender] = "en"
                reply = "Perfect! 😊 I will now speak in English.\nHow can I help you?"
            elif text in ["3", "ha", "hausa"]:
                user_language[sender] = "ha"
                reply = "Sannu! 😊 Yanzu zan yi magana da Hausa na Kano.\nMenene zan iya taimaka maka?"
            elif text in ["menu", "langue", "language", "change", "changer", "change language"]:
                user_language[sender] = None
                reply = WELCOME_MENU
            else:
                # Premier contact → menu
                if sender not in user_language or user_language[sender] is None:
                    user_language[sender] = None
                    reply = WELCOME_MENU
                else:
                    # Réponse normale dans la langue choisie
                    langue = user_language[sender]
                    reply = await ask_grok(msg["text"]["body"], langue)

            # Ajoute le disclaimer
            langue_actuelle = user_language.get(sender, "en")
            reply += DISCLAIMER.get(langue_actuelle, DISCLAIMER["en"])

            # Envoi réponse
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
    return {"status": "ok"}
