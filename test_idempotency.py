import unittest
from unittest.mock import patch
import app
import time

class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True
        app.processed_messages.clear()

    @patch('app.threading.Thread')
    def test_duplicate_request_idempotency_webhook(self, mock_thread):
        payload = {
            'id': 'unique-msg-id-123',
            'platformSenderId': '+919999999999',
            'type': 'audio',
            'fileUrl': 'http://example.com/audio.ogg',
            'direction': 'FROM_CUSTOMER',
            'text': '',
            'customer': {'platformSenderId': '+919999999999'}
        }

        # 1. Send first request
        resp1 = self.app.post('/bot', json=payload)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json['status'], 'received')

        # Verify thread spawned
        self.assertEqual(mock_thread.call_count, 1)

        # 2. Send duplicate request
        # The /bot endpoint ITSELF doesn't check idempotency anymore, it just queues.
        # Idempotency is inside the thread.
        # But for Zoko, we MUST return 200 OK every time.
        resp2 = self.app.post('/bot', json=payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json['status'], 'received')

        # Verify thread spawned again (it will handle duplicates internally)
        self.assertEqual(mock_thread.call_count, 2)

if __name__ == '__main__':
    unittest.main()
