import sys
from unittest.mock import MagicMock

# Mock everything needed for app.py
sys.modules['flask'] = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['pytz'] = MagicMock()
sys.modules['PyPDF2'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['knowledge_base_data'] = MagicMock()

try:
    # Set dummy objects in mocked modules
    sys.modules['knowledge_base_data'].AGENTS = []
    sys.modules['knowledge_base_data'].PRODUCT_IMAGES = {}
    sys.modules['knowledge_base_data'].LINKS = {}
    sys.modules['knowledge_base_data'].GOOGLE_FORM_URL = ""
    sys.modules['knowledge_base_data'].FORM_FIELDS = {}
    sys.modules['knowledge_base_data'].PRODUCT_MANUALS = {}

    import app
    print("App import successful.")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"App import failed: {e}")
    sys.exit(1)

try:
    from system_prompt import SYSTEM_PROMPT
    if "STRICT KNOWLEDGE BASE HIERARCHY" in SYSTEM_PROMPT:
        print("KB Hierarchy rule found in SYSTEM_PROMPT.")
    else:
        print("KB Hierarchy rule NOT found in SYSTEM_PROMPT.")
        sys.exit(1)

    if "I’m AIVA, Ayurvedic Expert" in SYSTEM_PROMPT:
         print("New greeting placeholder found in SYSTEM_PROMPT.")
    else:
         print("New greeting placeholder NOT found in SYSTEM_PROMPT.")
         sys.exit(1)

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"System prompt import failed: {e}")
    sys.exit(1)

print("Verification complete.")
