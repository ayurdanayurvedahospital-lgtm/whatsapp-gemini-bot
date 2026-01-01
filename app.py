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

# --- MEMORY STORAGE ---
user_sessions = {}

# --- SYSTEM INSTRUCTIONS (FULL DATA + CLEAN FORMATTING) ---
SYSTEM_PROMPT = """
**Role:** Alpha Ayurveda Product Specialist.
**Tone:** Warm, empathetic, polite (English/Malayalam).
**Rules:**
1. Answer CONCISELY.
2. STRICTLY follow the pricing list below.
3. **FORMATTING:** Use Single Asterisks (*) for bold text. Do NOT use double asterisks (**).
   - Correct: *Price:* ₹749
   - Wrong: **Price:** ₹749
4. If asked about serious illness (Heart, Liver, Pregnancy), suggest a doctor.
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
- **Course:** 1 bottle lasts ~15 days. Recommended: 3-4 bottles for full results.

**3. JUNIOR STAAMIGEN MALT (Kids 3-12 Years)**
- **Best For:** Kids with poor appetite, low immunity, or slow growth.
- **Benefits:** Increases hunger, boosts memory and concentration, reduces frequent sickness (fever/cold), and supports height/weight growth.
- **Key Ingredients:** Brahmi (Memory), Sigru (Moringa/Vitamins), Vidangam (Worms/Gut health), Sitopala (Taste).
- **Dosage:** 5g (1 tsp) twice a day after food. Tasty and easy to eat.

**4. AYUR DIABET POWDER (Diabetes Control)**
- **Best For:** High blood sugar, insulin resistance, diabetic fatigue.
- **Benefits:** Controls sugar spikes, reduces frequent urination, fights fatigue and numbness, protects liver/kidney.
- **Key Ingredients:** Amla, Meshashringi (The "Sugar Destroyer"), Jamun Seeds, Turmeric, Fenugreek.
- **Usage:** Mix 1 spoon (10g) in lukewarm water/milk. Take twice daily after meals.
- **Safety:** Safe to take along with allopathic medicines (leave a 30-min gap).

**5. VRINDHA TONE SYRUP (White Discharge)**
- **Best For:** White discharge, internal body heat, burning sensation.
- **Benefits:** Cools the body from within, balances acidic/heat levels, cures discharge.
- **Key Ingredients:** Cooling Ayurvedic herbs specially for 'Ushna Roga' (Heat diseases).
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
[THIRUVANANTHAPURAM] Guruvayoorappan Agencies: 9895324721, Sreedhari: 0471 2331524
[KOLLAM] AB Agencies: 9387359803, Western: 0474 2750933
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
        # We send the request and print the response status for debugging
        response = requests.post(GOOGLE_FORM_URL, data=form_data)
        if response.status_code == 200:
            print(f"✅ Data Saved for {user_data.get('name')}")
        else:
            print(f"❌ Error saving to Sheet: {response.status_code}")
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
        msg.body("Namaste! Welcome to Alpha Ayurveda. 🙏\nTo better assist you, may I know your *Name*?")
        return str(resp)

    session = user_sessions[sender_phone]
    step = session["step"]

    # 2. Capture Name -> Ask AGE
    if step == "ask_name":
        session["data"]["name"] = incoming_msg
        session["step"] = "ask_age"
        msg.body(f"Nice to meet you, {incoming_msg}. \nMay I know your *Age*?")
        return str(resp)

    # 3. Capture Age -> Ask PLACE
    elif step == "ask_age":
        session["data"]["age"] = incoming_msg
        session["step"] = "ask_place"
        msg.body("Thank you. Which *Place/District* are you from?")
        return str(resp)

    # 4. Capture Place -> Ask PHONE
    elif step == "ask_place":
        session["data"]["place"] = incoming_msg
        session["step"] = "ask_phone"
        msg.body("Please type your *Phone Number* for our doctor to contact you:")
        return str(resp)

    # 5. Capture Phone -> Ask PRODUCT
    elif step == "ask_phone":
        session["data"]["phone"] = incoming_msg
        session["step"] = "ask_product"
        msg.body("Noted. Which *Product* do you want to know about? (e.g., Staamigen, Sakhi Tone, Diabetes Powder?)")
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
