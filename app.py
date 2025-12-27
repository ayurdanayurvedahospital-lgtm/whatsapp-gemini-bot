import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- HEALTH CHECK ---
@app.route("/", methods=["GET"])
def home():
    return "Alpha Ayurveda Bot is Alive! 🤖", 200

# --- THE BRAIN ---
SYSTEM_PROMPT = """
You are the "Alpha Ayurveda Expert". 
You are NOT a doctor. You are a knowledgeable wellness guide.

--- RULES ---
1. BREVITY: Answer ONLY what is asked. Keep it under 40 words.
2. TYPO HANDLING: "Sahitone" -> Sakhi Tone. "Vrinda" -> Vrindha Tone.
3. DISCLAIMER: Always end with: "Note: I am an Ayurvedic expert, not a doctor."
4. LANGUAGE: Reply in the user's language (Malayalam/English).

--- PRODUCTS ---
1. Staamigen Malt (Men) - ₹749. Weight gain.
2. Sakhi Tone (Women) - ₹749. Weight gain.
3. Junior Malt (Kids) - ₹599. Growth.
4. Ayur Diabet - ₹690. Sugar control.
5. Vrindha Tone - ₹440. White discharge.
6. Muktanjan Oil - ₹295. Pain.
7. Hair Oil - ₹845. Hair fall.
8. Medi Gas - ₹585. Gas.

--- CONTACT ---
- Phone: +91 80781 78799
- Website: https://ayuralpha.in/
"""

def get_working_model():
    # Ask Google which models are available for this Key
    url = f"https://generativelanguage.googleapis.com/v1/models?key={API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            models = response.json().get('models', [])
            # Priority list: Look for Flash, then Pro, then anything else
            for m in models:
                name = m['name'].replace("models/", "")
                if "flash" in name: return name
            for m in models:
                name = m['name'].replace("models/", "")
                if "pro" in name: return name
            # If no preference found, just take the first one
            if models: return models[0]['name'].replace("models/", "")
    except:
        pass
    # Fallback if auto-detection fails
    return "gemini-pro"

def try_generate(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg
    
    # 1. Find a valid model name
    model_name = get_working_model()
    print(f"Attempting to use model: {model_name}")

    # 2. Construct the URL dynamically
    url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={API_KEY}"
    
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"GOOGLE ERROR ({model_name}): {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"CONNECTION ERROR: {e}")
        return None

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")
    
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("Namaste! I am the Alpha Ayurveda Expert.")
        return str(resp)

    bot_reply = try_generate(user_msg)

    if bot_reply:
        msg.body(bot_reply)
    else:
        # If this happens, check logs to see which model failed
        msg.body("System Error: Unable to access AI models. Please check logs.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
