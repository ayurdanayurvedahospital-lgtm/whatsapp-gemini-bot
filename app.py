import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# We will try these models in order until one works
MODELS_TO_TRY = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-001",
    "gemini-1.5-flash-002",
    "gemini-2.0-flash-exp",
    "gemini-pro",
    "gemini-1.0-pro"
]

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("I am listening.")
        return str(resp)

    # Try to find a working model
    success = False
    error_log = []

    for model_name in MODELS_TO_TRY:
        try:
            # We use v1beta as it supports the most models
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
            
            payload = {"contents": [{"parts": [{"text": user_msg}]}]}
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                # SUCCESS! We found a working model
                data = response.json()
                bot_reply = data["candidates"][0]["content"]["parts"][0]["text"]
                msg.body(bot_reply)
                success = True
                print(f"Success with model: {model_name}")
                break # Stop looping, we found the winner
            else:
                # Log the failure and try the next one
                error_msg = response.json().get('error', {}).get('message', 'Unknown Error')
                print(f"Failed {model_name}: {response.status_code} - {error_msg}")
                error_log.append(f"{model_name}: {response.status_code}")

        except Exception as e:
            print(f"Connection Error on {model_name}: {e}")

    # If ALL models failed, tell the user exactly why on WhatsApp
    if not success:
        debug_info = ", ".join(error_log)
        msg.body(f"Sorry, Google rejected all models. Debug info: {debug_info}")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
