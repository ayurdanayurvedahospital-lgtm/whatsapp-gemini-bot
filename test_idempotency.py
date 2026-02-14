import unittest
from unittest.mock import patch, MagicMock
import json
import time
import threading
from app import app, user_sessions, processed_messages

class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        user_sessions.clear()
        processed_messages.clear()

    @patch('app.process_message_async')
    def test_duplicate_request_idempotency(self, mock_process_async):
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
        self.assertEqual(resp1.json['status'], 'queued')

        # Verify thread was started (async process called)
        # Note: In the actual app, it spawns a thread which calls this function.
        # Since we patch it, the thread calls the mock.
        # We need to wait a tiny bit for thread to start?
        # Actually, threading.Thread(target=mock).start() runs instantly usually.
        # But to be safe, we can wait a small amount.
        time.sleep(0.1)
        self.assertEqual(mock_process_async.call_count, 1)

        # 2. Send duplicate request
        resp2 = self.app.post('/bot', json=payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json['status'], 'ignored')
        self.assertEqual(resp2.json['reason'], 'duplicate_id')

        # Verify process_async was NOT called again
        time.sleep(0.1)
        self.assertEqual(mock_process_async.call_count, 1)

    @patch('app.process_message_async')
    def test_different_ids(self, mock_process_async):
        payload1 = {
            'id': 'msg-1',
            'platformSenderId': '+919999999999',
            'type': 'text',
            'text': 'Hi',
            'direction': 'FROM_CUSTOMER',
            'customer': {'platformSenderId': '+919999999999'}
        }
        payload2 = {
            'id': 'msg-2', # Different ID
            'platformSenderId': '+919999999999',
            'type': 'text',
            'text': 'Hello',
            'direction': 'FROM_CUSTOMER',
            'customer': {'platformSenderId': '+919999999999'}
        }

        self.app.post('/bot', json=payload1)
        time.sleep(0.1)
        self.assertEqual(mock_process_async.call_count, 1)

        self.app.post('/bot', json=payload2)
        time.sleep(0.1)
        self.assertEqual(mock_process_async.call_count, 2)

if __name__ == '__main__':
    unittest.main()
