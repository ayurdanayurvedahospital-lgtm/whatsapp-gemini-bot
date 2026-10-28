import sys
from unittest.mock import MagicMock, patch

# Comprehensive Global Mocking
sys.modules["requests"] = MagicMock()
sys.modules["requests.adapters"] = MagicMock()
sys.modules["flask"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["urllib3.util.retry"] = MagicMock()
sys.modules["pytz"] = MagicMock()

import unittest
import app

class TestExistingLogic(unittest.TestCase):

    def setUp(self):
        # Clear database for each test
        conn = app.sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

        app.processed_messages.clear()
        app.stop_bot_cache.clear()

    @patch('app.send_whatsapp_message')
    @patch('app.get_ai_response')
    def test_handle_message_basic(self, mock_ai, mock_send):
        mock_ai.return_value = "Hello Patient"
        payload = {
            "messageId": "msg_1",
            "platformSenderId": "9100000000",
            "type": "text",
            "text": "Help me",
            "direction": "incoming"
        }

        app.handle_message(payload)
        mock_send.assert_called()
        # Verify it sent the AI response
        args, kwargs = mock_send.call_args
        self.assertEqual(args[1], "Hello Patient")

    def test_memory_rolling_window(self):
        phone = "+9100000000"

        # Fill with 20 messages
        for i in range(20):
            history = app.get_user_history(phone)
            history.append({"role": "user", "parts": [f"msg {i}"]})
            history.append({"role": "model", "parts": [f"resp {i}"]})
            app.save_user_history(phone, history)

        final_history = app.get_user_history(phone)
        self.assertLessEqual(len(final_history), 14)
        self.assertEqual(final_history[-1]["parts"][0], "resp 19")

    @patch('app.zoko_session.post')
    def test_shopify_token_caching(self, mock_post):
        app.shopify_token_cache = {"access_token": None, "expires_at": 0}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "token123", "expires_in": 3600}
        mock_post.return_value = mock_resp

        # Call twice
        app.get_shopify_token()
        app.get_shopify_token()

        # Should only call API once
        self.assertEqual(mock_post.call_count, 1)


    def test_trim_history_with_latch_multi_turn_string(self):
        # 1-element list containing a multi-turn conversation string (previously bypassed len <= 16 check)
        multi_turn_text = "Master Grounding Directive: You are AIVA.\n"
        for i in range(30):
            multi_turn_text += f"User: message {i}\nAssistant: response {i}\n"

        contents = [multi_turn_text]
        trimmed = app.trim_history_with_latch(contents)

        # Verify it trimmed the multi-turn string despite len(contents) == 1
        self.assertIn("message 0", trimmed[0])
        self.assertIn("response 29", trimmed[0])
        self.assertNotIn("message 10", trimmed[0])

    def test_user_sessions_ram_trimming_and_no_system_prompt(self):
        phone = "919999988888"
        app.user_sessions[phone] = {"chat": [], "last_active": 0}

        with patch("app.call_gemini_with_retry", return_value="AI Reply"):
            app.get_ai_response(phone, "Hello AIVA", [])

        chat = app.user_sessions[phone]["chat"]
        # Verify SYSTEM_PROMPT is NOT in chat
        for msg in chat:
            self.assertFalse(app.is_system_prompt_content(msg))

        self.assertEqual(len(chat), 2) # user msg + model reply

    @patch("app.client")
    def test_in_flight_request_deduplication(self, mock_client):
        app.in_flight_requests.clear()
        contents = ["test_in_flight_payload"]

        # Simulate in-flight payload
        payload_hash = app.hashlib.md5(str(contents).encode("utf-8")).hexdigest()
        app.in_flight_requests.add(payload_hash)

        res = app.call_gemini_with_retry(contents)
        self.assertIn("double-checking your details", res)

        app.in_flight_requests.clear()

    @patch("app.send_whatsapp_message")
    @patch("app.get_ai_response")
    def test_status_updates_ignored_early(self, mock_ai, mock_send):
        payload = {
            "messageId": "msg_status_1",
            "platformSenderId": "9100000000",
            "type": "READ",
            "status": "DELIVERED",
            "direction": "incoming"
        }
        app.handle_message(payload)
        mock_ai.assert_not_called()
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
