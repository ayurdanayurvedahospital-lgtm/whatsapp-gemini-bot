import unittest
import sqlite3
import os
from unittest.mock import patch, MagicMock
import app

class TestBackgroundLogic(unittest.TestCase):
    def setUp(self):
        app.db_init()
        conn = sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()
        app.stop_bot_cache.clear()
        app.processed_messages.clear()
        app.user_last_messages.clear()
        for phone in list(app.followup_timers.keys()):
            app.cancel_timers(phone)
        app.followup_timers.clear()

        # Manually initialize app.client for tests if needed, or mock calls
        app.client = MagicMock()

    @patch('app.send_whatsapp_message')
    @patch('app.get_ist_time_greeting')
    @patch('app.start_inactivity_timer')
    def test_audio_processing_error(self, mock_start_timer, mock_greeting, mock_send):
        mock_greeting.return_value = "Good Morning"
        phone = '+919999999999'
        data = {
            'customer': {'platformSenderId': phone},
            'direction': 'incoming',
            'type': 'audio',
            'fileUrl': 'http://bad.url/audio.ogg',
            'messageId': '1'
        }

        # Mock zoko_session.get instead of requests.get
        with patch('app.zoko_session.get', side_effect=Exception("Download Failed")):
            with patch('threading.Thread', side_effect=lambda target, args, **kwargs: target(*args, **kwargs)):
                app.handle_message(data)

        expected_phone = '919999999999'
        mock_send.assert_called_with(expected_phone, "I'm sorry, I couldn't hear that clearly. Could you please type your message?", "text")

    @patch('app.send_whatsapp_message')
    @patch('app.start_inactivity_timer')
    def test_file_cleanup(self, mock_start_timer, mock_send):
        phone = '+919999999999'
        data = {
            'customer': {'platformSenderId': phone},
            'direction': 'incoming',
            'type': 'audio',
            'fileUrl': 'http://good.url/audio.ogg',
            'messageId': '2'
        }

        with patch('app.zoko_session.get') as mock_get:
            mock_get.return_value.iter_content.return_value = [b'data']
            mock_get.return_value.status_code = 200

            # Mock Gemini client
            app.client.files.upload.return_value = MagicMock(name="files/test")
            app.client.models.generate_content.return_value = MagicMock(text="Audio Answer")

            with patch('os.remove') as mock_remove:
                with patch('os.path.exists', return_value=True):
                    with patch('threading.Thread', side_effect=lambda target, args, **kwargs: target(*args, **kwargs)):
                        app.handle_message(data)

                mock_remove.assert_called()

if __name__ == '__main__':
    unittest.main()
