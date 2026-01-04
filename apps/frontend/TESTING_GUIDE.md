# Windows .exe Testing Guide

This directory contains comprehensive testing documentation and scripts for verifying the Windows .exe build fixes for issue #630 (Planning timeout errors).

## Quick Start

### For Windows Testers

**Complete verification workflow:**

1. **Pre-build verification** (optional if using pre-built .exe):
   ```bash
   npm run package:win
   ```

2. **Pre-test checks**:
   ```powershell
   cd apps/frontend
   .\scripts\test-e2e-spec-creation.ps1 -Phase pretest
   ```

3. **Manual E2E testing** (follow detailed guide):
   - See `E2E_SPEC_CREATION_TEST.md` for step-by-step instructions
   - Or run through the automated test flow below

4. **Post-test verification**:
   ```powershell
   .\scripts\test-e2e-spec-creation.ps1 -Phase posttest
   ```

### For Developers (macOS/Linux)

**Platform limitation:** Windows .exe files cannot be tested on macOS/Linux.

**What you can do:**
- Review test documentation for completeness
- Verify code changes are in place
- Run pre-build checks (e.g., verify-python-bundling.cjs)
- Coordinate with Windows testers for actual .exe verification

## Documentation Index

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **WINDOWS_BUILD_VERIFICATION.md** | Complete build and verification guide | First-time build verification, troubleshooting package structure |
| **E2E_SPEC_CREATION_TEST.md** | Detailed E2E test procedure for spec creation | Manual testing, detailed verification steps, troubleshooting |
| **TESTING_GUIDE.md** (this file) | Overview and quick start guide | Quick reference, workflow overview |

## Script Index

| Script | Purpose | Usage |
|--------|---------|-------|
| **verify-windows-build.ps1** | Automated build structure verification | `.\scripts\verify-windows-build.ps1` |
| **test-e2e-spec-creation.ps1** | Pre/post-test automation for E2E testing | `.\scripts\test-e2e-spec-creation.ps1 -Phase [pretest\|posttest]` |
| **test-agent-subprocess.cjs** | Minimal reproducible test for agent subprocess | `node scripts\test-agent-subprocess.cjs` |
| **verify-python-bundling.cjs** | Python bundling verification (cross-platform) | `node scripts\verify-python-bundling.cjs` |

## Testing Phases Overview

### Phase 1: Python Path Fix ✓
**Status:** Complete (subtasks 1-1 through 1-4)

**What was fixed:**
- package.json extraResources now bundles to `python/Lib/site-packages` (correct path)
- sitecustomize.py generated and bundled to inject packages into sys.path
- Python imports (dotenv, anthropic, graphiti_core, claude_agent_sdk) now work

**How to verify:**
```powershell
.\resources\python\python.exe -c "import dotenv; import anthropic; print('OK')"
```

### Phase 2: Agent Timeout Investigation ✓
**Status:** Complete (subtasks 2-1 through 2-4)

**What was fixed:**
- Added comprehensive logging to track agent initialization timing
- Fixed subprocess spawn configuration (stdio: 'pipe', windowsHide: true)
- Created diagnostic tools for debugging timeout issues

**How to verify:**
```powershell
node scripts\test-agent-subprocess.cjs
```

### Phase 3: Integration Testing
**Status:** In Progress

| Subtask | Status | Document |
|---------|--------|----------|
| 3-1: Build verification | ✓ Complete | WINDOWS_BUILD_VERIFICATION.md |
| 3-2: E2E spec creation test | 🔄 Current | E2E_SPEC_CREATION_TEST.md |
| 3-3: Insights/Context test | ⏳ Pending | (See WINDOWS_BUILD_VERIFICATION.md Step 6) |
| 3-4: Git version regression test | ⏳ Pending | (Run in dev mode: npm run dev) |

## Common Test Scenarios

### Scenario 1: First-Time Build Verification

**Goal:** Verify the build includes all fixes and is ready for testing.

**Steps:**
1. Build: `npm run package:win`
2. Verify structure: `.\scripts\verify-windows-build.ps1`
3. Check Python imports:
   ```powershell
   cd dist\win-unpacked
   .\resources\python\python.exe -c "import dotenv; import anthropic; print('OK')"
   ```

**Expected:** All checks pass, "OK" printed.

### Scenario 2: E2E Spec Creation (Primary Test)

**Goal:** Verify Planning completes without timeout errors.

**Steps:**
1. Pre-test: `.\scripts\test-e2e-spec-creation.ps1 -Phase pretest`
2. Manual test:
   - Launch `dist\win-unpacked\Auto-Claude.exe`
   - Create task: "Add a hello world function"
   - Wait for Planning to complete
3. Post-test: `.\scripts\test-e2e-spec-creation.ps1 -Phase posttest`

**Expected:** spec.md created, no timeout errors, post-test verification passes.

### Scenario 3: Troubleshooting Timeout Issues

**Goal:** Diagnose why Planning is timing out.

**Steps:**
1. Run diagnostic: `node scripts\test-agent-subprocess.cjs`
2. Check application logs (DevTools → Console)
3. Search for errors:
   ```powershell
   Get-Content $env:APPDATA\Auto-Claude\logs\main.log | Select-String "timeout|error|ModuleNotFoundError"
   ```
4. Verify Python environment:
   ```powershell
   .\resources\python\python.exe -c "import sys; print('\n'.join(sys.path))"
   ```

**Look for:**
- Agent timing logs: `[Agent Timing]`, `[SDK Timing]`
- Subprocess spawn logs
- Python import errors

### Scenario 4: Regression Testing (Git Version)

**Goal:** Ensure fixes don't break the Git/development version.

**Steps:**
1. Start dev mode: `npm run dev`
2. Create a test task
3. Verify Planning completes
4. Verify all features work

**Expected:** No regressions, all features work as before.

## Success Criteria Summary

**The Windows .exe build is considered fixed when:**

- [x] Python imports work (dotenv, anthropic, graphiti_core, claude_agent_sdk)
- [ ] **Agent subprocess initializes without timeout (PRIMARY TEST)**
- [ ] spec.md successfully created during Planning
- [ ] No "Control request timeout: initialize" errors
- [ ] Insights feature works without errors
- [ ] Context refresh works without errors
- [ ] Git/development version has no regressions

## Reporting Test Results

### If Tests Pass ✓

1. Update implementation_plan.json:
   ```json
   "status": "completed"
   ```

2. Update build-progress.txt with test results

3. Prepare for QA sign-off

### If Tests Fail ✗

**Include in bug report:**
1. **Error messages** (exact text from logs)
2. **Screenshots**:
   - Error dialogs
   - DevTools console
   - Planning progress (what phase failed)
3. **Environment**:
   - Windows version
   - Auto-Claude build version
   - Python version
4. **Diagnostic output**:
   ```powershell
   # Python imports test
   .\resources\python\python.exe -c "import dotenv; import anthropic; print('OK')"

   # Python sys.path
   .\resources\python\python.exe -c "import sys; print('\n'.join(sys.path))"

   # Site-packages contents
   dir resources\python\Lib\site-packages\
   ```
5. **Timing information**:
   - How long Planning ran before timeout
   - Which phase failed

## Platform Limitations

**IMPORTANT:** These tests require a Windows environment.

**macOS/Linux developers:**
- ✓ Can review and improve test documentation
- ✓ Can verify code changes are correct
- ✓ Can run Python bundling verification (cross-platform)
- ✗ **Cannot execute Windows .exe files**
- ✗ **Cannot run full E2E tests**

**Solution:** Use Windows VM, Windows CI/CD, or coordinate with Windows testers.

## CI/CD Integration

**For automated testing in CI/CD:**

```yaml
# Example GitHub Actions workflow
- name: Build Windows .exe
  run: npm run package:win

- name: Verify build structure
  run: |
    cd apps/frontend
    .\scripts\verify-windows-build.ps1

- name: Test Python imports
  run: |
    cd dist/win-unpacked
    .\resources\python\python.exe -c "import dotenv; import anthropic; print('OK')"

# Note: Full E2E testing requires UI automation (Playwright, Puppeteer, etc.)
```

## Next Steps

1. **Complete subtask-3-2** (E2E spec creation test)
   - Follow `E2E_SPEC_CREATION_TEST.md`
   - Use automation scripts for pre/post verification

2. **Complete subtask-3-3** (Insights and Context testing)
   - See `WINDOWS_BUILD_VERIFICATION.md` Step 6

3. **Complete subtask-3-4** (Git version regression test)
   - Run in dev mode, verify no regressions

4. **QA sign-off**
   - All tests pass
   - Documentation complete
   - Ready for release

## Getting Help

**If you encounter issues:**

1. Check **E2E_SPEC_CREATION_TEST.md** Troubleshooting section
2. Check **WINDOWS_BUILD_VERIFICATION.md** Common Issues section
3. Run diagnostic scripts:
   - `.\scripts\verify-windows-build.ps1`
   - `node scripts\test-agent-subprocess.cjs`
4. Review application logs (DevTools Console or log files)
5. Report issue with detailed diagnostics (see Reporting Test Results above)
