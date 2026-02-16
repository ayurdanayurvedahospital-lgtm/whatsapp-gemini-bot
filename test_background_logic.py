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
    @patch('app.get_ist_time_greeting')
    def test_greeting_12h_rule(self, mock_greeting, mock_send):
        mock_greeting.return_value = "Good Morning"
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'Hi', 'type': 'text', 'messageId': '1'}

        # 1. First Greeting
        with patch('app.get_ai_response') as mock_ai:
            app.handle_message(data)
            mock_ai.assert_not_called()

        # Verify call arguments
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], phone)
        self.assertIn("Good Morning! ☀️ I am AIVA, the Senior Ayurvedic Expert", call_args[1]['text'])

        self.assertIn(phone, app.last_greeted)
        last_time = app.last_greeted[phone]

        mock_send.reset_mock()

        # 2. Greeting within 12h (should go to AI)
        data['messageId'] = '2'
        with patch('app.get_ai_response', return_value="AI Response"):
            app.handle_message(data)
            mock_send.assert_called_with(phone, text="AI Response")

        mock_send.reset_mock()

        # 3. Greeting after 13h (should greet again)
        app.user_last_messages.clear()

        with patch('time.time', return_value=last_time + (13*3600)):
            data['messageId'] = '3'
            app.handle_message(data)
            call_args = mock_send.call_args
            self.assertIn("Good Morning! ☀️ I am AIVA, the Senior Ayurvedic Expert", call_args[1]['text'])

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot', return_value=False)
    def test_handover_logic(self, mock_check, mock_send):
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'I have thyroid', 'type': 'text', 'messageId': 'h1'}

        # Mock AI response containing [HANDOVER]
        ai_resp = "Given your medical history, please speak to Sreelekha. [HANDOVER]"

        with patch('app.get_ai_response', return_value=ai_resp):
            app.handle_message(data)

        # Expected calls:
        # 1. "Given your medical history..." (cleaned)
        # 2. Contact info
        self.assertEqual(mock_send.call_count, 2)
        call1 = mock_send.call_args_list[0]
        call2 = mock_send.call_args_list[1]

        self.assertEqual(call1.kwargs['text'], "Given your medical history, please speak to Sreelekha.")
        self.assertIn("+91 9895900809", call2.kwargs['text'])

        # Verify Mute
        self.assertIn(phone, app.muted_users)

    @patch('app.send_zoko_message')
    @patch('app.check_stop_bot', return_value=False)
    def test_image_caption(self, mock_check, mock_send):
        phone = '+919999999999'
        # Key needs to be in the message text.

        with patch.dict(app.PRODUCT_IMAGES, {'sakhi': 'http://img.url'}, clear=True):
            data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'Tell me about Sakhi', 'type': 'text', 'messageId': 'img1'}

            with patch('app.get_ai_response', return_value="AI info"):
                app.handle_message(data)

            # Expected calls: 1. Image, 2. Text
            self.assertEqual(mock_send.call_count, 2)

            call1 = mock_send.call_args_list[0]

            # Check Image Call
            # kwargs might be missing if passed positionally in actual code but app.py uses keywords for url/caption in send_zoko_message definition?
            # send_zoko_message(phone, text=None, image_url=None, caption=None)
            # app.py call: send_zoko_message(sender_phone, image_url=found_image_url, caption=product_name)

            self.assertEqual(call1.kwargs.get('image_url'), 'http://img.url')
            self.assertEqual(call1.kwargs.get('caption'), 'Sakhi') # Title cased

if __name__ == '__main__':
    unittest.main()
