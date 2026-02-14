import unittest
from unittest.mock import patch, MagicMock
import app
import json

class TestRepetition(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True
        app.processed_messages.clear() # Clear idempotency cache (just in case)
        app.user_sessions.clear() # Clear sessions for isolation

    @patch('app.requests.post')
    @patch('app.check_stop_bot')
    @patch('app.model.start_chat')
    def test_repetition_logic(self, mock_start_chat, mock_check_stop_bot, mock_post):
        # Mock Zoko Stop Bot check
        mock_check_stop_bot.return_value = False

        # Mock Gemini
        mock_chat = MagicMock()
        mock_start_chat.return_value = mock_chat
        mock_ai_resp = MagicMock()
        mock_ai_resp.text = "Hello"
        mock_chat.send_message.return_value = mock_ai_resp

        # Test Payload (NO ID -> unique messages for idempotency logic)
        payload = {
            'direction': 'FROM_CUSTOMER',
            'platformSenderId': '+919946388900',
            'text': 'Same message',
            'type': 'text'
        }

        # 1. Send first message
        resp1 = self.app.post('/bot', json=payload)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.get_json()['status'], 'queued')

        # 2. Send second message
        resp2 = self.app.post('/bot', json=payload)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.get_json()['status'], 'queued')

        # 3. Send third message (should trigger stop)
        # Note: Repetition logic runs BEFORE async processing, so it returns immediately.
        resp3 = self.app.post('/bot', json=payload)
        self.assertEqual(resp3.status_code, 200)
        data = resp3.get_json()
        print(f"Repetition Trigger Response: {data}")
        # We expect a status indicating stop or ignore
        self.assertTrue(data['status'] in ['stopped', 'stopped_repetition'])

        # 4. Send fourth message (should be stopped)
        resp4 = self.app.post('/bot', json=payload)
        data = resp4.get_json()
        print(f"Subsequent Message Response: {data}")
        self.assertTrue(data['status'] in ['stopped', 'stopped_repetition'])

if __name__ == '__main__':
    unittest.main()
