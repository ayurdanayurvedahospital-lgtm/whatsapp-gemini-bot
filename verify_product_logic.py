
import sys
from unittest.mock import MagicMock
import json
import re

# Mock dependencies
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()
sys.modules['flask'] = MagicMock()
sys.modules['pytz'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Mock knowledge_base_data
mock_kb = MagicMock()
mock_kb.PRODUCT_MANUALS = {"saphala_capsule": {}}
sys.modules['knowledge_base_data'] = mock_kb

def verify_updates():
    try:
        from system_prompt import SYSTEM_PROMPT
        print("SYSTEM_PROMPT loaded successfully.")

        # 1. Staamigen Powder Range and Unisex
        if "13 to 35" in SYSTEM_PROMPT and "UNISEX" in SYSTEM_PROMPT:
            print("Verified Staamigen Powder 13-35 UNISEX range.")
        else:
            print("ERROR: Staamigen Powder range or Unisex tag missing.")
            sys.exit(1)

        # 2. Gym Trigger
        if "GYM-GOER TRIGGER" in SYSTEM_PROMPT and "workout" in SYSTEM_PROMPT.lower():
            print("Verified Gym-goer trigger.")
        else:
            print("ERROR: Gym-goer trigger missing.")
            sys.exit(1)

        # 3. Dosage Logic (13-19: 6gm, 20-35: 10gm)
        if "6gm" in SYSTEM_PROMPT and "10gm" in SYSTEM_PROMPT:
             print("Verified dosage strings (6gm, 10gm).")
        else:
             print("ERROR: Dosages (6gm/10gm) missing.")
             sys.exit(1)

        # 4. Diabetic + Sexual Issues Logic
        if "DIABETIC CONSTRAINT" in SYSTEM_PROMPT and "STRICTLY AVOID recommending Saphala" in SYSTEM_PROMPT:
            print("Verified Diabetic sexual issues constraint.")
        else:
            print("ERROR: Diabetic constraint missing.")
            sys.exit(1)

        if "Ayur Diabet Powder" in SYSTEM_PROMPT and "sexual issues" in SYSTEM_PROMPT:
             print("Verified Ayur Diabet positioning for sexual issues.")
        else:
             print("ERROR: Ayur Diabet sexual issues positioning missing.")
             sys.exit(1)

        # 5. Preservation Checks
        if "Balamurali V" in SYSTEM_PROMPT:
            print("Verified creator signature preservation.")
        else:
            # Check the whole file if not in SYSTEM_PROMPT string (it's at the top of the file)
            with open('system_prompt.py', 'r') as f:
                if "Balamurali V" in f.read():
                    print("Verified creator signature preservation in file.")
                else:
                    print("ERROR: Creator signature lost.")
                    sys.exit(1)

        if "Height in cm - 100 = Required Weight in kg" in SYSTEM_PROMPT:
            print("Verified Passive BMI formula preservation.")
        else:
            print("ERROR: BMI formula modified.")
            sys.exit(1)

        if "PATH A: IF WEIGHT DEFICIT IS 15 KG OR MORE" in SYSTEM_PROMPT:
            print("Verified 15kg deficit flow preservation.")
        else:
            print("ERROR: Deficit flow lost.")
            sys.exit(1)

        if "*NEW DOSAGE PROTOCOL (STRICT AGE-GATING):*" in SYSTEM_PROMPT:
            print("Verified Junior dosage protocol preservation.")
        else:
            print("ERROR: Junior dosage protocol lost.")
            sys.exit(1)

    except Exception as e:
        print(f"FAILED verification: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_updates()
