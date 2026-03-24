import sys
from unittest.mock import MagicMock, patch

# Comprehensive Global Mocking
sys.modules["requests"] = MagicMock()
sys.modules["flask"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["pytz"] = MagicMock()

import unittest
import app

class TestExistingLogic(unittest.TestCase):

    def setUp(self):
        app.user_sessions.clear()
        app.processed_messages.clear()
        app.muted_users.clear()
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
        app.user_sessions[phone] = []
        app.user_last_active[phone] = 1000 # old time

        # Fill with 20 messages
        for i in range(20):
            history = app.get_user_history(phone)
            history.append({"role": "user", "parts": [f"msg {i}"]})
            history.append({"role": "model", "parts": [f"resp {i}"]})
            app.save_user_history(phone, history)

        final_history = app.get_user_history(phone)
        self.assertLessEqual(len(final_history), 14)
        self.assertEqual(final_history[-1]["parts"][0], "resp 19")

    @patch('app.requests.post')
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

if __name__ == '__main__':
    unittest.main()
