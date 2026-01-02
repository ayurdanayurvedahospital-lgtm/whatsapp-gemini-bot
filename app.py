import os
import time
import requests
from flask import Flask, request, Response
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

# --- 📸 IMAGE LIBRARY 📸 ---
PRODUCT_IMAGES = {
    "junior": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "powder": "https://ayuralpha.in/cdn/shop/files/Ad2-03.jpg?v=1747049628&width=600",
    "staamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "sakhi": "https://ayuralpha.in/cdn/shop/files/WhatsApp-Image-2025-02-11-at-16.40.jpg?v=1747049518&width=600",
    "vrindha": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "kanya": "https://ayuralpha.in/cdn/shop/files/Kanya_Tone_7.png?v=1727072110&width=823",
    "diabet": "https://ayuralpha.in/cdn/shop/files/ayur_benefits.jpg?v=1755930537",
    "gas": "https://ayuralpha.in/cdn/shop/files/medigas-syrup.webp?v=1750760543&width=823",
    "hair": "https://ayuralpha.in/cdn/shop/files/Ayurdan_hair_oil_1_f4adc1ed-63f9-487d-be08-00c4fcf332a6.png?v=1727083604&width=823",
    "strength": "https://ayuralpha.in/cdn/shop/files/strplus1.jpg?v=1765016122&width=823",
    "gain": "https://ayuralpha.in/cdn/shop/files/gain-plus-2.jpg?v=1765429628&width=823",
    "pain": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "muktanjan": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "saphala": "https://ayuralpha.in/cdn/shop/files/saphalacap1.png?v=1766987920",
    "neeli": "https://ayuralpha.in/cdn/shop/files/18.png?v=1725948517&width=823"
}

# --- MEMORY STORAGE ---
user_sessions = {}

# --- SYSTEM INSTRUCTIONS ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. **CONTENT:** Provide **Benefits ONLY** (English & Malayalam).
2. **RESTRICTIONS:** Do **NOT** mention Usage/Dosage or Price unless asked.
3. **LENGTH:** Keep it SHORT (Under 100 words).
4. **FORMATTING:** Use Single Asterisks (*) for bold.
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
    # ⚠️ HARDCODE YOUR TWILIO NUMBER HERE TO BE SAFE
    # Replace +14155238886 with your actual Sandbox number if different
    msg = resp.message(from_='whatsapp:+14155238886') 

    if sender_phone not in user_sessions:
        new_session = {
            "step": "ask_name",
            "data": {
                "wa_number": sender_phone, 
                "phone": sender_phone  
            },
            "sent_images": []
        }
        
        # Product Detection
        user_text_lower = incoming_msg.lower()
        for key in PRODUCT_IMAGES.keys():
            if key in user_text_lower:
                new_session["data"]["product"] = key
                break
        
        user_sessions[sender_phone] = new_session
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return Response(str(resp), mimetype="application/xml")

    session = user_sessions[sender_phone]
    step = session["step"]
    
    if "sent_images" not in session: session["sent_images"] = []

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
            
            if product_name in PRODUCT_IMAGES and product_name not in session["sent_images"]:
                 msg.media(PRODUCT_IMAGES[product_name])
                 session["sent_images"].append(product_name)
                 
            return Response(str(resp), mimetype="application/xml")
        else:
            session["step"] = "ask_product"
            msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
            return Response(str(resp), mimetype="application/xml")

    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        save_to_google_sheet(session["data"])
        session["step"] = "chat_active" 
        
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} benefits ONLY. Answer in English and Malayalam.")
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 800: ai_reply = ai_reply[:800] + "..."

        msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
        
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                break

        return Response(str(resp), mimetype="application/xml")

    elif step == "chat_active":
        ai_reply = get_ai_reply(incoming_msg)
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 1000: ai_reply = ai_reply[:1000] + "..."
        msg.body(ai_reply)
        
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                break
        
        return Response(str(resp), mimetype="application/xml")

    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
