import os
import re
import time
import requests
import logging
import threading
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from prompts import SYSTEM_PROMPT

# --- CONFIGURATION ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
API_KEY = os.environ.get("GEMINI_API_KEY")

# FORM FIELDS (Google Sheets)
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"
FORM_FIELDS = {
    "name": "entry.2005620554",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

# 👥 AGENT ROTATION LIST
AGENTS = [
    {"name": "Sreelekha", "phone": "+91 9895900809", "link": "https://wa.link/t45vpy"},
    {"name": "Savitha", "phone": "+91 9447225084", "link": "https://wa.link/nxzz8w"},
    {"name": "Sreelakshmi", "phone": "+91 8304945580", "link": "https://wa.link/i4d2yf"},
    {"name": "Rekha", "phone": "+91 9526530800", "link": "https://wa.link/t4huis"}
]
# global_agent_counter = 0  <-- PAUSED (Agent 1 Forced)
current_agent = AGENTS[0]

# 🖼️ SMART IMAGE LIBRARY
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

# LANGUAGE OPTIONS
LANGUAGES = {
    "1": "English",
    "2": "Malayalam",
    "3": "Tamil",
    "4": "Hindi",
    "5": "Kannada",
    "6": "Telugu",
    "7": "Bengali"
}

# 🌐 UI TRANSLATION DICTIONARY
UI_STRINGS = {
    "English": {
        "ask_name": "Great! You selected English.\nMay I know your *Name*?",
        "ask_product": "Thank you! Which product would you like to know about? (e.g., Sakhitone, Staamigen Malt, Junior Staamigen?)",
        "confirm_switch": "Do you want me to talk in English from now? (Yes/No)",
        "intro_prefix": "You are inquiring about"
    },
    "Malayalam": {
        "ask_name": "നന്ദി! നിങ്ങളുടെ പേര് എന്താണ്? (What is your name?)",
        "ask_product": "നന്ദി! നിങ്ങൾക്ക് ഏത് ഉൽപ്പന്നത്തെക്കുറിച്ചാണ് അറിയേണ്ടത്? (e.g., Sakhitone, Staamigen Malt, Junior Staamigen?)",
        "confirm_switch": "നിങ്ങൾക്ക് ഭാഷ മലയാളത്തിലേക്ക് മാറ്റണോ? (അതെ/അല്ല)",
        "intro_prefix": "താങ്കൾ അന്വേഷിക്കുന്നത്"
    },
    "Tamil": {
        "ask_name": "நன்றி! உங்கள் பெயர் என்ன? (What is your name?)",
        "ask_product": "நன்றி! எந்த தயாரிப்பு பற்றி நீங்கள் அறிய விரும்புகிறீர்கள்? (e.g., Sakhitone, Staamigen Malt?)",
        "confirm_switch": "நீங்கள் தமிழுக்கு மாற விரும்புகிறீர்களா? (ஆம்/இல்லை)",
        "intro_prefix": "நீங்கள் விசாரிப்பது"
    },
    "Hindi": {
        "ask_name": "धन्यवाद! आपका शुभ नाम क्या है?",
        "ask_product": "धन्यवाद! आप किस उत्पाद के बारे में जानना चाहते हैं? (e.g., Sakhitone, Staamigen Malt?)",
        "confirm_switch": "क्या आप हिंदी में बात करना चाहते हैं? (हाँ/नहीं)",
        "intro_prefix": "आप पूछताछ कर रहे हैं"
    },
    "Kannada": {
        "ask_name": "ಧನ್ಯವಾದ! ನಿಮ್ಮ ಹೆಸರೇನು?",
        "ask_product": "ಧನ್ಯವಾದ! ನೀವು ಯಾವ ಉತ್ಪನ್ನದ ಬಗ್ಗೆ ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ?",
        "confirm_switch": "ನೀವು ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಲು ಬಯಸುವಿರಾ?",
        "intro_prefix": "ನೀವು ಕೇಳುತ್ತಿದ್ದೀರಿ"
    },
    "Telugu": {
        "ask_name": "ధన్యవాదాలు! మీ పేరు ఏమిటి?",
        "ask_product": "ధన్యవాదాలు! మీరు ఏ ఉత్పత్తి గురించి తెలుసుకోవాలనుకుంటున్నారు?",
        "confirm_switch": "మీరు తెలుగుకు మారాలనుకుంటున్నారా?",
        "intro_prefix": "మీరు అడుగుతున్నారు"
    },
    "Bengali": {
        "ask_name": "ধন্যবাদ! আপনার নাম কি?",
        "ask_product": "ধন্যবাদ! আপনি কোন পণ্য সম্পর্কে জানতে চান?",
        "confirm_switch": "আপনি কি বাংলায় কথা বলতে চান?",
        "intro_prefix": "আপনি জিজ্ঞাসা করছেন"
    }
}

# --- PRODUCT INTRO SCRIPTS (Bilingual Support) ---
PRODUCT_INTROS = {
    "sakhitone": {
        "English": "Sakhi Tone, specifically designed to help women improve body weight and figure naturally.",
        "Malayalam": "സ്ത്രീകൾക്ക് ശരീരഭാരവും ശരീരസൗന്ദര്യവും മെച്ചപ്പെടുത്താൻ സപ്പോർട്ട് ചെയ്യുന്ന സഖിടോണിനെ പറ്റിയാണ്.",
        "Tamil": "பெண்களின் உடல் எடை மற்றும் தோற்றத்தை மேம்படுத்த உதவும் சகி டோன் பற்றி.",
        "Hindi": "सखी टोन के बारे में, जो महिलाओं को वजन और फिगर बढ़ाने में मदद करता है।"
    },
    "staamigen": {
        "English": "Staamigen Malt, designed to help men build muscle and healthy weight.",
        "Malayalam": "പുരുഷന്മാർക്ക് ശരീരഭാരവും മസിലും വർധിപ്പിക്കാൻ സഹായിക്കുന്ന സ്റ്റാമിജൻ മാൾട്ടിനെ പറ്റിയാണ്.",
        "Tamil": "ஆண்களுக்கு தசை மற்றும் எடையை அதிகரிக்க உதவும் ஸ்டாமிஜென் மால்ட் பற்றி.",
        "Hindi": "स्टैमिजेन माल्ट के बारे में, जो पुरुषों को वजन बढ़ाने में मदद करता है।"
    },
    "gain": {
        "English": "Ayurdan Gain Plus, an appetite restorer to help you eat well and build a healthy body.",
        "Malayalam": "വിശപ്പ് വർധിപ്പിക്കാനും അതുവഴി ശരീരഭാരം കൂട്ടാനും സഹായിക്കുന്ന ആയുർദാൻ ഗെയിൻ പ്ലസിനെക്കുറിച്ചാണ്.",
        "Tamil": "பசியைத் தூண்டி, உடல் எடையை அதிகரிக்க உதவும் ஆயுர்தான் கெயின் பிளஸ் பற்றி."
    }
}

# VOICE REJECTION
VOICE_REPLIES = {
    "English": "Sorry, I cannot listen to voice notes. Please type your message. 🙏",
    "Malayalam": "ക്ഷമിക്കണം, എനിക്ക് വോയിസ് മെസേജ് കേൾക്കാൻ കഴിയില്ല. ദയവായി ടൈപ്പ് ചെയ്യാമോ? 🙏",
    "Tamil": "மன்னிக்கவும், என்னால் ஆடியோ கேட்க முடியாது. தயவுசெய்து டைப் செய்யவும். 🙏",
    "Hindi": "क्षमा करें, मैं वॉयस नोट नहीं सुन सकता। कृपया टाइप करें। 🙏",
    "Kannada": "ಕ್ಷಮಿಸಿ, ನಾನು ಧ್ವನಿ ಸಂದೇಶಗಳನ್ನು ಕೇಳಲು ಸಾಧ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಟೈಪ್ ಮಾಡಿ. 🙏",
    "Telugu": "క్షమించండి, నేను వాయిస్ మెసేజ్ వినలేను. దయచేసి టైప్ చేయండి. 🙏",
    "Bengali": "দুঃখিত, আমি ভয়েস মেসেজ শুনতে পাই না। দয়া করে লিখে পাঠান। 🙏"
}

# --- MALAYALAM SCRIPTS (Legacy/Fallback) ---
M_SCRIPTS = {
    "ask_doubts": "താങ്കളുടെ സംശയങ്ങൾ എന്താണെങ്കിലും ഇപ്പോൾ ആത്മവിശ്വാസത്തോടു കൂടി ഞങ്ങളോട് ചോദിച്ചോളൂ.",
    "collect_data": "കൂടുതൽ കൃത്യമായ നിർദ്ദേശങ്ങൾക്കായി ദയവായി താങ്കളുടെ **പ്രായം, ഉയരം, ഭാരം (Age, Height, Weight)** എന്നിവ പറയുക.",
    "underweight_msg": "{name}, നിങ്ങൾക്ക് ആവശ്യമുള്ളതിലും {diff}kg കുറവാണെന്ന കാര്യം താങ്കൾ മനസ്സിലാക്കിയിട്ടുണ്ടോ? ഇത്രയും kg കുറയാൻ ഉള്ള കാരണം എന്താണെന്നാണ് താങ്കൾ മനസ്സിലാക്കുന്നത്?",
    "normalweight_msg": "{name}, നിങ്ങൾ തന്ന വിവരങ്ങൾ പ്രകാരം താങ്കൾക്ക് ഉയരത്തിനൊത്ത ശരീരഭാരം ആണല്ലോ! അപ്പോൾ എന്താണ് നേരിടുന്ന മറ്റ് ബുദ്ധിമുട്ടുകൾ എന്ന് ഞങ്ങളോട് പറയാമോ?",
    "women_health": "നിങ്ങൾക്ക് white discharge, PCOD, Thyroid, Gastric issues, Diabetes, Ulcer പോലത്തെ എന്തെങ്കിലും ബുദ്ധിമുട്ടുകളുണ്ടോ?",
    "men_health": "നിങ്ങൾക്ക് Thyroid, Diabetes, Ulcer പോലത്തെ എന്തെങ്കിലും ബുദ്ധിമുട്ടുകളോ, മദ്യപാനം, പുകവലി മറ്റും പോലെയുള്ള ദുഃശീലങ്ങൾ ഉണ്ടോ?",
    "closing_advice": "ആരോഗ്യകരമായി ശരീര ഭാരം വർധിപ്പിക്കാൻ ആഗ്രഹിക്കുന്ന ഒരാൾക്ക് ഒരു മാസം 3 മുതൽ 4 കിലോഗ്രാം വരെയാണ് പാർശ്വഫലങ്ങൾ ഒന്നുമില്ലാതെ വർധിപ്പിക്കാൻ കഴിയുന്നത്. നമ്മൾ കഴിക്കുന്ന ഭക്ഷണം ഉപയോഗിച്ച് ശരീരഭാരം കൂടുമ്പോഴാണ് അത് സ്ഥിരമായി നിലനിൽക്കുന്നത് എന്ന് തിരിച്ചറിയണം."
}

# 🛠️ AUTO-DETECT MODEL AT STARTUP
def get_working_model_name():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for model in data.get('models', []):
                m_name = model['name'].replace("models/", "")
                if "flash" in m_name and "generateContent" in model.get('supportedGenerationMethods', []):
                    return m_name
            for model in data.get('models', []):
                if "gemini" in model['name'] and "generateContent" in model.get('supportedGenerationMethods', []):
                    return model['name'].replace("models/", "")
    except Exception as e:
        logging.error(f"⚠️ MODEL INIT ERROR: {e}")
    return "gemini-1.5-flash"

ACTIVE_MODEL_NAME = get_working_model_name()

def save_to_google_sheet_thread(user_data):
    try:
        phone_clean = user_data.get('phone', '').replace("+", "")
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name", "Unknown"),
            FORM_FIELDS["phone"]: phone_clean,
            FORM_FIELDS["product"]: user_data.get("product", "Pending")
        }
        requests.post(GOOGLE_FORM_URL, data=form_data, timeout=8)
    except Exception as e:
        logging.error(f"❌ SAVE ERROR: {e}")

def save_to_google_sheet(user_data):
    # Run in separate thread to be non-blocking
    thread = threading.Thread(target=save_to_google_sheet_thread, args=(user_data,))
    thread.start()

def get_ai_reply(user_msg, product_context=None, user_name="Customer", language="English", history=[], assigned_agent=None):
    # INJECT PRODUCT CONTEXT STRONGLY
    context_instruction = ""
    if product_context and product_context != "Pending":
        context_instruction = f"IMPORTANT: The user is asking about '{product_context}'. Answer ONLY about '{product_context}' unless they explicitly ask for another product."

    full_prompt = SYSTEM_PROMPT + f"\n\n{context_instruction}\nUser: {user_name}\nLanguage: {language}\nQuery: {user_msg}"

    if assigned_agent:
        full_prompt += f"\nORDER LINK: {assigned_agent['link']} (Phone: {assigned_agent['phone']})"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{ACTIVE_MODEL_NAME}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}

    try:
        response = requests.post(url, json=payload, timeout=12)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return "Sorry, I am thinking... please ask again."
    except:
        return "Server busy. Please try again."

def parse_measurements(text):
    height_cm = 0
    weight_kg = 0
    text_lower = text.lower()

    # Height: explicit "cm" or "cms"
    cm_match = re.search(r'(\d{2,3})\s*(?:cm|cms)', text_lower)
    if cm_match:
        height_cm = int(cm_match.group(1))
    else:
        # Height: explicit ft/in or ' "
        # 1. "5.8" with explicit "ft" or "feet" following
        ft_decimal_match = re.search(r'(\d)\.(\d+)\s*(?:ft|feet)', text_lower)
        # 2. 5'8 or 5' 8"
        ft_quote_match = re.search(r'(\d)\s*[\'’]\s*(\d+)(?:\s*[\"”])?', text_lower)

        if ft_decimal_match:
             feet = int(ft_decimal_match.group(1))
             inches = int(ft_decimal_match.group(2))
             height_cm = int((feet * 30.48) + (inches * 2.54))
        elif ft_quote_match:
             feet = int(ft_quote_match.group(1))
             inches = int(ft_quote_match.group(2))
             height_cm = int((feet * 30.48) + (inches * 2.54))

    # Weight: explicit kg, kgs, kilo
    kg_match = re.search(r'(\d{2,3})\s*(?:kg|kgs|kilo)', text_lower)
    if kg_match:
        weight_kg = int(kg_match.group(1))
    return height_cm, weight_kg

@app.route("/bot", methods=["POST"])
def bot():
    incoming_msg = request.values.get("Body", "").strip()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")
    num_media = int(request.values.get("NumMedia", 0))

    resp = MessagingResponse()

    if sender_phone not in user_sessions:
         detected_product = "Pending"
         incoming_lower = incoming_msg.lower()

         # Enhanced Product Detection Logic
         matches = []
         for key in PRODUCT_IMAGES.keys():
             if key in incoming_lower:
                 matches.append(key)

         if matches:
             # Specific keywords to prioritize
             specific_keywords = ["malt", "powder", "junior", "kids", "sakhi", "diabet", "gain", "hair", "pain"]
             best_match = None
             for m in matches:
                 if any(s in m for s in specific_keywords):
                     best_match = m
                     break

             detected_product = best_match if best_match else matches[0]

         # global global_agent_counter  <-- DISABLED ROTATION
         current_agent = AGENTS[0] # <-- FORCED AGENT 1
         # global_agent_counter += 1

         user_sessions[sender_phone] = {
             "step": "ask_language",
             "data": {"wa_number": sender_phone, "phone": sender_phone, "language": "English", "product": detected_product},
             "agent": current_agent,
             "consultation_state": "none",
             "history": []
         }
         msg = resp.message()
         msg.body("Namaste! Welcome to Alpha Ayurveda Assistant. 🙏\n\nPlease select your preferred language:\n1️⃣ English\n2️⃣ Malayalam (മലയാളം)\n3️⃣ Tamil (தமிழ்)\n4️⃣ Hindi (हिंदी)\n5️⃣ Kannada (ಕನ್ನಡ)\n6️⃣ Telugu (తెలుగు)\n7️⃣ Bengali (বাংলা)\n\n*(Reply with 1, 2, 3...)*")
         return Response(str(resp), mimetype="application/xml")

    session = user_sessions[sender_phone]
    step = session["step"]

    # 🔄 DYNAMIC LANGUAGE SWITCHER
    if session.get("step") == "confirm_lang":
        if "yes" in incoming_msg.lower() or "ok" in incoming_msg.lower():
            session["data"]["language"] = session.get("pending_lang")
            session["step"] = "consultation_active"
            msg = resp.message()
            msg.body(f"✅ Language changed to {session['data']['language']}. How can I help you?")
            return Response(str(resp), mimetype="application/xml")
        else:
            session["step"] = "consultation_active"

    for lang_name in LANGUAGES.values():
        if lang_name.lower() in incoming_msg.lower() and lang_name != session["data"]["language"]:
            session["pending_lang"] = lang_name
            session["step"] = "confirm_lang"
            msg = resp.message()
            msg.body(f"Do you want me to talk in {lang_name} from now? (Yes/No)")
            return Response(str(resp), mimetype="application/xml")

    # 🔄 SMART PRODUCT CONTEXT SWITCHER
    incoming_lower = incoming_msg.lower()
    current_product_key = session["data"].get("product", "")

    if current_product_key not in incoming_lower:
        for key in PRODUCT_IMAGES.keys():
            if key in incoming_lower and key != current_product_key:
                session["data"]["product"] = key
                session["step"] = "consultation_active"
                session["consultation_state"] = "intro"
                return run_consultation_flow(session, incoming_msg, resp)

    # RESET
    if incoming_msg.lower() in ["reset", "restart"]:
        del user_sessions[sender_phone]
        msg = resp.message()
        msg.body("🔄 Reset. Say Hi.")
        return Response(str(resp), mimetype="application/xml")

    # MEDIA CHECK
    if num_media > 0:
        msg = resp.message()
        msg.body(VOICE_REPLIES.get(session["data"].get("language", "English"), VOICE_REPLIES["English"]))
        return Response(str(resp), mimetype="application/xml")

    # --- FLOW LOGIC ---

    # 1. LANGUAGE SELECTION
    if step == "ask_language":
        selection = incoming_msg.strip()
        selected_lang = LANGUAGES.get(selection, "English")
        for key, val in LANGUAGES.items():
            if val.lower() in selection.lower() or key in selection:
                selected_lang = val
                break
        session["data"]["language"] = selected_lang
        session["step"] = "ask_name"

        # FIX: Reply in the selected language using Dictionary
        msg = resp.message()
        msg_text = UI_STRINGS.get(selected_lang, UI_STRINGS["English"])["ask_name"]
        msg.body(msg_text)
        return Response(str(resp), mimetype="application/xml")

    # 2. NAME & PRODUCT ROUTING
    elif step == "ask_name":
        session["data"]["name"] = incoming_msg
        save_to_google_sheet(session["data"])

        prod = session["data"]["product"]

        # AMBIGUITY CHECK
        if "staamigen" in prod and "malt" not in prod and "powder" not in prod:
             session["step"] = "resolve_staamigen"
             msg = resp.message()
             msg.body("We have Staamigen Malt (Men) & Staamigen Powder (Teenagers). Which one?")
             return Response(str(resp), mimetype="application/xml")

        # AD LEAD
        if prod != "Pending":
            session["step"] = "consultation_active"
            session["consultation_state"] = "intro"
            return run_consultation_flow(session, incoming_msg, resp)
        else:
            # DIRECT MSG - FIX: Ask in correct language
            session["step"] = "ask_product_manual"
            msg = resp.message()
            lang = session["data"]["language"]
            msg_text = UI_STRINGS.get(lang, UI_STRINGS["English"])["ask_product"]
            msg.body(msg_text)
            return Response(str(resp), mimetype="application/xml")

    # 3. RESOLVE AMBIGUITY
    elif step == "resolve_staamigen":
        if "malt" in incoming_msg.lower():
            session["data"]["product"] = "staamigen malt"
        elif "powder" in incoming_msg.lower():
            session["data"]["product"] = "staamigen powder"
        else:
            session["data"]["product"] = "staamigen malt"

        session["step"] = "consultation_active"
        session["consultation_state"] = "intro"
        return run_consultation_flow(session, incoming_msg, resp)

    # 4. MANUAL PRODUCT ENTRY
    elif step == "ask_product_manual":
        found = False
        for key in PRODUCT_IMAGES.keys():
            if key in incoming_msg.lower():
                session["data"]["product"] = key
                found = True
                break
        if not found:
            session["data"]["product"] = "general"

        save_to_google_sheet(session["data"])
        session["step"] = "consultation_active"
        session["consultation_state"] = "intro"
        return run_consultation_flow(session, incoming_msg, resp)

    # 5. CONSULTATION LOOP
    elif step == "consultation_active":
        return run_consultation_flow(session, incoming_msg, resp)

    return Response(str(resp), mimetype="application/xml")

# --- 🧠 THE CONSULTATION ENGINE ---
def run_consultation_flow(session, user_text, resp):
    state = session["consultation_state"]
    product = session["data"]["product"]
    name = session["data"]["name"]
    lang = session["data"]["language"]

    # ONLY TRIGGER FOR WEIGHT GAIN PRODUCTS
    weight_products = ["sakhi", "malt", "powder", "staamigen", "gain", "strength"]
    is_weight_flow = any(x in product for x in weight_products)

    if not is_weight_flow:
        ai_reply = get_ai_reply(user_text, product, name, lang, session["history"], session["agent"])
        msg = resp.message()
        msg.body(ai_reply)
        return Response(str(resp), mimetype="application/xml")

    # PHASE 1: INTRO (Step-by-Step Fix)
    if state == "intro":
        msg = resp.message()

        # Send Image
        for key, url in PRODUCT_IMAGES.items():
            if key in product:
                msg.media(url)
                break

        # Send Dynamic Intro Text based on Language
        # AI will generate a polite intro if specific script is missing
        intro_text = ""
        if "sakhi" in product:
            intro_text = PRODUCT_INTROS["sakhitone"].get(lang, PRODUCT_INTROS["sakhitone"]["English"])
        elif "malt" in product:
            intro_text = PRODUCT_INTROS["staamigen"].get(lang, PRODUCT_INTROS["staamigen"]["English"])
        else:
            # Fallback to AI for intro
            intro_text = get_ai_reply("Give a 1 sentence intro about " + product, product, name, lang, [], None)

        msg.body(intro_text)

        session["consultation_state"] = "waiting_for_doubts"
        return Response(str(resp), mimetype="application/xml")

    # PHASE 2: HANDLE DOUBTS
    elif state == "waiting_for_doubts":
        h, w = parse_measurements(user_text)
        if h > 0 and w > 0:
             return calculate_bmi_reply(h, w, name, product, resp, session)

        ai_reply = get_ai_reply(user_text, product, name, lang, session["history"], session["agent"])
        msg = resp.message()
        msg.body(ai_reply)

        # Ask for measurements only if not given
        # msg2 = resp.message()
        # msg2.body("To give you the best dosage, tell me your Age, Height & Weight.")

        session["consultation_state"] = "waiting_for_measurements"
        return Response(str(resp), mimetype="application/xml")

    # PHASE 3: CALCULATE
    elif state == "waiting_for_measurements":
        h, w = parse_measurements(user_text)

        if h > 0 and w > 0:
            return calculate_bmi_reply(h, w, name, product, resp, session)
        else:
            ai_reply = get_ai_reply(user_text, product, name, lang, session["history"], session["agent"])
            msg = resp.message()
            msg.body(ai_reply)
            return Response(str(resp), mimetype="application/xml")

    # PHASE 4: CLOSING
    elif state == "health_check":
        ai_reply = get_ai_reply(user_text, product, name, lang, session["history"], session["agent"])
        msg = resp.message()
        msg.body(ai_reply)
        session["consultation_state"] = "chat_open"
        return Response(str(resp), mimetype="application/xml")

    # PHASE 5: OPEN CHAT
    else:
        ai_reply = get_ai_reply(user_text, product, name, lang, session["history"], session["agent"])
        msg = resp.message()
        msg.body(ai_reply)
        return Response(str(resp), mimetype="application/xml")

def calculate_bmi_reply(h, w, name, product, resp, session):
    rbw = h - 100
    diff = rbw - w

    msg = resp.message()

    if w < rbw:
        txt = f"{name}, You are underweight by {diff}kg. We need to fix your metabolism."
        msg.body(txt)
    else:
        txt = f"{name}, Your weight is normal. You can use this for fitness."
        msg.body(txt)

    msg_health = resp.message()
    if "sakhi" in product:
        msg_health.body("Do you have thyroid or period issues?")
    elif "malt" in product:
        msg_health.body("Do you smoke or have gastric issues?")
    else:
        msg_health.body("Any other health issues?")

    session["consultation_state"] = "health_check"
    return Response(str(resp), mimetype="application/xml")

@app.route("/")
def wake_up():
    return "Bot is awake!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
