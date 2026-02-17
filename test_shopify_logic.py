import unittest
from unittest.mock import patch, MagicMock
import app
import logging

# Disable logging for tests
logging.disable(logging.CRITICAL)

class TestShopifyLogic(unittest.TestCase):

    @patch('app.requests.post')
    def test_get_shopify_token_success(self, mock_post):
        app.SHOPIFY_DOMAIN = "test.myshopify.com"
        app.SHOPIFY_CLIENT_ID = "cid"
        app.SHOPIFY_CLIENT_SECRET = "sec"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "fake_token"}
        mock_post.return_value = mock_resp

        token = app.get_shopify_token()
        self.assertEqual(token, "fake_token")
        mock_post.assert_called_with(
            "https://test.myshopify.com/admin/oauth/access_token",
            json={
                "client_id": "cid",
                "client_secret": "sec",
                "grant_type": "client_credentials"
            },
            timeout=10
        )

    @patch('app.get_shopify_token')
    @patch('app.requests.get')
    def test_check_order_by_id(self, mock_get, mock_token):
        mock_token.return_value = "fake_token"
        app.SHOPIFY_DOMAIN = "test.myshopify.com"

        # Mock Orders Response (Fulfilled with Tracking)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "orders": [{
                "name": "#1001",
                "fulfillment_status": "fulfilled",
                "financial_status": "paid",
                "fulfillments": [{"tracking_url": "http://track.me"}]
            }]
        }
        mock_get.return_value = mock_resp

        status = app.get_order_status("1001")
        self.assertIn("Your order *#1001* is *fulfilled*", status)
        self.assertIn("Tracking: http://track.me", status)
        self.assertIn("919526530900", status)

        # Verify URL
        mock_get.assert_called_with(
            "https://test.myshopify.com/admin/api/2023-10/orders.json?name=#1001&status=any",
            headers={"X-Shopify-Access-Token": "fake_token", "Content-Type": "application/json"},
            timeout=10
        )

    @patch('app.get_shopify_token')
    @patch('app.requests.get')
    def test_check_order_by_phone(self, mock_get, mock_token):
        mock_token.return_value = "fake_token"
        app.SHOPIFY_DOMAIN = "test.myshopify.com"

        # 1. Mock Order Name Search (Fail)
        mock_fail_resp = MagicMock()
        mock_fail_resp.status_code = 200
        mock_fail_resp.json.return_value = {"orders": []}

        # 2. Mock Customer Search Response (Success)
        mock_cust_resp = MagicMock()
        mock_cust_resp.status_code = 200
        mock_cust_resp.json.return_value = {
            "customers": [{"id": 123}]
        }

        # 3. Mock Order Lookup Response (Success - Unfulfilled)
        mock_order_resp = MagicMock()
        mock_order_resp.status_code = 200
        mock_order_resp.json.return_value = {
            "orders": [{
                "name": "#2002",
                "fulfillment_status": None, # Unfulfilled
                "financial_status": "pending"
            }]
        }

        # Side effect for consecutive calls
        mock_get.side_effect = [mock_fail_resp, mock_cust_resp, mock_order_resp]

        status = app.get_order_status("9999999999")
        self.assertIn("Your order is not fulfilled yet", status)
        self.assertIn("919526530900", status)

    @patch('app.get_shopify_token')
    def test_check_order_fail(self, mock_token):
        mock_token.return_value = None
        status = app.get_order_status("123")
        self.assertIn("unable to access", status)

if __name__ == '__main__':
    unittest.main()
