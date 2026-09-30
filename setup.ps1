# Kavach Setup Script for Windows
# Detects architecture, creates virtual environment, installs dependencies

param(
    [switch]$Dev = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== Kavach Setup ===" -ForegroundColor Cyan
Write-Host ""

# Detect the operating-system architecture separately from the PowerShell process.
try {
    $osArchitecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    $processArchitecture = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
} catch {
    $processArchitecture = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $nativeArchitecture = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
    $osArchitecture = if ($nativeArchitecture) { $nativeArchitecture } else { $processArchitecture }
}

$normalizedOsArchitecture = $osArchitecture.ToUpperInvariant()
$arch = if ($normalizedOsArchitecture -match "^ARM(64)?$") {
    "ARM64"
} elseif ($normalizedOsArchitecture -match "64$") {
    "x64"
} else {
    $osArchitecture
}
$normalizedProcessArchitecture = $processArchitecture.ToUpperInvariant()
$processArchitectureLabel = if ($normalizedProcessArchitecture -match "^ARM(64)?$") {
    "ARM64"
} elseif ($normalizedProcessArchitecture -match "64$") {
    "x64"
} else {
    $processArchitecture
}
Write-Host "Detected Windows architecture: $arch" -ForegroundColor Green
Write-Host "PowerShell process architecture: $processArchitectureLabel" -ForegroundColor Gray

if ($arch -ne "x64" -and $arch -ne "ARM64") {
    Write-Host "Error: Unsupported architecture '$arch'. Expected x64 or ARM64." -ForegroundColor Red
    exit 1
}
if ($arch -eq "ARM64") {
    Write-Host "ARM64/Snapdragon compatibility is unverified; package installation may not be available." -ForegroundColor Yellow
}

# Check Python version
Write-Host ""
Write-Host "Checking Python..." -ForegroundColor Cyan
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python 3.11, 3.12, or 3.13 is required." -ForegroundColor Red
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green
$pythonArchitecture = python -c "import platform; print(platform.machine())"
Write-Host "Python architecture: $pythonArchitecture" -ForegroundColor Green

# Parse version
$versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)"
if ($versionMatch) {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    
    if ($major -ne 3 -or $minor -lt 11 -or $minor -ge 14) {
        Write-Host "Error: Python 3.11, 3.12, or 3.13 is required. Found: $pythonVersion" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Warning: Could not parse Python version." -ForegroundColor Yellow
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
if (Test-Path ".venv") {
    Write-Host "Virtual environment already exists." -ForegroundColor Yellow
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Host "Error: Activation script not found at $activateScript" -ForegroundColor Red
    exit 1
}
& $activateScript

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Cyan
if ($Dev) {
    Write-Host "Installing with development and ingestion dependencies..." -ForegroundColor Cyan
    pip install -e ".[dev,ingestion]"
} else {
    Write-Host "Installing with ingestion dependencies..." -ForegroundColor Cyan
    pip install -e ".[ingestion]"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to install dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed." -ForegroundColor Green

# Smoke check
Write-Host ""
Write-Host "Running smoke check..." -ForegroundColor Cyan
python -c "import kavach; print(f'Kavach version: {kavach.__version__}')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Smoke check failed." -ForegroundColor Red
    exit 1
}

python -c "import fastapi, uvicorn, pydantic; print('Core dependencies OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Core dependency check failed." -ForegroundColor Red
    exit 1
}

Write-Host "Smoke check passed." -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Windows architecture: $arch" -ForegroundColor White
Write-Host "Python architecture: $pythonArchitecture" -ForegroundColor White
Write-Host "Python: $pythonVersion" -ForegroundColor White
Write-Host "Virtual environment: .venv" -ForegroundColor White
Write-Host ""
Write-Host "To activate the environment manually:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To run quality checks:" -ForegroundColor Cyan
Write-Host "  ruff check ." -ForegroundColor White
Write-Host "  ruff format --check ." -ForegroundColor White
Write-Host "  mypy src" -ForegroundColor White
Write-Host ""
Write-Host "To run tests:" -ForegroundColor Cyan
Write-Host "  pytest" -ForegroundColor White
Write-Host ""
