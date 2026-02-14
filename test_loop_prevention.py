import unittest
from unittest.mock import patch
import app

class TestZokoLoop(unittest.TestCase):
    def setUp(self):
        app.user_sessions.clear()

    @patch('app.send_zoko_message')
    def test_zoko_ignores_own_message(self, mock_send):
        payload = {
            'direction': 'FROM_BUSINESS',
            'platformSenderId': '+919946388900',
            'text': 'This is a bot message',
            'type': 'text'
        }

        # Call handler directly
        app.handle_message(payload)

        # Should NOT send message
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
