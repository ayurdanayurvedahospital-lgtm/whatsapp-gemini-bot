import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from google import genai

app = Flask(__name__)

# Initialize client with your API Key
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
        # SWITCHING TO GEMINI-PRO (The most stable model)
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_msg
        )
        msg.body(response.text)
        
    except Exception as e:
        # If the first model fails, try the backup model automatically
        try:
            print(f"Primary model failed, trying backup. Error: {e}")
            response = client.models.generate_content(
                model="gemini-1.5-pro",
                contents=user_msg
            )
            msg.body(response.text)
        except Exception as e2:
            print(f"All models failed. Error: {e2}")
            msg.body("Sorry, I am having trouble connecting to Google. Please try again later.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
