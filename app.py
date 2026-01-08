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

# ⚠️ FORM FIELDS (KEPT EXACTLY AS ORIGINAL)
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"

FORM_FIELDS = {
    "name": "entry.2005620554",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

# 🔴 SMART IMAGE LIBRARY (KEPT EXACTLY AS ORIGINAL)
PRODUCT_IMAGES = {
    "junior": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "kids": "https://ayuralpha.in/cdn/shop/files/Junior_Stamigen_634a1744-3579-476f-9631-461566850dce.png?v=1727083144",
    "powder": "https://ayuralpha.in/cdn/shop/files/Ad2-03.jpg?v=1747049628&width=600",
    "staamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "stamigen": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "malt": "https://ayuralpha.in/cdn/shop/files/Staamigen_1.jpg?v=1747049320&width=600",
    "sakhi": "https://ayuralpha.in/cdn/shop/files/WhatsApp-Image-2025-02-11-at-16.40.jpg?v=1747049518&width=600",
    "vrindha": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "vrinda": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "white": "https://ayuralpha.in/cdn/shop/files/Vrindha_Tone_3.png?v=1727084920&width=823",
    "kanya": "https://ayuralpha.in/cdn/shop/files/Kanya_Tone_7.png?v=1727072110&width=823",
    "period": "https://ayuralpha.in/cdn/shop/files/Kanya_Tone_7.png?v=1727072110&width=823",
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

# 🌐 LANGUAGE OPTIONS
LANGUAGES = {
    "1": "English",
    "2": "Malayalam",
    "3": "Tamil",
    "4": "Hindi",
    "5": "Kannada",
    "6": "Telugu"
}

# 🧠 THE SUPER-BRAIN (UPDATED WITH JUNIOR STAAMIGEN EMOTIONAL MANUAL)
SYSTEM_PROMPT = """
**Role:** Senior Consultant at Alpha Ayurveda.
**Tone:** Empathetic, Authoritative, "The Expert Coach".

**⚠️ CRITICAL RULES:**
1. **IDENTIFY THE USER & ADAPT TONE:**
   - **Teens/Kids (Staamigen Powder/Junior):** Be a "Parent Coach". Focus on warmth, reassurance, and "Sparkle in the eyes".
   - **Men/Gym (Staamigen Malt):** Be a "Fitness Big Brother". Focus on Muscle, Confidence, "Bio-Fuel".
   - **Women (Sakhi Tone):** Be a "Wellness Partner". Focus on Hormones, Stress, "Metabolic Correction".
2. **NO ESSAYS:** Users are on WhatsApp. Keep answers **SHORT** (Max 2-3 sentences per language) unless explaining a process.
3. **DUAL LANGUAGE:** You MUST reply in the **Selected Language** first, followed by **English**.
4. **PERSONAL TOUCH:** You know the user's name. Use it naturally.

*** 👶 JUNIOR STAAMIGEN (PARENTS & KIDS 2-12 YRS) - "THE PARENT COACH" ***
*Philosophy:* We are not selling a tonic; we are helping a child FALL IN LOVE WITH FOOD.
*Tone:* Warm, Reassuring, "Advice from a Friend".
- **Step 1: Validate & Remove Guilt:** "It is painful when a child refuses food. You are not alone. It is not your fault. Modern lifestyle makes hunger hard."
- **Step 2: The Solution:** "Junior Staamigen is like a grandmother's recipe. It gently wakes up the 'Digestive Fire' (Hunger Switch)."
- **Step 3: The Promise:** "We don't want 'balloon weight'. We want 'Strong Weight' (Active, Happy, Sparkle in eyes)."
- **Usage (Dosage):**
  - **3 Years:** 1/2 teaspoon twice daily.
  - **8 Years:** 1 full teaspoon twice daily.
  - **Best Time:** After breakfast and after dinner.
- **Safety:** "As safe as home food. No chemicals, no steroids. 100% Vegetarian."
- **Taste:** "Sweet and yummy like a treat (Jam). Kids love it!"
- **Results:** First week: "Sparkle in eyes" & active. 10 days: Asking for food/Second helping.
- **Lifestyle Advice:** "Don't force feed (War Zone). Eat together. Limit screen time. Swap packets for fruits."

*** 💪 MEN (STAAMIGEN MALT - AGES 18-35) - "FITNESS BROTHER" ***
*Core Concept:* Shift from "Gas-causing Powders" to "Pre-digested Bio-Fuel (Lehya)."
- **Why Paste (Lehya)?** Powders sit in the stomach and cause gas in skinny men. Lehya enters blood immediately.
- **Gym Truth:** "Gym breaks muscle; Food builds muscle." Staamigen delivers food to the muscle.
- **Ectomorphs:** "You burn fuel too fast. Staamigen slows down the burn so you can store mass."
- **Results:** Expect 2-4kg/month. Real muscle takes time.

*** 🌸 WOMEN (SAKHI TONE) - "WELLNESS PARTNER" ***
*Core Concept:* Metabolic Correction. Not just "getting fat," but vitality.
- **The Analogy:** "Pouring water into a cracked pot." If digestion is weak, more food won't help. Sakhi Tone seals the crack.
- **Stress:** Stress (Cortisol) eats muscle. Sakhi Tone reduces stress and supports hormones.
- **Timeline:** Internal changes (sleep/hunger) in 10 days. Weight in 30 days.
- **Note:** For White Discharge, recommend **Vrindha Tone** first.

*** 🌿 PRODUCT QUICK DATABASE 🌿 ***
- **Vrindha Tone:** White Discharge. (Usage: 15ml BEFORE food).
- **Kanya Tone:** Period Cramps/Teen Girls. (Usage: 15ml BEFORE food).
- **Ayur Diabet:** Sugar Control. (10g in warm water).
- **Medi Gas:** For Gas/Acidity.
- **Hair Oil:** For Hair Fall/Dandruff.

*** 💰 PRICING LIST (Reveal ONLY if asked) ***
- Staamigen Malt: ₹749
- Sakhi Tone: ₹749
- Junior Staamigen: ₹599
- Ayur Diabet: ₹690
- Vrindha Tone: ₹440
- Kanya Tone: ₹495
- Staamigen Powder: ₹950
- Ayurdan Hair Oil: ₹845
- Medi Gas Syrup: ₹585
- Muktanjan Pain Oil: ₹295
- Strength Plus: ₹395
- Neelibringadi Oil: ₹599
- Weight Gainer Combo: ₹1450
- Feminine Wellness Combo: ₹1161

*** 📄 OFFICIAL POLICIES ***
- **Shipping:** Free above ₹599.
- **Return:** No returns (hygiene), exchange only for damage.
- **Contact:** +91 9072727201 | alphahealthplus@gmail.com
- **Diet:** "80/20 Rule" (80% Healthy, 20% Fun). Hydration (3L water) is mandatory.

*** 📄 MALAYALAM KNOWLEDGE BASE (ORIGINAL) ***
1. സ്റ്റാമിജൻ മാൾട്ട് (Staamigen Malt) - പുരുഷന്മാർക്ക്: ശരീരഭാരവും, മസിലും, കരുത്തും വർദ്ധിപ്പിക്കാൻ.
2. സഖി ടോൺ (Sakhi Tone) - സ്ത്രീകൾക്ക്: ശരീരഭാരം കൂട്ടാനും ഹോർമോൺ പ്രശ്നങ്ങൾ പരിഹരിക്കാനും.
3. ജൂനിയർ സ്റ്റാമിജൻ മാൾട്ട് (Junior Staamigen Malt): കുട്ടികളുടെ വളർച്ചയ്ക്കും, വിശപ്പിനും, പ്രതിരോധശേഷിക്കും.
4. ആയുർ ഡയബെറ്റ് (Ayur Diabet): പ്രമേഹം നിയന്ത്രിക്കാൻ.
5. വൃന്ദ ടോൺ (Vrindha Tone): വെള്ളപോക്ക് (White Discharge) മാറ്റാൻ.
6. കന്യ ടോൺ (Kanya Tone): കൗമാരക്കാരായ പെൺകുട്ടികൾക്ക് (Periods).

*** 🏪 OFFLINE STORE LIST (KERALA) ***
[Thiruvananthapuram]: Guruvayoorappan Agencies, Sreedhari, Vishnu Medicals.
[Kollam]: AB Agencies, Western, A&A, Krishna.
[Pathanamthitta]: Ayurdan Hospital (Pandalam), Benny, Nagarjuna.
[Alappuzha]: Nagarjuna, Archana, Sreeja.
[Kottayam]: Elsa, Mavelil, Shine.
[Idukki]: Vaidyaratnam, Sony.
[Ernakulam]: Soniya, Ojus, Nakshathra.
[Thrissur]: Siddhavaydyasramam, Kandamkulathy.
[Palakkad]: Palakkad Agencies, Shifa.
[Malappuram]: ET Oushadhashala, CIMS.
[Kozhikode]: Dhanwanthari, Sobha.
[Wayanad]: Jeeva, Reena.
[Kannur]: Lakshmi, Falcon.
[Kasaragod]: Bio, VJ.
"""

def save_to_google_sheet(user_data):
    try:
        phone_clean = user_data.get('phone', '').replace("+", "")
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name", "Unknown"),
            FORM_FIELDS["phone"]: phone_clean, 
            FORM_FIELDS["product"]: user_data.get("product", "Pending")
        }
        requests.post(GOOGLE_FORM_URL, data=form_data, timeout=8)
        print(f"✅ DATA SAVED for {user_data.get('name')}")
    except Exception as e:
        print(f"❌ SAVE ERROR: {e}")

# 🟢 AI FUNCTION (SPEED OPTIMIZED: 25s TIMEOUT)
def get_ai_reply(user_msg, product_context=None, user_name="Customer", language="English"):
    full_prompt = SYSTEM_PROMPT
    
    # --- DUAL LANGUAGE INSTRUCTION ---
    full_prompt += f"\n\n*** LANGUAGE INSTRUCTION (CRITICAL) ***"
    full_prompt += f"\nThe user has selected: **{language}**."
    
    if language != "English":
        full_prompt += f"\n1. You MUST provide the answer in **{language}** FIRST."
        full_prompt += f"\n2. Then add a separator line '---'."
        full_prompt += f"\n3. Then provide the EXACT SAME answer in **English** below it."
    else:
        full_prompt += "\nReply in English only."

    full_prompt += f"\n\n*** USER CONTEXT: The user's name is '{user_name}'. Use this name occasionally. ***"
    if product_context:
        full_prompt += f"\n*** PRODUCT CONTEXT: The user is asking about '{product_context}'. Focus your answers on this product. ***"
    
    full_prompt += "\n\nUser Query: " + user_msg
    
    # 🔴 DIRECT CALL, SINGLE ATTEMPT
    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    try:
        print(f"🤖 AI Request for {user_name} | Lang: {language}")
        # ⚡️ TIMEOUT SET TO 25 SECONDS TO PREVENT RENDER CRASH ⚡️
        response = requests.post(url, json=payload, timeout=25) 
        
        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return text
        else:
            print(f"❌ API ERROR: {response.status_code} - {response.text}")
            return "My brain is a bit slow right now. Please ask me again! 🙏"
    except Exception as e:
        print(f"❌ TIMEOUT/ERROR: {e}")
        return "I am having a connection issue. Please type your message again."

# ✂️ SPLITTER FUNCTION
def split_message(text, limit=1500):
    chunks = []
    while len(text) > limit:
        split_at = text.rfind(' ', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].strip()
    chunks.append(text)
    return chunks

@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    
    resp = MessagingResponse()
    msg = resp.message() 

    # --- SESSION START ---
    if sender_phone not in user_sessions:
         user_sessions[sender_phone] = {
             "step": "ask_language",
             "data": {"wa_number": sender_phone, "phone": sender_phone, "language": "English"},
             "sent_images": []
         }
         msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\n\nPlease select your preferred language:\n1️⃣ English\n2️⃣ Malayalam (മലയാളം)\n3️⃣ Tamil (தமிழ்)\n4️⃣ Hindi (हिंदी)\n5️⃣ Kannada (ಕನ್ನಡ)\n6️⃣ Telugu (తెలుగు)\n\n*(Reply with 1, 2, 3...)*")
         return Response(str(resp), mimetype="application/xml")

    session = user_sessions[sender_phone]
    step = session["step"]
    
    if "sent_images" not in session: session["sent_images"] = []

    # --- STEP 1: HANDLE LANGUAGE SELECTION ---
    if step == "ask_language":
        selection = incoming_msg.strip()
        selected_lang = LANGUAGES.get(selection, "English") 
        for key, val in LANGUAGES.items():
            if val.lower() in selection.lower():
                selected_lang = val
                break
        
        session["data"]["language"] = selected_lang
        session["step"] = "ask_name"
        
        if selected_lang == "Malayalam":
            msg.body("നന്ദി! നിങ്ങളുടെ പേര് എന്താണ്? (What is your name?)")
        elif selected_lang == "Tamil":
            msg.body("நன்றி! உங்கள் பெயர் என்ன? (What is your name?)")
        elif selected_lang == "Hindi":
            msg.body("धन्यवाद! आपका नाम क्या है? (What is your name?)")
        else:
            msg.body(f"Great! You selected {selected_lang}.\nMay I know your *Name*?")
            
        return Response(str(resp), mimetype="application/xml")

    # --- STEP 2: ASK NAME ---
    elif step == "ask_name":
        session["data"]["name"] = incoming_msg
        save_to_google_sheet(session["data"]) # Save Immediately
        session["step"] = "chat_active"
        
        user_lang = session["data"]["language"]
        welcome_text = f"Thank you, {incoming_msg}! Which product would you like to know about? (e.g., Staamigen, Sakhi Tone, Vrindha Tone?)"
        
        if user_lang == "Malayalam":
             welcome_text = f"നന്ദി {incoming_msg}! നിങ്ങൾക്ക് ഏത് ഉൽപ്പന്നത്തെക്കുറിച്ചാണ് അറിയേണ്ടത്? (Staamigen, Sakhi Tone?)"
        elif user_lang == "Tamil":
             welcome_text = f"நன்றி {incoming_msg}! இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?"

        msg.body(welcome_text)

    # --- STEP 3: MAIN CHAT (DUAL LANGUAGE) ---
    elif step == "chat_active":
        user_text_lower = incoming_msg.lower()
        
        for key, image_url in PRODUCT_IMAGES.items():
            if key in user_text_lower:
                if key not in session["sent_images"]:
                    msg.media(image_url)
                    session["sent_images"].append(key)
                
                session["data"]["product"] = key
                save_to_google_sheet(session["data"])
                break

        current_product = session["data"].get("product")
        current_name = session["data"].get("name", "Friend")
        current_lang = session["data"].get("language", "English")
        
        ai_reply = get_ai_reply(incoming_msg, product_context=current_product, user_name=current_name, language=current_lang)
        
        if ai_reply: 
            ai_reply = ai_reply.replace("**", "*")
            chunks = split_message(ai_reply, limit=1500)
            msg.body(chunks[0])
            for chunk in chunks[1:]:
                resp.message(chunk)

    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
