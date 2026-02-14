import unittest
from unittest.mock import patch
import app
import json

class TestZokoPayload(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

    @patch('app.threading.Thread')
    def test_zoko_payload_root_sender(self, mock_thread):
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

        # Should be 200 OK
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'received')

        # Verify background processing was triggered
        self.assertEqual(mock_thread.call_count, 1)

if __name__ == '__main__':
    unittest.main()
