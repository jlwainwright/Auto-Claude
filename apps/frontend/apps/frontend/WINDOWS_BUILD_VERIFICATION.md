# Windows .exe Build Verification

This document describes how to verify the Windows .exe build includes all necessary Python components and that the fixes for issue #630 are working correctly.

## Prerequisites

- Windows 10/11 machine
- Git (if building from source)
- Node.js 24+ (if building from source)

## Quick Verification (Pre-built .exe)

If you have a pre-built .exe from CI/CD:

1. Extract the .exe to a folder
2. Navigate to the folder in PowerShell
3. Run the verification script:
   ```powershell
   .\resources\backend\scripts\verify-windows-build.ps1
   ```

## Building and Verifying from Source

### Step 1: Build the Windows .exe

```bash
cd apps/frontend
npm install
npm run package:win
```

This will:
- Download Windows Python runtime
- Install dependencies from requirements.txt
- Bundle everything into `dist/win-unpacked/`

### Step 2: Verify Package Structure

Check that these files exist:

```
dist/win-unpacked/
├── Auto-Claude.exe
└── resources/
    ├── python/
    │   ├── python.exe
    │   ├── python312.dll
    │   └── Lib/
    │       └── site-packages/
    │           ├── sitecustomize.py         ← CRITICAL: Must exist
    │           ├── dotenv/                  ← Required packages
    │           ├── anthropic/
    │           ├── graphiti_core/
    │           └── claude_agent_sdk/
    └── backend/                             ← Python backend code
```

**Key files to verify:**

1. **`resources/python/Lib/site-packages/sitecustomize.py`**
   - This file adds the bundled packages directory to `sys.path`
   - If missing, Python won't find the bundled packages

2. **`resources/python/Lib/site-packages/` contains packages**
   - Must have: `dotenv`, `anthropic`, `graphiti_core`, `claude_agent_sdk`
   - If missing, the build didn't bundle dependencies correctly

### Step 3: Test Python Imports

Open PowerShell in `dist/win-unpacked/` and run:

```powershell
.\resources\python\python.exe -c "import dotenv; import anthropic; print('Success!')"
```

**Expected output:**
```
Success!
```

**If you get `ModuleNotFoundError`:**
- Check that `sitecustomize.py` exists
- Check that packages exist in `Lib/site-packages/`
- Run: `.\resources\python\python.exe -c "import sys; print('\n'.join(sys.path))"`
  - Should include `...\python-site-packages` in the path

### Step 4: Test Agent SDK Initialization

This tests the fix for "Control request timeout: initialize" error:

```powershell
# Use the test script created in subtask-2-3
cd ../../
node apps/frontend/scripts/test-agent-subprocess.cjs
```

**Expected output:**
- ✓ Python imports succeed
- ✓ Claude SDK client initializes within 10 seconds
- ✓ No timeout errors

**If you get timeout errors:**
- Check logs for subprocess spawn issues
- Verify stdio configuration is set correctly in agent-process.ts
- Check that all previous fixes are in place

### Step 5: End-to-End Test

1. Run the packaged .exe:
   ```powershell
   cd dist/win-unpacked
   .\Auto-Claude.exe
   ```

2. Create a new task:
   - Click "Create New Spec"
   - Enter a simple task description: "Add a hello world function"
   - Click "Create"

3. Monitor Planning phase:
   - Watch for "COMPLEXITY ASSESSMENT" phase
   - Watch for "SPEC DOCUMENT CREATION" phase
   - **Critical:** These should complete without timeout errors

4. Verify success:
   - Check that `.auto-claude/specs/001-*/spec.md` was created
   - Check Application logs for any errors
   - No "Control request timeout: initialize" errors should appear

### Step 6: Test Additional Features

**Insights:**
1. Open Insights tab
2. Wait for analysis to complete
3. Verify insights are displayed without errors

**Context Refresh:**
1. Open Context/Project Structure view
2. Click refresh button
3. Verify context updates successfully

## Automated Verification Script

Run the PowerShell verification script:

```powershell
cd apps/frontend
.\scripts\verify-windows-build.ps1
```

This script checks:
- ✓ Build directory exists
- ✓ Python executable exists
- ✓ site-packages directory exists
- ✓ sitecustomize.py exists
- ✓ Required packages are bundled
- ✓ Python imports work correctly
- ✓ sys.path includes bundled packages

## Common Issues

### Issue 1: ModuleNotFoundError for dotenv/anthropic

**Symptom:** `ModuleNotFoundError: No module named 'dotenv'`

**Cause:** Packages not bundled correctly or sitecustomize.py missing

**Fix:**
1. Check that `sitecustomize.py` exists in `Lib/site-packages/`
2. Verify packages exist in `Lib/site-packages/`
3. Rebuild with: `npm run package:win`

### Issue 2: Control request timeout: initialize

**Symptom:** Planning phase fails with timeout error after 60 seconds

**Cause:** Agent subprocess stdio not configured correctly

**Fix:**
1. Verify `agent-process.ts` has `stdio: 'pipe'` configuration
2. Verify `windowsHide: true` is set
3. Check logs for subprocess spawn errors
4. Rebuild with latest changes

### Issue 3: Empty site-packages directory

**Symptom:** `Lib/site-packages/` exists but has no packages

**Cause:** Python download script didn't install dependencies

**Fix:**
1. Delete `python-runtime/win-x64/` directory
2. Run: `npm run python:download --platform win32 --arch x64`
3. Verify packages are installed
4. Rebuild

## Success Criteria

All of these must pass:

- [x] Windows .exe builds without errors
- [x] Python executable is bundled
- [x] sitecustomize.py exists in Lib/site-packages/
- [x] All required packages are bundled (dotenv, anthropic, graphiti_core, claude_agent_sdk)
- [x] Python imports work: `import dotenv; import anthropic`
- [x] Agent subprocess initializes without timeout
- [x] Planning phase completes and creates spec.md
- [x] Insights feature works without errors
- [x] Context refresh works without errors
- [x] No regressions in other features

## Reporting Issues

If verification fails, include:

1. Error messages (exact text)
2. Screenshots of errors
3. Output of verification script
4. Python sys.path output:
   ```powershell
   .\resources\python\python.exe -c "import sys; print('\n'.join(sys.path))"
   ```
5. Contents of `Lib/site-packages/` directory:
   ```powershell
   dir resources\python\Lib\site-packages\
   ```
