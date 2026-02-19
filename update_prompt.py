
import sys

try:
    with open('system_prompt.py', 'r') as f:
        content = f.read()

    # 1. Global replace ** -> *
    content = content.replace("**", "*")

    # 2. Insert new rules
    marker = "7. *CONTEXT SWITCHING:* If the user switches products, STOP the old topic and answer the NEW topic immediately."

    if marker not in content:
        print("Error: Could not find Rule 7 marker")
        print("Content snippet around 'CONTEXT SWITCHING':")
        idx = content.find('CONTEXT SWITCHING')
        if idx != -1:
            print(content[idx-20:idx+50])
        sys.exit(1)

    new_rules = """
8. *LANGUAGE CONTINUITY (CRITICAL):* ALWAYS reply in the exact language the user used to initiate the chat or their voice note (e.g., Malayalam). If the user answers a question with just a number (like '30') or a single English word (like 'Male'), DO NOT switch back to English. Maintain their preferred language strictly throughout the entire conversation.
9. *WHATSAPP FORMATTING:* Use single asterisks for bold text (e.g., bold text). NEVER use double asterisks."""

    # Note: I am appending the new rules AFTER the marker.
    content = content.replace(marker, marker + new_rules)

    with open('system_prompt.py', 'w') as f:
        f.write(content)

    print("Successfully updated system_prompt.py")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
