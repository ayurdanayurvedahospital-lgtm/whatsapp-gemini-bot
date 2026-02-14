import unittest
from unittest.mock import patch, MagicMock
import app
import json

class TestZokoPayload(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True
        app.processed_messages.clear() # Clear idempotency cache

    @patch('app.requests.post')
    @patch('app.check_stop_bot')
    @patch('app.model.start_chat')
    def test_zoko_payload_root_sender(self, mock_start_chat, mock_check_stop_bot, mock_post):
        # Mock Zoko Stop Bot check
        mock_check_stop_bot.return_value = False

        # Mock Gemini Response
        mock_chat = MagicMock()
        mock_start_chat.return_value = mock_chat
        mock_ai_resp = MagicMock()
        mock_ai_resp.text = "Hello from AI"
        mock_chat.send_message.return_value = mock_ai_resp

        # Payload from the log (platformSenderId at root)
        payload = {
            'customer': {
                'id': '8275201a-49a1-11f0-924e-42010a020911',
                'name': 'Ayurdan Ayurveda Hospital'
            },
            'customerName': 'Ayurdan Ayurveda Hospital',
            'deliveryStatus': 'received',
            'direction': 'FROM_CUSTOMER',
            'event': 'message:user:in',
            'id': 'd96091bf-096d-11f1-8d8b-1e5a62c68e34',
            'platform': 'WHATSAPP',
            'platformSenderId': '+919946388900',
            'platformTimestamp': '2026-02-14T06:24:41Z',
            'senderName': 'Ayurdan Ayurveda Hospital',
            'text': 'Hello',
            'type': 'text'
        }

        response = self.app.post('/bot', json=payload)

        # Should be 200 OK and queued
        self.assertEqual(response.status_code, 200, f"Expected 200 but got {response.status_code}. Response: {response.data}")
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'queued')

if __name__ == '__main__':
    unittest.main()
