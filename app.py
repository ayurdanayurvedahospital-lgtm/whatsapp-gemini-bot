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
last_greeted = {} # phone -> timestamp (tracks last greeting time for 12h rule)
followup_timers = {} # phone -> {'t1': Timer, 't2': Timer}

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

def send_zoko_message(phone, text=None, image_url=None, caption=None):
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
    recipient = phone.replace("+", "")
    url = "https://chat.zoko.io/v2/message"
    headers = {
        'apikey': ZOKO_API_KEY,
        'Content-Type': 'application/json'
    }

    # Send Image First if exists
    if image_url:
        try:
            # Ensure caption is present
            img_caption = caption if caption else "Ayurdan Ayurveda"

            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "image",
                "url": image_url,
                "caption": img_caption
            }
            logging.info(f"Sending Image to {recipient} with caption: {img_caption}")
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
                'recipient': recipient,
                'type': 'text',
                'message': text
            }
            logging.info(f"Sending Text to {recipient}")
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            logging.info(f"Text Sent: {resp.status_code}")
        except Exception as e:
            logging.error(f"Failed to send text: {e}")

def cancel_timers(phone):
    """Cancels any pending inactivity timers for a user."""
    if phone in followup_timers:
        if followup_timers[phone].get('t1'):
            try:
                followup_timers[phone]['t1'].cancel()
            except Exception: pass
        if followup_timers[phone].get('t2'):
            try:
                followup_timers[phone]['t2'].cancel()
            except Exception: pass
        del followup_timers[phone]

def send_followup_1(phone):
    """First followup after 2 minutes."""
    if phone in muted_users or check_stop_bot(phone):
        return

    logging.info(f"Sending Follow-up 1 to {phone}")
    send_zoko_message(phone, text="Just checking in 😊 Whenever you're comfortable, you can share the details. I'm here to help.")

    # Start Timer 2 (5 mins from now)
    t = threading.Timer(300, send_followup_2, args=[phone]) # 5 mins = 300s
    t.daemon = True # ensure it doesn't block exit
    if phone in followup_timers: # Check if still relevant
        followup_timers[phone]['t2'] = t
        t.start()

def send_followup_2(phone):
    """Second followup after 5 minutes."""
    if phone in muted_users or check_stop_bot(phone):
        return

    logging.info(f"Sending Follow-up 2 to {phone}")
    send_zoko_message(phone, text="Your health deserves thoughtful attention. I’m here to guide you whenever you’re ready. Please feel free to ask me anything at any time.")

    # Clean up
    if phone in followup_timers:
        del followup_timers[phone]

def start_inactivity_timer(phone):
    """Starts the first inactivity timer."""
    # Cancel old ones first to be safe
    cancel_timers(phone)

    # Start Timer 1 (2 mins)
    t = threading.Timer(120, send_followup_1, args=[phone]) # 2 mins = 120s
    t.daemon = True
    followup_timers[phone] = {'t1': t}
    t.start()

def check_stop_bot(phone):
    """
    Check if bot is stopped via Zoko tags (STOP_BOT) or cache.
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

        greeting = get_ist_time_greeting()

        history = user_sessions.get(sender_phone, [])
        chat = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": [f"Understood. I am AIVA. Current Time Greeting is: {greeting}."]}
        ] + history)

        prompt = f"Listen to this audio. You are AIVA. Current Time Greeting: {greeting}. Answer as a consultant."
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

        response = chat.send_message(message_text)
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

        # CANCEL INACTIVITY TIMERS (User Replied)
        cancel_timers(sender_phone)

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
                send_zoko_message(sender_phone, text="Bot is already active. How can I help?")

            # Start timer after resuming
            start_inactivity_timer(sender_phone)
            return

        # --- STEP 2: CHECK MUTE STATUS ---
        if sender_phone in muted_users:
            logging.info(f"User {sender_phone} is muted (talking to human). Ignoring message.")
            return

        # Check Stop Bot (Tag-based)
        if check_stop_bot(sender_phone):
            logging.info(f"Bot Stopped for {sender_phone} (Tag Check)")
            return

        if text_body and text_body.strip().upper() == "STOP BOT":
            stop_bot_cache[sender_phone] = {"stopped": True, "timestamp": time.time()}
            muted_users.add(sender_phone)
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

        # --- STEP 3: SMART GREETING LOGIC (12 HOUR RULE) ---
        current_time = time.time()
        last_time = last_greeted.get(sender_phone, 0)

        is_greeting_keyword = text_body and text_body.strip().lower() in ["hi", "hello", "start", "good morning", "good afternoon", "good evening"]

        if is_greeting_keyword and (current_time - last_time > 12 * 3600):
            time_greeting = get_ist_time_greeting()
            greeting_msg = f"{time_greeting}! ☀️ I am AIVA, the Senior Ayurvedic Expert at Ayurdan Ayurveda Hospital. I am here to understand your health concerns and guide you to the right solution. You can type your message or send a Voice Note. How may I help you today? 🌿"
            send_zoko_message(sender_phone, text=greeting_msg)
            last_greeted[sender_phone] = current_time
            logging.info(f"Sent 12h greeting to {sender_phone}")

            # Start timer after greeting
            start_inactivity_timer(sender_phone)
            return

        logging.info("STEP 4: Processing Logic (AI/Image)")

        response_text = ""
        found_image_url = None

        # Image Logic
        if text_body:
            lower_msg = text_body.lower()
            for key, url in PRODUCT_IMAGES.items():
                if key in lower_msg:
                    found_image_url = url
                    product_name = key.replace('_', ' ').title()
                    send_zoko_message(sender_phone, image_url=found_image_url, caption=product_name)
                    break

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

        logging.info("STEP 5: Sending AI Response")

        if response_text:
            if "[HANDOVER]" in response_text:
                clean_text = response_text.replace("[HANDOVER]", "").strip()
                if clean_text:
                    send_zoko_message(sender_phone, text=clean_text)

                send_zoko_message(sender_phone, text="📞 You can contact our Expert Sreelekha directly at +91 9895900809.")

                muted_users.add(sender_phone)
                logging.info(f"User {sender_phone} handed over to agent (Medical Red Flag).")
            else:
                send_zoko_message(sender_phone, text=response_text)

            # Start timer after bot replies (expecting user follow-up)
            # Unless handover happened (muted_users would prevent follow-up sending anyway, but good to check)
            if sender_phone not in muted_users:
                start_inactivity_timer(sender_phone)

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
