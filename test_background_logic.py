import unittest
from unittest.mock import patch, MagicMock, call
import app
import time

class TestBackgroundLogic(unittest.TestCase):
    def setUp(self):
        app.user_sessions.clear()
        app.stop_bot_cache.clear()
        app.processed_messages.clear()
        app.user_last_messages.clear()

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.process_audio')
    def test_audio_processing(self, mock_process_audio, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        mock_process_audio.return_value = "Audio Response"

        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'type': 'audio',
            'fileUrl': 'http://example.com/audio.ogg',
            'messageId': 'msg_audio_1'
        }

        # We mock threading to run synchronously for test
        with patch('threading.Thread', side_effect=lambda target, args: target(*args)):
            app.handle_message(data)

        # Verify calls
        # 1. "Listening..."
        # 2. Response
        self.assertEqual(mock_send.call_count, 2)

        # Check args
        calls = mock_send.call_args_list
        self.assertEqual(calls[0].kwargs.get('text'), "Listening... 🎧")
        self.assertEqual(calls[1].kwargs.get('text'), "Audio Response")

    @patch('app.send_zoko_message')
    def test_stop_bot_command(self, mock_send):
        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'STOP BOT',
            'type': 'text',
            'messageId': 'msg_stop_1'
        }

        with patch('app.check_stop_bot', return_value=False):
            app.handle_message(data)

        # Verify cache update
        self.assertTrue(app.stop_bot_cache['+919999999999']['stopped'])
        # Verify response
        mock_send.assert_called_with('+919999999999', text='Bot has been stopped for this chat.')

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.model.start_chat') # Mock Gemini
    @patch('time.sleep') # Mock sleep to speed up test
    def test_image_logic(self, mock_sleep, mock_start_chat, mock_check_stop, mock_send):
        mock_check_stop.return_value = False

        # Mock Gemini Response
        mock_chat = MagicMock()
        mock_start_chat.return_value = mock_chat
        mock_chat.send_message.return_value.text = "Here is info about Junior Staamigen."

        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'Tell me about Junior Staamigen please',
            'type': 'text',
            'messageId': 'msg_img_1'
        }

        app.handle_message(data)

        # Expected:
        # 1. Image message (url found for 'junior')
        # 2. Sleep
        # 3. Text message (AI response)

        self.assertEqual(mock_send.call_count, 2)

        # Check first call (Image)
        call1_args = mock_send.call_args_list[0]
        # send_zoko_message(sender_phone, image_url=found_image_url)
        self.assertEqual(call1_args.args[0], '+919999999999')
        self.assertIsNotNone(call1_args.kwargs.get('image_url'))
        self.assertIsNone(call1_args.kwargs.get('text')) # Ensure text is None for image call

        # Check second call (Text)
        call2_args = mock_send.call_args_list[1]
        self.assertEqual(call2_args.args[0], '+919999999999')
        self.assertEqual(call2_args.kwargs.get('text'), "Here is info about Junior Staamigen.")
        self.assertIsNone(call2_args.kwargs.get('image_url'))

    @patch('app.send_zoko_message')
    def test_loop_prevention(self, mock_send):
        # Send same message 4 times
        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'Hello',
            'type': 'text',
            'messageId': 'msg_loop_1'
        }

        with patch('app.check_stop_bot', return_value=False):
            with patch('app.get_ai_response', return_value="Hi"):
                 # 1st
                 data['messageId'] = '1'
                 app.handle_message(data)
                 # 2nd
                 data['messageId'] = '2'
                 app.handle_message(data)
                 # 3rd
                 data['messageId'] = '3'
                 app.handle_message(data)
                 # 4th (Should be ignored)
                 data['messageId'] = '4'
                 app.handle_message(data)

        # Only 2 calls expected (1, 2 sent response. 3, 4 blocked because they complete the set of 3 identical)
        self.assertEqual(mock_send.call_count, 2)

if __name__ == '__main__':
    unittest.main()
