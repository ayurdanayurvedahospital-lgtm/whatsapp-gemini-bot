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

        self.assertTrue(app.stop_bot_cache['+919999999999']['stopped'])
        mock_send.assert_called_with('+919999999999', text='Bot has been stopped for this chat.')

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot')
    @patch('app.get_ist_time_greeting')
    def test_image_logic(self, mock_greeting, mock_check_stop, mock_send):
        mock_check_stop.return_value = False
        mock_greeting.return_value = "Good Evening"

        app.model = MagicMock()
        app.model.start_chat.return_value.send_message.return_value.text = "Here is info about Junior Staamigen."

        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'Tell me about Junior Staamigen please',
            'type': 'text',
            'messageId': 'msg_img_1'
        }

        app.handle_message(data)

        self.assertEqual(mock_send.call_count, 2)

        call1_args = mock_send.call_args_list[0]
        self.assertEqual(call1_args.args[0], '+919999999999')
        self.assertIsNotNone(call1_args.kwargs.get('image_url'))

        call2_args = mock_send.call_args_list[1]
        self.assertEqual(call2_args.args[0], '+919999999999')
        self.assertEqual(call2_args.kwargs.get('text'), "Here is info about Junior Staamigen.")

    @patch('app.send_zoko_message')
    def test_loop_prevention(self, mock_send):
        # Note: "Hello" is now caught by greeting check, so we use a different text for loop test
        # to ensure it hits the loop logic and AI logic (mocked)
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

        # 1. User asks for agent
        data_agent = {
            'platformSenderId': phone,
            'direction': 'incoming',
            'text': 'I want to speak to an agent',
            'type': 'text',
            'messageId': 'msg_agent'
        }

        app.handle_message(data_agent)

        self.assertIn(phone, app.muted_users)
        mock_send.assert_called_with(phone, text="You can contact our Agent Sreelekha at +91 9895900809. I will now pause so you can speak with her.")
        mock_send.reset_mock()

        # 2. User sends another message (should be ignored)
        data_ignore = {
            'platformSenderId': phone,
            'direction': 'incoming',
            'text': 'Hello?',
            'type': 'text',
            'messageId': 'msg_ignore'
        }
        app.handle_message(data_ignore)
        mock_send.assert_not_called()

        # 3. Resume command
        data_resume = {
            'platformSenderId': phone,
            'direction': 'incoming',
            'text': 'START BOT',
            'type': 'text',
            'messageId': 'msg_resume'
        }
        app.handle_message(data_resume)

        self.assertNotIn(phone, app.muted_users)
        mock_send.assert_called_with(phone, text="Bot resumed. How can I help?")

    @patch('app.send_zoko_message')
    @patch('app.get_ist_time_greeting')
    def test_explicit_greeting(self, mock_greeting, mock_send):
        mock_greeting.return_value = "Good Morning"

        data = {
            'platformSenderId': '+919999999999',
            'direction': 'incoming',
            'text': 'Hi',
            'type': 'text',
            'messageId': 'msg_hi'
        }

        # Ensure AI is NOT called
        with patch('app.get_ai_response') as mock_ai:
            app.handle_message(data)
            mock_ai.assert_not_called()

        expected_msg = "Good Morning! ☀️ I am AIVA, an empathetic and warm AI Virtual Assistant from Ayurdan Ayurveda Hospital! I am here to help you with any questions about our Ayurvedic products and services. You can type your message or send a Voice Note. How may I help you? 😊"
        mock_send.assert_called_with('+919999999999', text=expected_msg)

if __name__ == '__main__':
    unittest.main()
