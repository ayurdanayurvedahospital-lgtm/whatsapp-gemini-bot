import unittest
from unittest.mock import patch, MagicMock
import time
import app

class TestBackgroundLogic(unittest.TestCase):
    def setUp(self):
        # Reset caches
        app.user_sessions.clear()
        app.processed_messages.clear()
        app.stop_bot_cache.clear()

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.process_audio')
    def test_audio_processing(self, mock_process_audio, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        mock_process_audio.return_value = "Audio Transcript Response"

        data = {
            'customer': {'platformSenderId': '+919999999999'},
            'direction': 'FROM_CUSTOMER',
            'type': 'audio',
            'fileUrl': 'http://example.com/audio.ogg',
            'id': 'msg-1'
        }

        # Call logic directly (bypass thread for unit testing logic)
        app.handle_background_message(data)

        # Verify
        mock_process_audio.assert_called_once()
        # send_zoko_message called twice: 1. "Listening...", 2. Response
        self.assertEqual(mock_send.call_count, 2)
        args, _ = mock_send.call_args
        self.assertEqual(args[1], "Audio Transcript Response")

    @patch('app.send_zoko_message')
    def test_loop_prevention(self, mock_send):
        data = {
            'direction': 'FROM_BUSINESS', # Should be ignored
            'platformSenderId': '+919999999999',
            'text': 'Bot msg',
            'type': 'text'
        }

        app.handle_background_message(data)

        mock_send.assert_not_called()

    @patch('app.send_zoko_message')
    def test_idempotency_in_background(self, mock_send):
        data = {
            'customer': {'platformSenderId': '+919999999999'},
            'direction': 'FROM_CUSTOMER',
            'type': 'text',
            'text': 'Hello',
            'id': 'msg-unique'
        }

        # First call
        with patch('app.model.start_chat') as mock_chat:
            mock_chat.return_value.send_message.return_value.text = "Hi"
            app.handle_background_message(data)
            mock_send.assert_called_once()
            mock_send.reset_mock()

            # Second call (Duplicate ID)
            app.handle_background_message(data)
            mock_send.assert_not_called() # Should be ignored

if __name__ == '__main__':
    unittest.main()
