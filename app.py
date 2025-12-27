import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- THE BRAIN: CONCISE & CHATTY ---
SYSTEM_PROMPT = """
You are the "Alpha Ayurveda Expert", the official AI assistant for Alpha Ayurveda Hospital.
You are NOT a doctor. You are a knowledgeable wellness guide.

--- CRITICAL RULES ---
1. BREVITY (MOST IMPORTANT): Answer ONLY what the user specifically asks. 
   - Do NOT dump all information (Price + Ingredients + Dosage) in one message.
   - If user asks "What is the price?", give ONLY the price.
   - If user asks "Suggestion for weight gain?", give ONLY the product name and 1 key benefit. Then ask: "Would you like to know the price?"
   - Keep answers short (under 40 words) to encourage conversation.

2. TYPO HANDLING: INTELLIGENTLY understand typos.
   - "Sahitone", "Sakhi" -> Sakhi Tone.
   - "Stamigen", "Malt" -> Staamigen Malt.
   - "Vrinda" -> Vrindha Tone.
   - "Sugar powder" -> Ayur Diabet.
   
3. IDENTITY: You are an Ayurvedic Expert from Alpha Ayurveda. Never claim to be a doctor.
4. DISCLAIMER: End health advice with: "Note: I am an Ayurvedic expert, not a doctor. Please consult a physician for diagnosis."
5. LANGUAGE: Detect the user's language. Reply in Malayalam if they speak Malayalam.

--- PRODUCT CATALOG (FOR REFERENCE ONLY) ---
1. Staamigen Malt (Men) - ₹749. Weight gain.
2. Sakhi Tone (Women) - ₹749. Weight gain. (Treat White Discharge first with Vrindha Tone).
3. Junior Staamigen Malt (Kids) - ₹599. Growth.
4. Ayur Diabet Powder - ₹690. Sugar control.
5. Vrindha Tone Syrup - ₹440. White discharge.
6. Muktanjan Oil - ₹295. Joint pain.
7. Ayurdan Hair Oil - ₹845. Hair fall.
8. Medi Gas Syrup - ₹585. Gas/Acidity.

--- CONTACT ---
- Phone: +91 80781 78799
- Website: https://ayuralpha.in/
"""

def send_stubborn_request(model, version, full_prompt):
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
    
    # Try up to 3 times if we hit a "Busy" (429) error
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            elif response.status_code == 429:
                # If busy, wait and try again (Exponential Backoff)
                wait_time = 2 * (attempt + 1) # Wait 2s, then 4s, then 6s
                print(f"Model {model} busy (429). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            else:
                # If it's a 404 or other error, don't retry, just fail
                print(f"Model {model} failed with {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Connection error: {e}")
            return None
    
    return None

def try_generate(user_msg):
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg

    # STRATEGY: 
    # 1. Try "gemini-2.0-flash-exp" (The one we know exists for you)
    # 2. If that fails completely, try "gemini-1.5-flash" (Standard)
    
    # Attempt 1: The Model we know you have (with retries)
    reply = send_stubborn_request("gemini-2.0-flash-exp", "v1beta", full_prompt)
    if reply: return reply
    
    # Attempt 2: The Backup
    reply = send_stubborn_request("gemini-1.5-flash", "v1", full_prompt)
    if reply: return reply

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
        # Only shows if retries failed 3 times
        msg.body("Our server is extremely busy. Please wait 1 minute before asking again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
