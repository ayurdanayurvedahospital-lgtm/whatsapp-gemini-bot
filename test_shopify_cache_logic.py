import unittest
import time
import threading
from unittest.mock import MagicMock, patch
import app

class TestShopifyCacheLogic(unittest.TestCase):

    def setUp(self):
        # Reset the cache and other globals before each test
        app.shopify_token_cache = {"access_token": None, "expires_at": 0}
        app.SHOPIFY_DOMAIN = "test.myshopify.com"
        app.SHOPIFY_CLIENT_ID = "cid"
        app.SHOPIFY_CLIENT_SECRET = "sec"

    @patch('app.requests.post')
    def test_token_is_cached(self, mock_post):
        # Mock successful response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "token123", "expires_in": 3600}
        mock_post.return_value = mock_resp

        # First call - should trigger API call
        token1 = app.get_shopify_token()
        self.assertEqual(token1, "token123")
        self.assertEqual(mock_post.call_count, 1)

        # Second call - should return cached token
        token2 = app.get_shopify_token()
        self.assertEqual(token2, "token123")
        self.assertEqual(mock_post.call_count, 1)

    @patch('app.requests.post')
    def test_token_refresh_after_expiry(self, mock_post):
        # Mock first response
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = {"access_token": "token1", "expires_in": 10}

        # Mock second response
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {"access_token": "token2", "expires_in": 3600}

        mock_post.side_effect = [mock_resp1, mock_resp2]

        # First call
        token1 = app.get_shopify_token()
        self.assertEqual(token1, "token1")

        # Manually expire the cache (below threshold)
        app.shopify_token_cache["expires_at"] = time.time() - 10

        # Second call - should trigger NEW API call
        token2 = app.get_shopify_token()
        self.assertEqual(token2, "token2")
        self.assertEqual(mock_post.call_count, 2)

    @patch('app.requests.post')
    def test_thread_safety_locking(self, mock_post):
        # Mock response with a slight delay to test locking
        def slow_response(*args, **kwargs):
            time.sleep(0.1)
            m = MagicMock()
            m.status_code = 200
            m.json.return_value = {"access_token": "lock_token", "expires_in": 3600}
            return m

        mock_post.side_effect = slow_response

        results = []
        def call_token():
            token = app.get_shopify_token()
            results.append(token)

        threads = [threading.Thread(target=call_token) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        # All threads should get the same token
        for r in results:
            self.assertEqual(r, "lock_token")

        # Requests.post should only be called ONCE despite concurrent requests
        self.assertEqual(mock_post.call_count, 1)

if __name__ == '__main__':
    unittest.main()
