import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

def try_generate(user_msg):
    # LIST 1: Stable Models (Use v1 URL)
    # This fixes the "404 Not Found" error by using the stable door.
    stable_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
    for model in stable_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": user_msg}]}]}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except:
            continue # Try next model

    # LIST 2: Beta/New Models (Use v1beta URL)
    # If stable fails, we try the cutting-edge ones you found in documentation.
    beta_models = [
        "gemini-2.5-flash", 
        "gemini-3-flash-preview", 
        "gemini-2.0-flash-exp"
    ]
    for model in beta_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": user_msg}]}]}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 429:
                return "Quota Limit Hit. Please wait 30 seconds."
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
        msg.body("I am listening.")
        return str(resp)

    # Try to find ANY working model
    bot_reply = try_generate(user_msg)

    if bot_reply:
        msg.body(bot_reply)
    else:
        msg.body("Sorry, all Google models are currently busy or locked. Please try again in 1 hour.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
