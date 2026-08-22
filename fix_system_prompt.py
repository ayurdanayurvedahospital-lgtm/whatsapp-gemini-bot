import re

with open('system_prompt.py', 'r') as f:
    content = f.read()

content = content.replace("SYSTEM_PROMPT = f\n🛑 SMART SANITY FILTER", "SYSTEM_PROMPT = f'''\n🛑 SMART SANITY FILTER")

with open('system_prompt.py', 'w') as f:
    f.write(content)
