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

    # THE SHOTGUN LIST: Try all these models in order
    # If one fails (404/429), it instantly tries the next.
    model_list = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-pro",        # The Classic Stable Model (v1.0)
        "gemini-1.0-pro"
    ]

    for model in model_list:
        try:
            # We try the 'v1beta' endpoint as it supports more models
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
            
            response = requests.post(url, json=payload, timeout=8)
            
            if response.status_code == 200:
                print(f"SUCCESS with model: {model}") # Log which one worked
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"Failed {model}: {response.status_code}")
                continue # Try next model
                
        except:
            continue

    return None

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("Namaste! I am the Alpha Ayurveda Expert.")
        return str(resp)

    bot_reply = try_generate(user_msg)

    if bot_reply:
        msg.body(bot_reply)
    else:
        # If ALL models fail, then the Key is truly broken
        msg.body("System Error: No working AI models found. Please check API Key.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
