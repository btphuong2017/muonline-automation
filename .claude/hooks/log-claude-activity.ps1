#requires -Version 5.1
<#
.SYNOPSIS
  PostToolUse hook: appends a one-line JSONL record per tool call to .claude/logs/activity.jsonl.

.DESCRIPTION
  Runs on every PostToolUse event. Captures: timestamp (ISO8601), session id (if
  provided), tool name, target file (if any), and a short summary. Never blocks.
  Writes UTF-8 without BOM. Truncates the log if it exceeds 5 MB by rotating to
  activity.jsonl.1.

  Designed to be cheap. No JSON parsing of huge tool outputs; just metadata.
#>

$ErrorActionPreference = 'Continue'

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $event = $raw | ConvertFrom-Json
} catch {
  exit 0
}

# Project-relative log directory. Hook scripts are at .claude/hooks/, so go two up.
$hookDir = Split-Path -Parent $PSCommandPath
$logDir  = Join-Path (Split-Path -Parent $hookDir) 'logs'
if (-not (Test-Path -LiteralPath $logDir)) {
  try { New-Item -ItemType Directory -Path $logDir -Force | Out-Null } catch { exit 0 }
}
$logFile = Join-Path $logDir 'activity.jsonl'

# Rotate if > 5 MB.
try {
  if (Test-Path -LiteralPath $logFile) {
    $size = (Get-Item -LiteralPath $logFile).Length
    if ($size -gt 5MB) {
      $rotated = "$logFile.1"
      if (Test-Path -LiteralPath $rotated) { Remove-Item -LiteralPath $rotated -Force -ErrorAction SilentlyContinue }
      Rename-Item -LiteralPath $logFile -NewName 'activity.jsonl.1' -Force -ErrorAction SilentlyContinue
    }
  }
} catch { }

$targetPath = $null
if ($event.tool_input) {
  if     ($event.tool_input.file_path)         { $targetPath = $event.tool_input.file_path }
  elseif ($event.tool_input.path)              { $targetPath = $event.tool_input.path }
  elseif ($event.tool_input.notebook_path)     { $targetPath = $event.tool_input.notebook_path }
  elseif ($event.tool_input.command)           { $targetPath = ($event.tool_input.command -as [string]) }
}

$record = [ordered]@{
  ts          = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
  hook_event  = $event.hook_event_name
  tool        = $event.tool_name
  session_id  = $event.session_id
  target      = $targetPath
  cwd         = $event.cwd
}

try {
  $line = ($record | ConvertTo-Json -Compress -Depth 4)
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::AppendAllText($logFile, $line + [Environment]::NewLine, $utf8NoBom)
} catch {
  # Logging must never fail the hook.
}

exit 0
