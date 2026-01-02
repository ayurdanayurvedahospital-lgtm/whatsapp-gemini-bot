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

# --- SYSTEM INSTRUCTIONS ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. **CONTENT:** When asked about a product, provide **Benefits ONLY** (English & Malayalam).
2. **RESTRICTIONS:** - Do **NOT** mention Usage/Dosage unless explicitly asked.
   - Do **NOT** mention Price unless explicitly asked.
3. **LENGTH:** Keep it SHORT (Under 100 words).
4. **FORMATTING:** Use Single Asterisks (*) for bold text.
5. **MEDICAL DISCLAIMER:** If asked about medical prescriptions/diseases, state: "I am not a doctor. Please consult a qualified doctor for medical advice."

*** INTERNAL PRICING (Reveal ONLY if asked) ***
- Staamigen Malt: ₹749
- Sakhi Tone: ₹749
- Junior Staamigen: ₹599
- Ayur Diabet: ₹690
- Vrindha Tone: ₹440
- Staamigen Powder: ₹950
- Ayurdan Hair Oil: ₹845
- Kanya Tone: ₹495
- Combo: ₹1450

--- WEBSITE HIGHLIGHTS ---
* **Staamigen:** Ashwagandha, Draksha.
* **Sakhi:** Shatavari, Vidari.
* **Junior:** Brahmi, Sigru.
* **Diabet:** Meshashringi, Jamun.

*** EXTENSIVE KNOWLEDGE BASE INCLUDED ***
"""

# --- FUNCTION: SAVE TO GOOGLE SHEET ---
def save_to_google_sheet(user_data):
    try:
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name"),
            FORM_FIELDS["age"]: "",                      
            FORM_FIELDS["place"]: "",                    
            FORM_FIELDS["phone"]: user_data.get("phone"),
            FORM_FIELDS["product"]: user_data.get("product")
        }
        requests.post(GOOGLE_FORM_URL, data=form_data, timeout=5)
        print(f"✅ Data Saved for {user_data.get('name')}")
    except Exception as e:
        print(f"❌ Error saving to Sheet: {e}")

# --- SMART MODEL DETECTOR ---
def get_safe_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            all_models = [m['name'].replace("models/", "") for m in data.get('models', [])]
            safe_models = [m for m in all_models if "gemini" in m and "embedding" not in m and "exp" not in m]
            if any("flash" in m for m in safe_models): return [m for m in safe_models if "flash" in m][0]
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
    
    for attempt in range(2): 
        try:
            response = requests.post(url, json=payload, timeout=8)
            if response.status_code == 200:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return text
            elif response.status_code in [429, 503]:
                time.sleep(1)
                continue
            else:
                return "Our servers are busy right now. Please try again."
        except:
            time.sleep(1)
    
    return "Our servers are busy right now. Please try again."

# --- MAIN BOT ROUTE ---
@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    
    resp = MessagingResponse()
    msg = resp.message()

    if sender_phone not in user_sessions:
        new_session = {
            "step": "ask_name",
            "data": {
                "wa_number": sender_phone, 
                "phone": sender_phone  
            }
        }
        
        # Product Detection (Simplified)
        user_text_lower = incoming_msg.lower()
        if "sakhi" in user_text_lower: new_session["data"]["product"] = "sakhi"
        elif "staamigen" in user_text_lower: new_session["data"]["product"] = "staamigen"
        elif "junior" in user_text_lower: new_session["data"]["product"] = "junior"
        elif "diabet" in user_text_lower: new_session["data"]["product"] = "diabet"
        
        user_sessions[sender_phone] = new_session
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]

    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        
        if "product" in session["data"]:
            session["step"] = "chat_active"
            product_name = session["data"]["product"]
            save_to_google_sheet(session["data"])
            
            ai_reply = get_ai_reply(f"Tell me about {product_name} benefits ONLY. Answer in English and Malayalam.")
            if ai_reply: ai_reply = ai_reply.replace("**", "*")
            if len(ai_reply) > 800: ai_reply = ai_reply[:800] + "..."
            
            msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
            
            # ❌ IMAGES REMOVED FOR TESTING ❌
            # If this message arrives, we know the image links were breaking it.
                 
            return str(resp)
        else:
            session["step"] = "ask_product"
            msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
            return str(resp)

    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        save_to_google_sheet(session["data"])
        session["step"] = "chat_active" 
        
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} benefits ONLY. Answer in English and Malayalam.")
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 800: ai_reply = ai_reply[:800] + "..."

        msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
        # ❌ IMAGES REMOVED FOR TESTING ❌
        return str(resp)

    elif step == "chat_active":
        ai_reply = get_ai_reply(incoming_msg)
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 1000: ai_reply = ai_reply[:1000] + "..."
        msg.body(ai_reply)
        # ❌ IMAGES REMOVED FOR TESTING ❌
        return str(resp)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
