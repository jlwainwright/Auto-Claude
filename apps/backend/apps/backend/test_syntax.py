#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Compile the file to check for syntax errors
    import py_compile
    py_compile.compile('security/output_validation/custom_rules.py', doraise=True)
    print("✓ Syntax is valid")

    # Try to import it
    from security.output_validation import custom_rules
    print("✓ Module imported successfully")

except SyntaxError as e:
    print(f"✗ Syntax error at line {e.lineno}:")
    print(f"  {e.msg}")
    if e.text:
        print(f"  Code: {e.text.strip()}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
