import unittest
from unittest.mock import patch, MagicMock
import app
import time

class TestStopCache(unittest.TestCase):
    def setUp(self):
        app.stop_bot_cache = {} # Clear cache
        app.ZOKO_API_KEY = "dummy_key" # Enable API logic
        self.phone = "+919999999999"

    def tearDown(self):
        app.ZOKO_API_KEY = None

    @patch('app.requests.get')
    def test_cache_hit_and_miss(self, mock_get):
        # 1. API Call setup - STOPPED
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # The code expects data -> list -> tags
        mock_resp.json.return_value = {"data": [{"tags": ["STOP_BOT"]}]}
        mock_get.return_value = mock_resp

        # 2. First call (Cache Miss -> API Call)
        is_stopped = app.check_stop_bot(self.phone)
        self.assertTrue(is_stopped, "Should be stopped from API")
        self.assertEqual(mock_get.call_count, 1, "Should call API once")

        # 3. Second call (Cache Hit -> No API Call)
        is_stopped_2 = app.check_stop_bot(self.phone)
        self.assertTrue(is_stopped_2, "Should remain stopped from Cache")
        self.assertEqual(mock_get.call_count, 1, "Should NOT call API again")

        # 4. Expire Cache
        app.stop_bot_cache[self.phone]["timestamp"] = time.time() - app.CACHE_TTL - 1

        # 5. Third call (Cache Miss -> API Call)
        # Change mock to return NOT STOPPED to verify new fetch
        mock_resp.json.return_value = {"data": [{"tags": ["VIP"]}]}

        is_stopped_3 = app.check_stop_bot(self.phone)
        self.assertFalse(is_stopped_3, "Should be updated to allowed")
        self.assertEqual(mock_get.call_count, 2, "Should call API again after expiry")

    def test_local_stop_override(self):
        # Verify that set_stop_bot_locally works immediately
        self.assertFalse(app.check_stop_bot(self.phone), "Initially should not be stopped (no key/mock)")

        app.set_stop_bot_locally(self.phone)

        self.assertTrue(app.check_stop_bot(self.phone), "Should be stopped after local override")
        self.assertTrue(app.stop_bot_cache[self.phone]["stopped"])

if __name__ == '__main__':
    unittest.main()
