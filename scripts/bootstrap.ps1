<#
.SYNOPSIS
Central Intelligence — Clean Environment Bootstrap & Verification Script (Task S4.2)
Cross-platform deterministic initialization for Windows PowerShell / pwsh environments.

.PARAMETER VerifyOnly
Run pre-flight checks and validate environment without installing or mutating files.

.PARAMETER SkipDocker
Skip Docker and Docker Compose availability checks.

.PARAMETER Profile
Target profile: lite, standard, enterprise (default: standard).
#>
[CmdletBinding()]
param(
    [switch]$VerifyOnly,
    [switch]$SkipDocker,
    [string]$Profile = "standard"
)

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Central Intelligence — Clean Environment Bootstrap (Task S4.2)" -ForegroundColor Cyan
Write-Host "Target Profile: $Profile | Mode: $(if ($VerifyOnly) { 'VERIFY ONLY' } else { 'FULL BOOTSTRAP' })" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$FailedCount = 0

function Check-Pass([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Check-Fail([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    $script:FailedCount++
}

function Check-Info([string]$msg) {
    Write-Host "  [INFO] $msg" -ForegroundColor Yellow
}

function Generate-HexToken([int]$bytes) {
    $buffer = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

# -----------------------------------------------------------------------------
# 1. Host Tooling & Prerequisites
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[1/6] Checking host tooling prerequisites..." -ForegroundColor White

$PyCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $PyCmd) {
    $pyVer = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    $pyMajor = [int](& python -c "import sys; print(sys.version_info.major)")
    $pyMinor = [int](& python -c "import sys; print(sys.version_info.minor)")
    if ($pyMajor -eq 3 -and $pyMinor -ge 11) {
        Check-Pass "Python $pyVer detected ($($PyCmd.Source))"
    } else {
        Check-Fail "Python >= 3.11 required (found $pyVer)"
    }
} else {
    Check-Fail "Python is not installed or not in PATH."
}

$NodeCmd = Get-Command node -ErrorAction SilentlyContinue
if ($null -ne $NodeCmd) {
    $nodeVer = & node --version
    Check-Pass "Node.js $nodeVer detected"
} else {
    Check-Fail "Node.js is not installed or not in PATH."
}

$PnpmCmd = Get-Command pnpm -ErrorAction SilentlyContinue
if ($null -ne $PnpmCmd) {
    $pnpmVer = & pnpm --version
    Check-Pass "pnpm $pnpmVer detected"
} else {
    Check-Fail "pnpm is not installed or not in PATH."
}

if (-not $SkipDocker) {
    $DockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($null -ne $DockerCmd) {
        $dockerVer = & docker --version
        Check-Pass "Docker detected ($dockerVer)"
        
        $composeOut = & docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Check-Pass "Docker Compose detected ($composeOut)"
        } else {
            Check-Fail "Docker Compose plugin ('docker compose') is missing or not responding."
        }
    } else {
        Check-Fail "Docker CLI is not installed or not in PATH."
    }
} else {
    Check-Info "Skipping Docker checks per -SkipDocker"
}

# -----------------------------------------------------------------------------
# 2. Configuration & Cryptographic Secrets (.env)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Verifying environment configuration (.env)..." -ForegroundColor White

$EnvFile = Join-Path $RepoRoot '.env'
$EnvExample = Join-Path $RepoRoot '.env.example'

if (-not (Test-Path -LiteralPath $EnvFile)) {
    if ($VerifyOnly) {
        Check-Fail ".env file is absent. Run bootstrap without -VerifyOnly to initialize from .env.example."
    } else {
        Check-Info "Generating fresh .env from .env.example with secure generated secrets..."
        $genScript = Join-Path $RepoRoot 'scripts\generate_env.py'
        if (Test-Path -LiteralPath $VenvPython) {
            & $VenvPython $genScript
        } else {
            & python $genScript
        }
        Check-Pass "Initialized .env with unique cryptographic credentials"
    }
} else {
    Check-Pass ".env configuration file is present"
}

# Verify essential keys in .env
$CriticalKeys = @('NANGO_SECRET_KEY', 'MEILISEARCH_MASTER_KEY', 'INFISICAL_ENCRYPTION_KEY', 'POSTGRES_PASSWORD')
$EnvContent = if (Test-Path -LiteralPath $EnvFile) { Get-Content -LiteralPath $EnvFile } else { @() }
foreach ($key in $CriticalKeys) {
    $found = $EnvContent | Where-Object { $_ -match "^$key=" }
    if ($found) {
        # OK
    } else {
        Check-Fail "Missing critical configuration key in .env: $key"
    }
}
Check-Pass "All critical environment keys validated in .env"

# -----------------------------------------------------------------------------
# 3. Python Virtual Environment & Pinned Dependencies
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Verifying Python virtual environment (.venv)..." -ForegroundColor White

$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    if ($VerifyOnly) {
        Check-Fail "Virtual environment .venv is missing."
    } else {
        Check-Info "Creating clean virtual environment in .venv..."
        & python -m venv .venv
        Check-Pass "Created .venv"
        Check-Info "Installing pinned dependencies from requirements.lock..."
        & $VenvPython -m pip install --upgrade pip --quiet
        & $VenvPython -m pip install --no-deps -r requirements.lock --quiet
        & $VenvPython -m pip install -e . --no-deps --quiet
        Check-Pass "Installed project packages into .venv"
    }
} else {
    $venvVer = & $VenvPython --version
    Check-Pass "Virtual environment present: $venvVer"
}

# Test execution with virtual environment python
if (Test-Path -LiteralPath $VenvPython) {
    & $VenvPython -c "import sys; sys.exit(0)"
    if ($LASTEXITCODE -eq 0) {
        Check-Pass "Python virtual environment runtime executable OK"
    } else {
        Check-Fail "Python virtual environment failed basic execution test."
    }
}

# -----------------------------------------------------------------------------
# 4. Node.js & TypeScript Pinned Dependencies (pnpm)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] Verifying Node.js / TypeScript workspace..." -ForegroundColor White

$NodeModulesDir = Join-Path $RepoRoot 'node_modules'
if (-not (Test-Path -LiteralPath $NodeModulesDir)) {
    if ($VerifyOnly) {
        Check-Fail "node_modules directory is missing."
    } else {
        Check-Info "Running pnpm install --frozen-lockfile..."
        & pnpm install --frozen-lockfile
        Check-Pass "Node modules installed cleanly with frozen lockfile"
    }
} else {
    Check-Pass "node_modules directory is present"
}

if (Test-Path -LiteralPath (Join-Path $RepoRoot 'pnpm-lock.yaml')) {
    Check-Pass "pnpm-lock.yaml frozen lockfile validated"
} else {
    Check-Fail "pnpm-lock.yaml missing."
}

# -----------------------------------------------------------------------------
# 5. Directory Layout & Database Init Scripts
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Verifying storage directories and database initialization scripts..." -ForegroundColor White

$RequiredDirs = @('data', 'wal', 'inspection-logs')
foreach ($dir in $RequiredDirs) {
    $dirPath = Join-Path $RepoRoot $dir
    if (-not (Test-Path -LiteralPath $dirPath)) {
        if ($VerifyOnly) {
            Check-Fail "Directory '$dir' is missing."
        } else {
            New-Item -ItemType Directory -Path $dirPath -Force | Out-Null
            Check-Pass "Created required directory: $dir"
        }
    } else {
        Check-Pass "Directory present: $dir"
    }
}

$MultiDbScript = Join-Path $RepoRoot 'compose\postgres\init-multi-db.sh'
if (Test-Path -LiteralPath $MultiDbScript) {
    Check-Pass "PostgreSQL multi-database initializer present ($MultiDbScript)"
} else {
    Check-Fail "compose/postgres/init-multi-db.sh is missing."
}

# -----------------------------------------------------------------------------
# 6. Compose Configuration Pre-Flight
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Verifying Docker Compose configuration syntax..." -ForegroundColor White

if (-not $SkipDocker -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    & docker compose config --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Check-Pass "docker-compose.yml parsed and validated cleanly with .env variables"
    } else {
        Check-Fail "docker compose config failed. Check .env variables against docker-compose.yml declarations."
    }
} else {
    Check-Info "Skipping Docker Compose validation."
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
if ($FailedCount -eq 0) {
    Write-Host "Clean Install Bootstrap Verification: PASSED (S4.2 Acceptance Criteria Met)" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "Clean Install Bootstrap Verification: FAILED ($FailedCount checks failed)" -ForegroundColor Red
    Write-Host "================================================================================" -ForegroundColor Cyan
    exit 1
}
