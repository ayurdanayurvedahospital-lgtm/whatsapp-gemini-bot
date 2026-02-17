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
        for phone in list(app.followup_timers.keys()):
            app.cancel_timers(phone)
        app.followup_timers.clear()

    @patch('app.send_zoko_message')
    @patch('app.get_ist_time_greeting')
    @patch('app.start_inactivity_timer') # Mock to prevent Thread.__init__ error in tests
    def test_audio_processing_error(self, mock_start_timer, mock_greeting, mock_send):
        mock_greeting.return_value = "Good Morning"
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'type': 'audio', 'fileUrl': 'http://bad.url/audio.ogg', 'messageId': '1'}

        # Simulate Error during processing
        with patch('requests.get', side_effect=Exception("Download Failed")):
            with patch('threading.Thread', side_effect=lambda target, args: target(*args)):
                app.handle_message(data)

        # Expect error message
        mock_send.assert_called_with(phone, text="I'm sorry, I couldn't hear that clearly. Could you please type your message?")

    @patch('app.send_zoko_message')
    @patch('app.start_inactivity_timer') # Mock to prevent Thread.__init__ error in tests
    def test_file_cleanup(self, mock_start_timer, mock_send):
        # We can't easily test OS removal with mocks unless we mock os.remove and file existence
        # But we can verify the 'finally' block logic by seeing if handle_message completes without error
        phone = '+919999999999'
        data = {'platformSenderId': phone, 'direction': 'incoming', 'type': 'audio', 'fileUrl': 'http://good.url/audio.ogg', 'messageId': '2'}

        with patch('requests.get') as mock_get:
            mock_get.return_value.iter_content.return_value = [b'data']
            with patch('google.generativeai.upload_file') as mock_upload:
                mock_upload.return_value.state.name = "ACTIVE"
                with patch('app.model.start_chat') as mock_chat:
                    mock_chat.return_value.send_message.return_value.text = "Audio Answer"
                    with patch('os.remove') as mock_remove:
                        with patch('os.path.exists', return_value=True):
                            with patch('threading.Thread', side_effect=lambda target, args: target(*args)):
                                app.handle_message(data)

                        mock_remove.assert_called()

if __name__ == '__main__':
    unittest.main()
