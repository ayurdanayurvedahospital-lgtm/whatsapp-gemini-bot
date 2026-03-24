import sys
from unittest.mock import MagicMock, patch

# Global Mocking
sys.modules["requests"] = MagicMock()
sys.modules["flask"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["pytz"] = MagicMock()

import unittest
import app

class TestZokoPayload(unittest.TestCase):

    @patch('app.threading.Thread')
    def test_webhook_triggers_thread(self, mock_thread):
        # Mock request context
        mock_flask = sys.modules["flask"]
        mock_flask.request.json = {"messageId": "123", "platformSenderId": "9100"}

        from app import bot
        with patch('app.request', mock_flask.request):
            resp, status = bot()
            self.assertEqual(status, 200)
            self.assertTrue(mock_thread.called)

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

if __name__ == '__main__':
    unittest.main()
