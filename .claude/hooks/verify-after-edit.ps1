#requires -Version 5.1
<#
.SYNOPSIS
  PostToolUse hook for Claude Code (Edit/Write/MultiEdit). Light verification only.

.DESCRIPTION
  Reads a JSON event payload from stdin, identifies the edited file, and runs a
  small, safe check based on file type:
    - .py  -> python -m py_compile <file>           (if python is on PATH)
    - .json/.yaml/.toml -> none yet (skipped — heavy parsers introduce coupling)
    - .ps1 -> none (parsing PowerShell from PowerShell is fine but noisy; skipped)

  Behaviour rules:
    - Always exits 0. Verification is informational only; never blocks an edit.
    - Skips entirely if no toolchain is detected, and prints what is missing.
    - Never runs lint, typecheck, full test suite, or anything network-bound.
    - Prints output to stderr so it shows up next to Claude's tool output.
#>

$ErrorActionPreference = 'Continue'

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $event = $raw | ConvertFrom-Json
} catch {
  exit 0
}

$path = $null
if ($event.tool_input) {
  if ($event.tool_input.file_path)         { $path = $event.tool_input.file_path }
  elseif ($event.tool_input.path)          { $path = $event.tool_input.path }
  elseif ($event.tool_input.notebook_path) { $path = $event.tool_input.notebook_path }
}
if (-not $path) { exit 0 }
if (-not (Test-Path -LiteralPath $path)) { exit 0 }

$ext = [System.IO.Path]::GetExtension($path).ToLowerInvariant()

function Get-CommandPath([string]$name) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source } else { return $null }
}

switch ($ext) {
  '.py' {
    $py = Get-CommandPath 'python'
    if (-not $py) { $py = Get-CommandPath 'py' }
    if (-not $py) {
      [Console]::Error.WriteLine("[verify-after-edit] python not on PATH; skipping py_compile for $path")
      exit 0
    }
    $proc = Start-Process -FilePath $py -ArgumentList @('-m', 'py_compile', $path) `
      -NoNewWindow -Wait -PassThru `
      -RedirectStandardError "$env:TEMP\claude_verify_err.txt" `
      -RedirectStandardOutput "$env:TEMP\claude_verify_out.txt"
    if ($proc.ExitCode -ne 0) {
      [Console]::Error.WriteLine("[verify-after-edit] py_compile FAILED for $path:")
      Get-Content "$env:TEMP\claude_verify_err.txt" -ErrorAction SilentlyContinue | ForEach-Object { [Console]::Error.WriteLine($_) }
    } else {
      [Console]::Error.WriteLine("[verify-after-edit] py_compile OK: $path")
    }
    Remove-Item "$env:TEMP\claude_verify_err.txt" -ErrorAction SilentlyContinue
    Remove-Item "$env:TEMP\claude_verify_out.txt" -ErrorAction SilentlyContinue
  }
  default {
    # No verification wired up for this file type yet. Stay silent to avoid noise.
  }
}

exit 0
