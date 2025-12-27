import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

app = Flask(__name__)

# 1. Configure the stable Google library
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 2. Setup the model
# We use 'gemini-1.5-flash' because it is fast, free, and reliable.
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/bot", methods=["POST"])
def bot():
    # Get the incoming message
    user_msg = request.values.get("Body", "").strip()
    print(f"User: {user_msg}")

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
        # Print error to logs
        print(f"Error: {e}")
        msg.body("Sorry, I am having a connection issue. Please try again.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
