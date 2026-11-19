# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
#
# proving54 operator runner, Windows PowerShell 5.1, ASCII only. It lives in the
# reviewed checkout at <Base>\src\proving54\operator\tick54.ps1 and writes only
# <Base>\run (through cli.py) and <Base>\tick-ledger.jsonl. One call does at most
# one `init` (hour zero only) and at most one `tick`, then a `status` readback,
# and appends one JSON line to the ledger. No loops, deletes, network, GPU work
# or settings changes. The window comes from the pinned manifest, not from here.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedHead,
    # Python312E (3.12.10): the py-launcher 3.12 install on the operator laptop
    # was found without its Lib folder on 2026-11-19.
    [string]$Python = 'C:\Users\steph\AppData\Local\Programs\Python\Python312E\python.exe',
    # Setup dry run: guard, source and `doctor` only. Never calls init or tick.
    [switch]$Check
)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$Src    = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$Base   = Split-Path -Parent $Src
$Run    = Join-Path $Base 'run'
$Ledger = Join-Path $Base 'tick-ledger.jsonl'
$Cli    = Join-Path $Src 'proving54\cli.py'
$Inv    = [System.Globalization.CultureInfo]::InvariantCulture
$Utf8   = New-Object System.Text.UTF8Encoding($false)
$IsoFmt = "yyyy-MM-dd'T'HH:mm:ss'Z'"
# Engine reasons worth one more try in the same hour; anything else needs a person.
$Retryable = @('ANOTHER_WORKER_OWNS_THIS_RUN', 'HOUR_WRITTEN_STATE_NOT_COMMITTED',
    'UNCOMMITTED_HOUR_QUARANTINED', 'PermissionError', 'OSError', 'FileExistsError',
    'BlockingIOError', 'TimeoutError', 'InterruptedError')

function Out-Record($Record) {
    $line = $Record | ConvertTo-Json -Compress -Depth 8
    [System.IO.File]::AppendAllText($Ledger, $line + "`n", $Utf8)
    Write-Output $line
}

function Invoke-Native([string]$Exe, [string[]]$Argv) {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $text = (& $Exe @Argv 2>&1 | Out-String).Trim()
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    return [ordered]@{ rc = $code; out = $text }
}

function Read-Json([string]$Text) {
    try { return ($Text | ConvertFrom-Json) } catch { return $null }
}

function Get-Field($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

function As-Evidence($Result) {
    $parsed = Read-Json $Result.out
    if ($null -ne $parsed) { return [ordered]@{ rc = $Result.rc; json = $parsed } }
    return [ordered]@{ rc = $Result.rc; text = $Result.out }
}

function Get-Moment($Value) {
    if ($Value -is [DateTime]) { return [DateTimeOffset]$Value.ToUniversalTime() }
    if ($null -eq $Value) { return $null }
    try { return [DateTimeOffset]::Parse([string]$Value, $Inv) } catch { return $null }
}

function Get-Slot([DateTimeOffset]$At, [DateTimeOffset]$From) {
    return [int][math]::Floor(($At - $From).TotalSeconds / 3600)
}

function Invoke-Cli([string]$Action) {
    return Invoke-Native $Python @('-I', '-B', '-X', 'utf8', $Cli, $Action, '--run', $Run)
}

$now  = [DateTimeOffset]::UtcNow
$disk = Get-PSDrive -Name C
$os   = Get-CimInstance -ClassName Win32_OperatingSystem
$freeGb  = [math]::Round($disk.Free / 1GB, 2)
$usedGb  = [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB, 2)
$limitGb = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
$ramGb   = [math]::Round($os.FreePhysicalMemory / 1MB, 2)

$rec = [ordered]@{
    schema        = 'szl.proving54-operator-tick/v2'
    utc           = $now.ToString($IsoFmt, $Inv)
    window_start  = $null
    window_end    = $null
    slot          = $null
    slot_after    = $null
    guard         = [ordered]@{ c_free_gb = $freeGb; ram_avail_gb = $ramGb; commit_used_gb = $usedGb; commit_limit_gb = $limitGb }
    expected_head = $ExpectedHead
    python        = $null
    head          = $null
    doctor        = $null
    init          = $null
    init_reason   = $null
    tick          = $null
    tick_reason   = $null
    status        = $null
    result        = $null
    next          = $null
    signed        = $false
}

if ($freeGb -lt 15 -or ($limitGb - $usedGb) -lt 2) {
    $rec.result = 'SKIP_GUARD'; $rec.next = 'RETRY_THIS_HOUR'; Out-Record $rec; exit 3
}
if (-not (Test-Path -LiteralPath $Cli -PathType Leaf) -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $rec.result = 'SKIP_SOURCE_OR_PYTHON_MISSING'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 5
}
$pyv = Invoke-Native $Python @('-I', '-B', '-X', 'utf8', '-c', 'import sys; print(sys.version.split()[0])')
$rec.python = [ordered]@{ path = $Python; rc = $pyv.rc; version = $pyv.out }
if ($pyv.rc -ne 0) {
    $rec.result = 'SKIP_SOURCE_OR_PYTHON_MISSING'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 5
}

$head  = Invoke-Native 'git' @('-C', $Src, 'rev-parse', 'HEAD')
$dirty = Invoke-Native 'git' @('-C', $Src, 'status', '--porcelain', '--untracked-files=all')
$rec.head = $head.out
if ($head.rc -ne 0 -or $head.out -ne $ExpectedHead -or $dirty.rc -ne 0 -or $dirty.out) {
    $rec.result = 'SKIP_SOURCE_DRIFT'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 6
}

# The pinned, clean manifest owns the window.
$manifest = Read-Json ([System.IO.File]::ReadAllText((Join-Path $Src 'proving54\manifest.json'), $Utf8))
$window = Get-Field $manifest 'window'
$Start = Get-Moment (Get-Field $window 'start_utc')
$End = Get-Moment (Get-Field $window 'end_utc')
if ($null -eq $Start -or $null -eq $End -or ($End - $Start).TotalHours -ne 54) {
    $rec.result = 'SKIP_WINDOW_UNREADABLE'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 14
}
$rec.window_start = $Start.ToString($IsoFmt, $Inv)
$rec.window_end = $End.ToString($IsoFmt, $Inv)
$slot = Get-Slot $now $Start
$rec.slot = $slot

if ($Check) {
    $doctor = Invoke-Native $Python @('-I', '-B', '-X', 'utf8', $Cli, 'doctor')
    $rec.doctor = As-Evidence $doctor
    if ($doctor.rc -eq 0) { $rec.result = 'CHECK_OK' } else { $rec.result = 'CHECK_FAILED' }
    $rec.next = 'WAIT'; Out-Record $rec
    if ($doctor.rc -eq 0) { exit 0 } else { exit 13 }
}
if ($now -lt $Start) {
    $rec.result = 'SKIP_BEFORE_WINDOW'; $rec.next = 'WAIT'; Out-Record $rec; exit 4
}
if ($now -ge $End) {
    if (Test-Path -LiteralPath $Run) { $rec.status = As-Evidence (Invoke-Cli 'status') }
    $rec.result = 'WINDOW_ENDED'; $rec.next = 'STOP'; Out-Record $rec; exit 0
}

if (-not (Test-Path -LiteralPath $Run)) {
    if ($slot -ne 0) {
        $rec.result = 'NO_RUN_AFTER_HOUR_ZERO'; $rec.next = 'STOP'; Out-Record $rec; exit 7
    }
    $init = Invoke-Cli 'init'
    $rec.init = As-Evidence $init
    if ($init.rc -ne 0) {
        $reason = [string](Get-Field (Read-Json $init.out) 'reason')
        $rec.init_reason = $reason
        $rec.result = 'INIT_HOLD'
        if ($reason -eq 'INITIALIZATION_OUTSIDE_SOURCE_HOUR_ZERO') { $rec.next = 'STOP' }
        elseif ($Retryable -contains $reason) { $rec.next = 'RETRY_THIS_HOUR' }
        else { $rec.next = 'NEEDS_OPERATOR' }
        Out-Record $rec; exit 8
    }
}

$tick   = Invoke-Cli 'tick'
$status = Invoke-Cli 'status'
$rec.tick   = As-Evidence $tick
$rec.status = As-Evidence $status
if ($tick.rc -ne 0) { $rec.tick_reason = [string](Get-Field (Read-Json $tick.out) 'reason') }
$hours = Get-Field (Read-Json $status.out) 'hours_recorded'
# The engine reads its own clock after Python starts; judge against both reads.
$slotAfter = Get-Slot ([DateTimeOffset]::UtcNow) $Start
$rec.slot_after = $slotAfter

if ($null -eq $hours) {
    $rec.result = 'STATUS_UNREADABLE'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 9
}
$hours = [int]$hours
if ($hours -eq ($slot + 1) -or $hours -eq ($slotAfter + 1)) {
    if ($tick.rc -eq 0) { $rec.result = 'HOUR_RECORDED' } else { $rec.result = 'HOUR_ALREADY_RECORDED' }
    if ($hours -ge 54) { $rec.next = 'COMPLETE' } else { $rec.next = 'CONTINUE' }
    Out-Record $rec; exit 0
}
if ($hours -lt $slot) {
    $rec.result = 'RUN_ENDED_MISSED_HOUR'; $rec.next = 'STOP'; Out-Record $rec; exit 10
}
if ($hours -eq $slot) {
    $rec.result = 'TICK_HOLD'
    if ($rec.tick_reason -eq 'OUTSIDE_54H_WINDOW') { $rec.next = 'STOP' }
    elseif ($Retryable -contains $rec.tick_reason) { $rec.next = 'RETRY_THIS_HOUR' }
    else { $rec.next = 'NEEDS_OPERATOR' }
    Out-Record $rec; exit 11
}
$rec.result = 'LEDGER_AHEAD_OF_CLOCK'; $rec.next = 'NEEDS_OPERATOR'; Out-Record $rec; exit 12
