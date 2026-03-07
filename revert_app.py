import re

with open('app.py', 'r') as f:
    content = f.read()

# Remove import json
content = content.replace('import json\n', '')

# Helper to revert the logic in functions
def revert_func(match):
    # We want to replace the try-except-json-cleaning block with just returning response.text
    # The block starts with cleaning markdown and ends with return clean_msg
    return '            response = chat.send_message([myfile, prompt])\n            return response.text'

content = re.sub(r'            response = chat\.send_message\(\[myfile, prompt\]\)\n            raw_msg = response\.text.*?return clean_msg',
                 revert_func, content, flags=re.DOTALL)

def revert_func_image(match):
    return '            response = chat.send_message([myfile, full_prompt])\n\n            try:\n                return response.text'

content = re.sub(r'            response = chat\.send_message\(\[myfile, full_prompt\]\).*?return clean_msg',
                 revert_func_image, content, flags=re.DOTALL)

def revert_func_ai(match):
    return '        response = chat.send_message(message_text)\n        return response.text'

content = re.sub(r'        response = chat\.send_message\(message_text\)\n        raw_msg = response\.text.*?return clean_msg',
                 revert_func_ai, content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(content)
