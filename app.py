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

    # SOLUTION: Use the 'v1' (Stable) URL with the standard Flash model.
    # This URL is the most compatible with new keys.
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            # If this fails, we print the FULL error message to logs
            print(f"GOOGLE ERROR: {response.status_code} - {response.text}")
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
        # If this appears, check Render logs for "GOOGLE ERROR"
        msg.body("System Error: AI Connection Failed. Please check logs.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
