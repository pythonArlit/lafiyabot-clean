from fastapi import FastAPI, Request
import httpx
import time
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI()

TOKEN = os.getenv("TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROK_KEY = os.getenv("GROK_KEY")
SHEET_ID = "1ABC123..."  # ← colle l'ID de ton Google Sheet (entre /d/ et /edit)

# Config Google Sheets (tu n'as pas besoin de clé – on utilise une méthode simple)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)  # Si tu as une clé, sinon on utilise public

last_used = {}
user_language = {}

DISCLAIMER = {
    "fr": "\n\nLafiyaBot n'est pas un médecin. Information générale uniquement. Consultez un médecin en cas de douleur grave.",
    "en": "\n\nLafiyaBot is not a doctor. General information only. See a doctor if you have severe pain.",
    "ha": "\n\nLafiyaBot ba likita ba ne. Bayani ne kawai. Idan kana jin ciwo mai tsanani, JE ASIBITI NAN TAKE"
}

PROMPTS = {
    "fr": "Réponds en français clair, poli et simple.",
    "en": "Answer in clear, polite and simple English.",
    "ha": "Ka amsa a harshen Hausa na Kano da kyau, a takaice."
}

WELCOME_MENU = """Sannu ! Bienvenue ! Welcome ! 😊

🇫🇷 Tapez *1* pour Français
🇬🇧 Tapez *2* pour English
🇳🇬 Tapez *3* pour Hausa

(ou tapez 1, 2, 3 à tout moment pour changer)"""

async def get_pharmacies_garde(ville: str = None) -> list:
    """Récupère la liste des pharmacies de garde depuis Google Sheet"""
    try:
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        
        # Filtre par ville si spécifiée
        if ville:
            data = [p for p in data if ville.lower() in p["Ville"].lower()]
        
        # Trie par distance (plus proche d'abord)
        data.sort(key=lambda x: int(x["Distance (km)"]))
        
        # Garde seulement les ouvertes
        ouvertes = [p for p in data if p["Ouverte ce soir ?"] == "OUI"]
        
        return ouvertes[:5]  # Top 5 les plus proches
    except:
        return []  # Fallback si Sheet HS

def format_pharmacies(ouvertes: list, langue: str) -> str:
    if not ouvertes:
        return {"fr": "Aucune pharmacie de garde trouvée. Essayez une autre ville.", "en": "No on-duty pharmacies found. Try another city.", "ha": "Ba a sami magunguna na gadi ba. Bugu da ƙari birni."}[langue]
    
    if langue == "fr":
        reply = "Pharmacies de garde les plus proches :\n\n"
        for p in ouvertes:
            reply += f"• {p['Nom Pharmacie']} ({p['Quartier']})\n  📞 {p['Téléphone']} (à {p['Distance (km)']} km)\n\n"
    elif langue == "en":
        reply = "Nearest on-duty pharmacies:\n\n"
        for p in ouvertes:
            reply += f"• {p['Nom Pharmacie']} ({p['Quartier']})\n  📞 {p['Téléphone']} ({p['Distance (km)']} km away)\n\n"
    else:  # Hausa
        reply = "Magungunan gadi mafi kusa :\n\n"
        for p in ouvertes:
            reply += f"• {p['Nom Pharmacie']} ({p['Quartier']})\n  📞 {p['Téléphone']} (km {p['Distance (km)']})\n\n"
    
    reply += "Appelle immédiatement en cas d'urgence."
    return reply

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
                    "temperature": 0.7
                }
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except:
            return {"fr": "Je n'ai pas pu répondre.", "en": "I couldn't answer.", "ha": "Na kasa amsawa."}[langue]

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

            # Anti-spam
            now = time.time()
            if sender in last_used and now - last_used[sender] < 30:
                continue
            last_used[sender] = now

            # Gestion menu et langue
            if sender not in user_language:
                user_language[sender] = None
                reply = WELCOME_MENU
            elif text in ["menu", "langue", "language", "change"]:
                user_language[sender] = None
                reply = WELCOME_MENU
            elif text in ["1", "fr", "français"]:
                user_language[sender] = "fr"
                reply = "🇫🇷 Parfait ! Je parle maintenant en français.\nComment puis-je vous aider ?"
            elif text in ["2", "en", "english"]:
                user_language[sender] = "en"
                reply = "🇬🇧 Perfect! I will now speak in English.\nHow can I help you?"
            elif text in ["3", "ha", "hausa"]:
                user_language[sender] = "ha"
                reply = "🇳🇬 Sannu! Yanzu zan yi magana da Hausa na Kano.\nMenene zan iya taimaka maka?"
            else:
                if user_language[sender] is None:
                    reply = WELCOME_MENU
                else:
                    langue = user_language[sender]
                    reply = await ask_grok(msg["text"]["body"], langue)

            # Détection pharmacie de garde
            if any(mot in text for mot in ["pharmacie", "garde", "pharmacy", "on duty", "ouverte", "buɗe"]):
                ville = "niamey" if "niamey" in text else "kano" if "kano" in text else None
                pharmacies = await get_pharmacies_garde(ville)
                reply = format_pharmacies(pharmacies, langue)

            reply += DISCLAIMER.get(langue, DISCLAIMER["en"])

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
