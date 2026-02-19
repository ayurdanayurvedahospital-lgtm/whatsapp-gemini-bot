import unittest
from unittest.mock import patch, MagicMock
import app

class TestSendMessage(unittest.TestCase):
    @patch('app.requests.post')
    def test_send_text(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        app.send_whatsapp_message("123", "Hello", "text")

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://chat.zoko.io/v2/message")
        self.assertEqual(kwargs['json']['message'], "Hello")
        self.assertEqual(kwargs['json']['type'], "text")

    @patch('app.requests.post')
    def test_send_image_valid(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        app.send_whatsapp_message("123", "Caption", "image", "http://example.com/img.png")

        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['type'], "image")
        self.assertEqual(kwargs['json']['url'], "http://example.com/img.png")

    @patch('app.requests.post')
    def test_send_image_invalid(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        # Invalid URL (no http)
        app.send_whatsapp_message("123", "Caption", "image", "broken_link")

        args, kwargs = mock_post.call_args
        # Should fall back to text
        self.assertEqual(kwargs['json']['type'], "text")
        # The payload message should be the caption
        self.assertEqual(kwargs['json']['message'], "Caption")

if __name__ == '__main__':
    unittest.main()
