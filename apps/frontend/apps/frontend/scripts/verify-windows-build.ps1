# Windows .exe Build Verification Script
# This script verifies that the Windows build includes all necessary Python components
# and that Python imports work correctly in the packaged .exe

Write-Host "=== Windows .exe Build Verification ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if build exists
$buildPath = "dist\win-unpacked"
if (!(Test-Path $buildPath)) {
    Write-Host "❌ Build not found at: $buildPath" -ForegroundColor Red
    Write-Host "Run: npm run package:win" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Build directory exists: $buildPath" -ForegroundColor Green

# Step 2: Check Python executable
$pythonExe = "$buildPath\resources\python\python.exe"
if (!(Test-Path $pythonExe)) {
    Write-Host "❌ Python executable not found at: $pythonExe" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python executable exists: $pythonExe" -ForegroundColor Green

# Step 3: Check site-packages directory
$sitePackages = "$buildPath\resources\python\Lib\site-packages"
if (!(Test-Path $sitePackages)) {
    Write-Host "❌ site-packages directory not found at: $sitePackages" -ForegroundColor Red
    exit 1
}
Write-Host "✓ site-packages directory exists: $sitePackages" -ForegroundColor Green

# Step 4: Check if sitecustomize.py exists
$sitecustomize = "$sitePackages\sitecustomize.py"
if (!(Test-Path $sitecustomize)) {
    Write-Host "❌ sitecustomize.py not found at: $sitecustomize" -ForegroundColor Red
    exit 1
}
Write-Host "✓ sitecustomize.py exists: $sitecustomize" -ForegroundColor Green

# Step 5: Check for bundled packages
$requiredPackages = @("dotenv", "anthropic", "graphiti_core", "claude_agent_sdk")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $packagePath = "$sitePackages\$package"
    if (!(Test-Path $packagePath)) {
        $missingPackages += $package
        Write-Host "❌ Package not found: $package" -ForegroundColor Red
    } else {
        Write-Host "✓ Package exists: $package" -ForegroundColor Green
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing packages:" -ForegroundColor Red
    $missingPackages | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Note: Packages should be in: $sitePackages" -ForegroundColor Yellow
    exit 1
}

# Step 6: Test Python imports
Write-Host ""
Write-Host "Testing Python imports..." -ForegroundColor Cyan

$importTest = "import sys; import dotenv; import anthropic; print('✓ All imports successful')"
$result = & $pythonExe -c $importTest 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python import test failed:" -ForegroundColor Red
    Write-Host $result -ForegroundColor Red
    exit 1
}

Write-Host $result -ForegroundColor Green

# Step 7: Display Python sys.path
Write-Host ""
Write-Host "Python sys.path:" -ForegroundColor Cyan
& $pythonExe -c "import sys; import pprint; pprint.pprint(sys.path)"

Write-Host ""
Write-Host "=== All Verification Steps Passed ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run the .exe: dist\win-unpacked\Auto-Claude.exe" -ForegroundColor White
Write-Host "  2. Create a new task in the UI" -ForegroundColor White
Write-Host "  3. Verify Planning completes without 'Control request timeout' errors" -ForegroundColor White
Write-Host "  4. Check that spec.md is created successfully" -ForegroundColor White
