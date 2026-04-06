# ==========================================
# Bot Architecture & Logic Created By: Balamurali V,  for Ayurdan Ayurveda Hospital
# ==========================================
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
GEMINI_PROCESSING_TIMEOUT = 60 # Seconds to wait for file processing

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
cached_system_prompt = None
cache_expiry = 0
system_prompt_lock = threading.Lock()

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

# Automated Reminder Strings for filtering from AI context
REMINDER_MESSAGES = [
    "Just checking in 😊 Whenever you're comfortable, you can share the details. I'm here to help.",
    "Your health deserves thoughtful attention. I’m here to guide you whenever you’re ready. Please feel free to ask me anything at any time."
]

# Shopify Token Cache
shopify_token_cache = {"access_token": None, "expires_at": 0}
shopify_token_lock = threading.Lock()

# --- HELPER FUNCTIONS ---

def get_cached_system_prompt_name(model_name):
    """Creates or retrieves a Gemini Context Cache for the SYSTEM_PROMPT."""
    global cached_system_prompt, cache_expiry
    now = time.time()
    with system_prompt_lock:
        if cached_system_prompt and cache_expiry > now + 300:
            return cached_system_prompt
        try:
            logging.info(f"Creating Context Cache for model: {model_name}...")
            cache = client.caches.create(
                model=model_name,
                config=types.CreateCachedContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    ttl="3600s",
                    display_name="AIVA_SYSTEM_PROMPT_CACHE"
                )
            )
            cached_system_prompt = cache.name
            cache_expiry = now + 3600
            logging.info(f"Cache created successfully: {cached_system_prompt}")
            return cached_system_prompt
        except Exception as e:
            logging.error(f"Context Caching Error: {e}")
            return None

def get_user_history(phone):
    """Retrieves rolling window of last 10 relevant messages."""
    now = time.time()
    last_active = user_last_active.get(phone, 0)
    if now - last_active > 12 * 3600:
        user_sessions[phone] = []
    history = user_sessions.get(phone, [])
    return history[-10:]

def save_user_history(phone, history):
    user_sessions[phone] = history[-10:]
    user_last_active[phone] = time.time()

def get_shopify_token():
    global shopify_token_cache
    now = time.time()
    if shopify_token_cache["access_token"] and shopify_token_cache["expires_at"] > now + 60:
        return shopify_token_cache["access_token"]
    with shopify_token_lock:
        now = time.time()
        if shopify_token_cache["access_token"] and shopify_token_cache["expires_at"] > now + 60:
            return shopify_token_cache["access_token"]
        try:
            url = f"https://{SHOPIFY_DOMAIN}/admin/oauth/access_token"
            payload = {"client_id": SHOPIFY_CLIENT_ID, "client_secret": SHOPIFY_CLIENT_SECRET, "grant_type": "client_credentials"}
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            if token: shopify_token_cache = {"access_token": token, "expires_at": now + expires_in}
            return token
        except Exception as e:
            logging.error(f"Shopify Token Error: {e}"); return None

def get_order_status(identifier):
    token = get_shopify_token()
    if not token: return "I am unable to access the order system right now."
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    try:
        search_term = identifier
        if identifier.isdigit(): search_term = f"#{identifier}"
        url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/orders.json?name={search_term}&status=any"
        resp = requests.get(url, headers=headers, timeout=10)
        def format_order_response(order):
            order_name = order.get('name', '')
            fulfillments = order.get('fulfillments', [])
            contact_info = "\n\nPlease contact 919526530900 (9:30 am to 5 pm) for tracking queries."
            if fulfillments:
                tracking_url = fulfillments[0].get('tracking_url', 'Not Available')
                return f"Your order *{order_name}* is *fulfilled*. Tracking: {tracking_url}{contact_info}"
            return f"Your order is not fulfilled yet. It's getting ready.{contact_info}"
        if resp.status_code == 200:
            orders = resp.json().get("orders", [])
            if orders: return format_order_response(orders[0])
        phone_query = identifier.replace(" ", "")
        cust_url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/customers/search.json?query=phone:{phone_query}"
        cust_resp = requests.get(cust_url, headers=headers, timeout=10)
        if cust_resp.status_code == 200:
            customers = cust_resp.json().get("customers", [])
            if customers:
                cust_id = customers[0]['id']
                order_url = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/customers/{cust_id}/orders.json?status=any&limit=1"
                order_resp = requests.get(order_url, headers=headers, timeout=10)
                if order_resp.status_code == 200:
                    orders = order_resp.json().get("orders", [])
                    if orders: return format_order_response(orders[0])
        return "I couldn't find an order with those details."
    except Exception as e:
        logging.error(f"Shopify Order Lookup Error: {e}"); return "I encountered an error while checking your order."

def get_ist_time_greeting():
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        hour = now.hour
        if 5 <= hour < 12: return "Good Morning"
        elif 12 <= hour < 17: return "Good Afternoon"
        return "Good Evening"
    except Exception: return "Hello"

def get_current_time_str():
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist); return now.strftime("%I:%M %p")
    except Exception: return "Unknown Time"

def send_whatsapp_message(to_number, message_text, message_type="text", image_url=None):
    url = "https://chat.zoko.io/v2/message"
    headers = {"apikey": os.environ.get("ZOKO_API_KEY"), "Content-Type": "application/json"}
    payload = {"channel": "whatsapp", "recipient": to_number, "type": message_type, "message": message_text}
    if message_type == "image": payload["url"] = image_url
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        logging.error(f"Failed to send message: {e}"); return None

def cancel_timers(phone):
    if phone in followup_timers:
        if followup_timers[phone].get('t1'): followup_timers[phone]['t1'].cancel()
        if followup_timers[phone].get('t2'): followup_timers[phone]['t2'].cancel()
        del followup_timers[phone]

def send_followup_1(phone):
    if phone in muted_users or check_stop_bot(phone): return
    send_whatsapp_message(phone.replace("+", ""), "Just checking in 😊", "text")
    t = threading.Timer(1800, send_followup_2, args=[phone])
    t.daemon = True
    if phone in followup_timers: followup_timers[phone]['t2'] = t; t.start()

def send_followup_2(phone):
    if phone in muted_users or check_stop_bot(phone): return
    send_whatsapp_message(phone.replace("+", ""), "Your health deserves thoughtful attention.", "text")
    if phone in followup_timers: del followup_timers[phone]

def start_inactivity_timer(phone):
    cancel_timers(phone)
    t = threading.Timer(120, send_followup_1, args=[phone])
    t.daemon = True
    followup_timers[phone] = {'t1': t}; t.start()

def check_stop_bot(phone):
    now = time.time()
    if phone in stop_bot_cache:
        cached = stop_bot_cache[phone]
        if now - cached["timestamp"] < CACHE_TTL: return cached["stopped"]
    if not ZOKO_API_KEY: return False
    is_stopped = False
    try:
        url = f"https://chat.zoko.io/v2/chats?phone={phone}"
        resp = requests.get(url, headers={'apikey': ZOKO_API_KEY}, timeout=5)
        if resp.status_code == 200:
            data = resp.json(); chat_data = data.get('data', []) if isinstance(data, dict) else data
            def has_stop_tag(tags):
                for t in tags:
                    name = t if isinstance(t, str) else t.get('name', '')
                    if name.lower() == "stop_bot": return True
                return False
            if isinstance(chat_data, list):
                for chat in chat_data:
                    if has_stop_tag(chat.get('tags', [])): is_stopped = True; break
            elif isinstance(chat_data, dict):
                 if has_stop_tag(chat_data.get('tags', [])): is_stopped = True
    except Exception: pass
    stop_bot_cache[phone] = {"stopped": is_stopped, "timestamp": now}
    return is_stopped

def call_gemini_with_retry(contents, system_instruction=None, cached_content=None):
    if not client: return "I am currently undergoing maintenance."
    primary_model = "gemini-2.0-flash"; fallback_model = "gemini-1.5-pro"
    flash_config = types.GenerateContentConfig(system_instruction=system_instruction, cached_content=cached_content, max_output_tokens=300)
    pro_config = types.GenerateContentConfig(system_instruction=system_instruction if not cached_content else SYSTEM_PROMPT, max_output_tokens=300)
    try:
        response = client.models.generate_content(model=primary_model, contents=contents, config=flash_config)
        raw_text = response.text
    except Exception as e:
        err = str(e).lower()
        if any(x in err for x in ["429", "quota", "500", "503", "timeout"]):
            try:
                response = client.models.generate_content(model=fallback_model, contents=contents, config=pro_config)
                raw_text = response.text
            except Exception: return "I am checking details with experts."
        else: return "I am checking details with experts."
    clean_text = re.sub(r'<!--.*?-->', '', raw_text, flags=re.DOTALL)
    filtered = re.sub(r'(?i)\*?(AEAC|Awareness|Education|Authority|Closing|അവബോധം|വിദ്യാഭ്യാസം|അധികാരം|ക്ലോസിംഗ്|Thought)\*?:?\s*', '', clean_text).strip()
    return filtered.replace('**', '*')

def get_contents_with_history(history, model_ack, cache_active):
    contents = []
    last_role = None
    if not cache_active:
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=SYSTEM_PROMPT)]))
        contents.append(types.Content(role="model", parts=[types.Part.from_text(text=model_ack)]))
        last_role = "model"
    for h in history:
        text = h["parts"][0]
        if h["role"] == "model" and any(rem in text for rem in REMINDER_MESSAGES): continue
        role = "user" if h["role"] == "user" else "model"
        if role == last_role:
            if contents: contents[-1].parts[0].text += f"\n{text}"
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
        last_role = role
    if cache_active:
        found_user = False
        for i, c in enumerate(contents):
            if c.role == "user":
                if i+1 < len(contents) and contents[i+1].role == "model":
                    contents[i+1].parts[0].text = f"{model_ack}\n\n{contents[i+1].parts[0].text}"
                else:
                    contents.insert(i+1, types.Content(role="model", parts=[types.Part.from_text(text=model_ack)]))
                    if last_role == "user" and i+1 == len(contents)-1: last_role = "model"
                found_user = True; break
        return contents, last_role, found_user
    return contents, last_role, True

def process_audio(file_url, sender_phone, history):
    local_filename = None
    try:
        r = requests.get(file_url, stream=True, headers={'apikey': ZOKO_API_KEY})
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            for chunk in r.iter_content(8192): tmp.write(chunk)
            local_filename = tmp.name
        myfile = client.files.upload(file=local_filename, config={'mime_type': 'audio/ogg'})
        start = time.time()
        while myfile.state == "PROCESSING":
            if time.time() - start > 60: raise TimeoutError()
            time.sleep(2); myfile = client.files.get(name=myfile.name)
        if myfile.state != "ACTIVE": raise ValueError()
        greeting = get_ist_time_greeting(); cur_time = get_current_time_str()
        cache_name = get_cached_system_prompt_name("gemini-2.0-flash")
        model_ack = f"Understood. I am AIVA. {greeting}. Current time: {cur_time}."
        contents, last_role, ack_injected = get_contents_with_history(history, model_ack, bool(cache_name))
        final_prompt = f"Listen to this audio. You are AIVA. Time: {cur_time}. Answer as expert."
        if not ack_injected: final_prompt = f"{model_ack}\n\n{final_prompt}"
        audio_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='audio/ogg')
        text_part = types.Part.from_text(text=final_prompt)
        if last_role == "user":
            contents[-1].parts.extend([audio_part, text_part])
        else:
            contents.append(types.Content(role="user", parts=[audio_part, text_part]))
        return call_gemini_with_retry(contents, cached_content=cache_name)
    except Exception: return "I couldn't hear that clearly. Please type."
    finally:
        if local_filename and os.path.exists(local_filename): os.remove(local_filename)

def process_image(file_url, sender_phone, prompt_text, history):
    local_filename = None
    try:
        r = requests.get(file_url, stream=True, headers={'apikey': ZOKO_API_KEY})
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            for chunk in r.iter_content(8192): tmp.write(chunk)
            local_filename = tmp.name
        myfile = client.files.upload(file=local_filename)
        start = time.time()
        while myfile.state == "PROCESSING":
            if time.time() - start > 60: raise TimeoutError()
            time.sleep(2); myfile = client.files.get(name=myfile.name)
        greeting = get_ist_time_greeting(); cur_time = get_current_time_str()
        cache_name = get_cached_system_prompt_name("gemini-2.0-flash")
        model_ack = f"Understood. I am AIVA. {greeting}. Current time: {cur_time}."
        contents, last_role, ack_injected = get_contents_with_history(history, model_ack, bool(cache_name))
        user_prompt = prompt_text if prompt_text else "Analyze this image."
        final_prompt = f"Look at this image. User says: {user_prompt}. Time: {cur_time}."
        if not ack_injected: final_prompt = f"{model_ack}\n\n{final_prompt}"
        image_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='image/jpeg')
        text_part = types.Part.from_text(text=final_prompt)
        if last_role == "user": contents[-1].parts.extend([image_part, text_part])
        else: contents.append(types.Content(role="user", parts=[image_part, text_part]))
        return call_gemini_with_retry(contents, cached_content=cache_name)
    except Exception: return "I couldn't analyze the image."
    finally:
        if local_filename and os.path.exists(local_filename): os.remove(local_filename)

def process_pdf(file_url, sender_phone, history):
    local_filename = None
    try:
        r = requests.get(file_url, stream=True, headers={'apikey': ZOKO_API_KEY})
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for chunk in r.iter_content(8192): tmp.write(chunk)
            local_filename = tmp.name
        myfile = client.files.upload(file=local_filename)
        start = time.time()
        while myfile.state == "PROCESSING":
            if time.time() - start > 60: raise TimeoutError()
            time.sleep(2); myfile = client.files.get(name=myfile.name)
        greeting = get_ist_time_greeting(); cur_time = get_current_time_str()
        cache_name = get_cached_system_prompt_name("gemini-2.0-flash")
        model_ack = f"Understood. I am AIVA. {greeting}. Current time: {cur_time}."
        contents, last_role, ack_injected = get_contents_with_history(history, model_ack, bool(cache_name))
        final_prompt = f"Analyze this medical document. Time: {cur_time}."
        if not ack_injected: final_prompt = f"{model_ack}\n\n{final_prompt}"
        pdf_part = types.Part.from_uri(file_uri=myfile.uri, mime_type='application/pdf')
        text_part = types.Part.from_text(text=final_prompt)
        if last_role == "user": contents[-1].parts.extend([pdf_part, text_part])
        else: contents.append(types.Content(role="user", parts=[pdf_part, text_part]))
        return call_gemini_with_retry(contents, cached_content=cache_name)
    except Exception: return "I received your document but couldn't read it."
    finally:
        if local_filename and os.path.exists(local_filename): os.remove(local_filename)

def get_ai_response(sender_phone, message_text, history):
    try:
        greeting = get_ist_time_greeting(); cur_time = get_current_time_str()
        cache_name = get_cached_system_prompt_name("gemini-2.0-flash")
        model_ack = f"Understood. I am AIVA. {greeting}. Current time: {cur_time}."
        contents, last_role, ack_injected = get_contents_with_history(history, model_ack, bool(cache_name))
        if not ack_injected: message_text = f"{model_ack}\n\n{message_text}"
        if last_role == "user": contents[-1].parts[0].text += f"\n{message_text}"
        else: contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))
        return call_gemini_with_retry(contents, cached_content=cache_name)
    except Exception: return "I am experiencing high traffic."

def handle_message(payload):
    try:
        logging.info(f"Received Payload: {payload}")
        message_id = payload.get("messageId") or payload.get("eventId")
        if message_id:
            with processed_messages_lock:
                if message_id in processed_messages: return
                processed_messages.add(message_id)
                if len(processed_messages) > 5000: processed_messages.clear()
        sender_phone = payload.get("platformSenderId")
        if not sender_phone: sender_phone = payload.get("customer", {}).get("platformSenderId")
        if not sender_phone: return
        cancel_timers(sender_phone)
        direction = payload.get("direction")
        if direction and direction.lower() in ["outgoing", "from_business"]: return
        msg_type = payload.get("type", "text"); text_body = payload.get("text", ""); file_url = payload.get("fileUrl")
        if text_body and text_body.strip().upper() == "START BOT":
            muted_users.discard(sender_phone); send_whatsapp_message(sender_phone.replace("+", ""), "Bot resumed.", "text")
            start_inactivity_timer(sender_phone); return
        if sender_phone in muted_users or check_stop_bot(sender_phone): return
        if text_body and text_body.strip().upper() == "STOP BOT":
            stop_bot_cache[sender_phone] = {"stopped": True, "timestamp": time.time()}
            muted_users.add(sender_phone); send_whatsapp_message(sender_phone.replace("+", ""), "Bot stopped.", "text"); return
        if text_body:
            last_msgs = user_last_messages.get(sender_phone, [])
            last_msgs.append(text_body)
            if len(last_msgs) > 3: last_msgs.pop(0)
            user_last_messages[sender_phone] = last_msgs
            if len(last_msgs) == 3 and all(m == last_msgs[0] for m in last_msgs): return
        is_tracking = text_body and any(k in text_body.lower() for k in ["where is my order", "track my order", "order status", "track order"])
        if is_tracking:
            p_id = "".join(filter(str.isdigit, text_body))
            if len(p_id) > 3: send_whatsapp_message(sender_phone.replace("+", ""), get_order_status(p_id), "text"); user_order_state[sender_phone] = False; return
            else: user_order_state[sender_phone] = True; send_whatsapp_message(sender_phone.replace("+", ""), "Enter Mobile or Order Number.", "text"); return
        if user_order_state.get(sender_phone):
            if any(k in text_body.lower() for k in ["pain", "weight", "hair", "skin", "diabetes", "gain"]): user_order_state[sender_phone] = False
            else: send_whatsapp_message(sender_phone.replace("+", ""), get_order_status(text_body), "text"); user_order_state[sender_phone] = False; return
        cur_t = time.time(); last_t = last_greeted.get(sender_phone, 0)
        is_greeting = text_body and text_body.strip().lower() in ["hi", "hello", "start", "good morning", "good afternoon", "good evening"]
        if is_greeting and (cur_t - last_t > 12 * 3600):
            msg = f"{get_ist_time_greeting()}! I’m AIVA. Please share health concerns.\n\nനിങ്ങളുടെ ബുദ്ധിമുട്ടുകൾ പങ്കുവെക്കാവുന്നതാണ്."
            send_whatsapp_message(sender_phone.replace("+", ""), msg, "text"); last_greeted[sender_phone] = cur_t
            start_inactivity_timer(sender_phone); return
        history = get_user_history(sender_phone); response_text = ""; user_in_hist = text_body
        if text_body:
            for key, val in PRODUCT_IMAGES.items():
                if key in text_body.lower():
                    f_url = val; m = re.search(r'\((https?://.*?)\)', val)
                    if m: f_url = m.group(1)
                    send_whatsapp_message(sender_phone.replace("+", ""), key.replace('_', ' ').title(), "image", image_url=f_url); break
        if msg_type == "document" and file_url and file_url.lower().endswith(".pdf"): response_text = process_pdf(file_url, sender_phone, history); user_in_hist = "[Sent PDF]"
        elif msg_type == "image" and file_url: response_text = process_image(file_url, sender_phone, text_body, history); user_in_hist = "[Sent Image]"
        elif msg_type == "audio" and file_url: response_text = process_audio(file_url, sender_phone, history); user_in_hist = "[Sent Audio]"
        elif text_body or msg_type == "text": response_text = get_ai_response(sender_phone, text_body, history)
        if response_text:
            history.append({"role": "user", "parts": [user_in_hist]}); history.append({"role": "model", "parts": [response_text]})
            save_user_history(sender_phone, history)
            if "[HANDOVER]" in response_text:
                clean = response_text.replace("[HANDOVER]", "").strip()
                if clean: send_whatsapp_message(sender_phone.replace("+", ""), clean, "text")
                send_whatsapp_message(sender_phone.replace("+", ""), "📞 Contact expert at +91 9072727201.", "text")
                muted_users.add(sender_phone)
            else: send_whatsapp_message(sender_phone.replace("+", ""), response_text, "text")
            if sender_phone not in muted_users: start_inactivity_timer(sender_phone)
    except Exception as e: logging.error(f"Error: {e}"); traceback.print_exc()

@app.route('/', methods=['GET'])
def health_check(): return "Active", 200

@app.route('/bot', methods=['POST'])
def bot():
    data = request.json
    if not data: return jsonify({"status": "error"}), 400
    t = threading.Thread(target=handle_message, args=(data,)); t.daemon = True; t.start()
    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000)); app.run(host="0.0.0.0", port=port)
