import os
import requests
import flask
import google.generativeai as genai
import tempfile
import threading
import logging
import time
from flask import Flask, request, jsonify

# Import Knowledge Base
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
    If image_url is present, sends as image type with caption.
    Otherwise sends as text type.
    """
    if not ZOKO_API_KEY:
        logging.warning("Skipping Zoko Send: API Key missing")
        return

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
        logging.error(f"Zoko Send Error: {e}")

def check_stop_bot(phone):
    """
    Checks if the user has a 'STOP_BOT' tag in Zoko.
    Returns True if stopped.
    Uses caching to reduce API calls.
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
            # Handle both list and dict returns just in case
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
        # On error, we default to False (allow) but rely on local cache if available?
        # No, if cache expired or missing, we have to guess. Defaulting to False.

    # Update Cache
    stop_bot_cache[phone] = {"stopped": is_stopped, "timestamp": now}
    return is_stopped

def set_stop_bot_locally(phone):
    """
    Manually sets the stop bot status in the local cache.
    Use this when the user sends a STOP command, so we don't need to wait for Zoko API or cache expiry.
    """
    stop_bot_cache[phone] = {"stopped": True, "timestamp": time.time()}
    logging.info(f"Manually set STOP_BOT for {phone} in local cache.")

def process_audio(file_url, history_context):
    """
    Downloads OGG file, uploads to Gemini, and answers directly.
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

        # Generate Response
        # We use the existing chat session to keep context if possible,
        # or start a new one if needed. Here we assume we want to maintain the session.
        chat_session = model.start_chat(
            history=[
                {"role": "user", "parts": [SYSTEM_PROMPT]},
                {"role": "model", "parts": ["Understood. I am AIVA, your AI Virtual Assistant."]}
            ] + history_context
        )

        prompt = "Listen to this audio. Transcribe it and answer the user's question directly as AIVA."
        response = chat_session.send_message([myfile, prompt])
        return response.text

    except Exception as e:
        logging.error(f"Audio Process Error: {e}")
        return "Sorry, I could not process your voice note. Please type your message."

    finally:
        if local_filename and os.path.exists(local_filename):
            os.remove(local_filename)

def _send_to_sheet_task(data):
    try:
        requests.post(GOOGLE_FORM_URL, data=data, timeout=10)
    except Exception as e:
        logging.error(f"Sheet Save Error: {e}")

def save_to_sheet(user_data):
    """
    Saves user data to Google Sheet in background.
    """
    phone_clean = user_data.get('phone', '').replace("+", "")
    form_data = {
        FORM_FIELDS["name"]: user_data.get("name", "Unknown"),
        FORM_FIELDS["phone"]: phone_clean,
        FORM_FIELDS["product"]: user_data.get("product", "Pending")
    }
    threading.Thread(target=_send_to_sheet_task, args=(form_data,)).start()

def get_product_image(text):
    text_lower = text.lower()
    for key, url in PRODUCT_IMAGES.items():
        if key in text_lower:
            return url
    return None

# --- MAIN LOGIC ---

@app.route("/bot", methods=["POST"])
def bot():
    data = request.json
    print(f"Incoming Zoko Payload: {data}")

    # 1. FIX JSON PARSING (Robust fallback per user request)
    sender_phone = data.get("customer", {}).get("platformSenderId")
    if not sender_phone:
        sender_phone = data.get("platformSenderId")

    incoming_msg = data.get("text", "")
    msg_type = data.get("type", "text")
    file_url = data.get("fileUrl")
    direction = data.get("direction")

    # IGNORE OUTGOING MESSAGES (Loop Prevention)
    if direction and direction != "FROM_CUSTOMER":
        return jsonify(status="ignored", reason="Not from customer"), 200

    if not sender_phone:
        return jsonify(status="error", reason="No sender_phone"), 400

    # 2. STOP LOGIC
    # Check 'STOP_BOT' tag via API or text command
    is_stopped = check_stop_bot(sender_phone)

    # If explicit STOP command, update local cache immediately
    if incoming_msg and incoming_msg.strip().upper() in ["STOP BOT", "STOP"]:
        set_stop_bot_locally(sender_phone)
        return jsonify(status="stopped")

    if is_stopped:
        return jsonify(status="stopped")

    # Session Management
    if sender_phone not in user_sessions:
        user_sessions[sender_phone] = {
            "history": [],
            "data": {"phone": sender_phone},
            "last_messages": [],
            "stopped_loop": False
        }
    session = user_sessions[sender_phone]

    # REPETITION CHECK (Stop if user sends same msg 3 times)
    if session.get("stopped_loop"):
        return jsonify(status="stopped_repetition")

    if incoming_msg:
        # Initialize if missing (backward compatibility)
        if "last_messages" not in session:
            session["last_messages"] = []

        session["last_messages"].append(incoming_msg)
        if len(session["last_messages"]) > 3:
            session["last_messages"].pop(0)

        if len(session["last_messages"]) == 3 and all(m == incoming_msg for m in session["last_messages"]):
             session["stopped_loop"] = True
             logging.info(f"Repetitive messages from {sender_phone}. Stopping bot loop.")
             return jsonify(status="stopped_repetition")

    try:
        response_text = ""
        image_url = None

        # 3. IMAGE LOGIC (Check for product keywords)
        if incoming_msg:
            image_url = get_product_image(incoming_msg)

            # Save product context if detected
            if image_url:
                # We can't easily extract the key from just URL, so re-scan keys
                for key in PRODUCT_IMAGES:
                    if key in incoming_msg.lower():
                        session["data"]["product"] = key
                        save_to_sheet(session["data"])
                        break

        # 4. PROCESSING
        if msg_type in ["audio", "audio_message"] and file_url:
            send_zoko_message(sender_phone, "Listening... 🎧")
            # History context is passed to maintain conversation flow if needed by internal logic,
            # but process_audio implements the specific prompt request.
            response_text = process_audio(file_url, session["history"])

            # Update history (mocked since we don't have the user text, only audio)
            session["history"].append({"role": "user", "parts": ["(User sent audio)"]})
            session["history"].append({"role": "model", "parts": [response_text]})

        elif msg_type == "text":
             # Start Chat with History
            chat_session = model.start_chat(
                history=[
                    {"role": "user", "parts": [SYSTEM_PROMPT]},
                    {"role": "model", "parts": ["Understood. I am AIVA."]}
                ] + session["history"]
            )

            ai_resp = chat_session.send_message(incoming_msg)
            response_text = ai_resp.text

            # Update History
            session["history"].append({"role": "user", "parts": [incoming_msg]})
            session["history"].append({"role": "model", "parts": [response_text]})

        # 5. RESPONSE
        if response_text:
            send_zoko_message(sender_phone, response_text, image_url)
            return jsonify(status="ok", response_sent=True)

    except Exception as e:
        logging.error(f"Bot Logic Error: {e}")
        return jsonify(status="error", reason=str(e)), 500

    return jsonify(status="ok")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
