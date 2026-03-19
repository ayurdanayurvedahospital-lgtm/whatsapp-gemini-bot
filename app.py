import os
import logging
import threading
import time
import re
import traceback
import requests
import flask
from google import genai
from google.genai import types
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


if not ZOKO_API_KEY:
    logging.warning("ZOKO_API_KEY not set!")

if not all([SHOPIFY_DOMAIN, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET]):
    logging.warning("Shopify Credentials missing! Order tracking will fail.")

# Initialize Gemini Client
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error(f"Gemini Client Init Error: {e}")
else:
    logging.warning("GEMINI_API_KEY not set!")

# --- GLOBAL STATE ---
user_sessions = {} # phone -> list of messages
user_last_active = {} # phone -> timestamp
stop_bot_cache = {}
CACHE_TTL = 300
processed_messages = set()
processed_messages_lock = threading.Lock()
user_last_messages = {}
muted_users = set()  # Tracks users currently talking to a human agent
last_greeted = {} # phone -> timestamp (tracks last greeting time for 12h rule)
followup_timers = {} # phone -> {'t1': Timer, 't2': Timer}
user_order_state = {} # phone -> boolean (True if expecting order details)

# Shopify Token Cache
shopify_token_cache = {"access_token": None, "expires_at": 0}
shopify_token_lock = threading.Lock()

# --- HELPER FUNCTIONS ---

def get_user_history(phone):
    """
    Retrieves history for a user, clearing it if inactive for >12 hours.
    Returns a rolling window of the last 14 messages.
    """
    now = time.time()
    last_active = user_last_active.get(phone, 0)

    # Action 2: 12-hour inactivity clearing
    if now - last_active > 12 * 3600:
        user_sessions[phone] = []

    history = user_sessions.get(phone, [])
    # Action 2: Strict rolling window (last 14)
    return history[-14:]

def save_user_history(phone, history):
    """
    Updates user history and activity timestamp.
    """
    user_sessions[phone] = history[-14:]
    user_last_active[phone] = time.time()

def get_shopify_token():
    """
    Obtains a temporary access token via Client Credentials Flow, with caching.
    Uses double-checked locking to minimize lock contention.
    """
    global shopify_token_cache

    now = time.time()
    # Fast path: check without lock
    if shopify_token_cache["access_token"] and shopify_token_cache["expires_at"] > now + 60:
        return shopify_token_cache["access_token"]

    with shopify_token_lock:
        # Second check after acquiring lock
        now = time.time()
        if shopify_token_cache["access_token"] and shopify_token_cache["expires_at"] > now + 60:
            return shopify_token_cache["access_token"]

        try:
            url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/access_token"
            payload = {
                "client_id": SHOPIFY_CLIENT_ID,
                "client_secret": SHOPIFY_CLIENT_SECRET,
                "grant_type": "client_credentials"
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            token = data.get("access_token")
            # Default to 3600 seconds if 'expires_in' is not provided
            expires_in = data.get("expires_in", 3600)

            if token:
                shopify_token_cache = {
                    "access_token": token,
                    "expires_at": now + expires_in
                }
            return token
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

    # Start Timer 2 (30 mins from now)
    t = threading.Timer(1800, send_followup_2, args=[phone]) # 30 mins = 1800s
    t.daemon = True # ensure it doesn't block exit
    if phone in followup_timers: # Check if still relevant
        followup_timers[phone]['t2'] = t
        t.start()

def send_followup_2(phone):
    """Second followup after 30 minutes."""
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

def call_gemini_with_retry(contents):
    """
    Helper to call Gemini with automatic fallback on quota exhaustion.
    Inverted Architecture: Gemini 3 Flash as Primary, 2.5 Pro as Fallback.
    """
    if not client:
        return "I am currently undergoing maintenance. Please try again later."

    # Action 1: Gemini 3 Flash Primary Config
    flash_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level="minimal",
            include_thoughts=False
        )
    )

    # Action 2: Gemini 2.5 Pro Fallback Config (Preserved)
    pro_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=1024
        )
    )

    raw_text = ""
    try:
        # 1. Attempt with Primary Model (Gemini 3 Flash)
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=contents,
            config=flash_config
        )
        raw_text = response.text
    except Exception as e:
        err_str = str(e).lower()
        # 2. Handle Quota/Rate Limit (429) via Fallback to Pro
        if "429" in err_str or "quota" in err_str:
            print("FLASH QUOTA EXCEEDED (429). Falling back to Pro...")
            try:
                # Nested fallback to Pro
                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=contents,
                    config=pro_config
                )
                raw_text = response.text
            except Exception as pro_e:
                print(f"CRITICAL SDK ERROR (Pro Fallback Failed): {str(pro_e)}")
                return "I am just double-checking your details with our senior experts. Give me just a moment, and I will get right back to you!"
        else:
            # 3. Handle Other Errors immediately
            print(f"CRITICAL SDK ERROR: {str(e)}")
            logging.error(f"Gemini Error: {e}")
            return "I am just double-checking your details with our senior experts. Give me just a moment, and I will get right back to you!"

    # Action 3: Global Anti-Leak Filter (HTML Comments + Structural Labels)
    clean_text = re.sub(r'<!--.*?-->', '', raw_text, flags=re.DOTALL)
    filtered_text = re.sub(r'(?i)\*?(AEAC|Awareness|Education|Authority|Closing|അവബോധം|വിദ്യാഭ്യാസം|അധികാരം|ക്ലോസിംഗ്|Thought)\*?:?\s*', '', clean_text).strip()
    # Action 4: WhatsApp Formatting Fix (Double Asterisks -> Single Asterisks)
    final_output = filtered_text.replace('**', '*')
    return final_output

def process_audio(file_url, sender_phone, history):
    """
    Process audio file via Gemini with robust error handling.
    """
    local_filename = None
    headers = {'apikey': ZOKO_API_KEY}
    try:
        logging.info(f"Downloading Audio: {file_url}")
        with requests.get(file_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        logging.info("Uploading Audio to Gemini...")

        try:
            myfile = client.files.upload(file=local_filename, config={'mime_type': 'audio/ogg'})

            while myfile.state == "PROCESSING":
                time.sleep(1)
                myfile = client.files.get(name=myfile.name)

            if myfile.state == "FAILED":
                raise ValueError("Audio processing failed in Gemini.")

            greeting = get_ist_time_greeting()
            current_time_str = get_current_time_str()

            # Construct conversation with history
            contents = [
                types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]),
                types.Content(role="model", parts=[types.Part.from_text(text=f"Understood. I am AIVA. Current Time Greeting is: {greeting}.")]),
            ]

            # Map history to types.Content
            for h in history:
                role = "user" if h["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["parts"][0])]))

            # Add final audio part and prompt
            audio_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='audio/ogg')
            text_part = types.Part.from_text(text=f"Listen to this audio. You are AIVA. Current time in Kerala is {current_time_str}. Answer as a consultant.")
            contents.append(types.Content(role="user", parts=[audio_part, text_part]))

            return call_gemini_with_retry(contents)

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

def process_image(file_url, sender_phone, prompt_text, history):
    local_filename = None
    headers = {'apikey': ZOKO_API_KEY}
    try:
        logging.info(f"Downloading Image: {file_url}")
        with requests.get(file_url, stream=True, headers=headers) as r:
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
            myfile = client.files.upload(file=local_filename)
            while myfile.state == "PROCESSING":
                time.sleep(1)
                myfile = client.files.get(name=myfile.name)

            if myfile.state == "FAILED":
                raise ValueError("Image processing failed in Gemini.")

            greeting = get_ist_time_greeting()
            current_time_str = get_current_time_str()

            contents = [
                types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]),
                types.Content(role="model", parts=[types.Part.from_text(text=f"Understood. I am AIVA. Current Time Greeting is: {greeting}.")]),
            ]

            for h in history:
                role = "user" if h["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["parts"][0])]))

            user_prompt = prompt_text if prompt_text else "Please analyze this image regarding my health."
            image_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='image/jpeg') # mime_type is optional/auto
            text_part = types.Part.from_text(text=f"Look at this image. Current time in Kerala is {current_time_str}. User says: {user_prompt}. Apply the Universal Language Protocol and answer as an expert.")
            contents.append(types.Content(role="user", parts=[image_part, text_part]))

            return call_gemini_with_retry(contents)

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

def process_pdf(file_url, sender_phone, history):
    local_filename = None
    headers = {'apikey': ZOKO_API_KEY}
    try:
        logging.info(f"Downloading PDF: {file_url}")
        with requests.get(file_url, stream=True, headers=headers) as r:
            r.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                local_filename = tmp.name

        logging.info("Uploading PDF to Gemini...")
        try:
            myfile = client.files.upload(file=local_filename)
            while myfile.state == "PROCESSING":
                time.sleep(1)
                myfile = client.files.get(name=myfile.name)

            if myfile.state == "FAILED":
                raise ValueError("PDF processing failed in Gemini.")

            greeting = get_ist_time_greeting()
            current_time_str = get_current_time_str()

            contents = [
                types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]),
                types.Content(role="model", parts=[types.Part.from_text(text=f"Understood. I am AIVA. Current Time Greeting is: {greeting}.")]),
            ]

            for h in history:
                role = "user" if h["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["parts"][0])]))

            pdf_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='application/pdf')
            text_part = types.Part.from_text(text=f"The user uploaded a medical document. Current time in Kerala is {current_time_str}. Please analyze the findings and respond as an expert.")
            contents.append(types.Content(role="user", parts=[pdf_part, text_part]))

            return call_gemini_with_retry(contents)

        except Exception as e:
            logging.error(f"Gemini PDF API Error: {e}")
            return "I received your document, but I am unable to read its contents. Could you please send it as a clear image or type out the details?"

    except Exception as e:
        logging.error(f"PDF Download/Process Error: {e}")
        return "I received your document, but I am unable to read its contents. Could you please send it as a clear image or type out the details?"
    finally:
        if local_filename and os.path.exists(local_filename):
            try:
                os.remove(local_filename)
            except Exception: pass

def get_ai_response(sender_phone, message_text, history):
    try:
        greeting = get_ist_time_greeting()
        current_time_str = get_current_time_str()

        system_instruction = SYSTEM_PROMPT
        context_injection = f" Current time in Kerala is {current_time_str}."
        model_ack = f"Understood. I am AIVA. Current Time Greeting is: {greeting}.{context_injection} I am actively monitoring the user's language and will instantly mirror their language and script as per the Universal Language Protocol."

        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=system_instruction)]),
            types.Content(role="model", parts=[types.Part.from_text(text=model_ack)])
        ]

        for h in history:
            role = "user" if h["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["parts"][0])]))

        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

        return call_gemini_with_retry(contents)
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
            greeting_msg = (
                f"{time_greeting}! I’m AIVA, Ayurvedic Expert at Ayurdan Ayurveda Hospital.\n"
                "Please share your health concern in *Any Language* so I can guide you to the right solution.\n\n"
                "നിങ്ങളുടെ ആരോഗ്യപരമായ എന്ത് ബുദ്ധിമുട്ടുകളും *ഏത് ഭാഷയിലും* ഞങ്ങളോട് പങ്കുവെക്കാവുന്നതാണ് "
            )
            send_whatsapp_message(sender_phone.replace("+", ""), greeting_msg, "text")
            last_greeted[sender_phone] = current_time
            logging.info(f"Sent 12h greeting to {sender_phone}")

            # Start timer after greeting
            start_inactivity_timer(sender_phone)
            return

        logging.info("STEP 5: Processing Logic (AI/Image)")

        response_text = ""
        found_image_url = None

        # Action 1: Retrieve Session History
        history = get_user_history(sender_phone)
        user_input_for_history = text_body

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

        # Image, Audio, PDF vs Text Logic
        if msg_type == "document" and file_url and file_url.lower().endswith(".pdf"):
            send_whatsapp_message(sender_phone.replace("+", ""), "Reading your document... 📄", "text")
            response_text = process_pdf(file_url, sender_phone, history)
            if not user_input_for_history: user_input_for_history = "[Sent a PDF document]"
        elif msg_type == "image" and file_url:
            send_whatsapp_message(sender_phone.replace("+", ""), "Analyzing your image... 👁️", "text")
            response_text = process_image(file_url, sender_phone, text_body, history)
            if not user_input_for_history: user_input_for_history = "[Sent an image]"
        elif msg_type == "audio" and file_url:
            send_whatsapp_message(sender_phone.replace("+", ""), "Listening... 🎧", "text")
            response_text = process_audio(file_url, sender_phone, history)
            if not user_input_for_history: user_input_for_history = "[Sent an audio message]"
        elif text_body or msg_type == "text":
            response_text = get_ai_response(sender_phone, text_body, history)

        if response_text:
            # Action 1: Update and Save History
            history.append({"role": "user", "parts": [user_input_for_history]})
            history.append({"role": "model", "parts": [response_text]})
            save_user_history(sender_phone, history)

        logging.info("STEP 6: Sending AI Response")

        if response_text:
            if "[HANDOVER]" in response_text:
                clean_text = response_text.replace("[HANDOVER]", "").strip()
                if clean_text:
                    send_whatsapp_message(sender_phone.replace("+", ""), clean_text, "text")

                send_whatsapp_message(sender_phone.replace("+", ""), "📞 You can contact our Senior Health Expert directly at +91 9072727201 (Note: Call only, No WhatsApp).", "text")

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

if __name__ == '__main__':
    # Render provides the PORT dynamically. Default to 10000 if running locally.
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
