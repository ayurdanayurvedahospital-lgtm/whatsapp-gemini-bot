import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- 🔴 GOOGLE FORM CONFIGURATION 🔴 ---
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"

FORM_FIELDS = {
    "name": "entry.2005620554",
    "age": "entry.1045781291",
    "place": "entry.942694214",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

# --- MEMORY STORAGE ---
user_sessions = {}

# --- SYSTEM INSTRUCTIONS (THE FULL BRAIN) ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. Answer CONCISELY.
2. STRICTLY follow the pricing list.
3. If asked about serious illness (Heart, Liver, Pregnancy), suggest a doctor.
4. Purchase options: Call +91 80781 78799 or Visit ayuralpha.in

**PRICES:**
- Ayur Diabet: ₹690
- Staamigen Malt: ₹749
- Sakhi Tone: ₹749
- Junior Malt: ₹599
- Vrindha Tone: ₹440
- Hair Oil: ₹845

--- KNOWLEDGE BASE: DETAILED INGREDIENTS ---

**1. STAAMIGEN MALT (Adult Weight Gain)**
- Benefits: Weight gain, Muscle Strength, Energy.
- Ingredients: Ashwagandha (Strength), Draksha (Energy), Pippali (Metabolism), Jeevanthi (Vitality).

**2. SAKHI TONE (Women's Weight Gain)**
- Benefits: Healthy Curves, Hormonal Balance, Weight Gain.
- Ingredients: Shatavari (Hormones), Vidari (Mass), Jeeraka (Digestion), Draksha (Nourishment).

**3. JUNIOR STAAMIGEN MALT (Kids 2-12 Years)**
- Benefits: Appetite, Growth, Immunity, Memory.
- Ingredients: Brahmi (Memory), Sigru (Vitamins), Vidangam (Gut Health/Worms).

**4. AYUR DIABET POWDER (Diabetes)**
- Benefits: Controls sugar, reduces fatigue & numbness.
- Ingredients: Turmeric, Amla, Jamun seeds (18+ Herbs).

**5. VRINDHA TONE (White Discharge)**
- Benefits: Cures White Discharge, reduces body heat.
- Diet: Avoid spicy/sour foods, chicken, eggs.

--- KNOWLEDGE BASE: OFFLINE SHOPS ---
[THIRUVANANTHAPURAM] Guruvayoorappan Agencies: 9895324721, Sreedhari: 0471 2331524
[KOLLAM] AB Agencies: 9387359803, Western: 0474 2750933, Amma: 9447093006
[PATHANAMTHITTA] Ayurdan Hospital: 95265 30400, Divine: 9037644232
[ALAPPUZHA] Nagarjuna: 8848054124, Archana: 4772261385
[KOTTAYAM] Elsa: 0481 2566923, Shine: 4828210911
[IDUKKI] Vaidyaratnam: 8547128298, Sony: 7559950989
[ERNAKULAM] Soniya: 9744167180, Ojus: 9562456123
[THRISSUR] Siddhavaydyasramam: 9895268099, Seetharam: 9846302180
[PALAKKAD] Palakkad Agencies: 0491-2522474, Shifa: 9846689715
[MALAPPURAM] ETM: 9947959865, Changampilly: 9895377210
[KOZHIKODE] Dhanwanthari: 9995785797, Sobha: 9496601785
[WAYANAD] Jeeva: 9562061514, Reena: 9447933863
[KANNUR] Lakshmi: 0497-2712730, Falcon: 9747624606
[KASARAGOD] Bio: 9495805099, Malabar: 9656089944

**Q&A KNOWLEDGE:**
- Diabetes? Safe to use. No side effects.
- Results? Visible in 15 days. Best in 90 days.
- Breastfeeding? Start 3-4 months after delivery.
"""

# --- FUNCTION: SAVE TO GOOGLE SHEET ---
def save_to_google_sheet(user_data):
    try:
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name"),
            FORM_FIELDS["age"]: user_data.get("age"),
            FORM_FIELDS["place"]: user_data.get("place"),
            FORM_FIELDS["phone"]: user_data.get("phone"),
            FORM_FIELDS["product"]: user_data.get("product")
        }
        requests.post(GOOGLE_FORM_URL, data=form_data)
        print(f"✅ Data Saved for {user_data.get('name')}")
    except Exception as e:
        print(f"❌ Error saving to Sheet: {e}")

# --- SMART MODEL DETECTOR ---
def get_safe_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            all_models = [m['name'].replace("models/", "") for m in data.get('models', [])]
            safe_models = [m for m in all_models if "gemini" in m and "embedding" not in m and "exp" not in m]
            if any("flash" in m for m in safe_models): return [m for m in safe_models if "flash" in m][0]
            if any("pro" in m for m in safe_models): return [m for m in safe_models if "pro" in m][0]
            if safe_models: return safe_models[0]
    except:
        pass
    return "gemini-1.5-flash"

# --- GENERATE WITH RETRY ---
def get_ai_reply(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg
    model_name = get_safe_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code in [429, 503]:
                time.sleep(2 ** attempt)
                continue
            else:
                return None
        except:
            time.sleep(1)
    return "Our servers are busy right now. Please try again in 1 minute."

# --- MAIN BOT ROUTE ---
@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    
    resp = MessagingResponse()
    msg = resp.message()

    # --- LEAD COLLECTION FLOW ---
    
    # 1. Start New Session -> Ask NAME
    if sender_phone not in user_sessions:
        user_sessions[sender_phone] = {"step": "ask_name", "data": {"wa_number": sender_phone}}
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your **Name**?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]

    # 2. Capture Name -> Ask AGE
    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        session["step"] = "ask_age"
        msg.body(f"Nice to meet you, {incoming_msg}. \nMay I know your **Age**?")
        return str(resp)

    # 3. Capture Age -> Ask PLACE (Updated Order)
    elif step == "ask_age":
        session["data"]["age"] = incoming_msg
        session["step"] = "ask_place"
        msg.body("Thank you. Which **Place/District** are you from?")
        return str(resp)

    # 4. Capture Place -> Ask PHONE (Updated Order)
    elif step == "ask_place":
        session["data"]["place"] = incoming_msg
        session["step"] = "ask_phone"
        msg.body("Please type your **Phone Number** for our doctor to contact you:")
        return str(resp)

    # 5. Capture Phone -> Ask PRODUCT
    elif step == "ask_phone":
        session["data"]["phone"] = incoming_msg
        session["step"] = "ask_product"
        msg.body("Noted. Which **Product** do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
        return str(resp)

    # 6. Capture Product -> SAVE -> Answer
    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        
        # Save to Google Sheet
        save_to_google_sheet(session["data"])
        
        # Switch to Normal Chat
        session["step"] = "chat_active" 
        
        # Get AI Answer
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} briefly.")
        msg.body(f"Thank you! I have noted your details for our expert team.\n\nHere is the info about {incoming_msg}:\n{ai_reply}")
        return str(resp)

    # 7. NORMAL CHAT (Gemini)
    elif step == "chat_active":
        ai_reply = get_ai_reply(incoming_msg)
        msg.body(ai_reply)
        return str(resp)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
