param(
    [switch]$InstallDeps,
    [switch]$BuildExe,
    [switch]$MakeInstaller
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Write-Info($message) {
    Write-Host "[INFO] $message"
}

function Write-ErrorAndExit($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
    exit 1
}

if (-not ($InstallDeps -or $BuildExe -or $MakeInstaller)) {
    $InstallDeps = $true
    $BuildExe = $true
    $MakeInstaller = $true
}

if ($InstallDeps) {
    Write-Info "Installing dependencies from requirements.txt..."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
}

if ($BuildExe) {
    Write-Info "Building standalone executable with PyInstaller..."
    if (-Not (Test-Path "main.py")) {
        Write-ErrorAndExit "main.py not found in the repository root."
    }
    python -m PyInstaller --clean --onefile --windowed --name main main.py
    if (-not (Test-Path "dist\main.exe")) {
        Write-ErrorAndExit "PyInstaller build failed; dist\main.exe not found."
    }
    Write-Info "Executable created at dist\main.exe"
}

if ($MakeInstaller) {
    Write-Info "Creating Inno Setup installer..."
    $issPath = Join-Path $root "installer.iss"
    if (-not (Test-Path $issPath)) {
        Write-ErrorAndExit "installer.iss not found in the repository root."
    }

    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $iscc) {
        Write-ErrorAndExit "Inno Setup compiler (ISCC.exe) was not found on PATH. Install Inno Setup and add ISCC.exe to PATH."
    }

    & $iscc.Path $issPath
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorAndExit "Inno Setup compilation failed with exit code $LASTEXITCODE."
    }

    Write-Info "Installer created in output\HoSK_Converter_Installer.exe"
}

Write-Info "Build/package flow complete."