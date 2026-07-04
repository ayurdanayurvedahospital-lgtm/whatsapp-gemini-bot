import unittest
import sqlite3
import time
import json
import os
from unittest.mock import MagicMock, patch

# No sys.modules mocking here, rely on installed packages
import app

class TestMemoryLogic(unittest.TestCase):
    def setUp(self):
        app.db_init()
        conn = sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()

    def test_rolling_window(self):
        phone = "+9100000000"
        # Fill with 40 messages
        history = []
        for i in range(40):
            history.append({"role": "user", "parts": [f"msg {i}"]})
            app.save_user_history(phone, history)
            history = app.get_user_history(phone)

        final_history = app.get_user_history(phone)
        # app.py sliding window is 30
        self.assertLessEqual(len(final_history), 30)
        self.assertEqual(final_history[-1]["parts"][0], "msg 39")

    def test_inactivity_clearing(self):
        phone = "+9111111111"
        # Simulate past activity by manually inserting into DB
        conn = sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        old_time = time.time() - (13 * 3600)
        cursor.execute("INSERT INTO sessions (phone, history, last_active) VALUES (?, ?, ?)",
                       (phone, json.dumps([{"role": "user", "parts": ["old msg"]}]), old_time))
        conn.commit()
        conn.close()

        history = app.get_user_history(phone)
        self.assertEqual(len(history), 0)

if __name__ == "__main__":
    unittest.main()
