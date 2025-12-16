from fastapi import FastAPI, Request
import httpx
import time
import os
from datetime import datetime, timedelta

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")

last_used = {}
user_language = {}

# Stockage du suivi des règles (numéro WhatsApp → données)
suivi_regles = {}

DISCLAIMER = "\n\nLafiyaBot ba likita ba ne · Bayani ne kawai · Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"

WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* pour English
🇳🇬 Tapez *3* pour Hausa

4 → Pharmacies de garde
5 → Suivi de mes règles

(ou tapez 1, 2, 3, 4, 5 à tout moment)"""

# Calcul du cycle (28 jours par défaut)
def calculer_cycle(derniere_date: str) -> dict:
    try:
        derniere = datetime.strptime(derniere_date, "%Y-%m-%d")
        aujourd_hui = datetime.now()
        jours_ecoules = (aujourd_hui - derniere).days
        cycle_moyen = 28
        prochain = cycle_moyen - (jours_ecoules % cycle_moyen)
        fertile = "OUI" if 10 <= (jours_ecoules % cycle_moyen) <= 16 else "NON"
        retard = "OUI" if jours_ecoules > cycle_moyen else "NON"
        return {
            "jours": jours_ecoules,
            "prochain": prochain,
            "fertile": fertile,
            "retard": retard
        }
    except:
        return None

async def ask_grok(text: str, langue: str = "ha") -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            r = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={"model":"grok-3","messages":[
                    {"role":"system","content":f"Réponds en {langue} clair et poli."},
                    {"role":"user","content":text}
                ],"temperature":0.7}
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return {"fr":"Je n’ai pas pu répondre.", "en":"I couldn’t answer.", "ha":"Na kasa amsawa."}.get(langue, "Na kasa amsawa.")

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

            now = time.time()
            if sender not in last_used: last_used[sender] = 0
            if now - last_used[sender] < 25: continue
            last_used[sender] = now

            text_lower = text.lower()

            # === CHOIX DE LANGUE ===
            if text_lower in ["1","fr","français","francais"]:
                user_language[sender] = "fr"
                reply = "🇫🇷 Français activé ! Comment puis-je vous aider ?"
            elif text_lower in ["2","en","english","anglais"]:
                user_language[sender] = "en"
                reply = "🇬🇧 English activated! How can I help you?"
            elif text_lower in ["3","ha","hausa"]:
                user_language[sender] = "ha"
                reply = "🇳🇬 Sannu! Yanzu zan yi magana da Hausa na Kano."
            # === PHARMACIES DE GARDE (exemple simple) ===
            elif "pharmacie" in text_lower and "garde" in text_lower:
                reply = "Pharmacies de garde les plus proches :\n• Pharmacie du Plateau (Niamey) +227 90 12 34 56\n• Alheri Pharmacy (Kano) +234 803 123 4567"
            # === SUIVI DES RÈGLES ===
            elif any(m in text_lower for m in ["règle","règles","cycle","retard","ovulation","grossesse","période","mens"]):
                if sender not in suivi_regles or "date" in text_lower:
                    reply = {"fr": "À quelle date as-tu eu tes dernières règles ? (ex: 5 décembre 2025)",
                             "en": "When was your last period? (ex: 5 December 2025)",
                             "ha": "A wace rana ka samu haila na ƙarshe? (misali: 5 Disamba 2025)"}.get(user_language.get(sender,"fr"),"À quelle date ?")
                    suivi_regles[sender] = {"attente_date": True}
                elif suivi_regles.get(sender, {}).get("attente_date"):
                    suivi_regles[sender] = {"derniere_regle": text.strip(), "attente_date": False}
                    reply = {"fr": "Parfait ! Je suis ton cycle maintenant. Tape « règles » pour voir ton statut.",
                             "en": "Perfect! I’m tracking your cycle. Type « period » anytime.",
                             "ha": "Na gode! Yanzu ina bin diddigin haila. Rubuta « règles » don ganin halin ki."}.get(user_language.get(sender,"fr"))
                else:
                    info = calculer_cycle(suivi_regles[sender]["derniere_regle"])
                    if not info:
                        reply = "Date invalide. Envoie-moi la date de tes dernières règles."
                    else:
                        langue = user_language.get(sender, "fr")
                        if langue == "fr":
                            reply = f"Tu es au jour {info['jours']} du cycle.\nProchaines règles dans {info['prochain']} jours.\nPériode fertile : {info['fertile']}\nRetard : {info['retard']}"
                        elif langue == "en":
                            reply = f"Day {info['jours']} of your cycle.\nNext period in {info['prochain']} days.\nFertile period: {info['fertile']}\nDelay: {info['retard']}"
                        else:
                            reply = f"Ke a rana {info['jours']} na cycle.\nHaila na gaba a cikin kwana {info['prochain']}.\nLokacin haihuwa: {info['fertile']}\nJinkiri: {info['retard']}"
            # === MENU OU PREMIER MESSAGE ===
            elif sender not in user_language or text_lower in ["menu","langue","change"]:
                reply = WELCOME_MENU
            # === RÉPONSE NORMALE ===
            else:
                reply = await ask_grok(text, user_language.get(sender, "ha"))

            reply += DISCLAIMER

            httpx.post(f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"messaging_product":"whatsapp","to":sender,"type":"text","text":{"body":reply}}
            )
    except Exception as e:
        print("Erreur:", e)
    return {"status":"ok"}
