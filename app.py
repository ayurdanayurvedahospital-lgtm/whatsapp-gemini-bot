import os
import requests
import flask
import google.generativeai as genai
import tempfile
import threading
import re
import logging
import time
from flask import Flask, request, jsonify

# Import Knowledge Base and System Prompt
from knowledge_base_data import AGENTS, PRODUCT_IMAGES, LINKS, GOOGLE_FORM_URL, FORM_FIELDS
from system_prompt import SYSTEM_PROMPT

# --- CONFIGURATION ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logging.warning("GEMINI_API_KEY not set!")

ZOKO_API_KEY = os.environ.get("ZOKO_API_KEY")
if not ZOKO_API_KEY:
    logging.warning("ZOKO_API_KEY not set!")

# Initialize Gemini Model
model = genai.GenerativeModel("gemini-2.5-flash")

# --- DATA STRUCTURES ---
user_sessions = {}
stop_bot_cache = {} # phone -> {"stopped": bool, "timestamp": float}
CACHE_TTL = 300  # 5 minutes

# --- HELPER FUNCTIONS ---

def send_zoko_message(phone, text, image_url=None):
    """
    Sends a message via Zoko API.
    Fixes 400 Error by cleaning phone number and handling empty text.
    """
    if not ZOKO_API_KEY:
        logging.warning("Skipping Zoko Send: API Key missing")
        return

    if not text and not image_url:
        logging.warning("Skipping Zoko Send: No text or image provided")
        return

    # Clean phone number (remove leading +)
    phone = phone.replace("+", "")

    url = "https://chat.zoko.io/v2/message"
    headers = {
        'apikey': ZOKO_API_KEY,
        'Content-Type': 'application/json'
    }

    if image_url:
        payload = {
            'channel': 'whatsapp',
            'recipient': phone,
            'type': 'image',
            'url': image_url,
            'caption': text
        }
    else:
        payload = {
            'channel': 'whatsapp',
            'recipient': phone,
            'type': 'text',
            'message': text
        }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Zoko Send Error: {e} | Payload: {payload}")

def check_stop_bot(phone):
    """
    Checks if the user has a 'STOP_BOT' tag in Zoko.
    Returns True if stopped.
    """
    # Check Cache
    now = time.time()
    if phone in stop_bot_cache:
        cached = stop_bot_cache[phone]
        if now - cached["timestamp"] < CACHE_TTL:
            return cached["stopped"]

    if not ZOKO_API_KEY:
        return False

    # Clean phone number for query as well? Usually query params handle + encoded.
    # But for consistency let's try with + first as it is in Zoko usually.
    # The helper `send_zoko_message` stripped it, but `chats?phone=` might need it.
    # I'll stick to the raw phone for the query unless it fails.

    url = f"https://chat.zoko.io/v2/chats?phone={phone}"
    headers = {'apikey': ZOKO_API_KEY}

    is_stopped = False
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            chat_data = data.get('data', []) if isinstance(data, dict) else data

            if isinstance(chat_data, list):
                for chat in chat_data:
                    tags = chat.get('tags', [])
                    if any(t.lower() == "stop_bot" for t in tags):
                        is_stopped = True
                        break
            elif isinstance(chat_data, dict):
                tags = chat_data.get('tags', [])
                if any(t.lower() == "stop_bot" for t in tags):
                    is_stopped = True
    except Exception as e:
        logging.error(f"Zoko Tag Check Error: {e}")

    # Update Cache
    stop_bot_cache[phone] = {"stopped": is_stopped, "timestamp": now}
    return is_stopped

def process_audio(file_url):
    """
    Downloads OGG file, uploads to Gemini, and returns text response.
    """
    local_filename = None
    try:
        # Download
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        # Upload
        myfile = genai.upload_file(local_filename, mime_type='audio/ogg')
        while myfile.state.name == "PROCESSING":
            time.sleep(1)
            myfile = genai.get_file(myfile.name)

        if myfile.state.name == "FAILED":
            raise ValueError("Audio processing failed in Gemini.")

        # Generate Response using System Prompt context if we were in a session,
        # but here we simplify as per instruction: "Download OGG, upload to Gemini, return text response."
        # We need a chat session or a generate_content call.
        # I'll use a new chat session with System Prompt to ensure persona.

        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["Understood. I am AIVA."]}
        ])

        prompt = "Listen to this audio. You are AIVA. Answer the user's question directly, briefly, and politely in the same language."
        response = chat.send_message([myfile, prompt])
        return response.text

    except Exception as e:
        logging.error(f"Audio Process Error: {e}")
        return "Sorry, I could not process your voice note. Please type your message."

    finally:
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

def handle_message(data):
    """
    Background Message Handler.
    """
    try:
        # 1. Parse
        customer = data.get("customer", {})
        sender_phone = customer.get("platformSenderId")
        if not sender_phone:
             # Fallback
             sender_phone = data.get("platformSenderId")

        if not sender_phone:
            logging.error("No sender_phone found.")
            return

        incoming_msg = data.get("text", "")
        msg_type = data.get("type", "text")
        file_url = data.get("fileUrl")
        direction = data.get("direction")

        # Ignore outgoing messages
        if direction and direction != "FROM_CUSTOMER":
            return

        # 2. STOP BOT Logic
        if check_stop_bot(sender_phone):
            logging.info(f"Bot is stopped for {sender_phone}")
            return

        if incoming_msg and incoming_msg.strip().upper() == "STOP BOT":
            # Update cache locally as well to be safe
            stop_bot_cache[sender_phone] = {"stopped": True, "timestamp": time.time()}
            send_zoko_message(sender_phone, "Bot Stopped")
            return

        # 3. Image Detection
        image_url = None
        if incoming_msg:
            msg_lower = incoming_msg.lower()
            for key, url in PRODUCT_IMAGES.items():
                if key in msg_lower:
                    image_url = url
                    break

        # 4. AI Generation
        response_text = ""

        # Session History
        if sender_phone not in user_sessions:
            user_sessions[sender_phone] = []
        history = user_sessions[sender_phone]

        if msg_type == "audio":
             if file_url:
                 send_zoko_message(sender_phone, "Listening... 🎧")
                 response_text = process_audio(file_url)
        else:
            # Text Processing
            chat = model.start_chat(history=[
                {"role": "user", "parts": [SYSTEM_PROMPT]},
                {"role": "model", "parts": ["Understood. I am AIVA."]}
            ] + history)

            try:
                ai_resp = chat.send_message(incoming_msg)
                response_text = ai_resp.text

                # Update History
                history.append({"role": "user", "parts": [incoming_msg]})
                history.append({"role": "model", "parts": [response_text]})
                # Keep history short? User didn't specify, but good practice.
                if len(history) > 20:
                    user_sessions[sender_phone] = history[-20:]

            except Exception as e:
                logging.error(f"Gemini Error: {e}")
                response_text = "I am currently experiencing high traffic. Please try again later."

        # 5. Send Response
        if response_text:
            send_zoko_message(sender_phone, response_text, image_url)

    except Exception as e:
        logging.error(f"Background Handler Error: {e}")

# --- MAIN ROUTE ---

@app.route("/bot", methods=["POST"])
def bot():
    """
    Webhook Endpoint.
    Returns 200 OK immediately and processes in background.
    """
    data = request.json
    print(f"Incoming Zoko Payload: {data}")

    # Start Background Thread
    thread = threading.Thread(target=handle_message, args=(data,))
    thread.start()

    return jsonify(status="received"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
