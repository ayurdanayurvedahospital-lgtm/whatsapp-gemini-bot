import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# We get the API Key from Render
API_KEY = os.environ.get("GEMINI_API_KEY")

# ------------------------------------------------------------------
# CHANGE HERE: We switched from 'v1beta' to 'v1' (The Stable Room)
# ------------------------------------------------------------------
API_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"

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
        # Prepare the letter to Google
        payload = {
            "contents": [{
                "parts": [{"text": user_msg}]
            }]
        }

        # Send it!
        response = requests.post(API_URL, json=payload)
        
        # Check if Google replied with success (200 OK)
        if response.status_code == 200:
            data = response.json()
            # Extract the answer
            bot_reply = data["candidates"][0]["content"]["parts"][0]["text"]
            msg.body(bot_reply)
        else:
            # If it fails, print the EXACT reason to the logs
            print(f"Google Error: {response.text}")
            msg.body("Sorry, I am having a connection issue with Google.")

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, something went wrong internally.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
