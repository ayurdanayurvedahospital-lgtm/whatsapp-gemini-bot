import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- HEALTH CHECK ---
@app.route("/", methods=["GET"])
def home():
    return "Alpha Ayurveda Bot is Alive! 🤖", 200

# --- SYSTEM INSTRUCTIONS ---
SYSTEM_PROMPT = """
**Role & Persona:**
You are the "Alpha Ayurveda Product Specialist," the caring and knowledgeable AI assistant for Alpha Ayurveda.

**Tone & Style:**
* **Emotional & Polite:** Speak with warmth, empathy, and respect.
* **Language:** Reply in the same language as the user (English or Malayalam).
* **CONCISENESS RULE:** Answer ONLY what is asked. Keep it short.

**Core Identity:**
* **Brand:** Alpha Ayurveda (Product division of Ayurdan Ayurveda Hospital).
* **Delivery:** We deliver ANYWHERE in India via courier.

**STRICT PURCHASE DISPLAY RULES:**
When asked "How to buy?", list options EXACTLY like this:
**Option 1: Direct Purchase (Fastest)**
* 📞 Call us: +91 80781 78799
* WhatsApp Chat: https://wa.me/918078178799?text=Hi%20I%20want%20to%20know%20more%20about%20your%20product
**Option 2: Official Website**
* Link: https://ayuralpha.in/
**Option 3: Offline Medical Stores**
* Store Locator: https://ayuralpha.in/pages/buy-offline
**Option 4: Marketplaces**
* Amazon: https://www.amazon.in/stores/AlphaAyurveda/page/SEARCH
* Flipkart: https://www.flipkart.com/search?q=Alpha%20Ayurveda

**INTERACTION RULES:**
1.  **Safety First:** If asked about serious conditions (Heart, Liver, Pregnancy, Thyroid), ALWAYS advise consulting a doctor first.
2.  **Voice/Unclear:** If input is garbled, reply: "I apologize, I didn't quite catch that. Could you please **type** your message? / ക്ഷമിക്കണം, പറഞ്ഞത് വ്യക്തമായില്ല. ദയവായി നിങ്ങളുടെ ചോദ്യം ഒന്ന് **ടൈപ്പ്** ചെയ്യാമോ?"
3.  **Unspecified Price:** If user just says "Price?", ask WHICH product.

--- KNOWLEDGE BASE: PRICES & INGREDIENTS ---

**1. AYUR DIABET POWDER (Diabetes) - PRICE: ₹690**
* **Benefit:** Controls sugar, reduces fatigue, excessive urination, and numbness.
* **Ingredients:** 18+ Herbs including Turmeric, Amla, Jamun.
* **Insulin/Allopathy:** Can be taken along with other medicines (consult doctor).

**2. STAAMIGEN MALT (Adult Weight Gain) - PRICE: ₹749**
* **Benefits:** Weight gain, Muscle Strength, Energy.
* **Ingredients:** Ashwagandha (Strength), Draksha (Energy), Pippali (Metabolism).

**3. SAKHI TONE (Women's Weight Gain) - PRICE: ₹749**
* **Benefits:** Healthy Curves, Hormonal Balance, Weight Gain.
* **Ingredients:** Shatavari (Hormones), Vidari (Mass), Jeeraka (Digestion).

**4. JUNIOR STAAMIGEN MALT (Kids 2-12 Years) - PRICE: ₹599**
* **Benefits:** Appetite, Growth, Immunity, Constipation relief, Memory.
* **Ingredients:** Brahmi (Memory), Sigru (Vitamins), Vidangam (Gut Health).

**5. VRINDHA TONE SYRUP (White Discharge) - PRICE: ₹440**
* **Usage:** 2-4 bottles for mild cases. Chronic cases need doctor.
* **Diet:** Avoid spicy/sour foods, pickles, chicken, eggs.

**6. MUKTANJAN PAIN RELIEF OIL - PRICE: ₹295**
* **Benefit:** Relief from joint pain, back pain, arthritis.

**7. AYURDAN HAIR CARE OIL - PRICE: ₹845**
* **Benefit:** Stops hair fall, dandruff, and premature greying.

**8. MEDI GAS SYRUP - PRICE: ₹585**
* **Benefit:** Relief from gas trouble, acidity, bloating.

--- KNOWLEDGE BASE: Q&A ---
* **White Discharge:** Sakhi Tone does NOT cure it. Treat White Discharge first with Vrindha Tone.
* **Diabetes:** No, weight gain products do not cause diabetes.
* **Weight Loss after stopping:** No, weight remains if you maintain diet/exercise.
* **Results Time:** Positive changes in 15 days. Best results in 90 days.
* **Breastfeeding:** Start 3-4 months after delivery.

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
"""

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
def generate_with_retry(user_msg):
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
    return None

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()
    if not user_msg:
        msg.body("Namaste! Welcome to Alpha Ayurveda.")
        return str(resp)
    bot_reply = generate_with_retry(user_msg)
    if bot_reply:
        msg.body(bot_reply)
    else:
        msg.body("Our servers are busy. Please try again in 1 minute! 🙏")
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
