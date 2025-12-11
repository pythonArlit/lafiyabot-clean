from fastapi import FastAPI, Request
import httpx
import time
import os

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}
user_language = {}

# ==================== PHARMACIES DE GARDE (modifie quand tu veux) ====================
PHARMACIES = [
    {"ville": "niamey", "quartier": "Plateau",    "nom": "Pharmacie du Plateau",     "tel": "+227 90 12 34 56", "distance": 2},
    {"ville": "niamey", "quartier": "Lazaret",    "nom": "Pharmacie Lazaret",        "tel": "+227 96 55 44 33", "distance": 1.5},
    {"ville": "niamey", "quartier": "Karo",       "nom": "Pharmacie Karo",           "tel": "+227 90 99 88 77", "distance": 1.2},
    {"ville": "kano",   "quartier": "Sabon Gari", "nom": "Alheri Pharmacy",          "tel": "+234 803 123 4567", "distance": 1},
    {"ville": "kano",   "quartier": "Kofar Mata", "nom": "Kofar Pharmacy",           "tel": "+234 801 234 5678", "distance": 2.5},
    {"ville": "zinder", "quartier": "Birni",      "nom": "Pharmacie Centrale",       "tel": "+227 92 11 22 33", "distance": 2.5},
    {"ville": "maradi", "quartier": "Centre",     "nom": "Pharmacie El Hadj",        "tel": "+227 91 00 11 22", "distance": 1},
    # Ajoute autant que tu veux ici
]

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Type *2* for English
🇳🇬 Danna *3* dan Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

# Recherche pharmacie de garde
def trouver_pharmacies(ville: str = "niamey") -> str:
    ville = ville.lower()
    resultats = [p for p in PHARMACIES if ville in p["ville"]]
    if not resultats:
        return "Ba mu da bayani na garuruwa na wannan birni ba a yanzu."

    resultats.sort(key=lambda x: x["distance"])
    langue = user_language.get(sender, "fr")

    if langue == "fr":
        msg = "Pharmacies de garde les plus proches :\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']} ({p['distance']} km)\n\n"
    elif langue == "en":
        msg = "Nearest on-duty pharmacies:\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']} ({p['distance']} km away)\n\n"
    else:
        msg = "Magungunan gadi mafi kusa :\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  📞 {p['tel']} (km {p['distance']})\n\n"
    return msg

# Réponse Grok
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
            global sender
            sender = msg["from"]
            text = msg["text"]["body"].strip().lower()

            # Anti-spam
            now = time.time()
            if sender not in last_used: last_used[sender] = 0
            if now - last_used[sender] < 25: continue
            last_used[sender] = now

            # === PHARMACIE DE GARDE EN PRIORITÉ (même avant choix langue) ===
            if any(m in text for m in ["pharmacie","garde","pharmacy","duty","ouverte","buɗe"]):
                ville = next((v for v in ["niamey","kano","zinder","maradi"] if v in text), "niamey")
                reply = trouver_pharmacies(ville)
                if sender not in user_language: user_language[sender] = "fr"

            # === CHOIX / CHANGEMENT DE LANGUE ===
            elif text in ["1","fr","français","francais"]:
                user_language[sender] = "fr"
                reply = "🇫🇷 Parfait ! Je parle maintenant en français."
            elif text in ["2","en","english","anglais"]:
                user_language[sender] = "en"
                reply = "🇬🇧 Perfect! I will now speak in English."
            elif text in ["3","ha","hausa"]:
                user_language[sender] = "ha"
                reply = "🇳🇬 Sannu! Yanzu zan yi magana da Hausa na Kano."
            elif text in ["menu","langue","change"]:
                reply = WELCOME_MENU

            # === PREMIER MESSAGE OU PAS DE LANGUE ===
            elif sender not in user_language or user_language[sender] is None:
                reply = WELCOME_MENU

            # === RÉPONSE NORMALE ===
            else:
                reply = await ask_grok(msg["text"]["body"])

            reply += DISCLAIMER

            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply}}
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
