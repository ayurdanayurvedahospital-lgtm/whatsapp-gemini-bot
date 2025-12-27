import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# We use the raw API URL directly (No google library needed)
API_KEY = os.environ.get("GEMINI_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

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
        # Construct the payload exactly like your working CURL command
        payload = {
            "contents": [{
                "parts": [{"text": user_msg}]
            }]
        }

        # Send raw request
        response = requests.post(API_URL, json=payload)
        
        # Check if it worked
        if response.status_code == 200:
            data = response.json()
            bot_reply = data["candidates"][0]["content"]["parts"][0]["text"]
            msg.body(bot_reply)
        else:
            print(f"Google Error: {response.text}")
            msg.body("Sorry, my brain is tired (Quota limit or connection error).")

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, I had a connection error.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
