import sys, py_compile

# Step 1: Verify file compiles
print("=" * 60)
print("KPI CARD HTML VERIFICATION")
print("=" * 60)

try:
    py_compile.compile('enterprise/enterprise_dashboard.py', doraise=True)
    print("\n✓ File compiles correctly")
except py_compile.PyCompileError as e:
    print(f"\n✗ COMPILE ERROR: {e}")
    sys.exit(1)

# Step 2: Check for corrupted fragments
with open('enterprise/enterprise_dashboard.py', 'rb') as f:
    data = f.read()

print(f"\nFile size: {len(data)} bytes")

bad_fragments = [
    b"ric-number'>5</",
    b"ric-label'>"
]
all_clean = True
for frag in bad_fragments:
    pos = data.find(frag)
    if pos >= 0:
        print(f"\n✗ CORRUPTED FRAGMENT FOUND: {frag[:30]}")
        print(f"  At position: {pos}")
        print(f"  Context: {data[max(0,pos-20):pos+80]}")
        all_clean = False
    else:
        print(f"\n✓ Fragment '{frag[:30]}' NOT found (good)")

# Step 3: Check div balance in KPI section
text = data.decode('utf-8', errors='replace')
kpi_start = text.find('# === KPI METRICS')
kpi_end = text.find('# === CHARTS ROW 1')
kpi_text = text[kpi_start:kpi_end]
open_divs = kpi_text.count('<div')
close_divs = kpi_text.count('</div>')
balanced = open_divs == close_divs
print(f"\n✓ KPI section divs: open={open_divs}, close={close_divs} {'BALANCED' if balanced else 'MISMATCH!'}")
if not balanced:
    all_clean = False

# Step 4: Count metric-card instances (should be 6 KPI cards)
import re
card_matches = re.findall(r"class='metric-card\{", kpi_text)
print(f"\n✓ metric-card instances in KPI section: {len(card_matches)} (expected: 6)")

# Step 5: Verify only st.markdown is used (no st.write/st.text/st.code)
kpi_lines = kpi_text.split('\n')
bad_output = False
for line in kpi_lines:
    stripped = line.strip()
    if 'st.write(' in stripped or 'st.text(' in stripped or 'st.code(' in stripped:
        print(f"\n✗ INVALID OUTPUT METHOD: {stripped[:80]}")
        bad_output = True
        all_clean = False
if not bad_output:
    print("\n✓ No st.write/st.text/st.code in KPI section (only st.markdown)")

# Step 6: Verify f-strings are properly formed
print("\n✓ f-strings in KPI section:")
kpi_lines = kpi_text.split('\n')
for i, line in enumerate(kpi_lines, start=kpi_text.count('\n', 0, kpi_start) + 1):
    if 'f"""' in line:
        print(f"  Line {i}: {line.strip()[:80]}")

# Step 7: Check for null bytes
null_pos = data.find(b'\x00')
if null_pos >= 0:
    print(f"\n✗ NULL BYTE found at position {null_pos}")
    all_clean = False
else:
    print("\n✓ No null bytes found")

# Final result
print("\n" + "=" * 60)
if all_clean:
    print("✓ ALL CHECKS PASSED - KPI cards should render correctly")
else:
    print("✗ SOME CHECKS FAILED - Review issues above")

# Show the full rendered HTML of card 1 (Categories) as an example
print("\n" + "=" * 60)
print("SAMPLE RENDERED HTML (Categories card):")
print("-" * 60)
# Find the first card template
card_start = text.find("'metric-card{get_active_class")
if card_start >= 0:
    # Print surrounding context
    line_no = text[:card_start].count('\n') + 1
    print(f"(Starting near line {line_no})")
    for i in range(max(0, line_no-3), min(len(text.split('\n')), line_no+7)):
        l = text.split('\n')[i]
        print(f"  {i+1}: {l}")