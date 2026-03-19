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

sys.modules['requests'] = mock_requests
sys.modules['flask'] = mock_flask
sys.modules['pytz'] = mock_pytz

import app

def test_rolling_window():
    print("Testing Rolling Window (14 messages)...")
    phone = "+9100000000"
    app.user_sessions[phone] = []
    app.user_last_active[phone] = time.time()

    # Fill with 20 messages
    for i in range(20):
        history = app.get_user_history(phone)
        history.append({"role": "user", "parts": [f"msg {i}"]})
        history.append({"role": "model", "parts": [f"resp {i}"]})
        app.save_user_history(phone, history)

    final_history = app.get_user_history(phone)
    print(f"History length: {len(final_history)}")
    assert len(final_history) <= 14
    # Check if we have the LATEST messages
    assert final_history[-1]["parts"][0] == "resp 19"
    print("✅ Rolling Window works.")

def test_inactivity_clearing():
    print("Testing Inactivity Clearing (12 hours)...")
    phone = "+9111111111"

    # Simulate past activity
    app.user_sessions[phone] = [{"role": "user", "parts": ["old msg"]}]
    app.user_last_active[phone] = time.time() - (13 * 3600) # 13 hours ago

    history = app.get_user_history(phone)
    assert len(history) == 0
    print("✅ Inactivity Clearing works.")

if __name__ == "__main__":
    try:
        test_rolling_window()
        test_inactivity_clearing()
        print("\nMEMORY LOGIC TESTS PASSED")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
