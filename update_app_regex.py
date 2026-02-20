
import sys

try:
    with open('app.py', 'r') as f:
        content = f.read()

    # Regex string to be inserted
    regex_pattern = r"^(?:തിങ്ക്|Think|THOUGHT|Thinking|The user|ദി യൂസർ).*?(?:\n|$)"

    # 1. process_audio (12 spaces)
    # The current text in app.py
    old_pa = '            # Strip internal AI thoughts regardless of language\n            reply_text = re.sub(r\'<think>.*?</think>\', \'\', reply_text, flags=re.DOTALL).strip()\n            return reply_text'

    # The new text
    new_pa_lines = [
        '            # 1. Strip <think> tags if the AI uses them correctly',
        '            reply_text = re.sub(r\'<think>.*?</think>\', \'\', reply_text, flags=re.DOTALL | re.IGNORECASE)',
        '',
        '            # 2. Aggressively strip rogue paragraphs that start with "Think:", "തിങ്ക്:", "ദി യൂസർ" or "The user"',
        '            # This deletes the entire thought paragraph up to the line break where the actual reply begins.',
        f'            reply_text = re.sub(r\'{regex_pattern}\', \'\', reply_text, flags=re.MULTILINE | re.IGNORECASE).strip()',
        '            return reply_text'
    ]
    new_pa = '\n'.join(new_pa_lines)

    if old_pa not in content:
        print('Warning: old_pa not found')
        # Debugging: Print surrounding text if possible
        idx = content.find('process_audio')
        if idx != -1:
            print('process_audio context:')
            # print(content[idx:idx+500])

    content = content.replace(old_pa, new_pa)

    # 2. get_ai_response (8 spaces)
    old_gar = '        # Strip internal AI thoughts regardless of language\n        reply_text = re.sub(r\'<think>.*?</think>\', \'\', reply_text, flags=re.DOTALL).strip()\n        return reply_text'

    new_gar_lines = [
        '        # 1. Strip <think> tags if the AI uses them correctly',
        '        reply_text = re.sub(r\'<think>.*?</think>\', \'\', reply_text, flags=re.DOTALL | re.IGNORECASE)',
        '',
        '        # 2. Aggressively strip rogue paragraphs that start with "Think:", "തിങ്ക്:", "ദി യൂസർ" or "The user"',
        '        # This deletes the entire thought paragraph up to the line break where the actual reply begins.',
        f'        reply_text = re.sub(r\'{regex_pattern}\', \'\', reply_text, flags=re.MULTILINE | re.IGNORECASE).strip()',
        '        return reply_text'
    ]
    new_gar = '\n'.join(new_gar_lines)

    if old_gar not in content:
        print('Warning: old_gar not found')

    content = content.replace(old_gar, new_gar)

    with open('app.py', 'w') as f:
        f.write(content)

    print('Successfully updated app.py with aggressive regex.')

except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
