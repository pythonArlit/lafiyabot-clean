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

# Liste des pharmacies (tu peux ajouter 100 lignes, c’est tout simple)
PHARMACIES = [
    {"ville": "niamey", "quartier": "Plateau",      "nom": "Pharmacie du Plateau",     "tel": "+227 90 12 34 56", "distance": 2},
    {"ville": "niamey", "quartier": "Lazaret",      "nom": "Pharmacie Lazaret",         "tel": "+227 96 55 44 33", "distance": 1.5},
    {"ville": "niamey", "quartier": "Karo",         "nom": "Pharmacie Karo",           "tel": "+227 90 99 88 77", "distance": 1.2},
    {"ville": "kano",   "quartier": "Sabon Gari",   "nom": "Alheri Pharmacy",          "tel": "+234 803 123 4567", "distance": 1},
    {"ville": "kano",   "quartier": "Kofar Mata",   "nom": "Kofar Pharmacy",           "tel": "+234 801 234 5678", "distance": 2.5},
    # Ajoute toutes tes pharmacies ici
]

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

WELCOME_MENU = """Sannu ! Bienvenue ! Welcome !

1 Tapez *1* pour Français
2 Type *2* for English
3 Danna *3* dan Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

def trouver_pharmacies(ville: str = None) -> str:
    ville = ville.lower() if ville else ""
    resultats = [p for p in PHARMACIES if ville in p["ville"]]
    if not resultats:
        return "Ba mu da bayani na garuruwa na wannan birni ba a yanzu."

    resultats.sort(key=lambda x: x["distance"])
    langue = user_language.get(sender, "fr")

    if langue == "fr":
        msg = "Pharmacies de garde les plus proches :\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  {p['tel']} ({p['distance']} km)\n\n"
    elif langue == "en":
        msg = "Nearest on-duty pharmacies:\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  {p['tel']} ({p['distance']} km away)\n\n"
    else:
        msg = "Magungunan gadi mafi kusa :\n\n"
        for p in resultats[:5]:
            msg += f"• {p['nom']} ({p['quartier']})\n  {p['tel']} (km {p['distance']})\n\n"
    return msg

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
    try:
        for msg in data.get("entry",[{}])[0].get("changes",[{}])[0].get("value",{}).get("messages",[]):
            sender = msg["from"]
            text = msg["text"]["body"].strip().lower()

            if sender not in last_used:
                last_used[sender] = 0
            if time.time() - last_used[sender] < 25:
                continue
            last_used[sender] = time.time()

            # Menu & changement de langue
            if text in ["menu","langue","change","1","2","3"]:
                if text in ["1","fr","français"]: user_language[sender] = "fr"; reply = "1 Parfait ! Français activé"
                elif text in ["2","en","english"]: user_language[sender] = "en"; reply = "2 Perfect! English activated"
                elif text in ["3","ha","hausa"]: user_language[sender] = "ha"; reply = "3 Sannu! Hausa na Kano activé"
                else: reply = WELCOME_MENU
            # Pharmacies de garde
            elif any(m in text for m in ["pharmacie","garde","pharmacy","duty"]):
                ville = next((v for v in ["niamey","kano","zinder","maradi"] if v in text), None)
                reply = trouver_pharmacies(ville)
            else:
                if sender not in user_language: reply = WELCOME_MENU
                else: reply = await ask_grok(msg["text"]["body"])

            reply += DISCLAIMER

            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply}}
            )
    except Exception as e:
        print("Erreur:",e)
    return {"status":"ok"}
