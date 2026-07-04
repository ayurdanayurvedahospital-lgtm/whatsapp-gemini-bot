import unittest
from unittest.mock import MagicMock, patch
import app

class TestZokoPayload(unittest.TestCase):

    def test_webhook_triggers_thread(self):
        with app.app.test_request_context(json={"messageId": "123", "platformSenderId": "9100"}):
            with patch('app.threading.Thread') as mock_thread:
                # Mock handle_message if needed
                with patch('app.handle_message') as mock_handle:
                    response = app.bot()
                    # response is a tuple (jsonify_data, status_code)
                    self.assertEqual(response[1], 200)
                    self.assertTrue(mock_thread.called)

    @patch('app.send_whatsapp_message')
    @patch('app.get_ai_response')
    def test_handle_message_basic(self, mock_ai, mock_send):
        mock_ai.return_value = "Hello Patient"
        payload = {
            "messageId": "msg_1",
            "customer": {"platformSenderId": "9100000000"},
            "type": "text",
            "text": "Help me",
            "direction": "incoming"
        }

        with patch('threading.Thread', side_effect=lambda target, args, **kwargs: target(*args, **kwargs)):
            app.handle_message(payload)

        mock_send.assert_called()
        args, kwargs = mock_send.call_args
        self.assertEqual(args[1], "Hello Patient")

if __name__ == '__main__':
    unittest.main()
