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
from knowledge_base_data import PRODUCT_IMAGES
from system_prompt import SYSTEM_PROMPT

# --- CONFIGURATION ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Idempotency & Loop Prevention
processed_messages = set() # Store message IDs
processed_messages_lock = threading.Lock()
user_last_messages = {} # phone -> [msg1, msg2, msg3]

# --- HELPER FUNCTIONS ---

def send_zoko_message(phone, text=None, image_url=None):
    """
    Sends a message via Zoko API.
    CRITICAL UPDATE: Handles EITHER text OR image. Mutually exclusive.
    """
    if not ZOKO_API_KEY:
        logging.warning("Skipping Zoko Send: API Key missing")
        return

    if not text and not image_url:
        logging.warning("Skipping Zoko Send: No text or image provided")
        return

    # Clean phone number (remove leading +)
    phone_clean = phone.replace("+", "")

    url = "https://chat.zoko.io/v2/message"
    headers = {
        'apikey': ZOKO_API_KEY,
        'Content-Type': 'application/json'
    }

    payload = {
        'channel': 'whatsapp',
        'recipient': phone_clean
    }

    if image_url:
        # Image Message - NO CAPTION to avoid 400 errors if caption is too long or malformed
        payload['type'] = 'image'
        payload['url'] = image_url
        # Zoko API might accept 'caption' for images, but user requested separation to avoid errors.
        # We will strictly send just the image here.
    elif text:
        # Text Message
        payload['type'] = 'text'
        payload['message'] = text

    try:
        logging.info(f"Sending Zoko Message: Type={'Image' if image_url else 'Text'} to {phone_clean}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info(f"Zoko Send Success: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Zoko Send Error: {e}")
        if e.response is not None:
             logging.error(f"Zoko Response: {e.response.text}")

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

    url = f"https://chat.zoko.io/v2/chats?phone={phone}"
    headers = {'apikey': ZOKO_API_KEY}

    is_stopped = False
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Handle potential list or dict return
            chat_data = data.get('data', []) if isinstance(data, dict) else data

            if isinstance(chat_data, list):
                for chat in chat_data:
                    tags = chat.get('tags', [])
                    # tags can be list of strings or list of dicts depending on API version
                    # assuming list of strings based on common Zoko usage, or list of dicts with 'name'
                    for t in tags:
                        tag_name = t if isinstance(t, str) else t.get('name', '')
                        if tag_name.lower() == "stop_bot":
                            is_stopped = True
                            break
                    if is_stopped: break
    except Exception as e:
        logging.error(f"Zoko Tag Check Error: {e}")

    # Update Cache
    stop_bot_cache[phone] = {"stopped": is_stopped, "timestamp": now}
    return is_stopped

def process_audio(file_url, sender_phone):
    """
    Downloads OGG/Audio file, uploads to Gemini, and returns text response.
    """
    local_filename = None
    try:
        # Download
        logging.info(f"Downloading audio from {file_url}")
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        # Upload to Gemini
        logging.info("Uploading audio to Gemini...")
        myfile = genai.upload_file(local_filename, mime_type='audio/ogg')

        # Wait for processing
        while myfile.state.name == "PROCESSING":
            time.sleep(1)
            myfile = genai.get_file(myfile.name)

        if myfile.state.name == "FAILED":
            raise ValueError("Audio processing failed in Gemini.")

        # Context
        history = user_sessions.get(sender_phone, [])
        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["Understood. I am AIVA."]}
        ] + history)

        prompt = "Listen to this audio. You are AIVA. Answer the user's question directly, briefly (under 60 words), and politely in the same language."
        response = chat.send_message([myfile, prompt])
        return response.text

    except Exception as e:
        logging.error(f"Audio Process Error: {e}")
        return "Sorry, I could not process your voice note. Please type your message."

    finally:
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

def get_ai_response(sender_phone, message_text, history):
    """
    Generates AI response using Gemini.
    """
    try:
        # Construct Chat
        chat_history = [
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["Understood. I am AIVA."]}
        ] + history

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(message_text)
        return response.text
    except Exception as e:
        logging.error(f"Gemini AI Error: {e}")
        return "I am currently experiencing high traffic. Please try again later."

def handle_message(payload):
    """
    Background worker to process incoming Zoko webhook.
    """
    try:
        # 1. Extract Basic Info
        # Zoko payloads vary. Try to extract aggressively.
        message_id = payload.get("messageId")
        if not message_id:
            # Fallback for some events
            message_id = payload.get("eventId")

        # Idempotency Check
        if message_id:
            with processed_messages_lock:
                if message_id in processed_messages:
                    logging.info(f"Duplicate Message ID {message_id}. Skipping.")
                    return
                processed_messages.add(message_id)
                # Cleanup old IDs? For now, let it grow (or we can use a TTL cache later)
                if len(processed_messages) > 10000:
                    processed_messages.clear() # Naive cleanup

        sender_phone = payload.get("platformSenderId")
        if not sender_phone:
            customer = payload.get("customer", {})
            sender_phone = customer.get("platformSenderId")

        if not sender_phone:
            logging.error("No sender_phone found in payload.")
            return

        # Check Direction - Ignore outgoing
        direction = payload.get("direction")
        if direction and direction != "incoming":
             # Zoko sometimes uses "from_customer" or "incoming".
             # If it's explicit "outgoing" or "from_business", ignore.
             if direction.lower() in ["outgoing", "from_business"]:
                 logging.info("Ignoring outgoing message.")
                 return

        # 2. Extract Content
        msg_type = payload.get("type", "text")
        text_body = payload.get("text", "")
        file_url = payload.get("fileUrl")

        # 3. Stop Bot Check
        if check_stop_bot(sender_phone):
            logging.info(f"Bot execution stopped for {sender_phone} (Tag: stop_bot)")
            return

        # Check for STOP command in text
        if text_body and text_body.strip().upper() == "STOP BOT":
            stop_bot_cache[sender_phone] = {"stopped": True, "timestamp": time.time()}
            send_zoko_message(sender_phone, text="Bot has been stopped for this chat.")
            return

        # 4. Loop Prevention
        if text_body:
            last_msgs = user_last_messages.get(sender_phone, [])
            last_msgs.append(text_body)
            if len(last_msgs) > 3:
                last_msgs.pop(0)
            user_last_messages[sender_phone] = last_msgs

            # Check if all 3 are identical
            if len(last_msgs) == 3 and all(m == last_msgs[0] for m in last_msgs):
                logging.warning(f"Loop detected for {sender_phone}. Ignoring.")
                return

        # 5. Logic Branching
        response_text = ""
        found_image_url = None

        # A. Image Keyword Detection
        if text_body:
            lower_msg = text_body.lower()
            for key, url in PRODUCT_IMAGES.items():
                if key in lower_msg:
                    found_image_url = url
                    break

        # B. Audio Processing
        if msg_type == "audio" and file_url:
            send_zoko_message(sender_phone, text="Listening... 🎧")
            response_text = process_audio(file_url, sender_phone)

        # C. Text Processing
        elif text_body or msg_type == "text":
            # Get History
            if sender_phone not in user_sessions:
                user_sessions[sender_phone] = []
            history = user_sessions[sender_phone]

            response_text = get_ai_response(sender_phone, text_body, history)

            # Update History
            history.append({"role": "user", "parts": [text_body]})
            history.append({"role": "model", "parts": [response_text]})
            # Keep history short (last 20 turns)
            if len(history) > 20:
                user_sessions[sender_phone] = history[-20:]

        else:
            logging.info(f"Unsupported message type: {msg_type}")
            return

        # 6. Send Response (Split Flow)
        if found_image_url:
            send_zoko_message(sender_phone, image_url=found_image_url)
            time.sleep(1) # Wait 1 second to ensure order

        if response_text:
            send_zoko_message(sender_phone, text=response_text)

    except Exception as e:
        logging.error(f"Error in handle_message: {e}")

# --- WEBHOOK ENTRY POINT ---

@app.route("/bot", methods=["POST"])
def bot():
    """
    Receives Webhook from Zoko.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        # Spawn background thread
        thread = threading.Thread(target=handle_message, args=(data,))
        thread.daemon = True # Daemon thread so it doesn't block shutdown
        thread.start()

        return jsonify({"status": "received"}), 200

    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
