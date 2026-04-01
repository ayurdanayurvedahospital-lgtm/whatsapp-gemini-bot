import sys
from unittest.mock import MagicMock

# Mock dependencies before importing app
mock_requests = MagicMock()
sys.modules["requests"] = mock_requests
sys.modules["flask"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["pytz"] = MagicMock()

import unittest
import app
from system_prompt import SYSTEM_PROMPT

class TestDeficitHardStop(unittest.TestCase):

    def test_path_a_hard_stop(self):
        # Verify Path A strict rules
        self.assertIn("PATH A: IF WEIGHT DEFICIT IS 15 KG OR MORE:", SYSTEM_PROMPT)
        self.assertIn("[PACING FIREWALL]", SYSTEM_PROMPT)
        self.assertIn("[STRICT PAUSE MANDATE]", SYSTEM_PROMPT)
        self.assertIn("The response MUST end immediately after the hook statement.", SYSTEM_PROMPT)
        self.assertIn("output the authoritative diagnostic hook EXACTLY as per these emotional blueprints", SYSTEM_PROMPT)
        self.assertIn("STOP and wait for the user to reply and commit to the \"skinny\" statement", SYSTEM_PROMPT)

    def test_path_b_bundling(self):
        # Verify Path B bundling rules
        self.assertIn("PATH B: IF WEIGHT DEFICIT IS LESS THAN 15 KG:", SYSTEM_PROMPT)
        self.assertIn("CALCULATE & BUNDLE", SYSTEM_PROMPT)
        self.assertIn("SKIP the \"skinny\" hook", SYSTEM_PROMPT)
        self.assertIn("MEDICAL FLOW: In the SAME message as the calculation, proceed directly to ask the relevant Medical History Check", SYSTEM_PROMPT)

if __name__ == '__main__':
    unittest.main()
