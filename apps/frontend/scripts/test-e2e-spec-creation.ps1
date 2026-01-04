#!/usr/bin/env pwsh
# E2E Spec Creation Test Automation
#
# This script helps automate parts of the E2E spec creation test for subtask-3-2.
# It performs pre-flight checks and post-test verification.
#
# Usage:
#   .\scripts\test-e2e-spec-creation.ps1 -Phase pretest    # Run before manual test
#   .\scripts\test-e2e-spec-creation.ps1 -Phase posttest   # Run after manual test

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("pretest", "posttest")]
    [string]$Phase,

    [Parameter(Mandatory=$false)]
    [string]$BuildPath = "dist\win-unpacked"
)

$ErrorActionPreference = "Continue"

function Write-TestResult {
    param([string]$Message, [bool]$Success)
    if ($Success) {
        Write-Host "✓ " -ForegroundColor Green -NoNewline
        Write-Host $Message
    } else {
        Write-Host "✗ " -ForegroundColor Red -NoNewline
        Write-Host $Message
    }
}

function Test-PreFlightChecks {
    Write-Host "`n=== PRE-TEST CHECKS ===" -ForegroundColor Cyan
    Write-Host "Verifying build is ready for E2E testing...`n"

    $allPassed = $true

    # Check 1: Build directory exists
    if (Test-Path $BuildPath) {
        Write-TestResult "Build directory exists: $BuildPath" $true
    } else {
        Write-TestResult "Build directory not found: $BuildPath" $false
        $allPassed = $false
        Write-Host "   → Run: npm run package:win" -ForegroundColor Yellow
        return $false
    }

    # Check 2: Auto-Claude.exe exists
    $exePath = Join-Path $BuildPath "Auto-Claude.exe"
    if (Test-Path $exePath) {
        Write-TestResult "Auto-Claude.exe exists" $true
    } else {
        Write-TestResult "Auto-Claude.exe not found" $false
        $allPassed = $false
    }

    # Check 3: Python executable exists
    $pythonPath = Join-Path $BuildPath "resources\python\python.exe"
    if (Test-Path $pythonPath) {
        Write-TestResult "Python executable exists" $true

        # Get Python version
        $pythonVersion = & $pythonPath --version 2>&1
        Write-Host "   Python version: $pythonVersion" -ForegroundColor Gray
    } else {
        Write-TestResult "Python executable not found" $false
        $allPassed = $false
    }

    # Check 4: sitecustomize.py exists
    $sitecustomizePath = Join-Path $BuildPath "resources\python\Lib\site-packages\sitecustomize.py"
    if (Test-Path $sitecustomizePath) {
        Write-TestResult "sitecustomize.py exists" $true
    } else {
        Write-TestResult "sitecustomize.py not found (CRITICAL)" $false
        $allPassed = $false
        Write-Host "   → This file is required for Python package discovery" -ForegroundColor Yellow
    }

    # Check 5: Required packages exist
    $packagesPath = Join-Path $BuildPath "resources\python\Lib\site-packages"
    $requiredPackages = @("dotenv", "anthropic", "graphiti_core", "claude_agent_sdk")

    Write-Host "`nChecking bundled packages..." -ForegroundColor Gray
    foreach ($pkg in $requiredPackages) {
        $pkgPath = Join-Path $packagesPath $pkg
        $exists = Test-Path $pkgPath
        Write-TestResult "Package: $pkg" $exists
        if (-not $exists) {
            $allPassed = $false
        }
    }

    # Check 6: Test Python imports
    if (Test-Path $pythonPath) {
        Write-Host "`nTesting Python imports..." -ForegroundColor Gray

        $importTest = "import dotenv; import anthropic; import claude_agent_sdk; print('OK')"
        $result = & $pythonPath -c $importTest 2>&1

        if ($LASTEXITCODE -eq 0 -and $result -match "OK") {
            Write-TestResult "Python imports work correctly" $true
        } else {
            Write-TestResult "Python imports FAILED" $false
            Write-Host "   Error: $result" -ForegroundColor Red
            $allPassed = $false
        }
    }

    # Check 7: Backend files exist
    $backendPath = Join-Path $BuildPath "resources\backend"
    if (Test-Path $backendPath) {
        Write-TestResult "Backend directory exists" $true

        # Check for key backend files
        $runPyPath = Join-Path $backendPath "run.py"
        if (Test-Path $runPyPath) {
            Write-TestResult "run.py exists" $true
        } else {
            Write-TestResult "run.py not found" $false
            $allPassed = $false
        }
    } else {
        Write-TestResult "Backend directory not found" $false
        $allPassed = $false
    }

    Write-Host "`n=== PRE-TEST SUMMARY ===" -ForegroundColor Cyan
    if ($allPassed) {
        Write-Host "✓ All pre-flight checks PASSED" -ForegroundColor Green
        Write-Host "`nYou can now proceed with manual E2E testing:" -ForegroundColor Gray
        Write-Host "1. Launch: $exePath" -ForegroundColor White
        Write-Host "2. Create a new task with description: 'Add a hello world function'" -ForegroundColor White
        Write-Host "3. Wait for Planning to complete" -ForegroundColor White
        Write-Host "4. Run: .\scripts\test-e2e-spec-creation.ps1 -Phase posttest" -ForegroundColor White
        return $true
    } else {
        Write-Host "✗ Some pre-flight checks FAILED" -ForegroundColor Red
        Write-Host "`nFix the issues above before proceeding with E2E testing." -ForegroundColor Yellow
        return $false
    }
}

function Test-PostTestVerification {
    Write-Host "`n=== POST-TEST VERIFICATION ===" -ForegroundColor Cyan
    Write-Host "Verifying spec creation results...`n"

    $allPassed = $true

    # Check 1: .auto-claude directory exists
    $autoCaudeDir = ".auto-claude"
    if (Test-Path $autoCaudeDir) {
        Write-TestResult ".auto-claude directory exists" $true
    } else {
        Write-TestResult ".auto-claude directory not found" $false
        Write-Host "   → Spec creation may not have started" -ForegroundColor Yellow
        return $false
    }

    # Check 2: specs directory exists
    $specsDir = Join-Path $autoCaudeDir "specs"
    if (Test-Path $specsDir) {
        Write-TestResult "specs directory exists" $true
    } else {
        Write-TestResult "specs directory not found" $false
        $allPassed = $false
        return $false
    }

    # Check 3: Find created spec directories
    $specDirs = Get-ChildItem -Path $specsDir -Directory | Sort-Object Name

    if ($specDirs.Count -eq 0) {
        Write-TestResult "No spec directories found" $false
        Write-Host "   → Spec creation did not complete" -ForegroundColor Yellow
        $allPassed = $false
        return $false
    }

    Write-Host "`nFound $($specDirs.Count) spec(s):" -ForegroundColor Gray
    foreach ($specDir in $specDirs) {
        Write-Host "   - $($specDir.Name)" -ForegroundColor White
    }

    # Check the most recent spec directory
    $latestSpec = $specDirs | Select-Object -Last 1
    Write-Host "`nVerifying latest spec: $($latestSpec.Name)" -ForegroundColor Cyan

    # Check 4: spec.md exists
    $specMdPath = Join-Path $latestSpec.FullName "spec.md"
    if (Test-Path $specMdPath) {
        Write-TestResult "spec.md exists" $true

        # Check file size
        $fileSize = (Get-Item $specMdPath).Length
        if ($fileSize -gt 1024) {
            Write-TestResult "spec.md has content (${fileSize} bytes)" $true

            # Check for required sections
            $content = Get-Content $specMdPath -Raw
            $requiredSections = @(
                "# Specification:",
                "## Overview",
                "## Workflow Type",
                "## Requirements"
            )

            Write-Host "`nChecking spec.md sections..." -ForegroundColor Gray
            $allSectionsPresent = $true
            foreach ($section in $requiredSections) {
                $present = $content -match [regex]::Escape($section)
                Write-TestResult "Section: $section" $present
                if (-not $present) {
                    $allSectionsPresent = $false
                    $allPassed = $false
                }
            }

            if ($allSectionsPresent) {
                Write-Host "`n✓ spec.md appears to be complete" -ForegroundColor Green
            }
        } else {
            Write-TestResult "spec.md is too small (${fileSize} bytes) - may be incomplete" $false
            $allPassed = $false
        }
    } else {
        Write-TestResult "spec.md not found (CRITICAL FAILURE)" $false
        $allPassed = $false
    }

    # Check 5: Other spec files
    $otherFiles = @("requirements.json", "context.json")
    Write-Host "`nChecking additional spec files..." -ForegroundColor Gray
    foreach ($file in $otherFiles) {
        $filePath = Join-Path $latestSpec.FullName $file
        $exists = Test-Path $filePath
        Write-TestResult "File: $file" $exists
    }

    # Check 6: Look for error indicators in file names
    $errorFiles = Get-ChildItem -Path $latestSpec.FullName -Filter "*error*" -Recurse
    if ($errorFiles.Count -gt 0) {
        Write-TestResult "Found error-related files" $false
        foreach ($errFile in $errorFiles) {
            Write-Host "   - $($errFile.Name)" -ForegroundColor Red
        }
        $allPassed = $false
    }

    Write-Host "`n=== POST-TEST SUMMARY ===" -ForegroundColor Cyan
    if ($allPassed) {
        Write-Host "✓ E2E test PASSED" -ForegroundColor Green
        Write-Host "`nSpec creation completed successfully!" -ForegroundColor Green
        Write-Host "Spec location: $($latestSpec.FullName)" -ForegroundColor White
        Write-Host "`nNext steps:" -ForegroundColor Gray
        Write-Host "1. Review spec.md content" -ForegroundColor White
        Write-Host "2. Check application logs for any warnings" -ForegroundColor White
        Write-Host "3. Mark subtask-3-2 as completed" -ForegroundColor White
        Write-Host "4. Proceed to subtask-3-3 (Test Insights and Context)" -ForegroundColor White
        return $true
    } else {
        Write-Host "✗ E2E test FAILED" -ForegroundColor Red
        Write-Host "`nSome verification checks failed. Review the errors above." -ForegroundColor Yellow
        Write-Host "`nTroubleshooting steps:" -ForegroundColor Gray
        Write-Host "1. Check application logs for 'Control request timeout' errors" -ForegroundColor White
        Write-Host "2. Check for 'ModuleNotFoundError' in logs" -ForegroundColor White
        Write-Host "3. Review E2E_SPEC_CREATION_TEST.md for detailed troubleshooting" -ForegroundColor White
        Write-Host "4. Run: Get-Content ${env:APPDATA}\Auto-Claude\logs\main.log | Select-String 'error|timeout'" -ForegroundColor White
        return $false
    }
}

# Main execution
Write-Host "`n=== E2E SPEC CREATION TEST ===" -ForegroundColor Cyan
Write-Host "Phase: $Phase`n" -ForegroundColor White

if ($Phase -eq "pretest") {
    $result = Test-PreFlightChecks
    exit ($result ? 0 : 1)
} elseif ($Phase -eq "posttest") {
    $result = Test-PostTestVerification
    exit ($result ? 0 : 1)
}
