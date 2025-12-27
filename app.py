import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from google import genai

app = Flask(__name__)

# 1. Setup the client (Uses the new library)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
        # 2. Generate Content
        # We use 'gemini-1.5-flash' as it is the most stable for bots right now
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_msg
        )
        msg.body(response.text)

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, I had a connection error. Please try again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
