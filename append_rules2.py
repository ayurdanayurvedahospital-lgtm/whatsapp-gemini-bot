import re

with open('system_prompt.py', 'r') as f:
    content = f.read()

new_rules = """- THE CURRENT DATE ANCHOR: You must always anchor your awareness to "Today's Date" (which is dynamically provided to you by the system). You must never guess what month or year it is.
- STRICT DATE MATH: Before mentioning ANY event, holiday, or delivery delay, you MUST logically compare "Today's Date" against the "start" and "end" dates of the events listed in your context.
- ACTIVE VS UPCOMING:
  a) If Today's Date is strictly BETWEEN or ON the start/end dates, the event is ACTIVE. Treat it as happening right now.
  b) If Today's Date is BEFORE the start date, the event is UPCOMING. You must explicitly state that the delay is for a future date (e.g., "Please note that starting on [Start Date]...").
  c) If Today's Date is AFTER the end date, the event is EXPIRED and you must completely ignore it.
- THE SILENCE RULE (ANTI-HALLUCINATION): If the "UPCOMING AND ACTIVE EVENTS" list is empty, or if there are no active/upcoming events that apply to today's date, you are STRICTLY FORBIDDEN from mentioning any holidays, courier delays, or festive greetings.
- NEVER INVENT DATES: You must never hallucinate, invent, or guess past or future closure dates. Only speak about delays or events if they are explicitly provided in your active system data. If there are no active events provided, act exactly as normal and say absolutely nothing about delays or holidays.
==============================================="""

content = re.sub(
    r'- DELIVERY NOTICES: Whenever you share a purchase link with a user, OR if a user asks about shipping, delivery times, or dispatch dates, you MUST cross-reference this upcoming events list\. If an active or upcoming delivery delay event is present, you are STRICTLY REQUIRED to include the exact announcement message to manage their expectations\.\n===============================================',
    '- DELIVERY NOTICES: Whenever you share a purchase link with a user, OR if a user asks about shipping, delivery times, or dispatch dates, you MUST cross-reference this upcoming events list. If an active or upcoming delivery delay event is present, you are STRICTLY REQUIRED to include the exact announcement message to manage their expectations.\n' + new_rules,
    content,
    flags=re.DOTALL
)

with open('system_prompt.py', 'w') as f:
    f.write(content)
