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
        # Cancel any active timers mocked or real
        for phone in list(app.followup_timers.keys()):
            app.cancel_timers(phone)
        app.followup_timers.clear()

    @patch('app.send_zoko_message')
    @patch('app.start_inactivity_timer')
    @patch('app.cancel_timers')
    def test_timer_lifecycle(self, mock_cancel, mock_start, mock_send):
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'text': 'Hi', 'type': 'text', 'messageId': '1'}

        # Test 1: New message triggers cancel and start
        with patch('app.get_ai_response', return_value="Response"):
            with patch('app.get_ist_time_greeting', return_value="Good Morning"):
                app.handle_message(data)

        mock_cancel.assert_called_with(phone)
        mock_start.assert_called_with(phone)

    @patch('app.send_zoko_message')
    @patch('threading.Timer')
    def test_followup_logic(self, mock_timer, mock_send):
        phone = '+919999999999'

        # Simulate send_followup_1
        app.followup_timers[phone] = {} # Mock presence
        app.send_followup_1(phone)

        mock_send.assert_called_with(phone, text="Just checking in 😊 Whenever you're comfortable, you can share the details. I'm here to help.")
        # Should start timer 2
        mock_timer.assert_called_with(300, app.send_followup_2, args=[phone])

        # Simulate send_followup_2
        mock_send.reset_mock()
        app.send_followup_2(phone)
        mock_send.assert_called_with(phone, text="Your health deserves thoughtful attention. I’m here to guide you whenever you’re ready. Please feel free to ask me anything at any time.")

        # Verify cleanup
        self.assertNotIn(phone, app.followup_timers)

    @patch('app.send_zoko_message')
    def test_no_followup_if_muted(self, mock_send):
        phone = '+919999999999'
        app.muted_users.add(phone)

        app.send_followup_1(phone)
        mock_send.assert_not_called()

        app.send_followup_2(phone)
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
