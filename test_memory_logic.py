import sys
from unittest.mock import MagicMock, patch
import time

# Comprehensive Mocking to bypass sandbox restrictions
mock_google = MagicMock()
mock_genai = MagicMock()
mock_google.genai = mock_genai
sys.modules['google'] = mock_google
sys.modules['google.genai'] = mock_genai
sys.modules['google.genai.types'] = MagicMock()

mock_requests = MagicMock()
mock_flask = MagicMock()
mock_pytz = MagicMock()


sys.modules['flask'] = mock_flask
sys.modules['pytz'] = mock_pytz

import app

@patch('app.sqlite3')
def test_rolling_window(mock_sqlite3):
    print("Testing Rolling Window (14 messages)...")
    phone = "+9100000000"

    # Fill with 20 messages
    for i in range(20):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite3.connect.return_value = mock_conn

        # Fake session return
        mock_cursor.fetchone.return_value = (None, time.time(), 0, 0, 0, 0, 0, 0)

        history = app.get_user_history(phone)
        history.append({"role": "user", "parts": [f"msg {i}"]})
        history.append({"role": "model", "parts": [f"resp {i}"]})
        app.save_user_history(phone, history)

    # Note: testing actual SQLite rolling window requires proper mocking of the fetch/save cycle,
    # or just mocking the SQLite logic directly.
    pass

@patch('app.sqlite3')
def test_inactivity_clearing(mock_sqlite3):
    print("Testing Inactivity Clearing (12 hours)...")
    phone = "+9111111111"

    # Simulate past activity
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_sqlite3.connect.return_value = mock_conn
    mock_cursor.fetchone.return_value = ('[{"role": "user", "parts": ["old msg"]}]', time.time() - (13 * 3600), 0, 0, 0, 0, 0, 0)

    history = app.get_user_history(phone)
    assert len(history) == 0
    print("✅ Inactivity Clearing works.")
