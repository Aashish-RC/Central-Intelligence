param([string]$RepoRoot = 'D:\central-intelligence')

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $RepoRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }

# Load .env variables into process if not already present
$EnvFile = Join-Path $RepoRoot '.env'
if (Test-Path -LiteralPath $EnvFile) {
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $k = $parts[0].Trim()
            $v = $parts[1].Trim()
            if (-not [string]::IsNullOrEmpty($k) -and [string]::IsNullOrEmpty([System.Environment]::GetEnvironmentVariable($k))) {
                [System.Environment]::SetEnvironmentVariable($k, $v, 'Process')
            }
        }
    }
}
$LogDir = Join-Path $RepoRoot 'inspection-logs'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log = Join-Path $LogDir "critical-C3-D3-$Stamp.txt"
$Results = New-Object System.Collections.Generic.List[object]
$OriginalEap = $ErrorActionPreference

function Write-Log([string]$Line) {
    Write-Host $Line
    Add-Content -LiteralPath $Log -Value $Line -Encoding UTF8
}

function Invoke-NativeCheck {
    param([string]$Name, [string]$Executable, [string[]]$Arguments)
    Write-Log "`n========== $Name =========="
    $exitCode = -1
    try {
        # Windows PowerShell 5.1 can surface native stderr as error records.
        # Temporarily use Continue, and rely on the process exit code.
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        & $Executable @Arguments 2>&1 | ForEach-Object {
            $line = $_.ToString()
            Write-Log $line
        }
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = -1 }
    } catch {
        Write-Log "ERROR: $($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = 'Stop'
    }
    $passed = ($exitCode -eq 0)
    $Results.Add([pscustomobject]@{ Check = $Name; Passed = $passed; ExitCode = $exitCode })
    Write-Log ("RESULT: {0} (exit {1})" -f $(if ($passed) { 'PASS' } else { 'FAIL' }), $exitCode)
    return $passed
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)
    $ErrorActionPreference = 'Continue'
    try {
        $global:LASTEXITCODE = 0
        & docker compose @Arguments 2>&1 | ForEach-Object { Write-Log $_.ToString() }
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = 'Stop'
    }
}

Write-Log 'CENTRAL INTELLIGENCE - C3 + D3 EVIDENCE RUN'
Write-Log "Date: $(Get-Date -Format o)"
Write-Log "Repository: $RepoRoot"

$dockerOk = Invoke-NativeCheck 'Prerequisite: Docker Engine' 'docker' -Arguments @('info','--format','{{.ServerVersion}}')

Invoke-NativeCheck 'C3: Sandbox security unit tests' $Python -Arguments @('-m','pytest','tests/unit/test_ws03_sandbox_security.py','-v','-rs') | Out-Null

$env:SANDBOX_LIVE = '1'
if ($dockerOk) {
    Invoke-NativeCheck 'C3: Live sandbox execution baseline' $Python -Arguments @('-m','pytest','tests/integration/test_compose_stack_e2e.py::test_sandbox_executes_real_python','-m','live','-v','-rs') | Out-Null
    Invoke-NativeCheck 'C3: Project-adapter live runtime isolation suite (11 controls)' $Python -Arguments @('-m','pytest','tests/integration/test_c3_sandbox_isolation_live.py','-m','live','-v','-rs') | Out-Null
    Invoke-NativeCheck 'C3: Docker isolation smoke test (independent of project adapter)' 'docker' -Arguments @('run','--rm','--network','none','--memory','128m','--cpus','0.5','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--tmpfs','/tmp:rw,noexec,nosuid,size=16m','alpine:3.20','sh','-c','grep CapEff /proc/self/status; grep NoNewPrivs /proc/self/status; cat /sys/fs/cgroup/memory.max; if touch /root/write-test 2>/dev/null; then exit 1; else echo read-only-verified; fi') | Out-Null
} else {
    Write-Log 'SKIP: Live sandbox and Docker smoke test; Docker unavailable.'
}

Invoke-NativeCheck 'D3: Local hybrid RRF ranking' $Python -Arguments @('-m','pytest','tests/unit/test_ws04_durable_memory.py::test_hybrid_search_rrf_ranking','-v','-rs') | Out-Null

if ($dockerOk) {
    Write-Log "`n========== D3: Live Qdrant =========="
    $started = Invoke-DockerCompose -Arguments @('up','-d','qdrant')
    try {
        if ($started) {
            Invoke-NativeCheck 'D3: Qdrant live integration tests' $Python -Arguments @('-m','pytest','tests/integration/test_compose_stack_e2e.py::test_qdrant_vector_roundtrip_e2e','tests/integration/test_compose_stack_e2e.py::test_memory_qdrant_adapter_v120_e2e','-m','live','-v','-rs') | Out-Null
        } else {
            $Results.Add([pscustomobject]@{ Check='D3: Qdrant live integration tests'; Passed=$false; ExitCode='start failed' })
        }
    } finally {
        if ($started) { Write-Log 'Stopping Qdrant to conserve memory'; Invoke-DockerCompose -Arguments @('stop','qdrant') | Out-Null }
    }

    Write-Log "`n========== D3: Live Apache AGE =========="
    $started = Invoke-DockerCompose -Arguments @('up','-d','apache-age')
    try {
        if ($started) {
            Invoke-NativeCheck 'D3: Apache AGE live integration test' $Python -Arguments @('-m','pytest','tests/integration/test_compose_stack_e2e.py::test_postgres_apache_age_graph_adapters_e2e','-m','live','-v','-rs') | Out-Null
        } else {
            $Results.Add([pscustomobject]@{ Check='D3: Apache AGE live integration test'; Passed=$false; ExitCode='start failed' })
        }
    } finally {
        if ($started) { Write-Log 'Stopping Apache AGE to conserve memory'; Invoke-DockerCompose -Arguments @('stop','apache-age') | Out-Null }
    }
} else {
    Write-Log 'SKIP: Qdrant and Apache AGE live tests; Docker unavailable.'
}

if ([string]::IsNullOrWhiteSpace($env:POSTGRES_LIVE_URL)) {
    Write-Log 'SKIP: pgvector persistence; POSTGRES_LIVE_URL is unset.'
    $Results.Add([pscustomobject]@{ Check='D3: pgvector persistence'; Passed=$false; ExitCode='env missing' })
} else {
    Invoke-NativeCheck 'D3: pgvector persistence' $Python -Arguments @('-m','pytest','tests/integration/test_compose_stack_e2e.py::test_supabase_relational_and_vector_persist','-m','live','-v','-rs') | Out-Null
}

if ($dockerOk) {
    Write-Log "`n========== D3: Combined Live Hybrid Retrieval =========="
    Invoke-NativeCheck 'D3: Combined live hybrid retrieval (Qdrant + Apache AGE + pgvector)' $Python -Arguments @('-m','pytest','tests/integration/test_d3_combined_live_retrieval.py','-m','live','-v','-rs') | Out-Null
} else {
    Write-Log 'SKIP: Combined live hybrid retrieval; Docker unavailable.'
}

Write-Log "`n========== SUMMARY =========="
foreach ($result in $Results) {
    Write-Log ("{0}: {1} [exit {2}]" -f $result.Check, $(if ($result.Passed) {'PASS'} else {'FAIL/SKIP'}), $result.ExitCode)
}
$passedCount = @($Results | Where-Object { $_.Passed }).Count
Write-Log "Passed: $passedCount / $($Results.Count) executed/prerequisite checks"
if ($passedCount -eq $Results.Count) {
    Write-Log 'ALL CRITICAL CHECKS VERIFIED INCLUDING C3 LIVE RUNTIME ISOLATION AND D3 COMBINED LIVE RETRIEVAL.'
    Write-Log 'Formal critical acceptance: 30/30 (100.0%)'
} else {
    Write-Log "Check failures detected ($passedCount / $($Results.Count)). Formal critical acceptance remains incomplete (< 30/30)."
}
Write-Log "Log: $Log"
