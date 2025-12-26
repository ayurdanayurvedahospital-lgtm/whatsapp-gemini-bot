import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from google import genai

app = Flask(__name__)

# Initialize the connection to Gemini
# We use the API Key stored in the cloud (Render) environment variables
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.route("/bot", methods=["POST"])
def bot():
    # 1. Get the message user sent on WhatsApp
    user_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    print(f"Message from {sender}: {user_msg}")

    # 2. Prepare the response container
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("I am listening, but I didn't hear anything.")
        return str(resp)

    try:
        # 3. Send the user's text to Gemini
        # We use 'gemini-1.5-flash' because it is fast and cheap
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_msg
        )
        
        # 4. Get Gemini's answer
        bot_reply = response.text
        
        # 5. Send the answer back to WhatsApp
        msg.body(bot_reply)

    except Exception as e:
        print(f"Error: {e}")
        msg.body("Sorry, I encountered an error. Please try again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)