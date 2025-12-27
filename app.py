import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from google import genai

app = Flask(__name__)

# Connect to Google using the NEW library
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
        # Using the correct model for the new library
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=user_msg
        )
        msg.body(response.text)

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, I had a technical hiccup. Please try again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
