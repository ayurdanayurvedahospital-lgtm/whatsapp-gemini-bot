import os
import logging
import threading
import time
import re
import traceback
import requests
import flask
import google.generativeai as genai
import tempfile
from datetime import datetime
import pytz
from flask import Flask, request, jsonify

# Import modularized data and prompt
try:
    from knowledge_base_data import AGENTS, PRODUCT_IMAGES, LINKS, GOOGLE_FORM_URL, FORM_FIELDS
    from system_prompt import SYSTEM_PROMPT
except ImportError as e:
    logging.error(f"Failed to import modular files: {e}")
    # Define minimal fallbacks to prevent crash if files are missing (though they should exist)
    AGENTS = []
    PRODUCT_IMAGES = {}
    LINKS = {}
    SYSTEM_PROMPT = "You are AIVA."

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ZOKO_API_KEY = os.environ.get("ZOKO_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logging.warning("GEMINI_API_KEY not set!")

if not ZOKO_API_KEY:
    logging.warning("ZOKO_API_KEY not set!")

# Initialize Gemini Model
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
except Exception as e:
    logging.error(f"Failed to initialize Gemini Model: {e}")
    model = None

# --- GLOBAL STATE ---
user_sessions = {}
stop_bot_cache = {}
CACHE_TTL = 300
processed_messages = set()
processed_messages_lock = threading.Lock()
user_last_messages = {}
muted_users = set()  # Tracks users currently talking to a human agent

# --- HELPER FUNCTIONS ---

def get_ist_time_greeting():
    """
    Returns 'Good Morning', 'Good Afternoon', or 'Good Evening' based on IST.
    """
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        hour = now.hour

        if 5 <= hour < 12:
            return "Good Morning"
        elif 12 <= hour < 17:
            return "Good Afternoon"
        else:
            return "Good Evening"
    except Exception as e:
        logging.error(f"Time Error: {e}")
        return "Hello"

def send_zoko_message(phone, text=None, image_url=None):
    """
    Sends message to Zoko. Handles Text vs Image split logic.
    Always sends image first if available.
    """
    if not ZOKO_API_KEY:
        logging.warning("Skipping Zoko Send: API Key missing")
        return

    if not text and not image_url:
        return

    # Crucial Fix: Clean phone number
    phone_clean = phone.replace("+", "")
    url = "https://chat.zoko.io/v2/message"
    headers = {
        'apikey': ZOKO_API_KEY,
        'Content-Type': 'application/json'
    }

    # Send Image First if exists
    if image_url:
        try:
            payload = {
                'channel': 'whatsapp',
                'recipient': phone_clean,
                'type': 'image',
                'url': image_url
                # NO CAPTION to avoid 400 errors
            }
            logging.info(f"Sending Image to {phone_clean}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code != 200:
                logging.error(f"Image Send Failed: {resp.status_code} - {resp.text}")
            else:
                logging.info(f"Image Sent: {resp.status_code}")
                time.sleep(1) # Wait 1 second
        except Exception as e:
            # Robust Image Sending: Log error but DO NOT CRASH. Proceed to text.
            logging.error(f"Failed to send image (Exception): {e}")

    # Send Text if exists
    if text:
        try:
            payload = {
                'channel': 'whatsapp',
                'recipient': phone_clean,
                'type': 'text',
                'message': text
            }
            logging.info(f"Sending Text to {phone_clean}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logging.info(f"Text Sent: {resp.status_code}")
        except Exception as e:
            logging.error(f"Failed to send text: {e}")

def check_stop_bot(phone):
    """
    Check if bot is stopped via Zoko tags (STOP_BOT) or cache.
    Note: This is separate from the in-memory 'muted_users' set.
    """
    now = time.time()
    if phone in stop_bot_cache:
        cached = stop_bot_cache[phone]
        if now - cached["timestamp"] < CACHE_TTL:
            return cached["stopped"]

    if not ZOKO_API_KEY:
        return False

    is_stopped = False
    try:
        url = f"https://chat.zoko.io/v2/chats?phone={phone}"
        headers = {'apikey': ZOKO_API_KEY}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            chat_data = data.get('data', []) if isinstance(data, dict) else data

            # Helper to check tags list
            def has_stop_tag(tags):
                for t in tags:
                    tag_name = t if isinstance(t, str) else t.get('name', '')
                    if tag_name.lower() == "stop_bot":
                        return True
                return False

            if isinstance(chat_data, list):
                for chat in chat_data:
                    if has_stop_tag(chat.get('tags', [])):
                        is_stopped = True
                        break
            elif isinstance(chat_data, dict):
                 if has_stop_tag(chat_data.get('tags', [])):
                     is_stopped = True

    except Exception as e:
        logging.error(f"Check Stop Bot Error: {e}")

    stop_bot_cache[phone] = {"stopped": is_stopped, "timestamp": now}
    return is_stopped

def process_audio(file_url, sender_phone):
    """
    Process audio file via Gemini.
    """
    local_filename = None
    try:
        logging.info(f"Downloading Audio: {file_url}")
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        logging.info("Uploading Audio to Gemini...")
        myfile = genai.upload_file(local_filename, mime_type='audio/ogg')

        while myfile.state.name == "PROCESSING":
            time.sleep(1)
            myfile = genai.get_file(myfile.name)

        if myfile.state.name == "FAILED":
            raise ValueError("Audio processing failed in Gemini.")

        # Determine Greeting
        greeting = get_ist_time_greeting()

        history = user_sessions.get(sender_phone, [])
        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": [f"Understood. I am AIVA. Current Time Greeting is: {greeting}."]}
        ] + history)

        prompt = f"Listen to this audio. You are AIVA. Current Time Greeting: {greeting}. Answer briefly (under 60 words) and politely in the same language."
        response = chat.send_message([myfile, prompt])
        return response.text

    except Exception as e:
        logging.error(f"Audio Process Error: {e}")
        return "Sorry, I could not process your voice note."
    finally:
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

def get_ai_response(sender_phone, message_text, history):
    try:
        greeting = get_ist_time_greeting()

        chat_history = [
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": [f"Understood. I am AIVA. Current Time Greeting is: {greeting}."]}
        ] + history

        chat = model.start_chat(history=chat_history)

        full_prompt = f"Current Time Greeting: {greeting}\nUser Message: {message_text}"

        response = chat.send_message(full_prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "I am currently experiencing high traffic. Please try again later."

def handle_message(payload):
    """
    Main Logic Handler (Background Thread).
    """
    try:
        logging.info(f"STEP 1: Received Payload: {payload}")

        # Extract Basics
        message_id = payload.get("messageId") or payload.get("eventId")
        if message_id:
            with processed_messages_lock:
                if message_id in processed_messages:
                    logging.info(f"Duplicate Message ID {message_id}. Skipping.")
                    return
                processed_messages.add(message_id)
                if len(processed_messages) > 5000: processed_messages.clear()

        sender_phone = payload.get("platformSenderId")
        if not sender_phone:
            customer = payload.get("customer", {})
            sender_phone = customer.get("platformSenderId")

        if not sender_phone:
            logging.error("No sender_phone found. Aborting.")
            return

        direction = payload.get("direction")
        if direction and direction != "incoming" and direction != "from_customer":
             if direction.lower() in ["outgoing", "from_business"]:
                 logging.info("Ignoring outgoing message.")
                 return

        msg_type = payload.get("type", "text")
        text_body = payload.get("text", "")
        file_url = payload.get("fileUrl")

        # --- STEP 1: RESUME COMMAND (Priority) ---
        if text_body and text_body.strip().upper() == "START BOT":
            if sender_phone in muted_users:
                muted_users.discard(sender_phone)
                logging.info(f"Bot resumed for {sender_phone} via 'START BOT' command.")
                send_zoko_message(sender_phone, text="Bot resumed. How can I help?")
            else:
                # If not muted, just acknowledge or proceed. Let's acknowledge to confirm it's running.
                send_zoko_message(sender_phone, text="Bot is already active. How can I help?")
            return

        # --- STEP 2: CHECK MUTE STATUS ---
        if sender_phone in muted_users:
            logging.info(f"User {sender_phone} is muted (talking to human). Ignoring message.")
            return

        # --- STEP 3: AGENT HANDOVER DETECTION ---
        if text_body:
            lower_msg = text_body.lower()
            handover_keywords = ["agent", "human", "customer care", "speak to person"]
            if any(k in lower_msg for k in handover_keywords):
                response_text = "You can contact our Agent Sreelekha at +91 9895900809. I will now pause so you can speak with her."
                send_zoko_message(sender_phone, text=response_text)
                muted_users.add(sender_phone)
                logging.info(f"User {sender_phone} requested agent. Bot muted.")
                return

        # --- STEP 4: EXISTING LOGIC ---

        # Check Stop Bot (Tag-based)
        if check_stop_bot(sender_phone):
            logging.info(f"Bot Stopped for {sender_phone} (Tag Check)")
            return

        if text_body and text_body.strip().upper() == "STOP BOT":
            # This logic mimics the tag-based stop but is triggered by text command.
            # We can also add to muted_users here or use the existing cache logic.
            # Using existing cache logic for "STOP BOT" command consistency.
            stop_bot_cache[sender_phone] = {"stopped": True, "timestamp": time.time()}
            send_zoko_message(sender_phone, text="Bot has been stopped for this chat.")
            return

        # Loop Prevention
        if text_body:
            last_msgs = user_last_messages.get(sender_phone, [])
            last_msgs.append(text_body)
            if len(last_msgs) > 3: last_msgs.pop(0)
            user_last_messages[sender_phone] = last_msgs
            if len(last_msgs) == 3 and all(m == last_msgs[0] for m in last_msgs):
                logging.warning(f"Loop detected for {sender_phone}. Ignoring.")
                return

        logging.info("STEP 2: Processing Logic (AI/Image)")

        response_text = ""
        found_image_url = None

        # Image Logic
        if text_body:
            lower_msg = text_body.lower()
            for key, url in PRODUCT_IMAGES.items():
                if key in lower_msg:
                    found_image_url = url
                    break

        # Send Image IMMEDIATELY if found
        if found_image_url:
            send_zoko_message(sender_phone, image_url=found_image_url)

        # Audio vs Text Logic
        if msg_type == "audio" and file_url:
            send_zoko_message(sender_phone, text="Listening... 🎧")
            response_text = process_audio(file_url, sender_phone)
        elif text_body or msg_type == "text":
            if sender_phone not in user_sessions:
                user_sessions[sender_phone] = []
            history = user_sessions[sender_phone]

            response_text = get_ai_response(sender_phone, text_body, history)

            history.append({"role": "user", "parts": [text_body]})
            history.append({"role": "model", "parts": [response_text]})
            if len(history) > 20:
                user_sessions[sender_phone] = history[-20:]

        logging.info("STEP 3: Sending Text Response")

        if response_text:
            send_zoko_message(sender_phone, text=response_text)

    except Exception as e:
        logging.error(f"CRITICAL ERROR in handle_message: {e}")
        traceback.print_exc()

# --- ROUTES ---

@app.route('/', methods=['GET'])
def health_check():
    """
    Health Check for Render.
    """
    return "Active", 200

@app.route('/bot', methods=['POST'])
def bot():
    """
    Webhook Endpoint.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        thread = threading.Thread(target=handle_message, args=(data,))
        thread.daemon = True
        thread.start()

        return jsonify({"status": "received"}), 200

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
