import sys, os, py_compile

# Step 1: Clear stale pyc cache
cache_dir = 'enterprise/__pycache__'
for f in os.listdir(cache_dir):
    if 'enterprise_dashboard' in f or 'dashboard' in f:
        os.remove(os.path.join(cache_dir, f))
        print(f"Removed stale cache: {f}")

# Step 2: Verify source compiles
try:
    py_compile.compile('enterprise/enterprise_dashboard.py', doraise=True)
    print("Source compiles correctly")
except py_compile.PyCompileError as e:
    print(f"COMPILE ERROR: {e}")
    sys.exit(1)

# Step 3: Check for corrupted HTML fragments
with open('enterprise/enterprise_dashboard.py', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")

fragments = [
    ("ric-number broken", b"ric-number'>5</"),
    ("ric-label corrupted", b"ric-label'>"),
]

all_clean = True
for name, frag in fragments:
    pos = data.find(frag)
    if pos >= 0:
        print(f"ISSUE: '{name}' found at byte {pos}")
        print(f"  Context: {data[max(0,pos-20):pos+60]}")
        all_clean = False
    else:
        print(f"OK: '{name}' not found")

# Step 4: Check KPI section div balance
text = data.decode('utf-8', errors='replace')
kpi_start = text.find('# === KPI METRICS')
kpi_end = text.find('# === CHARTS ROW 1')
kpi_text = text[kpi_start:kpi_end]
open_divs = kpi_text.count('<div')
close_divs = kpi_text.count('</div>')
if open_divs == close_divs:
    print(f"OK: KPI section divs balanced ({open_divs} open, {close_divs} close)")
else:
    print(f"ISSUE: KPI section divs UNBALANCED (${open_divs} open, ${close_divs} close)")
    all_clean = False

# Step 5: Count metric card instances
import re
cards = len(re.findall(r"class='metric-card\{", kpi_text))
print(f"OK: {cards} metric-card instances found")

# Step 6: No st.write/st.text/st.code
for method in ['st.write', 'st.text', 'st.code']:
    if method in kpi_text:
        line_no = text[:kpi_start + kpi_text.find(method)].count('\n') + 1
        print(f"ISSUE: {method} found near line {line_no}")
        all_clean = False
print(f"OK: No st.write/st.text/st.code in KPI section")

# Step 7: Check null bytes
null_pos = data.find(b'\x00')
if null_pos >= 0:
    print(f"ISSUE: Null byte at {null_pos}")
    all_clean = False
else:
    print("OK: No null bytes")

# Step 8: Verify each card has proper structure
for i, card_type in enumerate(["categories", "all", "healthy", "warning", "critical", "avg_health"]):
    card_pattern = f"metric-card{{get_active_class(\"{card_type}\")}}"
    if card_pattern in kpi_text:
        print(f"OK: Card {i+1} ('{card_type}') found")
    else:
        print(f"ISSUE: Card {i+1} ('{card_type}') MISSING")
        all_clean = False

# Step 9: Verify the rendered HTML would be valid
# For each card, find the complete f-string block
card_blocks = kpi_text.split("st.markdown(f\"\"\"")
print(f"\nFound {len(card_blocks)-1} f-string HTML blocks in KPI section")

for i, block in enumerate(card_blocks[1:], 1):
    # Extract the HTML part (before closing \""")
    html_part = block.split('\"\"\", unsafe_allow_html=True')[0]
    odivs = html_part.count('<div')
    cdivs = html_part.count('</div>')
    if odivs == cdivs:
        print(f"  Block {i}: OK (divs balanced: {odivs})")
    else:
        print(f"  Block {i}: ISSUE (divs: {odivs} open, {cdivs} close)")
        all_clean = False

print(f"\n{'='*50}")
if all_clean:
    print("ALL CHECKS PASSED - KPI cards will render correctly")
else:
    print("SOME CHECKS FAILED - Review issues above")

print("="*50)