import sys
import unittest
from unittest.mock import MagicMock

# Mocking dependencies
mock_flask = MagicMock()
mock_app = MagicMock()
mock_test_client = MagicMock()
mock_response = MagicMock()
mock_response.status_code = 200
mock_response.json = {'status': 'received'}

mock_test_client.post.return_value = mock_response
mock_app.test_client.return_value = mock_test_client
mock_flask.Flask.return_value = mock_app
sys.modules['flask'] = mock_flask

mock_requests = MagicMock()
sys.modules['requests'] = mock_requests

mock_genai = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = mock_genai

mock_pytz = MagicMock()
sys.modules['pytz'] = mock_pytz

mock_pypdf2 = MagicMock()
sys.modules['PyPDF2'] = mock_pypdf2

def run_tests():
    test_modules = [
        'test_background_logic',
        'test_shopify_logic',
        'test_stop_cache',
        'test_zoko_send_logic'
    ]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for module_name in test_modules:
        try:
            module = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"Failed to import {module_name}: {e}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
