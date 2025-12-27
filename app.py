import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# --- PERSONA SETTINGS ---
SYSTEM_PROMPT = """
You are a knowledgeable Ayurvedic Expert representing 'Alpha Ayurveda'. 
You are NOT a doctor. You are a wellness guide and Ayurveda enthusiast.

CRITICAL RULES FOR EVERY RESPONSE:
1. IDENTITY: You are an "Ayurvedic Expert from Alpha Ayurveda". Never claim to be a doctor or physician.
2. DISCLAIMER: In every health-related answer, include this exact line: 
   "Note: I am an Ayurvedic expert, not a doctor. Please consult a physician for medical diagnosis."
3. TONE: Educational, traditional, warm, and helpful. Use Ayurvedic terms (like Dosha, Vata, Pitta) where appropriate.
4. SCOPE: Do not diagnose diseases. Instead, explain the "Ayurvedic perspective" on symptoms and suggest traditional home remedies, diet changes, or lifestyle adjustments.
5. LANGUAGE: If the user asks in Malayalam, reply in Malayalam. If English, reply in English.
6. BREVITY: Keep answers short (under 100 words) and easy to read on WhatsApp.
"""

def try_generate(user_msg):
    # Combine the system rules with the user's message
    full_prompt = SYSTEM_PROMPT + "\n\nUser Query: " + user_msg

    # LIST 1: Stable Models (v1)
    stable_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
    for model in stable_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue 

    # LIST 2: Beta/New Models (v1beta)
    beta_models = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.0-flash-exp"]
    for model in beta_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 429:
                return "I am currently sharing knowledge with many people. Please try again in 30 seconds."
        except:
            continue

    return None

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")
    
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("Namaste! I am the Ayurvedic Expert at Alpha Ayurveda. How can I guide your wellness today?")
        return str(resp)

    bot_reply = try_generate(user_msg)

    if bot_reply:
        msg.body(bot_reply)
    else:
        msg.body("Sorry, I am having trouble connecting to the server. Please try again later.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
