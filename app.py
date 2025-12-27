import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

# This is the ONLY model that replied to you (even though it was an error)
# We will use v1beta because that is where the 2.0 models live
MODEL_NAME = "gemini-2.0-flash-exp"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")

    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("I am listening.")
        return str(resp)

    try:
        payload = {"contents": [{"parts": [{"text": user_msg}]}]}
        
        # ATTEMPT 1: Try to send the message
        response = requests.post(API_URL, json=payload)

        # If we hit the "Speed Limit" (429), wait 4 seconds and try again
        if response.status_code == 429:
            print("Too fast! Waiting 4 seconds...")
            time.sleep(4)
            response = requests.post(API_URL, json=payload)

        # Process the result
        if response.status_code == 200:
            data = response.json()
            bot_reply = data["candidates"][0]["content"]["parts"][0]["text"]
            msg.body(bot_reply)
        else:
            print(f"Google Error: {response.text}")
            msg.body("Sorry, I am receiving too many messages right now. Please wait 10 seconds and try again.")

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, something went wrong internally.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
