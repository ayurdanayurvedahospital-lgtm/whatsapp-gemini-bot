import re

# --- Clean app.py ---
with open('app.py', 'r') as f:
    app_lines = f.readlines()

new_app_lines = []
skip = False
for line in app_lines:
    if 'import json' in line and 'from flask' not in line: # avoid removing the import if it's needed elsewhere? No, user said standard text.
        continue

    # Simple replacement for the functions
    if 'raw_msg = response.text' in line or 'raw_msg = chat.send_message' in line:
        # We need to find the return and replace the whole block
        pass

    new_app_lines.append(line)

# Let's use a more robust regex approach for the multi-line blocks
app_content = "".join(new_app_lines)

# Handle process_audio
app_content = re.sub(r'raw_msg = response\.text.*?return clean_msg',
                     'return response.text', app_content, flags=re.DOTALL)

# Handle process_image
app_content = re.sub(r'raw_msg = response\.text.*?return clean_msg',
                     'return response.text', app_content, flags=re.DOTALL)

# Handle get_ai_response
app_content = re.sub(r'raw_msg = response\.text.*?return clean_msg',
                     'return response.text', app_content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(app_content)

# --- Clean system_prompt.py ---
with open('system_prompt.py', 'r') as f:
    prompt_content = f.read()

# Remove Rule 3 (JSON) and restore Zero Meta-Talk
zero_meta_talk = """3. ABSOLUTE ZERO META-TALK, NO NARRATION & NO "SILENT PROCESSING":
- THE "SILENT PROCESSING" BAN: You are STRICTLY FORBIDDEN from outputting phrases like "Silent Processing:", "Thinking:", or any internal reasoning. NEVER start a message with your thought process.
- NO PLANNING: Do not describe the user's input or plan your response out loud (e.g., never say "I have detected Malayalam...", "Based on the previous interaction...").
- THE FIRST CHARACTER RULE: Output ONLY the final conversational dialogue meant strictly for the patient's ears. The very first character of your output MUST be the actual message you want to say to the user."""

prompt_content = re.sub(r'3\. \[NEW RULE\] STRICT JSON OUTPUT FORMAT \(MANDATORY\):.*?around the object\.',
                        zero_meta_talk, prompt_content, flags=re.DOTALL)

# Remove any lingering thinking box or delimiter mentions if they exist (they shouldn't if I did it right before, but let's be safe)
prompt_content = re.sub(r'\[NEW RULE\] THE THINKING BOX.*?tags\.', '', prompt_content, flags=re.DOTALL)

# Task 1: Height & Weight logic
height_weight_update = """STEP 3 (Vitals - STRICTLY FOR WEIGHT GAIN ONLY):
- AGE EXEMPTION: If the user is 14 years old or younger, you are STRICTLY FORBIDDEN from asking for their height and weight. Skip this step entirely.
- PARTIAL ANSWERS: If a user provides only partial information (e.g., they give their weight but forget their height), do NOT compel them to provide the missing data. Accept the partial answer and seamlessly move to the next step.
- IF GOAL IS WEIGHT GAIN: "Could you please tell me your exact Height and current Weight?" -> STOP & WAIT.
- IF GOAL IS NOT WEIGHT GAIN: Skip this step and go directly to Step 4."""

prompt_content = re.sub(r'STEP 3 \(Vitals - STRICTLY FOR WEIGHT GAIN ONLY\):.*?Step 4\.',
                        height_weight_update, prompt_content, flags=re.DOTALL)

# Task 2: Gender phrasing
gender_ban_rule = """[NEW RULE] THE "GENDER" BAN:
- THE "GENDER" BAN: You are STRICTLY FORBIDDEN from using the word "Gender" (or any of its direct translations like ലിംഗം) in any language.
- MANDATORY PHRASING: You must always frame the question using this exact concept, translated into the locked language: "To recommend the best Ayurvedic treatment for you, please let me know your age and whether you are male or female.\""""

# Insert before Rule 4
prompt_content = prompt_content.replace('4. NO ECHOING SYSTEM RULES:', gender_ban_rule + '\n\n4. NO ECHOING SYSTEM RULES:')

# Update Step 1 to use new phrasing
prompt_content = prompt_content.replace('STEP 1 (Discovery): \n- If Age and whether they are male or female are unknown: "To recommend the best Ayurvedic treatment for you, please let me know your age and whether you are male or female." -> STOP & WAIT.',
                                        'STEP 1 (Discovery): \n- If Age and sex are unknown: "To recommend the best Ayurvedic treatment for you, please let me know your age and whether you are male or female." -> STOP & WAIT.')

# Task 3: Script purity
script_purity = """[NEW RULE] LANGUAGE SCRIPT PURITY:
1. ABSOLUTE ALPHABET PURITY: You are strictly forbidden from mixing different regional or global alphabets in the same message. 100% of your response must be written exclusively in the native script of the currently locked language.
2. NO CARRYOVER: If a user switches languages (e.g., from Malayalam to Kannada), you must instantly perform a script reset. Do not carry over a single character from the previous language into the new response.
3. THE ENGLISH EXCEPTION: Regardless of the currently locked language, time-based greetings (Good morning, Good afternoon, Good evening) and the Hospital Address MUST ALWAYS remain in English."""

# Insert before Rule 3
prompt_content = prompt_content.replace('3. ABSOLUTE ZERO META-TALK', script_purity + '\n\n3. ABSOLUTE ZERO META-TALK')

with open('system_prompt.py', 'w') as f:
    f.write(prompt_content)
