import unittest
from unittest.mock import patch, MagicMock
import app

class TestBackgroundLogic(unittest.TestCase):
    def setUp(self):
        app.user_sessions.clear()
        app.stop_bot_cache.clear()

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.process_audio')
    def test_audio_processing(self, mock_process_audio, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        mock_process_audio.return_value = "Audio Response"

        data = {
            'customer': {'platformSenderId': '+919999999999'},
            'direction': 'FROM_CUSTOMER',
            'type': 'audio',
            'fileUrl': 'http://example.com/audio.ogg'
        }

        app.handle_message(data)

        mock_process_audio.assert_called_once()
        self.assertEqual(mock_send.call_count, 2) # Listening... + Response
        args, _ = mock_send.call_args
        self.assertEqual(args[1], "Audio Response")

    @patch('app.send_zoko_message')
    def test_stop_bot_command(self, mock_send):
        data = {
            'customer': {'platformSenderId': '+919999999999'},
            'direction': 'FROM_CUSTOMER',
            'text': 'STOP BOT',
            'type': 'text'
        }

        with patch('app.check_stop_bot', return_value=False):
            app.handle_message(data)

        mock_send.assert_called_with('+919999999999', 'Bot Stopped')
        self.assertTrue(app.stop_bot_cache['+919999999999']['stopped'])

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.model.start_chat')
    def test_image_logic(self, mock_start_chat, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        # Mock Gemini
        mock_chat = MagicMock()
        mock_start_chat.return_value = mock_chat
        mock_chat.send_message.return_value.text = "Product Info"

        data = {
            'customer': {'platformSenderId': '+919999999999'},
            'direction': 'FROM_CUSTOMER',
            'text': 'Tell me about Junior Staamigen',
            'type': 'text'
        }

        app.handle_message(data)

        # Should detect "junior" or "staamigen" in text and set image_url
        # Check send_zoko_message call
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        # args[0] is phone, args[1] is text, args[2] is image_url
        self.assertEqual(args[1], "Product Info")
        self.assertIsNotNone(args[2]) # Image URL should be present

if __name__ == '__main__':
    unittest.main()
