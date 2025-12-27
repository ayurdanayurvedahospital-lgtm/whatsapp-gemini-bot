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

def try_generate(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg

    # THE SURVIVAL LIST:
    # 1. gemini-1.5-flash: New & Fast. (Your key struggles with this)
    # 2. gemini-pro: The Classic. (This works on 99% of keys)
    models_to_try = ["gemini-1.5-flash", "gemini-pro"]

    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                # SUCCESS! We found a working model.
                print(f"SUCCESS using model: {model}")
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                # Log the error and loop to the next model
                print(f"Model {model} failed with error {response.status_code}. Trying next...")
                continue
                
        except Exception as e:
            print(f"Connection error on {model}: {e}")
            continue

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
        # If this shows, your API Key is completely invalid for ALL Google models.
        msg.body("System Error: API Key is invalid for all models. Please generate a new key in a new Google Cloud Project.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
