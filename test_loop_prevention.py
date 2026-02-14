import unittest
from unittest.mock import patch, MagicMock
import app
import os

class TestZokoLoop(unittest.TestCase):
    def setUp(self):
        self.app = app.app.test_client()
        self.app.testing = True

        # Patch send_zoko_message directly to verify call
        self.patcher = patch('app.send_zoko_message')
        self.mock_send = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch('app.requests.post')
    @patch('app.check_stop_bot')
    @patch('app.model.start_chat')
    def test_zoko_ignores_own_message(self, mock_start_chat, mock_check_stop_bot, mock_post):
        # Mock Zoko Stop Bot check
        mock_check_stop_bot.return_value = False

        payload = {
            'direction': 'FROM_BUSINESS',  # Indicates message FROM the bot/business
            'platformSenderId': '+919946388900',
            'text': 'This is a bot message',
            'type': 'text'
        }

        # Mock Gemini
        mock_chat = MagicMock()
        mock_start_chat.return_value = mock_chat
        mock_ai_resp = MagicMock()
        mock_ai_resp.text = "I am replying to myself"
        mock_chat.send_message.return_value = mock_ai_resp

        response = self.app.post('/bot', json=payload)

        if self.mock_send.called:
            print("FAIL: Bot replied to its own message!")
        else:
            print("PASS: Bot ignored its own message.")

if __name__ == '__main__':
    unittest.main()
