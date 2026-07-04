import unittest
import sqlite3
from unittest.mock import patch
import app

class TestZokoLoop(unittest.TestCase):
    def setUp(self):
        app.db_init()
        conn = sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

    @patch('app.send_whatsapp_message')
    def test_zoko_ignores_own_message(self, mock_send):
        payload = {
            'direction': 'FROM_BUSINESS',
            'customer': {
                'platformSenderId': '+919946388900'
            },
            'text': 'This is a bot message',
            'type': 'text'
        }

        # Call handler directly
        app.handle_message(payload)

        # Should NOT send message
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
