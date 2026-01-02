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
    "place": "entry.942694214",     # Place comes 3rd in your form
    "phone": "entry.1117261166",     # Phone comes 4th in your form
    "product": "entry.839337160"
}

# --- 📸 IMAGE LIBRARY (UPDATED WITH YOUR LINKS) 📸 ---
# The bot checks if the 'Key' word exists in the user's message.
# If yes, it sends the corresponding 'Image Link'.
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
1. Answer CONCISELY.
2. STRICTLY follow the pricing list below.
3. **FORMATTING:** Use Single Asterisks (*) for bold text. Do NOT use double asterisks (**).
4. If asked about serious illness, suggest a doctor.
5. Purchase options: Call +91 80781 78799 or Visit ayuralpha.in

**STRICT PRICING & LINKS:**
- Staamigen Malt (Men): ₹749
- Sakhi Tone (Women): ₹749
- Junior Staamigen Malt (Kids): ₹599
- Ayur Diabet Powder: ₹690
- Vrindha Tone Syrup: ₹440
- Staamigen Powder (Advanced): ₹950
- Ayurdan Hair Care Oil: ₹845
- Medi Gas Syrup: ₹585
- Muktanjan Pain Relief Oil: ₹295
- Kanya Tone: ₹440
- Strength Plus: ₹890
- Gain Plus: ₹890
- Saphala Capsules: ₹450
- Neelibringadi Keram: ₹240
- **Combos:** Weight Gainer (Men/Women) ₹1450 | Feminine Wellness (Sakhi+Vrindha) ₹1161

--- KNOWLEDGE BASE: PRODUCT DETAILS ---

**1. STAAMIGEN MALT (Men's Weight Gainer)**
- **Best For:** Men who want to gain weight, muscle, and energy.
- **Benefits:** Increases appetite (hunger), improves digestion (Agni), builds lean muscle mass, reduces fatigue, and improves sleep.
- **Key Ingredients:** Ashwagandha (Stress/Energy), Draksha (Appetite), Jeeraka (Digestion), Vidarikand (Muscle strength), Gokshura (Stamina).
- **Timeline:** Appetite improves in 7-15 days. Visible weight gain in 30 days. Full transformation in 90 days.

**2. SAKHI TONE (Women's Weight Gainer)**
- **Best For:** Women (15+) for healthy curves, hormonal balance, and weight gain.
- **Benefits:** Enhances nutrient absorption, restores hormonal balance (regular periods), improves skin/hair health, and boosts energy.
- **Key Ingredients:** Shatavari (Hormones/Curves), Vidari (Strength), Jeeraka (Metabolism), Satahwa (Appetite).
- **Dosage:** 1 tablespoon (15g) morning and evening, 30 mins **AFTER** food.

**3. JUNIOR STAAMIGEN MALT (Kids 3-12 Years)**
- **Best For:** Kids with poor appetite, low immunity, or slow growth.
- **Benefits:** Increases hunger, boosts memory and concentration, reduces frequent sickness (fever/cold), and supports height/weight growth.
- **Dosage:** 5g (1 tsp) twice a day after food. Tasty and easy to eat.

**4. AYUR DIABET POWDER (Diabetes Control)**
- **Best For:** High blood sugar, insulin resistance, diabetic fatigue.
- **Benefits:** Controls sugar spikes, reduces frequent urination, fights fatigue and numbness, protects liver/kidney.
- **Key Ingredients:** Amla, Meshashringi (The "Sugar Destroyer"), Jamun Seeds, Turmeric, Fenugreek.
- **Usage:** Mix 1 spoon (10g) in lukewarm water/milk. Take twice daily after meals.

**5. VRINDHA TONE SYRUP (White Discharge)**
- **Best For:** White discharge, internal body heat, burning sensation.
- **Benefits:** Cools the body from within, balances acidic/heat levels, cures discharge.
- **Usage:** 15ml twice daily, 30 mins **BEFORE** food (Empty stomach is best).
- **Diet Rule:** Avoid chicken, eggs, pickles, and spicy/fried food during the course.

**6. MUKTANJAN PAIN RELIEF OIL**
- **Best For:** Joint pain, back pain, muscle stiffness, arthritis.
- **Usage:** Apply on the affected area and massage gently.

--- SPECIFIC Q&A (MEDICAL & USAGE) ---
* **Side Effects?** No. All products are 100% Ayurvedic, GMP Certified, and Chemical-free.
* **White Discharge & Weight Gain:** If you have White Discharge, treat that FIRST with Vrindha Tone. Once cured, use Sakhi Tone for weight gain.
* **Diabetes Safety:** Weight gain products (Staamigen/Sakhi) do NOT cause diabetes. However, diabetic patients should consult a doctor before using weight gainers.
* **Can I stop after gaining weight?** Yes. The weight gained is from muscle and healthy tissue, so it stays if you maintain a good diet.
* **Breastfeeding?** Safe to start 3-4 months after delivery.
* **Results Timeline?** Minimum 1 month for initial results. 3 months (90 days) for permanent healthy change.

--- OFFLINE SHOPS ---
[THIRUVANANTHAPURAM] Guruvayoorappan Agencies: 9895324721
[KOLLAM] AB Agencies: 9387359803
[PATHANAMTHITTA] Ayurdan Hospital: 95265 30400
[ALAPPUZHA] Nagarjuna: 8848054124
[ERNAKULAM] Soniya: 9744167180
[THRISSUR] Siddhavaydyasramam: 9895268099
[KOZHIKODE] Dhanwanthari: 9995785797
[KANNUR] Lakshmi: 0497-2712730
[KASARAGOD] Bio: 9495805099
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
    
    if sender_phone not in user_sessions:
        user_sessions[sender_phone] = {"step": "ask_name", "data": {"wa_number": sender_phone}}
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]

    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        session["step"] = "ask_age"
        msg.body(f"Nice to meet you, {incoming_msg}. \nMay I know your *Age*?")
        return str(resp)

    elif step == "ask_age":
        session["data"]["age"] = incoming_msg
        session["step"] = "ask_place"
        msg.body("Thank you. Which *Place/District* are you from?")
        return str(resp)

    elif step == "ask_place":
        session["data"]["place"] = incoming_msg
        session["step"] = "ask_phone"
        msg.body("Please type your *Phone Number* for our doctor to contact you:")
        return str(resp)

    elif step == "ask_phone":
        session["data"]["phone"] = incoming_msg
        session["step"] = "ask_product"
        msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
        return str(resp)

    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        save_to_google_sheet(session["data"])
        session["step"] = "chat_active" 
        
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} briefly.")
        msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
        
        # 📸 AUTO-ATTACH IMAGE 📸
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                msg.media(image_url)
                break
                
        return str(resp)

    # 7. NORMAL CHAT (With Image Detection)
    elif step == "chat_active":
        ai_reply = get_ai_reply(incoming_msg)
        msg.body(ai_reply)
        
        # 📸 AUTO-ATTACH IMAGE 📸
        user_text_lower = incoming_msg.lower()
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                msg.media(image_url)
                break
                
        return str(resp)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
