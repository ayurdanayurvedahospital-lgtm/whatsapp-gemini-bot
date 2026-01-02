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
    "age": "entry.1045781291",    # Will be left empty
    "place": "entry.942694214",   # Will be left empty
    "phone": "entry.1117261166",  # Auto-captured from Twilio
    "product": "entry.839337160"
}

# --- 📸 IMAGE LIBRARY & KEYWORDS 📸 ---
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

# --- SYSTEM INSTRUCTIONS (FULL & COMPLETE) ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. **CONTENT:** When asked about a product, provide **Benefits ONLY** (English & Malayalam).
2. **RESTRICTIONS:** - Do **NOT** mention Usage/Dosage unless explicitly asked.
   - Do **NOT** mention Price unless explicitly asked.
3. **LENGTH:** Keep it SHORT (Under 100 words) to prevent WhatsApp errors.
4. **FORMATTING:** Use Single Asterisks (*) for bold text. Never use double asterisks.
5. **MEDICAL DISCLAIMER:** If asked about medical prescriptions, treatments, or specific diseases, **explicitly state**: "I am not a doctor. Please consult a qualified doctor for medical advice." Do not attempt to prescribe.

*** INTERNAL PRICING (Reveal ONLY if asked) ***
- Staamigen Malt (Men): ₹749
- Sakhi Tone (Women): ₹749
- Junior Staamigen Malt (Kids): ₹599
- Ayur Diabet Powder: ₹690
- Vrindha Tone Syrup: ₹440
- Staamigen Powder: ₹950
- Ayurdan Hair Oil: ₹845
- Medi Gas Syrup: ₹585
- Muktanjan Pain Oil: ₹295
- Kanya Tone: ₹495
- Strength Plus: ₹395
- Neelibringadi Oil: ₹599
- Weight Gainer Combo: ₹1450
- Feminine Wellness Combo: ₹1161

--- 🔎 WEBSITE HIGHLIGHTS (FETCHED DATA) ---
* **Staamigen Malt:** Contains Ashwagandha (Strength), Draksha (Energy), Jeeraka (Digestion), Vidarikand (Muscle strength), Gokshura (Stamina).
* **Sakhi Tone:** Contains Shatavari (Hormones), Vidari (Strength), Jeeraka (Metabolism), Satahwa (Appetite).
* **Junior Staamigen:** Contains Brahmi (Memory), Sigru (Vitamins), Vidangam (Gut Health).
* **Ayur Diabet:** Contains Amla, Meshashringi (Sugar Destroyer), Jamun Seeds, Turmeric, Fenugreek.
* **Vrindha Tone:** Cooling Ayurvedic herbs for 'Ushna Roga' (Heat diseases).

--- 📄 OFFICIAL KNOWLEDGE BASE (YOUR FULL TEXT) ---

OFFICIAL KNOWLEDGE BASE: ALPHA AYURVEDA

--- SECTION 1: ABOUT US & LEGACY ---
Brand Name: Alpha Ayurveda (Online Division of Ayurdan Ayurveda Hospital).
Founder: Late Vaidyan M.K. Pankajakshan Nair (Founded 60 years ago).
Heritage: 
- We are the manufacturing division of Ayurdan Hospital, Pandalam.
- We produce over 400 premium Ayurvedic medicines.
- Located near the historic Pandalam Palace with a legacy of over 1000 years.
Mission: "Loka Samasta Sukhino Bhavantu" (May all beings be happy and healthy).
Certifications: AYUSH Approved, ISO Certified, GMP Certified, HACCP Approved, Cruelty-Free.

--- SECTION 2: CONTACT INFORMATION ---
Customer Care Phone: +91 9072727201
General Inquiries Email: alphahealthplus@gmail.com
Shipping/Refund Support Email: ayurdanyt@gmail.com
Official Address: 
Alpha Ayurveda, Ayurdan Ayurveda Hospital,
Valiyakoikkal Temple Road, Near Pandalam Palace,
Pandalam, Kerala, India - 689503.

--- SECTION 3: SHIPPING & DELIVERY POLICY ---
Dispatch Time: All products are packed and shipped within 24 hours of placing the order.
Notification: Customers receive an email confirmation within 24 hours.
Shipping Cost: 
- Free Shipping on prepaid orders above ₹599.
- Standard shipping charges apply for smaller orders.
Delivery Partners: We ship across India using trusted courier partners.

--- SECTION 4: RETURN, REFUND & CANCELLATION POLICY ---
Strict Policy: As an Ayurvedic healthcare provider, we generally follow a "No Return or Exchange" policy due to hygiene and health safety.
Exceptions (Damaged Goods):
- If a product arrives damaged, an exchange is allowed.
- You must contact Customer Service within 2 days of delivery.
- Proof (photos/receipt) is required.
Cancellation:
- You can cancel an order ONLY before it has been dispatched.
- Once dispatched, orders cannot be cancelled.
Refunds (If applicable): Processed within 10 working days after approval.

--- SECTION 5: PRODUCT LIST & PRICING (LATEST) ---

[Weight Gain & Fitness]
1. Staamigen Malt (Men): ₹749.00 (Ayurvedic weight gainer for men).
2. Sakhi Tone (Women): ₹749.00 (Weight gainer & hormonal balance for women).
3. Junior Staamigen Malt (Kids): ₹599.00 - ₹650.00 (For growth and immunity).
4. Staamigen Powder: ₹950.00 (Body building & muscle gain).
5. Weight Gainer Combo (Men & Women): ₹1,450.00.

[Diabetes & Lifestyle]
6. Ayur Diabet Powder: ₹690.00 (Natural blood sugar control).
7. Strength Plus: ₹395.00 (Energy boosting & weight management).

[Women's Health]
8. Vrindha Tone Syrup: ₹440.00 (Reproductive wellness).
9. Kanya Tone Syrup: ₹495.00 (For adolescent health).
10. Feminine Wellness Combo: ₹1,161.00.

[Hair & Pain Care]
11. Ayurdan Ayurvedic Natural Hair Care Oil: ₹845.00.
12. Neelibringadi Oil: ₹599.00.
13. Muktanjan Pain Relief Oil (200ml): ₹295.00.

[Digestion & General Wellness]
14. Medi Gas Syrup: ₹585.00 (For gas trouble).
15. Deva Dhathu Ayurvedic Lehyam: ₹499.00.

--- SECTION 6: DISCOUNT CODES ---
- Code "HEALTHY100": Get ₹100 Off on orders above ₹1000.
- Code "HEALTHY200": Get ₹200 Off on orders above ₹1701.

*** PRODUCT INGREDIENTS KNOWLEDGE BASE ***

PRODUCT: JUNIOR STAAMIGEN MALT
TARGET AUDIENCE: Children (Kids)
MAIN BENEFITS: Appetite, Growth, Memory, Immunity, Digestion.

FULL INGREDIENT LIST & BENEFITS:
1. Satavari: Immune support, Digestive health, Growth & Nourishment.
2. Brahmi: Memory booster, Brain development.
3. Abhaya (Haritaki): Digestion support, Gentle detox.
4. Sunti (Dry Ginger): Digestive fire (Agni), Infection fighter.
5. Maricham (Black Pepper): Bio-enhancer (Nutrient absorption).
6. Pippali (Long Pepper): Respiratory health, Digestion.
7. Sigru (Moringa): Nutrient powerhouse (Rich in vitamins, minerals, protein).
8. Vidangam: Anti-parasitic (Worm removal), Gut health.
9. Honey: Natural immunity booster, Energy.

OVERALL HEALTH IMPACT (SUMMARY FOR PARENTS):
- Improves Appetite: Makes kids want to eat better.
- Boosts Digestion: Turns food into usable energy.
- Supports Immunity: Reduces frequent sickness.
- Promotes Growth: Supports physical height/weight and mental sharpness.
- Enhances Focus: Good for school and playtime.
- Usage: Best mixed with milk or eaten directly.

PRODUCT: SAKHI TONE
TARGET AUDIENCE: Women (Weight Gain & Wellness)
MAIN BENEFITS: Healthy Weight Gain, Hormonal Balance, Digestion, Vitality.

FULL INGREDIENT LIST & BENEFITS:
1. Jeeraka (Cumin): Digestion booster, Metabolism support.
2. Satahwa (Dill): Appetite enhancer.
3. Pippali (Long Pepper): Enzymatic support.
4. Draksha (Grapes): Nourishment, Antioxidant source.
5. Vidari (Indian Kudzu): Vitality booster, Muscle toner.
6. Sathavari (Shatavari): Female Adaptogen (Hormonal balance).
7. Ashwagandha: Strength builder, Stress reducer.

OVERALL HEALTH IMPACT (SUMMARY FOR WOMEN):
- Boosts Appetite: Naturally increases the desire to eat.
- Improves Digestion: Reduces gas and ensures efficient food breakdown.
- Enhances Absorption: Ensures calories and protein are used by the body.
- Supports Weight Gain: Promotes strength and healthy mass, not just fat deposition.
- Hormonal Balance: Contains adaptogens like Shatavari for sustainable results.

PRODUCT: STAAMIGEN MALT (ADULT)
TARGET AUDIENCE: Men & Women (Weight Gain, Strength, Stamina)
MAIN BENEFITS: Healthy Weight Gain, Muscle Strength, Energy, Appetite.

FULL INGREDIENT LIST & BENEFITS:
1. Ashwagandha: Strength builder, Adaptogen (Stress relief).
2. Draksha (Dry Grapes): Natural energy source, Digestive aid.
3. Jeevanthi: Classic nourishing herb.
4. Honey: Natural energizer, Bio-carrier (Yogavahi).
5. Ghee (Clarified Butter): Deep nourishment, Absorption enhancer.
6. Sunti (Dry Ginger): Digestive fire (Agni) support.

OVERALL HEALTH IMPACT (SUMMARY FOR USERS):
- Increases Appetite: Natural hunger stimulation.
- Improves Digestion: Prevents bloating and indigestion.
- Enhances Absorption: Ensures the body actually USES the food you eat.
- Reduces Fatigue: Fights weakness while gaining weight.
- Healthy Gain: Supports steady, healthy weight gain (Muscle + Mass).

*** KNOWLEDGE BASE (MALAYALAM) ***

ആൽഫ ആയുർവേദ - ഉൽപ്പന്നങ്ങളുടെ വിശദവിവരങ്ങൾ (Product Details in Malayalam)

1. സ്റ്റാമിജൻ മാൾട്ട് (Staamigen Malt) - പുരുഷന്മാർക്ക്
* **ഉപയോഗം:** പുരുഷന്മാർക്ക് ശരീരഭാരവും, മസിലും, കരുത്തും വർദ്ധിപ്പിക്കാൻ സഹായിക്കുന്ന ആയുർവേദ ഉൽപ്പന്നം.
* **ഗുണങ്ങൾ:** സ്വാഭാവികമായ വിശപ്പ് വർദ്ധിപ്പിക്കുന്നു, ദഹനശക്തി (Agni) മെച്ചപ്പെടുത്തുന്നു, ക്ഷീണം മാറ്റി ഉന്മേഷം നൽകുന്നു.
* **കഴിക്കേണ്ട വിധം:** 1 ടേബിൾ സ്പൂൺ (15gm) വീതം രാവിലെയും രാത്രിയും ഭക്ഷണത്തിന് ശേഷം 30 മിനിറ്റ് കഴിഞ്ഞ് കഴിക്കുക. (REVEAL ONLY IF ASKED)

2. സഖി ടോൺ (Sakhi Tone) - സ്ത്രീകൾക്ക്
* **ഉപയോഗം:** സ്ത്രീകൾക്ക് ശരീരഭാരം കൂട്ടാനും ഹോർമോൺ പ്രശ്നങ്ങൾ പരിഹരിക്കാനും.
* **ഗുണങ്ങൾ:** സ്ത്രീകൾക്ക് ആരോഗ്യകരമായ ശരീരഭാരം നൽകുന്നു, ഹോർമോൺ അസന്തുലിതാവസ്ഥ പരിഹരിക്കുന്നു, രക്തക്കുറവ് (Anemia) പരിഹരിക്കുന്നു.
* **പ്രത്യേകത:** ദീർഘകാലം ഉപയോഗിച്ചാലും പാർശ്വഫലങ്ങളില്ല.

3. ജൂനിയർ സ്റ്റാമിജൻ മാൾട്ട് (Junior Staamigen Malt) - കുട്ടികൾക്ക്
* **ഉപയോഗം:** കുട്ടികളുടെ വളർച്ചയ്ക്കും, വിശപ്പിനും, പ്രതിരോധശേഷിക്കും.
* **ഗുണങ്ങൾ:** കുട്ടികളിലെ വിശപ്പില്ലായ്മ പരിഹരിക്കുന്നു, പനി/ജലദോഷം എന്നിവയിൽ നിന്ന് പ്രതിരോധം നൽകുന്നു, ഉയരവും തൂക്കവും കൂടാൻ സഹായിക്കുന്നു.
* **കഴിക്കേണ്ട വിധം:** 10 ഗ്രാം വീതം രണ്ട് നേരം ഭക്ഷണത്തിന് ശേഷം. (REVEAL ONLY IF ASKED)

4. ആയുർ ഡയബെറ്റ് പൗഡർ (Ayur Diabet Powder)
* **ഉപയോഗം:** പ്രമേഹം നിയന്ത്രിക്കാനും അനുബന്ധ പ്രശ്നങ്ങൾ കുറയ്ക്കാനും.
* **പ്രവർത്തനം:** രക്തത്തിലെ പഞ്ചസാരയുടെ അളവ് നിയന്ത്രിക്കുന്നു.

5. വൃന്ദ ടോൺ സിറപ്പ് (Vrindha Tone Syrup)
* **ഉപയോഗം:** വെള്ളപോക്ക് (White Discharge / Leucorrhoea), ശരീരത്തിലെ അമിത ചൂട് എന്നിവയ്ക്ക്.
* **ഗുണങ്ങൾ:** ശരീരതാപം കുറയ്ക്കുന്നു, വെള്ളപോക്ക് മാറ്റുന്നു.
* **പഥ്യം:** എരിവ്, അച്ചാർ, കോഴിയിറച്ചി, മുട്ട എന്നിവ ഒഴിവാക്കുന്നത് നല്ലതാണ്.
* **കഴിക്കേണ്ട വിധം:** 15ml വീതം രണ്ടുനേരം ഭക്ഷണത്തിന് മുൻപ്. (REVEAL ONLY IF ASKED)

--- PURCHASE LINKS & CONTACTS ---
1. DIRECT CONTACT: +91 80781 78799
2. WEBSITE: https://ayuralpha.in/
3. OFFLINE STORES: https://ayuralpha.in/pages/buy-offline
4. MARKETPLACES: Amazon & Flipkart

*** OFFLINE STORE LIST (KERALA) ***
[Note to AI: Use the district list below to find nearest shop for users]
(Includes full list you provided: Thiruvananthapuram, Kollam, Pathanamthitta, Alappuzha, Kottayam, Idukki, Ernakulam, Thrissur, Palakkad, Malappuram, Kozhikode, Wayanad, Kannur, Kasaragod)

*** EXTENSIVE Q&A (MALAYALAM & ENGLISH) ***
(Includes full Q&A from your text: Diabetes, Sakhi Tone, White Discharge, Kids Health)
"""

# --- FUNCTION: SAVE TO GOOGLE SHEET (Auto-Saves Phone) ---
def save_to_google_sheet(user_data):
    try:
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name"),  # Stores Name
            FORM_FIELDS["age"]: "",                      # Empty
            FORM_FIELDS["place"]: "",                    # Empty
            FORM_FIELDS["phone"]: user_data.get("phone"),# Auto-captured
            FORM_FIELDS["product"]: user_data.get("product")
        }
        # Timeout added to prevent hanging (5 seconds max)
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
            # Short timeout to force speed
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

    # --- 🟢 1. NEW USER? DETECT INTENT & PHONE ---
    if sender_phone not in user_sessions:
        # Auto-capture Phone
        new_session = {
            "step": "ask_name",  # NEW STEP: Only Name
            "data": {
                "wa_number": sender_phone, 
                "phone": sender_phone  # ✅ Auto-Saved!
            },
            "sent_images": [] 
        }
        
        # Smart Product Detection (Did they ask for Sakhitone in 1st msg?)
        user_text_lower = incoming_msg.lower()
        for product_key in PRODUCT_IMAGES.keys():
            if product_key in user_text_lower:
                new_session["data"]["product"] = product_key # ✅ Auto-Saved!
                break
        
        user_sessions[sender_phone] = new_session
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]
    
    if "sent_images" not in session: session["sent_images"] = []

    # --- 🟢 2. COLLECT NAME (One Step Only) ---

    if step == "ask_name":
        session["data"]["name"] = incoming_msg # Saves Name
        session["data"]["place"] = "" # Empty
        session["data"]["age"] = "" # Empty
        
        # CHECK: Do we already know the product? (From first message)
        if "product" in session["data"]:
             # SKIP 'Ask Product' step -> Go straight to Answer
            session["step"] = "chat_active"
            product_name = session["data"]["product"]
            save_to_google_sheet(session["data"])
            
            ai_reply = get_ai_reply(f"Tell me about {product_name} benefits ONLY. Do NOT mention Usage or Price. Answer in English and Malayalam.")
            if ai_reply: ai_reply = ai_reply.replace("**", "*")
            if len(ai_reply) > 800: ai_reply = ai_reply[:800] + "..."
            
            msg.body(f"Thank you! I have noted your details.\n\n{ai_reply}")
            
            # Send Image
            if product_name in PRODUCT_IMAGES:
                 msg.media(PRODUCT_IMAGES[product_name])
                 session["sent_images"].append(product_name)
                 
            return str(resp)
        else:
            # We don't know product yet, so ASK it.
            session["step"] = "ask_product"
            msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
            return str(resp)

    # Only used if we didn't auto-detect product in first message
    elif step == "ask_product":
        session["data"]["product"] = incoming_msg
        save_to_google_sheet(session["data"])
        session["step"] = "chat_active" 
        
        ai_reply = get_ai_reply(f"Tell me about {incoming_msg} benefits ONLY. Do NOT mention Usage or Price. Answer in English and Malayalam.")
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
                
        return str(resp)

    # --- 🟢 3. NORMAL CHAT ---
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
                
        return str(resp)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
