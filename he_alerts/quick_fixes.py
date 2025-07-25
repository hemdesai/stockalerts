"""Quick fixes for the email processing issues."""
import sys
from pathlib import Path

# Fix 1: Update gmail_client.py to handle timezone properly
gmail_client_path = Path("app/services/email/gmail_client.py")
content = gmail_client_path.read_text()

# Replace the parsedate_to_datetime import
content = content.replace(
    "from email.utils import parsedate_to_datetime",
    "from email.utils import parsedate_to_datetime\nfrom datetime import timezone"
)

# Fix the date parsing to remove timezone
content = content.replace(
    "received_date = parsedate_to_datetime(date_str)",
    "received_date = parsedate_to_datetime(date_str).replace(tzinfo=None)"
)

gmail_client_path.write_text(content)
print("✅ Fixed timezone issue in gmail_client.py")

# Fix 2: Update mistral.py to better handle JSON responses
mistral_path = Path("app/services/email/processors/mistral.py")
content = mistral_path.read_text()

# Update the JSON parsing to handle truncated responses
old_parse = '''            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\\s*({.*?})\\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like content
            json_match = re.search(r'{.*}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass'''

new_parse = '''            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\\s*({.*?})\\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like content (handle truncated responses)
            json_match = re.search(r'{[\\s\\S]*"extracted_items"[\\s\\S]*?\\[.*?\\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                # Find the last complete item
                last_brace = json_str.rfind('}')
                if last_brace > 0:
                    # Find the closing bracket and brace for the JSON
                    bracket_pos = json_str.find(']', last_brace)
                    if bracket_pos > 0:
                        json_str = json_str[:bracket_pos+1] + '}'
                    else:
                        json_str = json_str[:last_brace+1] + ']}'
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass'''

content = content.replace(old_parse, new_parse)
mistral_path.write_text(content)
print("✅ Improved JSON parsing in mistral.py")

# Fix 3: Update crypto price validation
crypto_path = Path("app/services/email/extractors/crypto.py")
content = crypto_path.read_text()

# Make crypto price validation more lenient
content = content.replace(
    "if buy_price < 0 or buy_price > 1000000:",
    "if buy_price < 0 or buy_price > 10000000:"
)
content = content.replace(
    "if sell_price < 0 or sell_price > 1000000:",
    "if sell_price < 0 or sell_price > 10000000:"
)

crypto_path.write_text(content)
print("✅ Fixed crypto price validation")

print("\n✅ All fixes applied! Ready to test again.")