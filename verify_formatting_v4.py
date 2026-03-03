import sys
from unittest.mock import MagicMock

# Mocking dependencies
sys.modules['flask'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['pytz'] = MagicMock()
sys.modules['PyPDF2'] = MagicMock()

try:
    from system_prompt import SYSTEM_PROMPT
    print("SUCCESS: system_prompt.py imported.")

    checks = {
        "Rule 2 (Post-Greeting Lock)": "POST-GREETING LOCK" in SYSTEM_PROMPT,
        "Rule 3 (Silent Processing Ban)": "SILENT PROCESSING" in SYSTEM_PROMPT,
        "Rule 6 (One-By-One Firewall)": "ONE-BY-ONE FIREWALL" in SYSTEM_PROMPT,
        "Formatting Firewall (Step 4)": "CRITICAL FORMATTING FIREWALL" in SYSTEM_PROMPT and "STRICTLY FORBIDDEN from outputting the structural labels" in SYSTEM_PROMPT,
        "Saphala Mapping": "- FOR SAPHALA (Premium Weight Gain):" in SYSTEM_PROMPT,
        "Knowledge Base (Ayur Diabet)": "AYUR DIABET USAGE INSTRUCTIONS" in SYSTEM_PROMPT,
        "Breastfeeding Rule": "BREASTFEEDING MOTHERS" in SYSTEM_PROMPT
    }

    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {label}")

    import app
    print("SUCCESS: app.py imported.")
except Exception as e:
    print(f"FAILURE: {e}")
