#requires -Version 5.1
<#
.SYNOPSIS
  PreToolUse hook for Claude Code (Edit/Write/MultiEdit). Blocks edits to sensitive files.

.DESCRIPTION
  Reads a JSON event payload from stdin (Claude Code hook contract). Inspects the
  target file path. If it matches a sensitive pattern, exits with code 2 to block
  the edit and prints a reason on stderr.

  Sensitive patterns:
    - .env, .env.*
    - **/credentials.*, **/secrets.*
    - **/*.pem, **/*.key, **/*.pfx, **/*.p12
    - **/account*.yaml|yml|json|toml (likely game account config)
    - assets/templates/** binary image assets (PNG/JPG/BMP) — opt-in via env var to allow

  Exit codes:
    0 -> allow
    2 -> block (Claude Code will surface the stderr message)
#>

$ErrorActionPreference = 'Stop'

try {
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  $event = $raw | ConvertFrom-Json
} catch {
  # If the payload is not parseable, do not block the edit.
  exit 0
}

# Resolve target file from common shapes used across hook versions.
$path = $null
if ($event.tool_input) {
  if ($event.tool_input.file_path)   { $path = $event.tool_input.file_path }
  elseif ($event.tool_input.path)    { $path = $event.tool_input.path }
  elseif ($event.tool_input.notebook_path) { $path = $event.tool_input.notebook_path }
}
if (-not $path) { exit 0 }

$normalized = $path -replace '\\', '/'
$lower = $normalized.ToLowerInvariant()
$leaf  = [System.IO.Path]::GetFileName($lower)

$blocked = $false
$reason  = ''

# .env family
if ($leaf -eq '.env' -or $leaf -like '.env.*') {
  $blocked = $true; $reason = 'Refusing to edit environment file (.env / .env.*).'
}
# credentials / secrets
elseif ($leaf -like 'credentials*' -or $leaf -like 'secrets*' -or $leaf -like '*secret*.json' -or $leaf -like '*secret*.yaml' -or $leaf -like '*secret*.yml') {
  $blocked = $true; $reason = 'Refusing to edit credentials/secrets file.'
}
# private keys
elseif ($leaf -like '*.pem' -or $leaf -like '*.key' -or $leaf -like '*.pfx' -or $leaf -like '*.p12') {
  $blocked = $true; $reason = 'Refusing to edit private key material.'
}
# game account configs
elseif ($leaf -like 'account*.yaml' -or $leaf -like 'account*.yml' -or $leaf -like 'account*.json' -or $leaf -like 'account*.toml') {
  $blocked = $true; $reason = 'Refusing to edit account file (likely contains game credentials).'
}
# binary template assets
elseif ($lower -like '*assets/templates/*' -and ($leaf -like '*.png' -or $leaf -like '*.jpg' -or $leaf -like '*.jpeg' -or $leaf -like '*.bmp')) {
  if ($env:CLAUDE_ALLOW_TEMPLATE_EDIT -ne '1') {
    $blocked = $true
    $reason  = 'Refusing to overwrite a template asset under assets/templates/. Set CLAUDE_ALLOW_TEMPLATE_EDIT=1 in this session to allow.'
  }
}
# screenshots / debug captures
elseif ($lower -like '*/.claude/logs/*' -and ($leaf -like '*.png' -or $leaf -like '*.jpg')) {
  if ($env:CLAUDE_ALLOW_LOG_IMAGE_EDIT -ne '1') {
    $blocked = $true
    $reason  = 'Refusing to edit a debug screenshot under .claude/logs/. Set CLAUDE_ALLOW_LOG_IMAGE_EDIT=1 to allow.'
  }
}

if ($blocked) {
  [Console]::Error.WriteLine("[protect-sensitive-files] BLOCKED: $path")
  [Console]::Error.WriteLine("[protect-sensitive-files] Reason : $reason")
  [Console]::Error.WriteLine("[protect-sensitive-files] If this is intentional, ask the user to confirm and edit the file outside Claude Code, or override the env var documented above for this session only.")
  exit 2
}

exit 0
