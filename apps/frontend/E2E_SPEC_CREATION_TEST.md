# E2E Spec Creation Test (Subtask 3-2)

**Purpose:** Verify that spec creation works end-to-end in the Windows .exe build without "Control request timeout: initialize" errors.

**Prerequisites:**
- Windows 10/11 machine
- Built Windows .exe (see `WINDOWS_BUILD_VERIFICATION.md` for build instructions)
- All previous fixes applied (subtasks 1-1 through 2-4)

## Test Procedure

### 1. Launch Packaged .exe

```powershell
cd dist/win-unpacked
.\Auto-Claude.exe
```

**Expected:**
- Application launches without errors
- Main window displays
- No console errors in DevTools

### 2. Create New Task with Simple Description

**Steps:**
1. Click "Create New Spec" or navigate to spec creation screen
2. Enter a simple task description:
   ```
   Add a hello world function to the project
   ```
3. Select default options (or leave settings as-is)
4. Click "Create" or "Start Planning"

**Expected:**
- Task creation UI accepts input
- Planning phase begins
- Progress indicator shows current phase

### 3. Wait for Planning to Complete

**Monitor these phases:**
- ✓ COMPLEXITY ASSESSMENT
- ✓ REQUIREMENTS GATHERING
- ✓ CODEBASE DISCOVERY (if applicable)
- ✓ CONTEXT ANALYSIS
- ✓ **SPEC DOCUMENT CREATION** ← Critical phase

**Timeline:**
- Normal Planning duration: 2-5 minutes for simple tasks
- Timeout threshold: 60 seconds per agent initialization
- If Planning hangs >5 minutes, check logs for errors

**What to watch for:**
- Each phase should complete and move to next
- No "Control request timeout: initialize" errors
- No "ModuleNotFoundError" errors
- Progress updates continuously

### 4. Verify spec.md Created in .auto-claude/specs/

**After Planning completes:**

```powershell
# Find the created spec directory (001-add-a-hello-world-function or similar)
dir .auto-claude\specs\
```

**Check for:**
1. Spec directory exists: `.auto-claude/specs/001-*` or similar
2. `spec.md` file exists in the spec directory
3. File is not empty (should be >1KB)

```powershell
# View spec.md content
type .auto-claude\specs\001-*\spec.md | more
```

**Expected spec.md sections:**
- `# Specification: [Task Name]`
- `## Overview`
- `## Workflow Type`
- `## Task Scope`
- `## Services Involved`
- `## Files to Modify`
- `## Requirements`
- `## Implementation Notes`
- `## Success Criteria`

### 5. Verify No 'Control request timeout: initialize' Errors in Logs

**Check application logs:**

**Option A: DevTools Console**
1. In Auto-Claude app, press `Ctrl+Shift+I` (open DevTools)
2. Go to Console tab
3. Search for "timeout" or "Control request"
4. Search for "ModuleNotFoundError"

**Option B: Log Files**
```powershell
# Check for log files in application directory or user data directory
# Exact path depends on Electron app configuration
dir %APPDATA%\Auto-Claude\logs\
type %APPDATA%\Auto-Claude\logs\main.log | findstr /i "timeout error"
```

**Expected:**
- ✅ NO "Control request timeout: initialize" errors
- ✅ NO "ModuleNotFoundError: No module named 'dotenv'" errors
- ✅ NO "ModuleNotFoundError: No module named 'anthropic'" errors
- ✅ NO agent subprocess spawn errors

**Acceptable logs:**
- ✓ "[Agent Timing] SDK client created in Xms"
- ✓ "[Agent Timing] First response received in Xms"
- ✓ "[SDK Timing] ClaudeSDKClient instantiated"
- ✓ Normal agent communication logs

## Success Criteria

**Test PASSES if:**
- [x] .exe launches successfully
- [x] Task creation UI is responsive
- [x] Planning completes all phases without hanging
- [x] SPEC DOCUMENT CREATION phase completes successfully
- [x] spec.md file is created in `.auto-claude/specs/XXX-*/`
- [x] spec.md contains all required sections
- [x] No "Control request timeout: initialize" errors in logs
- [x] No Python import errors (ModuleNotFoundError) in logs
- [x] Planning completes in reasonable time (<5 minutes for simple task)

**Test FAILS if:**
- [ ] Planning hangs or times out (>5 minutes)
- [ ] "Control request timeout: initialize" error appears
- [ ] "ModuleNotFoundError" for dotenv, anthropic, or other packages
- [ ] spec.md is not created
- [ ] spec.md is empty or malformed
- [ ] Application crashes during Planning

## Additional Verification (Optional)

If time permits, also verify:

### Test Insights Feature
1. Navigate to Insights tab
2. Wait for analysis to complete
3. Verify insights populate without errors
4. Check logs for no Python import errors

### Test Context Refresh
1. Navigate to Context/Project Structure view
2. Click refresh button
3. Verify context updates successfully
4. Check logs for no errors

## Troubleshooting

### If Planning Hangs

1. Check DevTools console for errors
2. Look for subprocess spawn errors
3. Verify Python executable exists:
   ```powershell
   .\resources\python\python.exe --version
   ```
4. Test Python imports manually:
   ```powershell
   .\resources\python\python.exe -c "import dotenv; import anthropic; import claude_agent_sdk; print('OK')"
   ```

### If spec.md Not Created

1. Check application logs for errors during SPEC DOCUMENT CREATION phase
2. Verify file permissions on `.auto-claude/specs/` directory
3. Check disk space availability
4. Look for backend Python errors in logs

### If Timeout Errors Appear

1. This indicates the fixes from subtask-2-4 may not be working
2. Verify `agent-process.ts` has `stdio: 'pipe'` configuration
3. Check that `windowsHide: true` is set
4. Review subprocess spawn logs for details

## Reporting Results

**When reporting test results, include:**

1. **Test outcome:** PASS or FAIL
2. **Screenshots:**
   - Planning in progress (showing phases)
   - Planning completed (or error state)
   - spec.md file in file explorer
   - DevTools console (any errors)
3. **Logs:**
   - Full console log output (copy/paste or screenshot)
   - Any error messages (exact text)
4. **Timing:**
   - How long Planning took (start to finish)
   - Which phase it failed on (if applicable)
5. **Environment:**
   - Windows version (10/11)
   - Build version of Auto-Claude
   - Python version (from `.\resources\python\python.exe --version`)

## Platform Limitation Note

**IMPORTANT:** This test requires a Windows environment to execute. The fixes were developed on macOS but cannot be fully verified on macOS because:

- macOS cannot execute Windows .exe files
- Electron Builder requires Windows for Windows .exe builds
- The bug is specific to Windows .exe packaging (Git version works on all platforms)

**For developers on macOS/Linux:**
- All code changes are complete and committed
- Configuration is verified to be correct
- Testing must be completed on Windows or Windows CI/CD
- See `WINDOWS_BUILD_VERIFICATION.md` for complete verification guide

## Next Steps After Testing

**If test PASSES:**
- Mark subtask-3-2 as completed in implementation_plan.json
- Update build-progress.txt with test results
- Proceed to subtask-3-3 (Test Insights and Context features)
- Prepare for final QA sign-off

**If test FAILS:**
- Document failure details (error messages, logs, screenshots)
- Create investigation subtask to diagnose root cause
- Review logs for clues (agent timing logs, subprocess spawn logs)
- May need to adjust timeout values or subprocess configuration
- Consult with team for Windows-specific debugging tools
