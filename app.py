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

# ⚠️ FORM FIELDS MUST BE "SHORT ANSWER" IN GOOGLE FORMS
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScyMCgip5xW1sZiRrlNwa14m_u9v7ekSbIS58T5cE84unJG2A/formResponse"

FORM_FIELDS = {
    "name": "entry.2005620554",
    "phone": "entry.1117261166",
    "product": "entry.839337160"
}

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

user_sessions = {}

SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. **CONTENT:** Provide **Benefits ONLY** (English & Malayalam).
2. **RESTRICTIONS:** Do **NOT** mention Usage/Dosage or Price unless asked.
3. **LENGTH:** Keep it SHORT (Under 100 words).
4. **FORMATTING:** Use Single Asterisks (*) for bold.
5. **MEDICAL DISCLAIMER:** If asked about medical prescriptions/diseases, state: "I am not a doctor. Please consult a qualified doctor for medical advice."
6. **STRICT INGREDIENTS:** If asked about ingredients, use the **EXACT LIST** below.

*** 🌿 STRICT INGREDIENT LIST 🌿 ***
1. **JUNIOR STAAMIGEN MALT:** Satavari, Brahmi, Abhaya (Haritaki), Sunti (Dry Ginger), Maricham (Black Pepper), Pippali (Long Pepper), Sigru (Moringa), Vidangam, Honey.
2. **SAKHI TONE:** Jeeraka (Cumin), Satahwa (Dill), Pippali, Draksha (Grapes), Vidari, Sathavari, Ashwagandha.
3. **STAAMIGEN MALT:** Ashwagandha, Draksha, Jeevanthi, Honey, Ghee, Sunti, Vidarikand, Gokshura.
4. **AYUR DIABET:** Amla, Meshashringi, Jamun Seeds, Turmeric, Fenugreek.

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

*** 📄 OFFICIAL KNOWLEDGE BASE ***
--- SECTION 1: ABOUT US & LEGACY ---
Brand Name: Alpha Ayurveda (Online Division of Ayurdan Ayurveda Hospital).
Founder: Late Vaidyan M.K. Pankajakshan Nair (Founded 60 years ago).
Heritage: Manufacturing division of Ayurdan Hospital, Pandalam.
Mission: "Loka Samasta Sukhino Bhavantu".
Certifications: AYUSH Approved, ISO, GMP, HACCP.

--- SECTION 2: CONTACT INFORMATION ---
Phone: +91 9072727201 | Email: alphahealthplus@gmail.com
Address: Alpha Ayurveda, Ayurdan Ayurveda Hospital, Valiyakoikkal Temple Road, Pandalam, Kerala - 689503.

--- SECTION 3: SHIPPING & RETURNS ---
Dispatch: Within 24 hours.
Shipping: Free above ₹599.
Returns: No returns due to hygiene. Exchange allowed only for damaged goods (contact within 2 days).

*** KNOWLEDGE BASE (MALAYALAM) ***
1. സ്റ്റാമിജൻ മാൾട്ട് (Staamigen Malt): പുരുഷന്മാർക്ക് ശരീരഭാരവും, മസിലും, കരുത്തും വർദ്ധിപ്പിക്കാൻ. ഗുണങ്ങൾ: വിശപ്പ് വർദ്ധിപ്പിക്കുന്നു, ദഹനശക്തി (Agni) മെച്ചപ്പെടുത്തുന്നു.
2. സഖി ടോൺ (Sakhi Tone): സ്ത്രീകൾക്ക് ശരീരഭാരം കൂട്ടാനും ഹോർമോൺ പ്രശ്നങ്ങൾ പരിഹരിക്കാനും. ഗുണങ്ങൾ: രക്തക്കുറവ് (Anemia) പരിഹരിക്കുന്നു.
3. ജൂനിയർ സ്റ്റാമിജൻ മാൾട്ട് (Junior Staamigen Malt): കുട്ടികളുടെ വളർച്ചയ്ക്കും, വിശപ്പിനും, പ്രതിരോധശേഷിക്കും.
4. ആയുർ ഡയബെറ്റ് (Ayur Diabet): പ്രമേഹം നിയന്ത്രിക്കാനും അനുബന്ധ പ്രശ്നങ്ങൾ കുറയ്ക്കാനും.
5. വൃന്ദ ടോൺ (Vrindha Tone): വെള്ളപോക്ക് (White Discharge), ശരീരത്തിലെ അമിത ചൂട് എന്നിവയ്ക്ക്.

*** OFFLINE STORE LIST (KERALA - FULL) ***
[Thiruvananthapuram]: Guruvayoorappan Agencies (West Fort), Sreedhari (Secretariat), Vishnu Medicals (Varkala), Shabnam (Attingal), Sasikala (Kattakkada), Krishna (Neyyattinkara), Karunya (Kesavadasapuram).
[Kollam]: AB Agencies (District Hospital), Western (Chinnakkada), A&A (Chavara), Krishna (Karunagapally), Karunya (Ochira), Bombay (Kundara), Peniyel (Kottarakkara), Marry (Punalur).
[Pathanamthitta]: Ayurdan Hospital (Pandalam), Benny (KSRTC), Nagarjuna (Bus Stand), Divine (Central Jn), Simon George (Hospital), Aswini (Bus Stand), Puloor (Kozhencherry), Durga (Thiruvalla), JJ (Adoor).
[Alappuzha]: Nagarjuna (Iron Bridge), Archana (MCH), Sreeja (Boat Jetty), Ayikattu (Kayamkulam), Kariyil (Cherthala), NNS (Mavelikkara), Anaswara (Chengannur).
[Kottayam]: Elsa (Sastri Rd), Mavelil (Changanassery), Shine (Erumeli), City (Kanjirapally), Hilda (Ponkunnam), Riya (Pala), Seetha (Vaikom).
[Idukki]: Vaidyaratnam (Thodupuzha), Sony (Adimaly), Jolly (Kattappana).
[Ernakulam]: Soniya (Vytila), Ojus (Edappally), Nakshathra (Kuruppampady), Aravind (Kaladi), Thomson (Perumbavoor), Jacob (Angamaly), Anjali (Paravoor), Mangot (Muvattupuzha).
[Thrissur]: Siddhavaydyasramam (Shornur Rd), Kandamkulathy (Naikkanal), Grace (Pallikulam), Sreepharma (Mala), Sastha (Vadakkancherry), Kollannur (Kunnamkulam), KMA (Guruvayoor).
[Palakkad]: Palakkad Agencies (Bus Stand), Shifa (Shornur), Madhura (Ottappalam), Aravind (Mannarkadu), Teekay (Pattambi).
[Malappuram]: ET Oushadhashala (Bus Stand), CIMS (Up Hill), Shanthi (Govt Hospital), Central (Manjeri), Mangalodayam (Tirur), Thangals (Perinthalmanna), Sanjeevani (Ponnani), National (Kuttippuram), Pulse (Areacode), Al Bayan (Nilamboor).
[Kozhikode]: Dhanwanthari (Kallai Rd), Sobha (Palayam), PRC (New Bus Stand), EP (Mankavu), National (Feroke), New Vadakara (Vadakara).
[Wayanad]: Jeeva (Kalpetta), Reena (Mananthavady), Janapriya (Panamaram), Nicol (Sulthan Bathery).
[Kannur]: Lakshmi (Caltex), Falcon (KSRTC), Jayasree (Stadium), Coimbathore (Thalassery), Perumba (Payyannur), Nagarjuna (Mattannur).
[Kasaragod]: Bio (Bus Stand), VJ (Thrikkarippur), Maithri (Neeleswaram), Malabar (Kanhangad), Indian (Kasaragod), Kerala (Kumbala).

*** EXTENSIVE Q&A (FULL) ***
Q: Can Sakhi Tone control White Discharge? A: No, treat with Vrindha Tone first.
Q: Is Sakhi Tone good for Body Shaping? A: Yes, for weight gain. Workouts help shape.
Q: Can recovered Hepatitis/Stroke patients take this? A: Yes, after liver function is normal.
Q: Will it cause Diabetes? A: No.
Q: Will I lose weight if I stop? A: No, if diet is maintained.
Q: Can I take this with Arthritis medicine? A: Yes.
Q: Can I take this with Fatty Liver? A: Only under doctor's advice.
Q: Can Thyroid patients take this? A: Yes, helps fatigue, but consult doctor.
Q: How many bottles to gain 5kg? A: 2-3 bottles average.
Q: Can breastfeeding mothers take this? A: Yes, after 3-4 months.
Q: Can heart/BP patients take this? A: Consult doctor.
Q: Will it increase breast size? A: It provides overall body fitness.
Q: Can women take Staamigen Malt? A: Staamigen Malt is for men, Sakhi Tone for women.
Q: Does it work for genetically thin people? A: Yes, but consult doctor.
Q: Does Ayur Diabet reduce sugar? A: Yes, helps manage levels.
Q: Can I take Ayur Diabet with Insulin? A: Yes, but consult doctor for dosage changes.
Q: Is it good for learning disability? A: Supports brain development and energy.
Q: Does Junior Malt help constipation? A: Yes, regulates digestion.
"""

def save_to_google_sheet(user_data):
    try:
        # Clean phone number (Remove + to satisfy Google Form if validation is on)
        phone_clean = user_data.get('phone', '').replace("+", "")
        
        form_data = {
            FORM_FIELDS["name"]: user_data.get("name", "Unknown"),
            FORM_FIELDS["phone"]: phone_clean, 
            FORM_FIELDS["product"]: user_data.get("product", "Pending")
        }
        
        # Send data
        response = requests.post(GOOGLE_FORM_URL, data=form_data, timeout=8)
        
        if response.status_code == 200:
            print(f"✅ DATA SAVED for {user_data.get('name')}")
        else:
            print(f"❌ GOOGLE REJECT: {response.status_code}. CHECK FORM VALIDATION!")
            
    except Exception as e:
        print(f"❌ SAVE ERROR: {e}")

# 🔴 NEW FUNCTION: AUTO-DETECT WORKING MODEL
def get_dynamic_model():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Look for ANY valid Gemini model
            for model in data.get('models', []):
                m_name = model['name'].replace("models/", "")
                if "gemini" in m_name and "generateContent" in model.get('supportedGenerationMethods', []):
                    return m_name
    except:
        pass
    # Fallback if detection fails
    return "gemini-1.5-flash"

def get_ai_reply(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg
    
    # 🔴 STEP 1: Auto-Detect the correct model name
    model_name = get_dynamic_model()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    for attempt in range(2): 
        try:
            print(f"🤖 Using Auto-Detected Model: {model_name}")
            response = requests.post(url, json=payload, timeout=12)
            
            if response.status_code == 200:
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                return text
            else:
                print(f"⚠️ API ERROR: {response.status_code} - {response.text}")
                time.sleep(1)
        except Exception as e:
            print(f"⚠️ CONNECTION ERROR: {e}")
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
        msg.body("Thank you! Which product would you like to know about? (e.g., Staamigen, Sakhi Tone?)")

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

        ai_reply = get_ai_reply(incoming_msg)
        if ai_reply: ai_reply = ai_reply.replace("**", "*")
        if len(ai_reply) > 1000: ai_reply = ai_reply[:1000] + "..."
        msg.body(ai_reply)

    return Response(str(resp), mimetype="application/xml")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
