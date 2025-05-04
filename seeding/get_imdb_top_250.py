import re
import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# Load raw text from file (one big block with “1. The Shawshank Redemption”, etc.)
with open(os.path.join(script_dir, 'imdb_list.txt'), encoding='utf-8') as f:
    text = f.read()

# Only match “1. Title”, “2. Another Movie”, … “250. Last Movie”
pattern = re.compile(r'^\s*\d{1,3}\.\s+(.+)$', re.MULTILINE)
titles = pattern.findall(text)

# Build JSON array
output = [{"title": t.strip()} for t in titles]

print(f"🔍 Extracted {len(output)} titles")
with open(os.path.join(script_dir, 'top250.json'), 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("✅ Saved top250.json")
