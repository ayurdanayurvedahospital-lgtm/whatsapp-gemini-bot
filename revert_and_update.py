import re

# --- REVERT app.py ---
with open('app.py', 'r') as f:
    app_content = f.read()

app_content = app_content.replace('import json\n', '')

# Logic to strip the JSON parsing and return raw text
def app_revert_logic(match):
    return match.group(1) + 'return response.text'

# Handle process_audio
app_content = re.sub(r'(response = chat\.send_message\(\[myfile, prompt\]\)\n\s+)raw_msg = response\.text.*?return clean_msg',
                     r'\1return response.text', app_content, flags=re.DOTALL)

# Handle process_image
app_content = re.sub(r'(response = chat\.send_message\(\[myfile, full_prompt\]\)\n\n\s+try:\n\s+)raw_msg = response\.text.*?return clean_msg',
                     r'\1return response.text', app_content, flags=re.DOTALL)

# Handle get_ai_response
app_content = re.sub(r'(response = chat\.send_message\(message_text\)\n\s+)raw_msg = response\.text.*?return clean_msg',
                     r'\1return response.text', app_content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(app_content)

# --- UPDATE system_prompt.py ---
with open('system_prompt.py', 'r') as f:
    prompt_content = f.read()

# Task 1 & 2 logic already exists but needs cleanup of JSON rules
# Actually, I should just overwrite the Rule 3 and add Task 3.

# Re-defining Rule 3 and removing JSON rule
new_rule_3 = """3. ABSOLUTE ZERO META-TALK, NO NARRATION & NO "SILENT PROCESSING":
- THE "SILENT PROCESSING" BAN: You are STRICTLY FORBIDDEN from outputting phrases like "Silent Processing:", "Thinking:", or any internal reasoning. NEVER start a message with your thought process.
- NO PLANNING: Do not describe the user's input or plan your response out loud (e.g., never say "I have detected Malayalam...", "Based on the previous interaction...").
- THE FIRST CHARACTER RULE: Output ONLY the final conversational dialogue meant strictly for the patient's ears. The very first character of your output MUST be the actual message you want to say to the user."""

prompt_content = re.sub(r'3\. \[NEW RULE\] STRICT JSON OUTPUT FORMAT \(MANDATORY\):.*?around the object\.',
                        new_rule_3, prompt_content, flags=re.DOTALL)

# Task 3: Language Script Purity
script_purity = """- ABSOLUTE ALPHABET PURITY: You are strictly forbidden from mixing different regional or global alphabets in the same message. 100% of your response must be written exclusively in the native script of the currently locked language.
- NO CARRYOVER: If a user switches languages (e.g., from Malayalam to Kannada), you must instantly perform a script reset. Do not carry over a single character from the previous language into the new response.
- THE ENGLISH EXCEPTION: Regardless of the currently locked language, time-based greetings (Good morning, Good afternoon, Good evening) and the Hospital Address MUST ALWAYS remain in English."""

prompt_content = prompt_content.replace('- TRANSLATION FIREWALL: Your internal logic is English, but you must not leak English sentences into other languages. (Exception: You may use English script ONLY for exact Brand/Product Names like "Sakhitone" or "Gain Plus" within a foreign language sentence. No other exceptions).',
                                        '- TRANSLATION FIREWALL: Your internal logic is English, but you must not leak English sentences into other languages. (Exception: You may use English script ONLY for exact Brand/Product Names like "Sakhitone" or "Gain Plus" within a foreign language sentence. No other exceptions).\n' + script_purity)

# Task 2: Gender Ban rule
gender_ban_rule = """[NEW RULE] THE "GENDER" BAN:
- THE "GENDER" BAN: You are STRICTLY FORBIDDEN from using the word "Gender" (or any of its direct translations, e.g., ലിംഗം in Malayalam, लिंग in Hindi) in ANY language.
- MANDATORY PHRASING: Whenever you need to ask for this information, you MUST use this exact concept (translated perfectly into the user's locked language): "To recommend the best Ayurvedic treatment for you, please let me know your age and whether you are male or female.\""""

# It was already there in the previous version I made, but let's ensure it's correct.
# Actually, the user wants me to add it.
if '[NEW RULE] THE "GENDER" BAN' not in prompt_content:
    prompt_content = prompt_content.replace('[NEW RULE] THE STRICT KNOWLEDGE BASE HIERARCHY:',
                                            gender_ban_rule + '\n\n[NEW RULE] THE STRICT KNOWLEDGE BASE HIERARCHY:')
else:
    # Update it to match the new mandatory phrasing if needed
    prompt_content = re.sub(r'\[NEW RULE\] THE "GENDER" BAN:.*?\n\n', gender_ban_rule + '\n\n', prompt_content, flags=re.DOTALL)

with open('system_prompt.py', 'w') as f:
    f.write(prompt_content)
