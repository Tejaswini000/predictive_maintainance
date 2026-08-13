import subprocess

# Get HEAD version
result = subprocess.run(['git', 'show', 'HEAD:enterprise/enterprise_dashboard.py'], capture_output=True)
head = result.stdout.decode('utf-8', errors='replace')

with open('enterprise/enterprise_dashboard.py', 'r', encoding='utf-8') as f:
    current = f.read()

head_lines = head.split('\n')
current_lines = current.split('\n')

# Find the difference between current and head analytics sections
# by looking at lines that exist in current but not in head
print("=== Lines in CURRENT that don't exist in HEAD (excluding trivial) ===")
for i, line in enumerate(current_lines):
    stripped = line.strip()
    if stripped and len(stripped) > 5:
        if stripped not in [h.strip() for h in head_lines]:
            # Skip pure whitespace/braces/parentheses lines
            if not stripped in ['{', '}', '}', '])', '])', '}']:
                print(f"  NEW L{i+1}: {stripped[:200]}")