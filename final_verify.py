import sys
from unittest.mock import MagicMock, patch
import time
import re

# Comprehensive Mocking
mock_google = MagicMock()
mock_genai = MagicMock()
mock_google.genai = mock_genai
sys.modules['google'] = mock_google
sys.modules['google.genai'] = mock_genai
sys.modules['google.genai.types'] = MagicMock()

mock_requests = MagicMock()
mock_flask = MagicMock()
mock_pytz = MagicMock()

sys.modules['requests'] = mock_requests
sys.modules['flask'] = mock_flask
sys.modules['pytz'] = mock_pytz

import app

def test_shopify_caching():
    print("Testing Shopify Caching...")
    app.SHOPIFY_DOMAIN = "test.myshopify.com"
    app.SHOPIFY_CLIENT_ID = "id"
    app.SHOPIFY_CLIENT_SECRET = "secret"

    # Mock successful token response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "token123", "expires_in": 3600}
    mock_resp.status_code = 200
    mock_requests.post.return_value = mock_resp

    # Reset call count
    mock_requests.post.reset_mock()

    # Reset cache
    app.shopify_token_cache = {"access_token": None, "expires_at": 0}

    # First call
    t1 = app.get_shopify_token()
    # Second call (should be cached)
    t2 = app.get_shopify_token()

    assert t1 == "token123"
    assert t2 == "token123"
    assert mock_requests.post.call_count == 1
    print("✅ Shopify Caching works.")

def test_html_stripping():
    print("Testing HTML Stripping...")
    input_text = "Hello world <!-- thinking: I should say hi --> How are you?"

    with patch('app.client') as mock_client:
        mock_response = MagicMock()
        mock_response.text = input_text
        mock_client.models.generate_content.return_value = mock_response

        output = app.call_gemini_with_retry([{"parts": [{"text": "hi"}]}])
        assert "<!--" not in output
        assert "thinking" not in output
        assert output == "Hello world  How are you?"
    print("✅ HTML Stripping works.")

def test_structural_leak_filter():
    print("Testing Structural Leak Filter...")
    test_cases = [
        ("AEAC: Hello", "Hello"),
        ("Awareness: I see you are struggling", "I see you are struggling"),
        ("*Education*: This is important", "This is important"),
        ("അവബോധം: നമസ്കാരം", "നമസ്കാരം"),
        ("Thought: I should recommend Sakhitone", "I should recommend Sakhitone"),
        ("thought: internal process", "internal process"),
        ("*Closing*: Have a nice day", "Have a nice day"),
        ("Normal message with no leaks", "Normal message with no leaks"),
        ("I thought you would like this", "I you would like this"),
        ("AEAC Education Closing", "")
    ]

    with patch('app.client') as mock_client:
        for input_raw, expected in test_cases:
            mock_response = MagicMock()
            mock_response.text = input_raw
            mock_client.models.generate_content.return_value = mock_response

            output = app.call_gemini_with_retry([{"parts": [{"text": "test"}]}])
            assert output == expected, f"Failed for '{input_raw}'. Got: '{output}', Expected: '{expected}'"
    print("✅ Structural Leak Filter works.")

def test_fallback_logic():
    print("Testing Fallback Logic (Flash -> Pro)...")

    class MockClient:
        def __init__(self):
            self.models = MagicMock()
            self.call_count = 0

        def generate_content_side_effect(self, model, contents, config):
            self.call_count += 1
            if model == "gemini-3-flash-preview":
                raise Exception("429 Resource exhausted")
            return MagicMock(text="Response from Pro")

    mock_c = MockClient()
    mock_c.models.generate_content.side_effect = mock_c.generate_content_side_effect

    # Ensure app.client is not None for the test
    with patch('app.client', mock_c):
        output = app.call_gemini_with_retry([{"parts": [{"text": "hi"}]}])
        assert output == "Response from Pro"
        assert mock_c.call_count == 2
    print("✅ Fallback Logic works.")

if __name__ == "__main__":
    try:
        test_shopify_caching()
        test_html_stripping()
        test_structural_leak_filter()
        test_fallback_logic()
        print("\nALL SYSTEM TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
