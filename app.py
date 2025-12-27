import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

app = Flask(__name__)

# Configure Google Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Use the 'gemini-pro' model which is the most stable version
model = genai.GenerativeModel('gemini-pro')

@app.route("/bot", methods=["POST"])
def bot():
    # 1. Get incoming message
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")

    # 2. Prepare response
    resp = MessagingResponse()
    msg = resp.message()

    if not user_msg:
        msg.body("I am listening.")
        return str(resp)

    try:
        # 3. Generate content
        response = model.generate_content(user_msg)
        msg.body(response.text)
        
    except Exception as e:
        print(f"Error: {e}")
        # If this fails, we will see the error in the logs
        msg.body("Sorry, I am having trouble connecting. Please try again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
