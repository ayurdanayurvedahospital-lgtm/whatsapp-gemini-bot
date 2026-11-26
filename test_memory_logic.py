import unittest
from unittest.mock import MagicMock, patch
import time
import app


class TestMemoryLogic(unittest.TestCase):

    def setUp(self):
        conn = app.sqlite3.connect(app.DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        conn.close()
        app.user_sessions.clear()
        app.processed_messages.clear()
        app.stop_bot_cache.clear()
        for phone in list(app.followup_timers.keys()):
            app.cancel_timers(phone)
        app.followup_timers.clear()

    @patch('app.sqlite3')
    def test_inactivity_clearing_48_hours(self, mock_sqlite3):
        phone = "+91 11111111"

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite3.connect.return_value = mock_conn

        # 1. Active at 24 hours (< 48 hours) -> history MUST be retained
        mock_cursor.fetchone.return_value = (
            '[{"role": "user", "parts": ["24h old msg"]}]',
            time.time() - (24 * 3600),
            0, 0, 0, 0, 0, 0
        )
        history_24h = app.get_user_history(phone)
        self.assertEqual(len(history_24h), 1)
        self.assertEqual(history_24h[0]["parts"][0], "24h old msg")

        # 2. Expired after 48 hours (e.g. 49 hours) -> history MUST be cleared
        mock_cursor.fetchone.return_value = (
            '[{"role": "user", "parts": ["49h old msg"]}]',
            time.time() - (49 * 3600),
            0, 0, 0, 0, 0, 0
        )
        history_49h = app.get_user_history(phone)
        self.assertEqual(len(history_49h), 0)

    def test_normalize_phone_consistency(self):
        raw_1 = "+91 9876543210"
        raw_2 = "919876543210"
        raw_3 = " +91-98765-43210 "

        norm_1 = app.normalize_phone(raw_1)
        norm_2 = app.normalize_phone(raw_2)
        norm_3 = app.normalize_phone(raw_3)

        self.assertEqual(norm_1, "919876543210")
        self.assertEqual(norm_1, norm_2)
        self.assertEqual(norm_2, norm_3)

        # Saving under raw_1 and retrieving under raw_2 must hit the same SQLite row
        app.save_user_history(raw_1, [{"role": "user", "parts": ["hello"]}])
        hist = app.get_user_history(raw_2)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["parts"][0], "hello")

    def test_trim_history_with_latch_preserves_system_prefix_and_first_6_chat_messages(self):
        system_content = app.types.Content(
            role="user",
            parts=[app.types.Part.from_text(text="You are AIVA, system prompt instructions.")]
        )
        ack_content = app.types.Content(
            role="model",
            parts=[app.types.Part.from_text(text="Understood. I am AIVA. Current Time Greeting is: Good Morning.")]
        )

        # Build 24 chat messages (12 user/model pairs) + 1 active turn => len(contents) = 27 (> 25)
        chat_turns = []
        for i in range(24):
            role = "user" if i % 2 == 0 else "model"
            text = f"chat_msg_{i}"
            if i == 9:
                text = "Your payment received and order confirmed!"
            chat_turns.append(app.types.Content(role=role, parts=[app.types.Part.from_text(text=text)]))

        active_turn = app.types.Content(
            role="user",
            parts=[app.types.Part.from_text(text="active_user_question")]
        )

        contents = [system_content, ack_content] + chat_turns + [active_turn]
        self.assertGreater(len(contents), 25)

        trimmed = app.trim_history_with_latch(contents)

        # 1. System prefix at indices 0 and 1 must be preserved intact
        self.assertEqual(trimmed[0], system_content)
        self.assertEqual(trimmed[1], ack_content)

        # 2. First 6 chat messages (chat_msg_0 .. chat_msg_5) must be pinned immediately after prefix
        for idx in range(6):
            self.assertEqual(trimmed[2 + idx], chat_turns[idx])

        # 3. Payment-latched message in the middle (chat_msg_9) must be preserved
        self.assertIn(chat_turns[9], trimmed)

        # 4. Recent 12 chat messages (chat_msg_12 .. chat_msg_23) and active_turn must be preserved
        self.assertEqual(trimmed[-13:-1], chat_turns[-12:])
        self.assertEqual(trimmed[-1], active_turn)

    @patch('app.send_whatsapp_message')
    @patch('app.start_inactivity_timer')
    @patch('app.call_gemini_with_retry')
    def test_triage_bypass_populates_user_sessions_for_turn_2(self, mock_gemini, mock_timer, mock_send):
        mock_gemini.return_value = "Thank you for sharing your age and gender. Let us check your weight."

        # Turn 1: User enquires about Staamigen Malt with "+91 9876543210"
        turn_1_payload = {
            "messageId": "triage_msg_1",
            "platformSenderId": "+91 9876543210",
            "type": "text",
            "text": "I want details about Staamigen Malt",
            "direction": "incoming"
        }
        app.handle_message(turn_1_payload)

        norm_key = "919876543210"
        self.assertIn(norm_key, app.user_sessions)
        chat_after_turn_1 = app.user_sessions[norm_key]["chat"]
        self.assertEqual(len(chat_after_turn_1), 2)
        self.assertIn("Staamigen Malt", app._extract_item_text(chat_after_turn_1[0]))
        self.assertIn("age", app._extract_item_text(chat_after_turn_1[1]).lower())

        # Turn 2: User replies with age and sex using "919876543210" (without + or space)
        turn_2_payload = {
            "messageId": "triage_msg_2",
            "platformSenderId": "919876543210",
            "type": "text",
            "text": "24 male",
            "direction": "incoming"
        }
        app.handle_message(turn_2_payload)

        self.assertTrue(mock_gemini.called)
        sent_contents = mock_gemini.call_args[0][0]
        # sent_contents = [system_content, ack_content, turn1_user, turn1_model, turn2_active_user]
        self.assertEqual(len(sent_contents), 5)
        self.assertIn("Staamigen Malt", app._extract_item_text(sent_contents[2]))
        self.assertEqual(len(app.user_sessions[norm_key]["chat"]), 4)


if __name__ == '__main__':
    unittest.main()
