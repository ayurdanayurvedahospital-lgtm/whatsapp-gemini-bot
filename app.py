import os
import time
import requests
import logging
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

# --- CONFIGURATION ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
API_KEY = os.environ.get("GEMINI_API_KEY")

# ⚠️ GOOGLE FORM: Ensure fields are set to "Short Answer"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"

FORM_FIELDS = {
    "name": "entry.2005620554",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

# 🔴 UPDATED: Includes common spelling variations for better detection
PRODUCT_IMAGES = {
    "junior": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "kids": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "powder": "https://ayuralpha.in/cdn/shop/files/Ad2-03.jpg?v=1747049628&width=600",
    "staamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "stamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "sakhi": "https://ayuralpha.in/cdn/shop/files/WhatsApp-Image-2025-02-11-at-16.40.jpg?v=1747049518&width=600",
    "vrindha": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "vrinda": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823", # Spelling fix
    "kanya": "https://ayuralpha.in/cdn/shop/files/Kanya_Tone_7.png?v=1727072110&width=823",
    "diabet": "https://ayuralpha.in/cdn/shop/files/ayur_benefits.jpg?v=1755930537",
    "sugar": "https://ayuralpha.in/cdn/shop/files/ayur_benefits.jpg?v=1755930537",
    "gas": "https://ayuralpha.in/cdn/shop/files/medigas-syrup.webp?v=1750760543&width=823",
    "hair": "https://ayuralpha.in/cdn/shop/files/Ayurdan_hair_oil_1_f4adc1ed-63f9-487d-be08-00c4fcf332a6.png?v=1727083604&width=823",
    "strength": "https://ayuralpha.in/cdn/shop/files/strplus1.jpg?v=1765016122&width=823",
    "gain": "https://ayuralpha.in/cdn/shop/files/gain-plus-2.jpg?v=1765429628&width=823",
    "pain": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "muktanjan": "https://ayuralpha.in/cdn/shop/files/Muktanjan_Graphics_img.jpg?v=1734503551&width=823",
    "saphala": "https://ayuralpha.in/cdn/shop/files/saphalacap1.png?v=1766987920",
    "neeli": "https://ayuralpha.in/cdn/shop/files/18.png?v=1725948517&width=823"
}

user_sessions = {}

# 🔴 UPDATED: FULL KNOWLEDGE BASE & STRICT PRICE LOGIC
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).

**⚠️ CRITICAL RULES (MUST FOLLOW):**
1. **CONTEXT-AWARE PRICING:** If the user asks for the price of ONE product (e.g., "Price of Sakhi Tone"), **ONLY** reveal the price of that specific product. **DO NOT** list prices for other products unless explicitly asked for a "Price List".
2. **CONTENT:** Provide **Benefits ONLY**. Do NOT mention Usage/Dosage unless asked.
3. **LENGTH:** Keep it SHORT (Under 100 words).
4. **MEDICAL DISCLAIMER:** If asked about medical prescriptions/diseases, state: "I am not a doctor. Please consult a qualified doctor for medical advice."
5. **STRICT INGREDIENTS:** If asked about ingredients, use the **EXACT LIST** below.

*** 🌿 STRICT INGREDIENT LIST 🌿 ***
1. **JUNIOR STAAMIGEN MALT:** Satavari, Brahmi, Abhaya, Sunti, Maricham, Pippali, Sigru, Vidangam, Honey.
2. **SAKHI TONE:** Jeeraka, Satahwa, Pippali, Draksha, Vidari, Sathavari, Ashwagandha.
3. **STAAMIGEN MALT:** Ashwagandha, Draksha, Jeevanthi, Honey, Ghee, Sunti, Vidarikand, Gokshura.
4. **AYUR DIABET:** Amla, Meshashringi, Jamun Seeds, Turmeric, Fenugreek.

*** 💰 INTERNAL PRICING DATABASE (Use only the relevant one) ***
- Staamigen Malt (Men): ₹749
- Sakhi Tone (Women): ₹749
- Junior Staamigen (Kids): ₹599
- Ayur Diabet: ₹690
- Vrindha Tone (White Discharge): ₹440
- Kanya Tone (Teens): ₹495
- Staamigen Powder: ₹950
- Ayurdan Hair Oil: ₹845
- Medi Gas Syrup: ₹585
- Muktanjan Pain Oil: ₹295
- Strength Plus: ₹395
- Neelibringadi Oil: ₹599
- Weight Gainer Combo: ₹1450
- Feminine Wellness Combo: ₹1161

*** 📄 FULL KNOWLEDGE BASE (ENGLISH) ***
--- SECTION 1: ABOUT US ---
Brand: Alpha Ayurveda (Online Division of Ayurdan Ayurveda Hospital).
Founder: Late Vaidyan M.K. Pankajakshan Nair (60 years legacy).
Location: Pandalam, Kerala.
Mission: "Loka Samasta Sukhino Bhavantu".
Certifications: AYUSH, ISO, GMP, HACCP.

--- SECTION 2: POLICIES ---
Shipping: Free above ₹599. Dispatched in 24 hrs.
Returns: No returns (hygiene). Exchange only for damaged goods (report in 2 days).

--- SECTION 3: PRODUCT SPECIFICS ---
* **Vrindha Tone:** For White Discharge (Leucorrhoea) and body heat. Cooling effect. Avoid spicy/sour foods.
* **Kanya Tone:** For adolescent girls' health and vitality.
* **Medi Gas:** For gas trouble and bloating.
* **Muktanjan:** For pain relief.

*** 📄 KNOWLEDGE BASE (MALAYALAM) ***
1. **സ്റ്റാമിജൻ മാൾട്ട്:** പുരുഷന്മാർക്ക് ഭാരവും മസിലും കൂട്ടാൻ. വിശപ്പും ദഹനവും കൂട്ടുന്നു.
2. **സഖി ടോൺ:** സ്ത്രീകൾക്ക് ഭാരം കൂട്ടാനും ഹോർമോൺ ബാലൻസിനും. രക്തക്കുറവ് മാറ്റുന്നു.
3. **ജൂനിയർ സ്റ്റാമിജൻ:** കുട്ടികളുടെ വളർച്ച, വിശപ്പ്, പ്രതിരോധശേഷി എന്നിവയ്ക്ക്.
4. **ആയുർ ഡയബെറ്റ്:** പ്രമേഹ നിയന്ത്രണത്തിന്.
5. **വൃന്ദ ടോൺ:** വെള്ളപോക്ക് (White Discharge), ശരീര ചൂട് എന്നിവയ്ക്ക് ഉത്തമം. എരിവും പുളിയും ഒഴിവാക്കണം.
6. **കന്യ ടോൺ:** കൗമാരക്കാരായ പെൺകുട്ടികളുടെ ആരോഗ്യത്തിന്.

*** EXTENSIVE Q&A (FULL) ***
Q: Can Sakhi Tone control White Discharge? A: No, use Vrindha Tone first.
Q: Is Sakhi Tone good for Body Shaping? A: Yes, via healthy weight gain.
Q: Can recovered Hepatitis/Stroke patients take this? A: Yes, after recovery.
Q: Will it cause Diabetes? A: No.
Q: Will I lose weight if I stop? A: No, if diet is maintained.
Q: Can I take this with Arthritis/Thyroid meds? A: Yes, but consult doctor.
Q: Fatty Liver/Heart/BP patients? A: Consult doctor first.
Q: Breastfeeding? A: Yes, after 3-4 months.
Q: How much to gain 5kg? A: 2-3 bottles.
Q: Age limit for Junior? A: 2-12 years.
Q: Staamigen Malt for women? A: No, women should use Sakhi Tone.
"""

def save_to_google_sheet(user_data):
    try:
        # Clean phone number (Remove + to satisfy Google Form)
        phone_clean = user_data.get('phone', '').replace("+", "")
        
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name", "Unknown"),
            FORM_FIELDS["phone"]: phone_clean, 
            FORM_FIELDS["product"]: user_data.get("product", "Pending")
        }
        
        # Send data
        requests.post(GOOGLE_FORM_URL, data=form_data, timeout=8)
        print(f"✅ DATA SAVED for {user_data.get('name')}")
            
    except Exception as e:
        print(f"❌ SAVE ERROR: {e}")

# AUTO-DETECT WORKING MODEL
def get_dynamic_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                m_name = model['name'].replace("models/", "")
                if "gemini" in m_name and "generateContent" in model.get('supportedGenerationMethods', []):
                    return m_name
    except:
        pass
    return "gemini-1.5-flash"

def get_ai_reply(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg
    model_name = get_dynamic_model()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    for attempt in range(2): 
        try:
            print(f"🤖 Using Model: {model_name}")
            response = requests.post(url, json=payload, timeout=12)
            
            if response.status_code == 200:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return text
            else:
                time.sleep(1)
        except Exception as e:
            time.sleep(1)

    return "Our servers are busy right now. Please try again later."

@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    
    resp = MessagingResponse()
    msg = resp.message() 

    # --- SESSION MANAGEMENT ---
    if sender_phone not in user_sessions:
        detected_product = None
        user_text_lower = incoming_msg.lower()
        
        # Check for product in first message
        for key in PRODUCT_IMAGES.keys():
            if key in user_text_lower:
                detected_product = key
                break
        
        if detected_product:
             user_sessions[sender_phone] = {
                 "step": "chat_active",
                 "data": {"wa_number": sender_phone, "phone": sender_phone, "product": detected_product, "name": "Returning User"},
                 "sent_images": []
             }
        else:
             user_sessions[sender_phone] = {
                 "step": "ask_name",
                 "data": {"wa_number": sender_phone, "phone": sender_phone},
                 "sent_images": []
             }
             msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
             return Response(str(resp), mimetype="application/xml")

    session = user_sessions[sender_phone]
    step = session["step"]
    
    if "sent_images" not in session: session["sent_images"] = []

    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        save_to_google_sheet(session["data"]) # Save Immediately
        session["step"] = "chat_active"
        msg.body("Thank you! Which product would you like to know about? (e.g., Staamigen, Sakhi Tone, Vrindha Tone?)")

    elif step == "chat_active":
        user_text_lower = incoming_msg.lower()
        
        # Check for keywords to trigger images
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                
                # Update product in sheet
                session["data"]["product"] = key
                save_to_google_sheet(session["data"])
                break

        ai_reply = get_ai_reply(incoming_msg)
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 1000: ai_reply = ai_reply[:1000] + "..."
        msg.body(ai_reply)

    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
