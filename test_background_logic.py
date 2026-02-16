import unittest
from unittest.mock import patch, MagicMock
import app
import time

class TestBackgroundLogic(unittest.TestCase):
    def setUp(self):
        app.user_sessions.clear()
        app.stop_bot_cache.clear()
        app.processed_messages.clear()
        app.user_last_messages.clear()
        app.muted_users.clear()
        app.last_greeted.clear()

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.process_audio')
    @patch('app.get_ist_time_greeting')
    def test_audio_processing(self, mock_greeting, mock_process_audio, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        mock_process_audio.return_value = "Audio Response"
        mock_greeting.return_value = "Good Morning"

        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'type': 'audio',
            'fileUrl': 'http://example.com/audio.ogg',
            'messageId': 'msg_audio_1'
        }

        with patch('threading.Thread', side_effect=lambda target, args: target(*args)):
            app.handle_message(data)

        self.assertEqual(mock_send.call_count, 2)
        # Check if one of the calls was "Listening..."
        texts = [c.kwargs.get('text') for c in mock_send.call_args_list]
        self.assertIn("Listening... 🎧", texts)
        self.assertIn("Audio Response", texts)

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

        self.assertTrue(app.stop_bot_cache['+919999999999']['stopped'])
        mock_send.assert_called_with('+919999999999', text='Bot has been stopped for this chat.')

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot', return_value=False)
    def test_image_caption(self, mock_check, mock_send):
        phone = '+919999999999'

        # Use patch.dict on the imported dictionary
        with patch.dict(app.PRODUCT_IMAGES, {'sakhi': 'http://img.url'}, clear=True):
            data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'Tell me about Sakhi', 'type': 'text', 'messageId': 'img1'}

            with patch('app.get_ai_response', return_value="AI info"):
                app.handle_message(data)

            # We expect 2 calls: Image and Text
            self.assertEqual(mock_send.call_count, 2)

            # Find the image call
            image_call = None
            for call in mock_send.call_args_list:
                if call.kwargs.get('image_url') == 'http://img.url':
                    image_call = call
                    break

            self.assertIsNotNone(image_call, "Image call not found")
            self.assertEqual(image_call.kwargs.get('caption'), 'Sakhi')

    @patch('app.send_zoko_message')
    def test_loop_prevention(self, mock_send):
        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'Loop Test',
            'type': 'text',
            'messageId': 'msg_loop_1'
        }

        with patch('app.check_stop_bot', return_value=False):
            with patch('app.get_ai_response', return_value="Hi"):
                 data['messageId'] = '1'
                 app.handle_message(data)
                 data['messageId'] = '2'
                 app.handle_message(data)
                 data['messageId'] = '3'
                 app.handle_message(data)
                 data['messageId'] = '4'
                 app.handle_message(data)

        self.assertEqual(mock_send.call_count, 2)

    def test_get_ist_time_greeting(self):
        greeting = app.get_ist_time_greeting()
        self.assertIn(greeting, ["Good Morning", "Good Afternoon", "Good Evening"])

    @patch('app.send_zoko_message')
    def test_agent_handover_and_resume(self, mock_send):
        phone = '+919999999999'
        data_agent = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'I want to speak to an agent', 'type': 'text', 'messageId': 'msg_agent'}

        # Mock AI response to trigger handover
        with patch('app.get_ai_response', return_value="Sure, handing you over. [HANDOVER]"):
            app.handle_message(data_agent)

        self.assertIn(phone, app.muted_users)
        # Verify contact info sent
        calls = [c.kwargs.get('text') for c in mock_send.call_args_list if c.kwargs.get('text')]
        self.assertTrue(any("Sreelekha" in t for t in calls))

        mock_send.reset_mock()
        data_resume = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'START BOT', 'type': 'text', 'messageId': 'msg_resume'}
        app.handle_message(data_resume)
        self.assertNotIn(phone, app.muted_users)
        mock_send.assert_called_with(phone, text="Bot resumed. How can I help?")

    @patch('app.send_zoko_message')
    @patch('app.get_ist_time_greeting')
    def test_one_time_greeting(self, mock_greeting, mock_send):
        mock_greeting.return_value = "Good Morning"
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'Hi', 'type': 'text', 'messageId': 'msg_hi'}

        # 1. First Greeting
        with patch('app.get_ai_response') as mock_ai:
            app.handle_message(data)
            mock_ai.assert_not_called()

        # Verify text content
        call_args = mock_send.call_args
        self.assertIn("Good Morning", call_args[1]['text'])
        self.assertIn("AIVA", call_args[1]['text'])

        mock_send.reset_mock()

        # 2. Second Greeting (skipped)
        data['messageId'] = 'msg_hi_2'
        with patch('app.get_ai_response', return_value="AI Response"):
            app.handle_message(data)
            mock_send.assert_called_with(phone, text="AI Response")

if __name__ == '__main__':
    unittest.main()
