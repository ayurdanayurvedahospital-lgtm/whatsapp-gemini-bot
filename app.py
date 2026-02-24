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

# Configure basic logging for local/dev use
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Link Flask logger to Gunicorn logger if running under Gunicorn
if __name__ != '__main__':
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

logging.info("App Starting...")

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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
ZOKO_API_KEY = os.environ.get("ZOKO_API_KEY")

# Shopify Config
SHOPIFY_DOMAIN = os.environ.get("SHOPIFY_DOMAIN")
SHOPIFY_CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET")

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error(f"Gemini Configure Error: {e}")
else:
    logging.warning("GEMINI_API_KEY not set!")

if not ZOKO_API_KEY:
    logging.warning("ZOKO_API_KEY not set!")

if not all([SHOPIFY_DOMAIN, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET]):
    logging.warning("Shopify Credentials missing! Order tracking will fail.")

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
user_order_state = {} # phone -> boolean (True if expecting order details)

# --- HELPER FUNCTIONS ---

def get_shopify_token():
    """
    Obtains a temporary access token via Client Credentials Flow.
    """
    try:
        url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/access_token"
        payload = {
            "client_id": SHOPIFY_CLIENT_ID,
            "client_secret": SHOPIFY_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        logging.error(f"Shopify Token Error: {e}")
        return None

def get_order_status(identifier):
    """
    Searches for an order by Name (e.g., #1001) or Phone Number.
    """
    token = get_shopify_token()
    if not token:
        return "I am unable to access the order system right now. Please try again later."

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json"
    }

    try:
        # 1. Search by Order Name (e.g., "#1001" or "1001")
        # Ensure it starts with # if digits only, or just search
        search_term = identifier
        if identifier.isdigit():
             search_term = f"#{identifier}"

        url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/orders.json?name={search_term}&status=any"
        resp = requests.get(url, headers=headers, timeout=10)
        def format_order_response(order):
            order_name = order.get('name', '')
            fulfillments = order.get('fulfillments', [])

            # Debug Log
            logging.info(f"DEBUG: Order {order_name} fulfillments data: {fulfillments}")

            contact_info = "\n\nPlease contact this number 919526530900 (9:30 am to 5 pm) if you have any queries in tracking details."

            if fulfillments:
                tracking_url = "Not Available"
                if fulfillments[0].get('tracking_url'):
                    tracking_url = fulfillments[0].get('tracking_url')

                return f"Your order *{order_name}* is *fulfilled*. Tracking: {tracking_url}{contact_info}"
            else:
                # partial, null (None), or unfulfilled (empty fulfillments list)
                return f"Your order is not fulfilled yet. It's getting ready, once fulfilled you will be receiving a message.{contact_info}"

        if resp.status_code == 200:
            orders = resp.json().get("orders", [])
            if orders:
                return format_order_response(orders[0])

        # 2. If not found, try searching by Phone (requires Customer Search first)
        # Search Customer by Phone
        phone_query = identifier.replace(" ", "")
        cust_url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/customers/search.json?query=phone:{phone_query}"
        cust_resp = requests.get(cust_url, headers=headers, timeout=10)

        if cust_resp.status_code == 200:
            customers = cust_resp.json().get("customers", [])
            if customers:
                cust_id = customers[0]['id']
                # Get Last Order for this customer
                order_url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/customers/{cust_id}/orders.json?status=any&limit=1"
                order_resp = requests.get(order_url, headers=headers, timeout=10)
                if order_resp.status_code == 200:
                    orders = order_resp.json().get("orders", [])
                    if orders:
                        return format_order_response(orders[0])

        return "I couldn't find an order with those details. Please check the number and try again."

    except Exception as e:
        logging.error(f"Shopify Order Lookup Error: {e}")
        return "I encountered an error while checking your order. Please try again later."

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

def get_current_time_str():
    """Returns formatted current time string in IST (e.g. '10:30 PM')"""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        return now.strftime("%I:%M %p")
    except Exception as e:
        logging.error(f"Time Str Error: {e}")
        return "Unknown Time"

def send_whatsapp_message(to_number, message_text, message_type="text", image_url=None):
    # FIX: Removed the leading space in the URL
    url = "https://chat.zoko.io/v2/message"

    headers = {
        "apikey": os.environ.get("ZOKO_API_KEY"),
        "Content-Type": "application/json"
    }

    if message_type == "text":
        payload = {
            "channel": "whatsapp",
            "recipient": to_number,
            "type": "text",
            "message": message_text
        }

    elif message_type == "image":
        # FIX: Ensure 'message' key is used for captions (not 'caption')
        if not image_url or not image_url.startswith("http"):
            logging.warning(f"Invalid image URL: {image_url}. Falling back to text.")
            payload = {
                "channel": "whatsapp",
                "recipient": to_number,
                "type": "text",
                "message": message_text if message_text else "Image unavailable."
            }
        else:
            payload = {
                "channel": "whatsapp",
                "recipient": to_number,
                "type": "image",
                "url": image_url,
                "message": message_text if message_text else "Here is the image."
            }

    try:
        response = requests.post(url, json=payload, headers=headers)
        logging.info(f"Sent {message_type}: {response.status_code}")
        if response.status_code >= 400:
             logging.error(f"Zoko API Error: {response.text}")
        return response.json()
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return None

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
    send_whatsapp_message(phone.replace("+", ""), "Just checking in 😊 Whenever you're comfortable, you can share the details. I'm here to help.", "text")

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
    send_whatsapp_message(phone.replace("+", ""), "Your health deserves thoughtful attention. I’m here to guide you whenever you’re ready. Please feel free to ask me anything at any time.", "text")

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
    Process audio file via Gemini with robust error handling.
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

        try:
            myfile = genai.upload_file(local_filename, mime_type='audio/ogg')

            while myfile.state.name == "PROCESSING":
                time.sleep(1)
                myfile = genai.get_file(myfile.name)

            if myfile.state.name == "FAILED":
                raise ValueError("Audio processing failed in Gemini.")

            greeting = get_ist_time_greeting()
            current_time_str = get_current_time_str()

            history = user_sessions.get(sender_phone, [])
            chat = model.start_chat(history=[
                {"role": "user", "parts": [SYSTEM_PROMPT]},
                {"role": "model", "parts": [f"Understood. I am AIVA. Current Time Greeting is: {greeting}."]}
            ] + history)

            prompt = f"Listen to this audio. You are AIVA. Current time in Kerala is {current_time_str}. Answer as a consultant."
            response = chat.send_message([myfile, prompt])
            reply_text = response.text
            # 1. Strip <think> tags if the AI uses them correctly
            reply_text = re.sub(r'<think>.*?</think>', '', reply_text, flags=re.DOTALL | re.IGNORECASE)

            # 2. Aggressively strip rogue paragraphs that start with "Think:", "തിങ്ക്:", "ദി യൂസർ" or "The user"
            # This deletes the entire thought paragraph up to the line break where the actual reply begins.
            reply_text = re.sub(r'^(?:തിങ്ക്|Think|THOUGHT|Thinking|The user|ദി യൂസർ).*?(?:\n|$)', '', reply_text, flags=re.MULTILINE | re.IGNORECASE).strip()
            return reply_text

        except Exception as e:
            logging.error(f"Gemini Audio API Error: {e}")
            return "I'm sorry, I couldn't hear that clearly. Could you please type your message?"

    except Exception as e:
        logging.error(f"Audio Download/Process Error: {e}")
        return "I'm sorry, I couldn't hear that clearly. Could you please type your message?"
    finally:
        if local_filename and os.path.exists(local_filename):
            try:
                os.remove(local_filename)
                logging.info(f"Cleaned up temp file: {local_filename}")
            except Exception as e:
                logging.error(f"Failed to cleanup temp file: {e}")

def process_image(file_url, sender_phone, prompt_text):
    local_filename = None
    try:
        logging.info(f"Downloading Image: {file_url}")
        with requests.get(file_url, stream=True) as r:
            r.raise_for_status()
            ext = ".jpg"
            if "png" in file_url.lower(): ext = ".png"
            elif "webp" in file_url.lower(): ext = ".webp"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        logging.info("Uploading Image to Gemini...")
        try:
            myfile = genai.upload_file(local_filename)
            while myfile.state.name == "PROCESSING":
                time.sleep(1)
                myfile = genai.get_file(myfile.name)

            if myfile.state.name == "FAILED":
                raise ValueError("Image processing failed in Gemini.")

            greeting = get_ist_time_greeting()
            current_time_str = get_current_time_str()
            history = user_sessions.get(sender_phone, [])

            chat = model.start_chat(history=[
                {"role": "user", "parts": [SYSTEM_PROMPT]},
                {"role": "model", "parts": [f"Understood. I am AIVA. Current Time Greeting is: {greeting}."]}
            ] + history)

            user_prompt = prompt_text if prompt_text else "Please analyze this image regarding my health."
            full_prompt = f"Look at this image. Current time in Kerala is {current_time_str}. User says: {user_prompt}. Apply the Universal Language Protocol and answer as an expert."

            response = chat.send_message([myfile, full_prompt])

            try:
                reply_text = response.text
            except ValueError:
                logging.warning(f"Gemini returned an empty image response.")
                return "I'm sorry, I couldn't quite process that image. Could you please describe it?"

            reply_text = re.sub(r'<think>.*?</think>', '', reply_text, flags=re.DOTALL | re.IGNORECASE)
            reply_text = re.sub(r'^(?:തിങ്ക്|Think|THOUGHT|Thinking|The user|ദി യൂസർ).*?(?:\n|$)', '', reply_text, flags=re.MULTILINE | re.IGNORECASE).strip()
            return reply_text

        except Exception as e:
            logging.error(f"Gemini Image API Error: {e}")
            return "I'm sorry, I couldn't analyze the image properly. Could you please describe it?"

    except Exception as e:
        logging.error(f"Image Download/Process Error: {e}")
        return "I'm sorry, I couldn't download the image. Could you please try again?"
    finally:
        if local_filename and os.path.exists(local_filename):
            try:
                os.remove(local_filename)
            except Exception: pass

def get_ai_response(sender_phone, message_text, history):
    try:
        if not model:
            return "I am currently undergoing maintenance. Please try again later."

        greeting = get_ist_time_greeting()
        current_time_str = get_current_time_str()

        system_instruction = SYSTEM_PROMPT
        context_injection = f" Current time in Kerala is {current_time_str}."
        model_ack = f"Understood. I am AIVA. Current Time Greeting is: {greeting}.{context_injection} I am actively monitoring the user's language and will instantly mirror their language and script as per the Universal Language Protocol."

        chat_history = [
            {"role": "user", "parts": [system_instruction]},
            {"role": "model", "parts": [model_ack]}
        ] + history

        chat = model.start_chat(history=chat_history)

        response = chat.send_message(message_text)
        reply_text = response.text
        # 1. Strip <think> tags if the AI uses them correctly
        reply_text = re.sub(r'<think>.*?</think>', '', reply_text, flags=re.DOTALL | re.IGNORECASE)

        # 2. Aggressively strip rogue paragraphs that start with "Think:", "തിങ്ക്:", "ദി യൂസർ" or "The user"
        # This deletes the entire thought paragraph up to the line break where the actual reply begins.
        reply_text = re.sub(r'^(?:തിങ്ക്|Think|THOUGHT|Thinking|The user|ദി യൂസർ).*?(?:\n|$)', '', reply_text, flags=re.MULTILINE | re.IGNORECASE).strip()
        return reply_text
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
                send_whatsapp_message(sender_phone.replace("+", ""), "Bot resumed. How can I help?", "text")
            else:
                send_whatsapp_message(sender_phone.replace("+", ""), "Bot is already active. How can I help?", "text")

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
            send_whatsapp_message(sender_phone.replace("+", ""), "Bot has been stopped for this chat.", "text")
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

        # --- STEP 3: ORDER TRACKING PROTOCOL ---
        is_tracking_intent = text_body and any(k in text_body.lower() for k in ["where is my order", "track my order", "order status", "track order", "status of my order"])

        # Case A: User explicitly asks to track
        if is_tracking_intent:
            # Check if they provided a number in the same message (digits > 3)
            potential_id = "".join(filter(str.isdigit, text_body))
            if len(potential_id) > 3:
                 status_msg = get_order_status(potential_id)
                 send_whatsapp_message(sender_phone.replace("+", ""), status_msg, "text")
                 # Reset state (Pivot back to AIVA implicitly)
                 user_order_state[sender_phone] = False
                 return
            else:
                 # Ask for details
                 user_order_state[sender_phone] = True
                 send_whatsapp_message(sender_phone.replace("+", ""), "Please enter the *Mobile Number* used for the order or your *Order Number*.", "text")
                 return

        # Case B: User is in Tracking Mode (waiting for input)
        if user_order_state.get(sender_phone):
            # Check if user is trying to pivot back to health (Health keyword check)
            # Simple heuristic: If it contains medical keywords or is long text
            is_health_query = any(k in text_body.lower() for k in ["pain", "weight", "hair", "skin", "diabetes", "sugar", "gain", "loss", "sleep"])

            if is_health_query:
                user_order_state[sender_phone] = False
                # Fall through to AIVA logic below
            else:
                # Treat as Order ID/Phone
                status_msg = get_order_status(text_body)
                send_whatsapp_message(sender_phone.replace("+", ""), status_msg, "text")
                user_order_state[sender_phone] = False

                # Check if we should pivot back explicitly?
                # "Post-Lookup: After providing details, if they ask a health question, pivot back..."
                # The user will likely reply to this status.
                # If they say "Thanks", the next message will hit AIVA.
                return

        # --- STEP 4: SMART GREETING LOGIC (12 HOUR RULE) ---
        current_time = time.time()
        last_time = last_greeted.get(sender_phone, 0)

        is_greeting_keyword = text_body and text_body.strip().lower() in ["hi", "hello", "start", "good morning", "good afternoon", "good evening"]

        if is_greeting_keyword and (current_time - last_time > 12 * 3600):
            time_greeting = get_ist_time_greeting()
            greeting_msg = f"{time_greeting} I am AIVA, the Senior Ayurvedic Expert at Ayurdan Ayurveda Hospital. I am here to understand your health concerns and guide you to the right solution. You can type your message or send a Voice Note in *Any Language*. How may I help you today? 🌿"
            send_whatsapp_message(sender_phone.replace("+", ""), greeting_msg, "text")
            last_greeted[sender_phone] = current_time
            logging.info(f"Sent 12h greeting to {sender_phone}")

            # Start timer after greeting
            start_inactivity_timer(sender_phone)
            return

        logging.info("STEP 5: Processing Logic (AI/Image)")

        response_text = ""
        found_image_url = None

        # Image Logic
        if text_body:
            lower_msg = text_body.lower()
            for key, val in PRODUCT_IMAGES.items():
                if key in lower_msg:
                    found_image_url = val
                    # Extract URL if it's in markdown format [url](url)
                    match = re.search(r'\((https?://.*?)\)', val)
                    if match:
                        found_image_url = match.group(1)

                    product_name = key.replace('_', ' ').title()
                    send_whatsapp_message(sender_phone.replace("+", ""), product_name, "image", image_url=found_image_url)
                    break

        # Image, Audio vs Text Logic
        if msg_type == "image" and file_url:
            send_whatsapp_message(sender_phone.replace("+", ""), "Analyzing your image... 👁️", "text")
            response_text = process_image(file_url, sender_phone, text_body)
        elif msg_type == "audio" and file_url:
            send_whatsapp_message(sender_phone.replace("+", ""), "Listening... 🎧", "text")
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

        logging.info("STEP 6: Sending AI Response")

        if response_text:
            if "[HANDOVER]" in response_text:
                clean_text = response_text.replace("[HANDOVER]", "").strip()
                if clean_text:
                    send_whatsapp_message(sender_phone.replace("+", ""), clean_text, "text")

                send_whatsapp_message(sender_phone.replace("+", ""), "📞 You can contact our Expert Sreelekha directly at +91 9895900809.", "text")

                muted_users.add(sender_phone)
                logging.info(f"User {sender_phone} handed over to agent (Medical Red Flag).")
            else:
                send_whatsapp_message(sender_phone.replace("+", ""), response_text, "text")

            # Start timer after bot replies (expecting user follow-up)
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
    # Render assigns a random port to the PORT environment variable
    # The app MUST listen on 0.0.0.0 to be accessible
    # Defaulting to 8080 as it's a standard cloud port
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
