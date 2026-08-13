# Simple script to find the duplicate section
with open('enterprise/enterprise_dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Search for lines containing common strings
needles = ['Maintenance History', 'maintenance history',
           'View History', 'view history',
           'Select a machine', 'select a machine']

for needle in needles:
    idx = 0
    count = 0
    while True:
        idx = content.find(needle, idx)
        if idx < 0:
            break
        count += 1
        linenum = content[:idx].count('\n') + 1
        start = max(0, idx-50)
        end = min(len(content), idx+150)
        print(f'=== Found "{needle}" #{count} at line {linenum} ===')
        print(content[start:end])
        print()
        idx += 1