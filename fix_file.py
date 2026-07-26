import subprocess

# Get committed version from git
result = subprocess.run(['git', '--no-pager', 'show', 'HEAD:enterprise/enterprise_dashboard.py'], 
                       capture_output=True)
committed_text = result.stdout.decode('utf-8', errors='replace')
committed_lines = committed_text.split('\n')

# Read the current file (has my changes in first section)
with open('enterprise/enterprise_dashboard.py', 'rb') as f:
    data = f.read()
data = data.replace(b'\x00', b'')
current_text = data.decode('utf-8', errors='replace')

# Find the boundary: my new code ends at the MACHINES PAGE section
# In the committed version, render_dashboard ends at line 478
# After that comes "# ==================== MACHINES PAGE ==="
# In my new code, I have the same structure but with the KPI card changes

# Find the first occurrence of MACHINES PAGE in current file
idx = current_text.find('# ==================== MACHINES PAGE ====================')
if idx >= 0:
    # Take everything up to and including the MACHINES PAGE header
    # Then append from committed version starting from the same section
    my_new_code = current_text[:idx]
    
    # Find the same section in committed version
    committed_idx = committed_text.find('# ==================== MACHINES PAGE ====================')
    if committed_idx >= 0:
        rest_from_committed = committed_text[committed_idx:]
        
        # Combine: my new code + rest from committed
        final_text = my_new_code + rest_from_committed
        
        with open('enterprise/enterprise_dashboard.py', 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"Combined file written: {len(final_text)} chars, {final_text.count(chr(10))} lines")
        
        # Verify it compiles
        import py_compile
        try:
            py_compile.compile('enterprise/enterprise_dashboard.py', doraise=True)
            print("File compiles successfully!")
        except py_compile.PyCompileError as e:
            print(f"Compile error: {e}")
    else:
        print("Could not find MACHINES PAGE in committed version")
else:
    print("Could not find MACHINES PAGE in current file")