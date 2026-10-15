<#
.SYNOPSIS
DISA STIG Conversion Tool - PowerShell edition.

.DESCRIPTION
Converts and imports DISA STIG content into SolarWinds NCM compliance policy
reports and Server Configuration Monitor compliance policies over the SWIS API,
or converts to console-importable files with no server connection at all.

Built-in only: Windows PowerShell 5.1+ / PowerShell 7+, .NET framework classes,
no modules (SwisPowerShell and orionsdk are NOT required), no gallery installs.
All code is visible in this one file for audit; the SWIS calls executed are
documented in README.md next to it. The Python edition (disa_stig_tool.py) is
the reference: both editions derive the same RuleIds, PolicyIds, SCM uniqueIds
and report names for the same input.

This file is deliberately pure ASCII. Windows PowerShell 5.1 reads a script
without a byte-order mark in the ANSI code page, and a UTF-8 dash or quote
inside a string would be decoded into characters the parser treats as quotes.

Security rules: TLS verification on by default (the stock self-signed
'SolarWinds-Orion' certificate is trusted by explicit fetch-and-pin);
credentials live in memory only and are redacted from every log line; empty
read-backs report "No Data Returned"; SCM configuration content
(Orion.SCM.Results.ElementContents) is never read.

-ApiToken (platform 2026.4+) authenticates with a SWIS API token instead of a
user name and password: the token is read from $env:SWIS_API_TOKEN, or prompted
for, and sent as a bearer token; it excludes -Username and -WindowsAuth.

Every run writes a log file in the same line format as the Python edition, one
line per decision and per SWIS call, secrets redacted; its path is printed when
the run starts and ends. -LogFile <path> and -LogLevel debug|info|warn change it.
See the "Run log" section of README.md.

.EXAMPLE
.\disa_stig_tool.ps1
Opens the GUI (Windows).

.EXAMPLE
.\disa_stig_tool.ps1 -Convert -Path .\U_Cisco_IOS_Router_Y26M07_STIG.zip
Local file conversion only - writes .ncm-report.xml / .scm-policy.yaml files.

.EXAMPLE
.\disa_stig_tool.ps1 -Path .\stig.zip -Server orion.example.com -Username admin
Imports over SWIS (password prompted, or set $env:SWIS_PASSWORD).

.EXAMPLE
.\disa_stig_tool.ps1 -Path .\stig.zip -Server orion.example.com -ApiToken
Imports over SWIS with an API token (prompted, or set $env:SWIS_API_TOKEN).

.EXAMPLE
.\disa_stig_tool.ps1 -Test -Path .\stig.zip -Server orion.example.com -Username admin -ConfigId <ConfigID>
Dry-runs the generated rules with TestRuleOnBackedUpConfig; creates nothing.

.EXAMPLE
.\disa_stig_tool.ps1 -Remove -Name "<report name>" -Server orion.example.com -Username admin -DryRun
Shows what removing that report would delete and keep; add -Yes instead of -DryRun to delete.
Report names end in the version suffix (_v1 by default), so give the full name.

.EXAMPLE
.\disa_stig_tool.ps1 -Path .\U_Cisco_IOS-XE_Router_Y26M07_STIG.zip -Server orion.example.com -Username admin -Suffix _v2
Imports a new release next to the _v1 import: every name ends in _v2 and every id is fresh.
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [switch]$Convert,
    [switch]$Test,
    [switch]$Remove,
    [string]$Server,
    [int]$Port = 17774,
    [string]$Username,
    [switch]$ApiToken,
    [switch]$WindowsAuth,
    [switch]$Insecure,
    [switch]$PinServerCert,
    [ValidateSet('auto', 'network', 'server')][string]$Target = 'auto',
    [string]$NodeWhere = 'auto',
    [string]$Vendor,
    [string]$MachineType,
    [switch]$AllowEmptyScope,
    [string]$Suffix = '_v1',
    [string]$ScmProbeTemplate,
    [ValidateSet('manual', 'heuristic', 'blocks')][string]$Mode = 'manual',
    [string]$PatternDrafts,
    [string]$WritePatternDrafts,
    [string]$Name,
    [string]$Grouping = 'DISA STIG',
    [string]$ConfigType = 'Any',
    [switch]$ImportDisabled,
    [switch]$NoCache,
    [switch]$NoRollback,
    [string]$ConfigFile,
    [string]$ConfigId,
    [int]$Limit = 10,
    [switch]$Yes,
    [switch]$DryRun,
    [switch]$NoGui,
    [switch]$Audit,
    [string]$LogFile,
    [ValidateSet('debug', 'info', 'warn')][string]$LogLevel = 'info',
    [int]$LogBodyLimit = 4096
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

# One version for the tool, shared by both editions (disa_stig_tool.py carries the
# same number). It is written into every log file's start-of-run line.
$script:ToolVersion = '2.1.0'
# The parameters this run was started with, for the start-of-run log line.
$script:BoundAtStart = [ordered]@{}
foreach ($boundKey in $PSBoundParameters.Keys) { $script:BoundAtStart[$boundKey] = $PSBoundParameters[$boundKey] }

# =========================================================================
# Shared state: secrets (memory only, always redacted), TLS mode
# =========================================================================
$script:Secrets = New-Object System.Collections.ArrayList
$script:TlsInsecure = $false
$script:PinnedThumbprint = $null
$script:MaxZipFiles = 10

function Register-Secret([string]$Value) {
    if ($Value) { [void]$script:Secrets.Add($Value) }
}
function Hide-Secrets([string]$Text) {
    foreach ($s in $script:Secrets) { $Text = $Text.Replace($s, ('*' * 6)) }
    return $Text
}

# =========================================================================
# Run log: one line per event, the same format as the Python edition
# =========================================================================
#   2026-10-09T14:03:07.123Z INFO  swis   Cirrus.PolicyReports.AddPolicyRule(...) -> ok 41 ms
# <UTC ISO-8601 with milliseconds>Z, the level padded to 5, the component padded
# to 6, then the message on one line (line breaks are written as a literal \n).
# Every line goes through Hide-Secrets. Console output is unchanged; the file is
# additive. Nothing is written until Initialize-ToolLog has run.
$script:LogComponents = @('main', 'parse', 'route', 'scope', 'build', 'swis', 'import', 'verify',
                          'rollbk', 'remove', 'scm', 'file', 'gui')
$script:LogLevels = @{ debug = 0; info = 1; warn = 2; error = 3 }
# Debug-level request, response and error bodies are cut to this many chars
# (-LogBodyLimit, Python --log-body-limit; 0 writes every body whole).
$script:LogBodyLimit = [Math]::Max(0, [int]$LogBodyLimit)
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:LogState = @{ Path = $null; Level = 'info'; Started = [datetime]::UtcNow; Stats = @{} }

function Reset-ToolLogStats {
    $script:LogState.Stats = @{ SwisCalls = 0; SwisFailed = 0; FilesWritten = 0; Imported = 0
                                Warnings = 0; Errors = 0 }
}
Reset-ToolLogStats

function Add-ToolLogStat([string]$Key, [int]$Count = 1) {
    $script:LogState.Stats[$Key] = $script:LogState.Stats[$Key] + $Count
}

function Format-ToolLogLine([datetime]$Utc, [string]$Level, [string]$Component, [string]$Message) {
    $stamp = $Utc.ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", [System.Globalization.CultureInfo]::InvariantCulture)
    $text = (Hide-Secrets $Message) -replace "`r`n", "`n" -replace "`r", "`n" -replace "`n", '\n'
    return ('{0} {1} {2} {3}' -f $stamp, $Level.ToUpperInvariant().PadRight(5), $Component.PadRight(6), $text)
}

function Get-DefaultLogPath {
    # Windows: %LOCALAPPDATA%\DisaStigTool\logs\disa-stig-tool_<yyyyMMdd-HHmmss>.log;
    # elsewhere ~/.local/state/disa-stig-tool/logs/ (or $XDG_STATE_HOME when set).
    # The time stamp in the name is UTC. The parameters exist for tests.
    param($NowUtc = $null, [string]$Platform = '', $Environment = $null, [string]$HomeDir = '')
    if ($null -eq $NowUtc) { $NowUtc = [datetime]::UtcNow }
    if (-not $Platform) { if ($env:OS -eq 'Windows_NT') { $Platform = 'windows' } else { $Platform = 'other' } }
    if ($null -eq $Environment) { $Environment = @{ LOCALAPPDATA = $env:LOCALAPPDATA; XDG_STATE_HOME = $env:XDG_STATE_HOME } }
    if (-not $HomeDir) { $HomeDir = [Environment]::GetFolderPath('UserProfile') }
    if (-not $HomeDir) { $HomeDir = $HOME }
    $name = 'disa-stig-tool_' + ([datetime]$NowUtc).ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture) + '.log'
    if ($Platform -like 'win*') {
        $base = $Environment['LOCALAPPDATA']
        if (-not $base) { $base = [System.IO.Path]::Combine($HomeDir, 'AppData', 'Local') }
        return [System.IO.Path]::Combine($base, 'DisaStigTool', 'logs', $name)
    }
    $base = $Environment['XDG_STATE_HOME']
    if (-not $base) { $base = [System.IO.Path]::Combine($HomeDir, '.local', 'state') }
    return [System.IO.Path]::Combine($base, 'disa-stig-tool', 'logs', $name)
}

function Initialize-ToolLog([string]$Path, [string]$Level = 'info') {
    # Opens the run log once per run and returns its full path. An explicit path
    # that cannot be written is an error; when the default location cannot be
    # created, the log falls back to the temp directory instead.
    if (-not $script:LogLevels.ContainsKey($Level)) { throw "unknown log level '$Level'; use debug, info or warn" }
    if ($Path) {
        $candidates = @($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path))
    } else {
        $default = Get-DefaultLogPath
        $candidates = @($default, [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(),
            'disa-stig-tool', 'logs', [System.IO.Path]::GetFileName($default)))
    }
    $chosen = $null; $lastError = ''
    foreach ($candidate in $candidates) {
        try {
            $dir = [System.IO.Path]::GetDirectoryName($candidate)
            if ($dir -and -not [System.IO.Directory]::Exists($dir)) { [void][System.IO.Directory]::CreateDirectory($dir) }
            [System.IO.File]::AppendAllText($candidate, '', $script:Utf8NoBom)
            $chosen = $candidate; break
        } catch { $lastError = $_.Exception.Message }
    }
    if (-not $chosen) { throw "cannot open the log file: $lastError" }
    Reset-ToolLogStats
    $script:LogState.Path = $chosen
    $script:LogState.Level = $Level
    $script:LogState.Started = [datetime]::UtcNow
    return $chosen
}

function Test-ToolLogDebug {
    return [bool]($script:LogState.Path -and $script:LogState.Level -eq 'debug')
}

function Write-ToolLog {
    # One event to the run log. -Component is one of $script:LogComponents.
    param([string]$Component = 'main',
          [ValidateSet('debug', 'info', 'warn', 'error')][string]$Level = 'info',
          [string]$Message = '')
    if ($Level -eq 'warn') { Add-ToolLogStat 'Warnings' } elseif ($Level -eq 'error') { Add-ToolLogStat 'Errors' }
    if (-not $script:LogState.Path) { return }
    if ($script:LogLevels[$Level] -lt $script:LogLevels[$script:LogState.Level]) { return }
    if ($script:LogComponents -notcontains $Component) { $Component = 'main' }
    $line = Format-ToolLogLine ([datetime]::UtcNow) $Level $Component $Message
    try { [System.IO.File]::AppendAllText($script:LogState.Path, $line + "`n", $script:Utf8NoBom) } catch { }
}

function Send-Log([scriptblock]$Log, [string]$Component, [string]$Level, [string]$Message) {
    # Send a message to the caller's console/GUI callback and to the run log.
    Write-ToolLog -Component $Component -Level $Level -Message $Message
    if ($Log) { & $Log $Message }
}

function Limit-LogBody([string]$Text) {
    if ($null -eq $Text) { return '' }
    if ($script:LogBodyLimit -eq 0 -or $Text.Length -le $script:LogBodyLimit) { return $Text }
    return (Limit-Text $Text $script:LogBodyLimit) + "... [truncated, $($Text.Length) chars]"
}

function Format-ToolCommandLine($Bound) {
    $parts = New-Object System.Collections.ArrayList
    [void]$parts.Add('disa_stig_tool.ps1')
    foreach ($k in $Bound.Keys) {
        $v = $Bound[$k]
        if ($v -is [System.Management.Automation.SwitchParameter]) {
            if ($v.IsPresent) { [void]$parts.Add("-$k") }
            continue
        }
        $vals = @(@($v) | ForEach-Object { "'" + ([string]$_).Replace("'", "''") + "'" }) -join ','
        [void]$parts.Add("-$k $vals")
    }
    return ($parts -join ' ')
}

function Write-ToolLogStart([string]$Mode) {
    # Start-of-run lines: tool version, interpreter, OS, the command line, the log file.
    Write-ToolLog main info "DISA STIG Conversion Tool $($script:ToolVersion) (PowerShell edition), $Mode run"
    $edition = 'Desktop'
    if ($PSVersionTable.ContainsKey('PSEdition')) { $edition = $PSVersionTable.PSEdition }
    Write-ToolLog main info "interpreter: PowerShell $($PSVersionTable.PSVersion) ($edition), CLR $([Environment]::Version)"
    $os = [Environment]::OSVersion.VersionString
    try { $os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription.Trim() } catch { }
    Write-ToolLog main info "os: $os"
    Write-ToolLog main info ('command line: ' + (Format-ToolCommandLine $script:BoundAtStart))
    Write-ToolLog main info "log file: $($script:LogState.Path) (level $($script:LogState.Level))"
}

function Write-ToolLogEnd([int]$ExitCode) {
    # End-of-run summary with counts and the exit code.
    $s = $script:LogState.Stats
    $secs = ([datetime]::UtcNow - $script:LogState.Started).TotalSeconds.ToString('0.0', [System.Globalization.CultureInfo]::InvariantCulture)
    Write-ToolLog main info ("run end: exit code $ExitCode; $($s.SwisCalls) SWIS call(s), $($s.SwisFailed) " +
        "failed; $($s.FilesWritten) file(s) written; $($s.Imported) import(s) verified; " +
        "$($s.Warnings) warning(s), $($s.Errors) error(s); $secs s")
}

# =========================================================================
# Safe output: generated file names and PowerShell probe literals
# =========================================================================
$script:MaxFileName = 200
$script:WindowsReservedNames = @('CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
    'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9')

function Get-SafeFileName([string]$Stem, [string]$Suffix = '') {
    # The one place every generated file name goes through (same rule as the
    # Python safe_file_name): keep [A-Za-z0-9._-], collapse every other run of
    # characters to one underscore, strip leading dots, and cap the whole name,
    # suffix included, at 200 characters. A STIG title can then neither climb out
    # of the output folder ("../../x") nor exceed the 255-character limit.
    $name = ([string]$Stem -replace '[^A-Za-z0-9._-]+', '_').TrimStart('.')
    if ($script:WindowsReservedNames -contains $name.Split('.')[0].ToUpperInvariant()) { $name = '_' + $name }
    $max = [Math]::Max(1, $script:MaxFileName - $Suffix.Length)
    if ($name.Length -gt $max) { $name = $name.Substring(0, $max) }
    if (-not $name) { $name = 'unnamed' }
    return $name + $Suffix
}

# SCM probes run as PowerShell on every assigned node, so nothing from the STIG
# may reach script source unquoted. Ids are validated, and the probe text is a
# single-quoted PowerShell literal, in which only the quote characters are
# special. PowerShell also treats U+2018-U+201B as single quotes.
$script:PsSingleQuoteChars = "'" + [char]0x2018 + [char]0x2019 + [char]0x201A + [char]0x201B

function ConvertTo-PsSingleQuoted([string]$Text) {
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append("'")
    foreach ($ch in ([string]$Text).ToCharArray()) {
        if ($script:PsSingleQuoteChars.IndexOf($ch) -ge 0) { [void]$sb.Append($ch) }
        [void]$sb.Append($ch)
    }
    [void]$sb.Append("'")
    return $sb.ToString()
}

function Get-ScmProbeId([string]$VulnId, [string]$RuleId = '') {
    # A DISA id is V-<digits> (rule ids SV-<digits>r<digits>_rule), after any SCAP
    # xccdf_ prefix is stripped. Anything else is reduced to [A-Za-z0-9._-] with a
    # warning in the log, so the probe and its expression stay predictable.
    $vid = Remove-ScapPrefix $VulnId
    $rid = Remove-ScapPrefix $RuleId
    if ($rid -and $rid -cnotmatch '^SV-[0-9]+r[0-9]+_rule\z') {
        Write-ToolLog scm warn "rule id '$rid' does not match SV-<n>r<n>_rule; it is used only in ids and comments, never in probe source"
    }
    if ($vid -cmatch '^V-[0-9]+\z') { return $vid }
    $safe = $vid -replace '[^A-Za-z0-9._-]+', '_'
    if (-not $safe) { $safe = 'V-unknown' }
    Write-ToolLog scm warn "vuln id '$vid' does not match V-<n>; the SCM probe uses the sanitized id '$safe'"
    return $safe
}

# =========================================================================
# Version suffix: every name and every generated id carries it
# =========================================================================
# Since 2.0.0 every NCM report name, NCM policy name and SCM policy name ends in a
# version suffix (_v1 by default), and the same suffix is part of the uuid5 seed of
# every generated id (NCM PolicyId and RuleIds, SCM policy uniqueId and rule
# uniqueIds), so -Suffix _v2 imports a new release with entirely fresh names and
# ids. Same rules as the Python edition (validate_suffix, with_suffix).
$script:DefaultSuffix = '_v1'
$script:NameLimit = 250
$script:RuleNameLimit = 200   # NCM_PolicyRules.Name: a 184-char name is stored on 2026.4.0, a 212-char one fails with SQL error 2628

function Test-Suffix([string]$Value) {
    # Returns the suffix to use, or throws. Empty means the default (_v1).
    if (-not $Value) { $Value = $script:DefaultSuffix }
    if ($Value -cnotmatch '^_v[0-9]+\z') {
        throw "-Suffix '$Value' is not valid: it must be _v followed by digits (_v1, _v2, ...)"
    }
    return $Value
}

function Get-SuffixedName([string]$Name, [string]$Suffix, [int]$Limit = 250) {
    # Python with_suffix: the name is cut so name + suffix fits the limit; the suffix
    # itself is never cut, so the base can be recovered for the collision check.
    if ($null -eq $Name) { $Name = '' }
    $max = [Math]::Max(0, $Limit - $Suffix.Length)
    return (Limit-Text $Name $max) + $Suffix
}

function Split-NameSuffix([string]$Name) {
    # @{ Base; N } for a name ending in _v<n>; N is $null when there is none.
    $m = [regex]::Match([string]$Name, '_v([0-9]+)\z')
    if (-not $m.Success) { return @{ Base = [string]$Name; N = $null } }
    return @{ Base = $Name.Substring(0, $m.Index); N = [long]$m.Groups[1].Value }
}

function Get-NextFreeSuffix($Names, [string]$Base, [string]$CurrentSuffix) {
    # One above the highest _v<n> any existing name base + _v<n> carries, and above
    # the suffix that collided (Python next_free_suffix).
    [long]$highest = [long]$CurrentSuffix.Substring(2)
    foreach ($n in @($Names)) {
        $parts = Split-NameSuffix ([string]$n)
        if ($null -ne $parts.N -and $parts.Base -ceq $Base -and $parts.N -gt $highest) { $highest = $parts.N }
    }
    return '_v' + ($highest + 1)
}

# =========================================================================
# SCM probe per OS family, and the -ScmProbeTemplate override
# =========================================================================
# Every family uses the same manual-review attestation today: a !scm.powershell
# source whose script is a single-quoted Write-Host literal. Windows is the source
# type SolarWinds' shipped STIG policies use. Linux STIGs also route to SCM with the
# same probe, but that is Unverified: no SCM policy source for Linux is documented
# in this repository, and script data sources on Linux are understood to be
# unsupported. -ScmProbeTemplate replaces the source block; README "Testing Linux
# STIGs in SCM" says what to check. Same as the Python edition (SCM_PROBES).
$script:ScmProbes = @{
    windows = @{ Tag = '!scm.powershell'; Verified = $true
                 Label = "!scm.powershell Write-Host attestation (the source type SolarWinds' shipped Windows STIG policies use)" }
    linux   = @{ Tag = '!scm.powershell'; Verified = $false
                 Label = '!scm.powershell Write-Host attestation (Unverified on Linux nodes)' }
}
$script:LinuxProbeWarning = ('Linux STIG routed to SCM: the generated probe is !scm.powershell, which is Unverified on ' +
    'Linux nodes (no SCM policy source for Linux is documented in this repository, and script data sources on Linux ' +
    'are understood to be unsupported), so its rules may report an error or Unknown rather than failed. Import one ' +
    "policy, assign it to one test node and check it as README.md 'Testing Linux STIGs in SCM' describes; " +
    '-ScmProbeTemplate FILE tries another source type.')
$script:ProbeTemplateMax = 4096

function ConvertFrom-ProbeTemplate([string]$Text, [string]$Source = 'template') {
    # Python parse_probe_template: the source tag (!scm.<type>) on the first line,
    # then 'key: value' mapping lines nested by spaces. {id} becomes the validated
    # probe id (Get-ScmProbeId), never raw STIG text, and is accepted only inside a
    # quoted scalar ("..." or '...'). Anything else is refused before any file is written.
    if ([System.Text.Encoding]::UTF8.GetByteCount($Text) -gt $script:ProbeTemplateMax) {
        throw "${Source}: the probe template is larger than $($script:ProbeTemplateMax) bytes"
    }
    $norm = $Text.TrimStart([char]0xFEFF) -replace "`r`n", "`n" -replace "`r", "`n"
    $lines = New-Object System.Collections.ArrayList
    foreach ($raw in ($norm -split "`n")) {
        $line = $raw.TrimEnd()
        if (-not $line.Trim() -or $line.TrimStart().StartsWith('#')) { continue }
        [void]$lines.Add($line)
    }
    if ($lines.Count -eq 0) { throw "${Source}: the probe template is empty" }
    if (($lines -join '').Contains("`t")) { throw "${Source}: tabs are not allowed in the probe template (YAML indents with spaces)" }
    if ($lines[0] -cnotmatch '^!scm\.[A-Za-z][A-Za-z0-9_.]*\z') {
        $shown = $lines[0]; if ($shown.Length -gt 60) { $shown = $shown.Substring(0, 60) }
        throw "${Source}: the probe template must start with an SCM source tag on its own line, such as !scm.powershell (found '$shown')"
    }
    $levels = New-Object System.Collections.ArrayList
    [void]$levels.Add(0)
    $opened = $false
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $number = $i + 1
        $line = $lines[$i]
        $m = [regex]::Match($line, '^( *)([A-Za-z_][A-Za-z0-9_-]*):(?: (.*))?\z')
        if (-not $m.Success) {
            throw "${Source}: line $number is not a 'key: value' mapping line; sequences, anchors and flow collections are not supported"
        }
        $indent = $m.Groups[1].Value.Length
        $value = $m.Groups[3].Value.Trim()
        if ($opened -and $indent -gt $levels[$levels.Count - 1]) {
            [void]$levels.Add($indent)
        } elseif ($levels.Contains($indent)) {
            $at = $levels.IndexOf($indent)
            while ($levels.Count -gt $at + 1) { $levels.RemoveAt($levels.Count - 1) }
        } else {
            throw "${Source}: line $number is indented inconsistently"
        }
        if ($m.Groups[2].Value.Contains('{id}')) { throw "${Source}: line ${number}: {id} is not allowed in a key" }
        $opened = -not $value
        if (-not $value) { continue }
        if ($value -cmatch '^"(?:[^"\\\x00-\x1f]|\\[^\x00-\x1f])*"\z' -or $value -cmatch "^'(?:[^'\x00-\x1f]|'')*'\z") {
            if ($value.Contains('\{id}')) { throw "${Source}: line ${number}: a backslash directly before {id} would turn the id into an escape sequence" }
            continue
        }
        if ($value.Contains('{id}')) { throw "${Source}: line ${number}: {id} is only allowed inside a quoted string (`"...`" or '...')" }
        if ($value -cnotmatch '^[A-Za-z0-9_./\\$(][^#\x00-\x1f]*\z' -or $value.Contains(': ') -or $value.EndsWith(':')) {
            throw "${Source}: line ${number}: the value is neither a quoted string nor a plain scalar this tool accepts"
        }
    }
    if ($opened) { throw "${Source}: the last key has no value" }
    return , [string[]]@($lines)
}

function Read-ProbeTemplate([string]$FilePath) {
    # Read and validate -ScmProbeTemplate (UTF-8, optional BOM); returns its lines.
    $bytes = [System.IO.File]::ReadAllBytes($FilePath)
    $strict = New-Object System.Text.UTF8Encoding($false, $true)
    try { $text = $strict.GetString($bytes) } catch { throw "${FilePath}: the probe template is not UTF-8 ($($_.Exception.Message))" }
    $lines = ConvertFrom-ProbeTemplate $text $FilePath
    $usesId = @($lines | Where-Object { $_.Contains('{id}') }).Count -gt 0
    $used = 'not used'; if ($usesId) { $used = 'used' }
    Write-ToolLog scm info "probe template ${FilePath}: source $($lines[0]), $($lines.Count - 1) mapping line(s), {id} $used"
    if (-not $usesId) {
        Write-ToolLog scm warn "probe template $FilePath does not use {id}, so every rule collects the same value; the expression '<id> reviewed: True' still never matches"
    }
    return , $lines
}

function Get-ScmProbeLines([string]$ProbeId, [string]$StigId, $Template) {
    # The source: block of one generated rule (Python scm_probe_lines).
    if ($Template) {
        $out = New-Object System.Collections.ArrayList
        [void]$out.Add("    source: $($Template[0])")
        for ($i = 1; $i -lt $Template.Count; $i++) { [void]$out.Add('      ' + $Template[$i].Replace('{id}', $ProbeId)) }
        return , @($out)
    }
    return , @('    source: !scm.powershell',
               ('      description: ' + (Y ('STIG ' + $StigId + ' manual-review attestation'))),
               ('      script: ' + (Y ('Write-Host ' + (ConvertTo-PsSingleQuoted ($ProbeId + ' reviewed: False'))))))
}

function Write-ScmProbePlan([string]$Family, $Template, [string]$TemplatePath, [scriptblock]$Log) {
    # One log line for the OS detected and the probe used; a WARN for Linux.
    if ($Template) {
        $shownPath = $TemplatePath; if (-not $shownPath) { $shownPath = '(given)' }
        $probe = "template $shownPath ($($Template[0]))"
    } elseif ($script:ScmProbes.ContainsKey($Family)) { $probe = $script:ScmProbes[$Family].Label }
    else { $probe = $script:ScmProbes['windows'].Label }
    Write-ToolLog scm info "SCM probe: OS family $Family; probe $probe"
    if ($Family -eq 'unknown' -and -not $Template) {
        Write-ToolLog scm warn 'the OS was not recognized from the file or benchmark names; the Windows probe is used'
    }
    if ($Family -eq 'linux') { Send-Log $Log 'scm' 'warn' ('[SCM] warning: ' + $script:LinuxProbeWarning) }
}

# =========================================================================
# XCCDF / SCAP parsing (manual 1.1 benchmarks and SCAP 1.3 data-streams)
# =========================================================================
$script:XccdfNamespaces = @('http://checklists.nist.gov/xccdf/1.1',
                            'http://checklists.nist.gov/xccdf/1.2')

function Get-XmlText($Node, $Name, $Ns) {
    foreach ($child in $Node.ChildNodes) {
        if ($child.LocalName -eq $Name -and $child.NamespaceURI -eq $Ns) {
            return ('' + $child.InnerText).Trim()
        }
    }
    return ''
}

function Remove-ScapPrefix([string]$Value) {
    return ($Value -replace '^xccdf_[^_]+(\.[^_]+)*_(group|rule|benchmark)_', '')
}

function Get-PseudoTag([string]$Description, [string]$Tag) {
    $m = [regex]::Match($Description, "<$Tag>(.*?)</$Tag>",
        [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($m.Success) { return $m.Groups[1].Value.Trim() } else { return '' }
}

$script:DtdRefusal = ('refused: the document declares a DTD (<!DOCTYPE>); DTDs and entity ' +
    'declarations are never processed, so external entities cannot be resolved')

function Read-SafeXmlDocument([byte[]]$Bytes) {
    # Every XML this tool reads goes through here: DtdProcessing=Prohibit and no
    # resolver close the external-entity (XXE) and entity-expansion classes, and
    # loading from the byte stream lets the reader honour the BOM and the
    # declared encoding instead of forcing UTF-8. The Python edition refuses any
    # DTD the same way (refuse_dtd).
    $settings = New-Object System.Xml.XmlReaderSettings
    $settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $settings.XmlResolver = $null
    $ms = New-Object System.IO.MemoryStream(, $Bytes)
    $reader = [System.Xml.XmlReader]::Create($ms, $settings)
    try {
        $doc = New-Object System.Xml.XmlDocument
        $doc.XmlResolver = $null
        $doc.Load($reader)
        return , $doc   # unary comma: an XmlDocument would otherwise enumerate its nodes
    } finally { $reader.Dispose(); $ms.Dispose() }
}

function ConvertFrom-BenchmarkXml([byte[]]$Bytes, [string]$SourceName) {
    # Returns a list of benchmark hashtables; empty when the XML is not XCCDF.
    # Zip discovery goes by content, and every skip is logged with its reason.
    $headLength = [Math]::Min(200, $Bytes.Length)
    if ($headLength -eq 0 -or [Array]::IndexOf($Bytes, [byte]0x3C, 0, $headLength) -lt 0) {
        Write-ToolLog parse warn "skipped ${SourceName}: does not look like XML"
        return @()
    }
    try { $doc = Read-SafeXmlDocument $Bytes }
    catch {
        $e = $_.Exception
        while ($e.InnerException) { $e = $e.InnerException }
        $reason = "not well-formed XML ($($e.Message))"
        if ($e.Message -match 'DTD') { $reason = $script:DtdRefusal }
        Write-ToolLog parse warn "skipped ${SourceName}: $reason"
        return @()
    }
    $found = New-Object System.Collections.ArrayList
    foreach ($ns in $script:XccdfNamespaces) {
        $mgr = New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
        $mgr.AddNamespace('x', $ns)
        $benches = $doc.SelectNodes('//x:Benchmark', $mgr)
        foreach ($b in $benches) {
            [void]$found.Add((Read-OneBenchmark $b $ns $SourceName))
        }
        if ($benches.Count -gt 0) { break }
    }
    if ($found.Count -eq 0) {
        $rootName = '(none)'
        if ($doc.DocumentElement) { $rootName = '{' + $doc.DocumentElement.NamespaceURI + '}' + $doc.DocumentElement.LocalName }
        Write-ToolLog parse warn "skipped ${SourceName}: no XCCDF Benchmark element found (root is $rootName)"
    } else {
        Write-ToolLog parse info "parsed ${SourceName}: $($found.Count) benchmark(s)"
    }
    return @($found)
}

# The pseudo-sections DISA embeds in a rule's <description>, in the order they are
# carried into the NCM rule Comments and the SCM rule description (Python
# DESCRIPTION_SECTIONS). Empty sections are left out.
$script:DescriptionSections = @(
    @('VulnDiscussion', 'Discussion'), @('FalsePositives', 'False positives'),
    @('FalseNegatives', 'False negatives'), @('Mitigations', 'Mitigations'),
    @('PotentialImpacts', 'Potential impacts'), @('ThirdPartyTools', 'Third-party tools'),
    @('MitigationControl', 'Mitigation control'), @('Responsibility', 'Responsibility'),
    @('IAControls', 'IA controls'))

function Get-NormalizedSeverity([string]$Raw) {
    # @{ Severity; Note }: high/medium/low are kept; a missing severity, unknown, info
    # and anything else become medium, and Note says what was there (Python
    # normalize_severity).
    $value = ([string]$Raw).Trim().ToLowerInvariant()
    if (@('high', 'medium', 'low') -ccontains $value) { return @{ Severity = $value; Note = $null } }
    if (-not $value) { return @{ Severity = 'medium'; Note = 'missing' } }
    return @{ Severity = 'medium'; Note = "'$value'" }
}

function Get-NoIdRuleId([string]$Title, [int]$Index) {
    # The deterministic id of a Rule without an id attribute (Python no_id_rule_id).
    return 'noid-' + (Get-DeterministicGuid ("stig2ncm-noid:$Title#$Index"))
}

function Set-UniqueRuleIds($Rules, [string]$BenchLabel) {
    # Python _unique_rule_ids: a repeated rule id gets -dup<n> with a warning, and every
    # rule gets DisplayId: the V- id, or V-id/rule id when the V- id is shared.
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($r in $Rules) {
        $rid = [string]$r.RuleId
        if ($seen.Contains($rid)) {
            $n = 2
            while ($seen.Contains("$rid-dup$n")) { $n++ }
            $r.RuleId = "$rid-dup$n"
            Write-ToolLog parse warn "${BenchLabel}: rule id $rid appears more than once; this occurrence is imported as $($r.RuleId)"
        }
        [void]$seen.Add([string]$r.RuleId)
    }
    $counts = New-Object 'System.Collections.Generic.Dictionary[string,int]' ([System.StringComparer]::Ordinal)
    foreach ($r in $Rules) {
        $v = [string]$r.VulnId
        if ($counts.ContainsKey($v)) { $counts[$v]++ } else { $counts[$v] = 1 }
    }
    foreach ($r in $Rules) {
        $v = [string]$r.VulnId
        if ($counts[$v] -gt 1) {
            $r.DisplayId = "$v/$($r.RuleId)"
            Write-ToolLog parse debug "${BenchLabel}: $v is shared by $($counts[$v]) rules; this one is named $($r.DisplayId)"
        } else {
            $r.DisplayId = $v
        }
    }
}

function Read-OneBenchmark($Root, [string]$Ns, [string]$SourceName) {
    $release = ''
    foreach ($pt in $Root.ChildNodes) {
        if ($pt.LocalName -eq 'plain-text' -and $pt.GetAttribute('id') -eq 'release-info') {
            $release = ('' + $pt.InnerText).Trim()
        }
    }
    $statusDate = ''
    foreach ($st in $Root.ChildNodes) {
        if ($st.LocalName -eq 'status' -and $st.NamespaceURI -eq $Ns) {
            $statusDate = '' + $st.GetAttribute('date'); break
        }
    }
    $edition = 'manual'
    if ($Ns -eq $script:XccdfNamespaces[1]) { $edition = 'scap' }
    $rules = New-Object System.Collections.ArrayList
    $defaulted = New-Object System.Collections.ArrayList
    $benchLabel = Remove-ScapPrefix $Root.GetAttribute('id'); if (-not $benchLabel) { $benchLabel = '(no id)' }
    $mgr = New-Object System.Xml.XmlNamespaceManager($Root.OwnerDocument.NameTable)
    $mgr.AddNamespace('x', $Ns)
    foreach ($group in $Root.SelectNodes('.//x:Group', $mgr)) {
        # Every Rule in a Group becomes a rule (2.0.0; earlier builds read the first
        # only). A multi-rule Group shares its V- id, so those rules are named by
        # V-id/rule id (Set-UniqueRuleIds) to keep names unique.
        $groupRules = @($group.SelectNodes('x:Rule', $mgr))
        if ($groupRules.Count -eq 0) { continue }
        $vulnId = Remove-ScapPrefix $group.GetAttribute('id')
        $vulnShown = $vulnId; if (-not $vulnShown) { $vulnShown = '(no id)' }
        $srgId = Get-XmlText $group 'title' $Ns
        if ($groupRules.Count -gt 1) {
            Write-ToolLog parse info "${benchLabel}: group $vulnShown holds $($groupRules.Count) rules; each becomes its own rule"
        }
        foreach ($rule in $groupRules) {
            $index = $rules.Count + 1
            $title = Get-XmlText $rule 'title' $Ns
            $ruleId = Remove-ScapPrefix $rule.GetAttribute('id')
            if (-not $ruleId) {
                $ruleId = Get-NoIdRuleId $title $index
                Write-ToolLog parse warn ("${benchLabel}: rule $index in group $vulnShown has no id; using the " +
                    "deterministic id $ruleId (from its title and position)")
            }
            $sevInfo = Get-NormalizedSeverity $rule.GetAttribute('severity')
            if ($sevInfo.Note) {
                [void]$defaulted.Add("$ruleId ($($sevInfo.Note))")
                Write-ToolLog parse debug "${benchLabel}: $ruleId severity $($sevInfo.Note); imported as medium"
            }
            $desc = Get-XmlText $rule 'description' $Ns
            $checkContent = ''
            $ovalRef = ''
            $check = $rule.SelectSingleNode('x:check', $mgr)
            if ($null -ne $check) {
                $cc = $check.SelectSingleNode('x:check-content', $mgr)
                if ($null -ne $cc) { $checkContent = ('' + $cc.InnerText).Trim() }
                $ref = $check.SelectSingleNode('x:check-content-ref', $mgr)
                if ($null -ne $ref -and ('' + $ref.GetAttribute('name')).StartsWith('oval:')) {
                    $ovalRef = $ref.GetAttribute('name')
                }
            }
            $ccis = New-Object System.Collections.ArrayList
            $legacy = New-Object System.Collections.ArrayList
            foreach ($ident in $rule.SelectNodes('x:ident', $mgr)) {
                $identText = ('' + $ident.InnerText).Trim()
                if (-not $identText) { continue }
                $system = '' + $ident.GetAttribute('system')
                if ($system.EndsWith('/cci')) { [void]$ccis.Add($identText) }
                elseif ($system.EndsWith('/legacy')) { [void]$legacy.Add($identText) }
            }
            $sections = New-Object System.Collections.ArrayList
            foreach ($pair in $script:DescriptionSections) {
                $body = Get-PseudoTag $desc $pair[0]
                if ($body) { [void]$sections.Add(@($pair[1], $body)) }
            }
            [void]$rules.Add(@{
                VulnId       = $vulnId
                RuleId       = $ruleId
                StigId       = Get-XmlText $rule 'version' $Ns
                Severity     = $sevInfo.Severity
                Title        = $title
                Discussion   = Get-PseudoTag $desc 'VulnDiscussion'
                CheckContent = $checkContent
                OvalRef      = $ovalRef
                FixText      = Get-XmlText $rule 'fixtext' $Ns
                Ccis         = @($ccis)
                LegacyIds    = @($legacy)
                SrgId        = $srgId
                Sections     = @($sections)
            })
        }
    }
    if ($defaulted.Count -gt 0) {
        $shown = (@($defaulted)[0..([Math]::Min(10, $defaulted.Count) - 1)]) -join ', '
        if ($defaulted.Count -gt 10) { $shown += ", and $($defaulted.Count - 10) more" }
        Write-ToolLog parse warn ("${benchLabel}: $($defaulted.Count) rule(s) had a missing or unrecognized " +
            "severity and were imported as medium: $shown")
    }
    Set-UniqueRuleIds $rules $benchLabel
    $benchmark = @{
        Source      = $SourceName
        BenchmarkId = Remove-ScapPrefix $Root.GetAttribute('id')
        Title       = Get-XmlText $Root 'title' $Ns
        Version     = Get-XmlText $Root 'version' $Ns
        Release     = $release
        StatusDate  = $statusDate
        Edition     = $edition
        Rules       = @($rules)
    }
    $bid = $benchmark.BenchmarkId; if (-not $bid) { $bid = '(no id)' }
    $rel = $release; if (-not $rel) { $rel = 'no release info' }
    Write-ToolLog parse info ("benchmark $bid `"$($benchmark.Title)`" V$($benchmark.Version) ($rel), " +
        "$edition edition, $($rules.Count) rule(s), from $SourceName")
    return $benchmark
}

function Get-ReleaseKey($Benchmark) {
    # Python release_key: @(version, release) as integers, -1 when unknown. The
    # version is a whole-number <version>, the release the N of "Release: N"; either
    # one missing falls back to the VnRm in the source file name.
    $rawVersion = ([string]$Benchmark.Version).Trim()
    $version = -1
    if ($rawVersion -cmatch '^[0-9]{1,9}\z') { $version = [int]$rawVersion }
    $release = -1
    $m = [regex]::Match([string]$Benchmark.Release, 'Release:\s*([0-9]{1,9})(?![0-9])', 'IgnoreCase')
    if ($m.Success) { $release = [int]$m.Groups[1].Value }
    if ($version -lt 0 -or $release -lt 0) {
        $n = [regex]::Match([string]$Benchmark.Source, '(?<![A-Za-z0-9])V([0-9]{1,9})R([0-9]{1,9})(?![0-9])', 'IgnoreCase')
        if ($n.Success) {
            if ($version -lt 0) { $version = [int]$n.Groups[1].Value }
            if ($release -lt 0) { $release = [int]$n.Groups[2].Value }
        }
    }
    return , @($version, $release)
}

function Format-ReleaseKey($Key) {
    $v = '?'; if ($Key[0] -ge 0) { $v = [string]$Key[0] }
    $r = '?'; if ($Key[1] -ge 0) { $r = [string]$Key[1] }
    return "V${v}R${r}"
}

function Get-DedupeEdition($Benchmark) {
    # Python dedupe_edition: XCCDF 1.2 is SCAP, and so is XCCDF 1.1 whose every rule
    # carries an OVAL reference and no check prose.
    if ($Benchmark.Edition -eq 'scap') { return 'scap' }
    $rules = @($Benchmark.Rules)
    if ($rules.Count -eq 0) { return 'manual' }
    foreach ($r in $rules) { if (-not $r.OvalRef -or $r.CheckContent) { return 'manual' } }
    return 'scap'
}

function Compare-BenchmarkRank($A, $B) {
    # 1 when $A outranks $B (higher version, then release, then manual over SCAP), else 0.
    $ka = Get-ReleaseKey $A; $kb = Get-ReleaseKey $B
    for ($i = 0; $i -lt 2; $i++) {
        if ($ka[$i] -gt $kb[$i]) { return 1 }
        if ($ka[$i] -lt $kb[$i]) { return 0 }
    }
    if ((Get-DedupeEdition $A) -eq 'manual' -and (Get-DedupeEdition $B) -eq 'scap') { return 1 }
    return 0
}

function Select-UniqueBenchmarks($Benchmarks) {
    # Python _dedupe_benchmarks: one benchmark per id, the highest release, manual over
    # SCAP at the same release. Every drop is a warning, and so is a benchmark present
    # only in its SCAP edition.
    $groups = [ordered]@{}
    foreach ($b in $Benchmarks) {
        $key = $b.BenchmarkId; if (-not $key) { $key = $b.Title }
        if (-not $groups.Contains($key)) { $groups[$key] = New-Object System.Collections.ArrayList }
        [void]$groups[$key].Add($b)
    }
    $kept = New-Object System.Collections.ArrayList
    foreach ($key in @($groups.Keys)) {
        $items = @($groups[$key])
        $best = $items[0]
        for ($i = 1; $i -lt $items.Count; $i++) {
            if ((Compare-BenchmarkRank $items[$i] $best) -eq 1) { $best = $items[$i] }
        }
        $allScap = $true
        foreach ($b in $items) {
            if ((Get-DedupeEdition $b) -ne 'scap') { $allScap = $false }
            if ([object]::ReferenceEquals($b, $best)) { continue }
            Write-ToolLog parse warn ("dedupe ${key}: kept $(Format-ReleaseKey (Get-ReleaseKey $best)) " +
                "$(Get-DedupeEdition $best) edition from $($best.Source), dropped " +
                "$(Format-ReleaseKey (Get-ReleaseKey $b)) $(Get-DedupeEdition $b) edition from $($b.Source)")
        }
        if ($allScap) {
            Write-ToolLog parse warn ("only the SCAP edition of $key is present ($($best.Source)): its rules " +
                'carry OVAL references instead of check prose, and a SCAP benchmark can leave out rules ' +
                'that cannot be automated; use the manual STIG for the full rule set')
        }
        [void]$kept.Add($best)
    }
    return , @($kept)
}

# Zip input limits (Python ZIP_MEMBER_MAX, ZIP_TOTAL_MAX, ZIP_NEST_MAX): a member whose
# uncompressed size is over the member limit is skipped, reading past the total limit
# refuses the whole input, and zips nest at most two levels deep; all are logged.
$script:ZipMemberMax = 200MB
$script:ZipTotalMax = 1GB
$script:ZipNestMax = 2

function Skip-ZipMember([string]$Label, [string]$Why) {
    # Every skipped member is a warning, except the XCCDF stylesheet DISA ships in
    # every package, which is expected and only noted.
    $level = 'warn'; if ($Label -match '\.xsl$') { $level = 'info' }
    Write-ToolLog parse $level "skipped ${Label}: $Why"
}

function Read-ZipEntryBytes($Entry, [long]$Max) {
    # The entry's bytes, read in chunks and never more than $Max + 1 of them, so a
    # member whose declared size understates its content cannot exhaust memory.
    $ms = New-Object System.IO.MemoryStream
    $s = $Entry.Open()
    try {
        $buf = New-Object byte[] 65536
        while ($true) {
            $n = $s.Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            $ms.Write($buf, 0, $n)
            if ($ms.Length -gt $Max) { throw "the member holds more than its declared $($Entry.Length) bytes" }
        }
    } finally { $s.Dispose() }
    return , $ms.ToArray()
}

function Read-StigZip($Archive, [string]$Prefix, [int]$Depth, $Budget, $Out) {
    # Python _read_zip: parse every XCCDF member, recursing into nested zips.
    # Ordinal order by full name, as Python sorts (a stable sort keeps duplicates in
    # archive order). [Array]::Sort(keys, items) would sort a converted copy of the
    # items, so the names are sorted alone and mapped back.
    $byName = New-Object 'System.Collections.Generic.Dictionary[string,System.Collections.ArrayList]' ([System.StringComparer]::Ordinal)
    foreach ($e in $Archive.Entries) {
        if (-not $byName.ContainsKey($e.FullName)) { $byName[$e.FullName] = New-Object System.Collections.ArrayList }
        [void]$byName[$e.FullName].Add($e)
    }
    $names = [string[]]@($byName.Keys)
    [Array]::Sort($names, [System.StringComparer]::Ordinal)
    $entries = @(foreach ($n in $names) { $byName[$n] })
    foreach ($entry in $entries) {
        if (-not $entry.Name) { continue }   # a directory entry
        $label = $Prefix + $entry.FullName
        $isXml = $entry.Name -match '\.xml$'
        $isZip = $entry.Name -match '\.zip$'
        if (-not $isXml -and -not $isZip) {
            if ($entry.Name -match '\.xsl$') { Skip-ZipMember $label 'the XCCDF stylesheet, not data' }
            else { Skip-ZipMember $label 'not an .xml or .zip member (document or other content)' }
            continue
        }
        if ($isZip -and $Depth -ge $script:ZipNestMax) {
            Skip-ZipMember $label "a zip nested more than $($script:ZipNestMax) levels deep is not read"
            continue
        }
        if ($entry.Length -gt $script:ZipMemberMax) {
            Skip-ZipMember $label "refused: $($entry.Length) bytes uncompressed is over the $($script:ZipMemberMax)-byte member limit"
            continue
        }
        if ($Budget[0] + $entry.Length -gt $script:ZipTotalMax) {
            $reason = "refused: reading $label would take the input past the $($script:ZipTotalMax)-byte total limit for zip members"
            Write-ToolLog parse warn $reason
            throw $reason
        }
        try { $bytes = Read-ZipEntryBytes $entry ([long]$entry.Length) }
        catch {
            $e = $_.Exception; while ($e.InnerException) { $e = $e.InnerException }
            Skip-ZipMember $label "the member cannot be read ($($e.Message))"
            continue
        }
        $Budget[0] += $bytes.Length
        if ($isXml) {
            foreach ($b in (ConvertFrom-BenchmarkXml $bytes $entry.Name)) { [void]$Out.Add($b) }
            continue
        }
        # Compilation zips (SRG-STIG Library) nest one zip per STIG, and those can
        # nest one zip per edition.
        $ms = New-Object System.IO.MemoryStream(, $bytes)
        try { $inner = New-Object System.IO.Compression.ZipArchive($ms) }
        catch {
            $e = $_.Exception; while ($e.InnerException) { $e = $e.InnerException }
            Skip-ZipMember $label "not a readable zip ($($e.Message))"
            $ms.Dispose()
            continue
        }
        Write-ToolLog parse info "nested zip $label (level $($Depth + 1)): reading its members"
        try { Read-StigZip $inner ($label + '/') ($Depth + 1) $Budget $Out }
        finally { $inner.Dispose(); $ms.Dispose() }
    }
}

function Get-StigBenchmarks([string]$SourcePath) {
    # Zip, directory, .xml, or .xsl (resolves the benchmark XML next to it).
    # Discovery is by content, not filename; zips nest up to two levels deep; one
    # benchmark id keeps its highest release, manual over SCAP (Select-UniqueBenchmarks).
    $benchmarks = New-Object System.Collections.ArrayList
    $addXml = {
        param($Bytes, $Name)
        foreach ($b in (ConvertFrom-BenchmarkXml $Bytes $Name)) { [void]$benchmarks.Add($b) }
    }
    if (Test-Path -LiteralPath $SourcePath -PathType Container) {
        Write-ToolLog parse info "input ${SourcePath}: directory"
        foreach ($f in Get-ChildItem -LiteralPath $SourcePath -Recurse -File) {
            if ($f.Name -match '\.xml$') {
                & $addXml ([System.IO.File]::ReadAllBytes($f.FullName)) $f.Name
            } elseif ($f.Name -match '\.xsl$') {
                Skip-ZipMember $f.Name 'the XCCDF stylesheet, not data'
            } else {
                Skip-ZipMember $f.Name 'not an .xml file'
            }
        }
    } elseif ($SourcePath -match '\.(zip)$') {
        Write-ToolLog parse info "input ${SourcePath}: zip ($((Get-Item -LiteralPath $SourcePath).Length) bytes)"
        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($SourcePath)
        try { Read-StigZip $zip '' 0 ([long[]]@(0)) $benchmarks }
        finally { $zip.Dispose() }
    } elseif ($SourcePath -match '\.xml$') {
        Write-ToolLog parse info "input ${SourcePath}: XML file"
        & $addXml ([System.IO.File]::ReadAllBytes($SourcePath)) (Split-Path -Leaf $SourcePath)
    } elseif ($SourcePath -match '\.xsl$') {
        Write-ToolLog parse info "input ${SourcePath}: stylesheet; reading the XML files next to it"
        foreach ($f in Get-ChildItem -LiteralPath (Split-Path -Parent $SourcePath) -Filter '*.xml') {
            & $addXml ([System.IO.File]::ReadAllBytes($f.FullName)) $f.Name
        }
    } else {
        Write-ToolLog parse warn "refused ${SourcePath}: not a zip, directory, or XCCDF .xml file"
        throw "$SourcePath is not a zip, directory, or XCCDF .xml file"
    }
    $kept = Select-UniqueBenchmarks $benchmarks
    if ($kept.Count -eq 0) {
        Write-ToolLog parse warn "${SourcePath}: no XCCDF benchmark found inside"
        throw "$SourcePath contains no XCCDF benchmark"
    }
    Write-ToolLog parse info "${SourcePath}: $($kept.Count) benchmark(s) after dedupe"
    return , @($kept)   # unary comma: stay an array even with one benchmark
}

# =========================================================================
# Target detection: network vendors -> NCM; server OSes -> SCM
# =========================================================================
$script:NetworkVendors = [ordered]@{
    'cisco' = 'Cisco'; 'ios ' = 'Cisco'; 'ios_' = 'Cisco'; 'nx-os' = 'Cisco'
    'asa' = 'Cisco'; 'juniper' = 'Juniper'; 'junos' = 'Juniper'; 'arista' = 'Arista'
    'palo alto' = 'Palo Alto'; 'palo_alto' = 'Palo Alto'; 'paloalto' = 'Palo Alto'
    'f5 ' = 'F5'; 'f5_' = 'F5'; 'big-ip' = 'F5'; 'bigip' = 'F5'
    'fortinet' = 'Fortinet'; 'fortigate' = 'Fortinet'; 'brocade' = 'Brocade'
    'check point' = 'Check Point'; 'checkpoint' = 'Check Point'
    'arubaos' = 'Aruba'; 'aruba' = 'Aruba'; 'extreme' = 'Extreme'
    'huawei' = 'Huawei'; 'dell os10' = 'Dell'
    'router' = ''; 'switch' = ''; 'firewall' = ''; 'network device' = ''
}
# keyword -> @(display OS name, SWQL filter for assignment, OS family for $script:ScmProbes)
$script:ServerOses = [ordered]@{
    'red hat'    = @('Red Hat Enterprise Linux', "MachineType LIKE '%Red Hat%'", 'linux')
    'rhel'       = @('Red Hat Enterprise Linux', "MachineType LIKE '%Red Hat%'", 'linux')
    'ubuntu'     = @('Ubuntu', "MachineType LIKE '%Ubuntu%'", 'linux')
    'debian'     = @('Debian', "MachineType LIKE '%Debian%'", 'linux')
    'centos'     = @('CentOS', "MachineType LIKE '%CentOS%'", 'linux')
    'linux'      = @('Linux', "MachineType LIKE '%Linux%'", 'linux')
    'windows'    = @('Windows', "MachineType LIKE '%Windows%'", 'windows')
    'sql server' = @('Windows', "MachineType LIKE '%Windows%'", 'windows')
    'iis'        = @('Windows', "MachineType LIKE '%Windows%'", 'windows')
    'exchange'   = @('Windows', "MachineType LIKE '%Windows%'", 'windows')
}
$script:UnknownServerOs = @('(OS not recognized)', "MachineType LIKE '%'", 'unknown')

function Resolve-StigTarget($Benchmarks, [string]$SourceName) {
    $text = ($SourceName + ' ' + (($Benchmarks | ForEach-Object { $_.Title + ' ' + $_.Source }) -join ' ')).ToLower()
    foreach ($kw in $script:ServerOses.Keys) {
        if ($text.Contains($kw)) {
            Write-ToolLog route info "server keyword '$kw' matched in the file/benchmark names -> server ($($script:ServerOses[$kw][0]), OS family $($script:ServerOses[$kw][2]))"
            return @('server', $script:ServerOses[$kw])
        }
    }
    $vendor = ''
    $matched = New-Object System.Collections.ArrayList
    foreach ($kw in $script:NetworkVendors.Keys) {
        if ($text.Contains($kw)) {
            [void]$matched.Add("'$kw'")
            if ($script:NetworkVendors[$kw]) { $vendor = $script:NetworkVendors[$kw]; break }
        }
    }
    if ($matched.Count -gt 0) {
        $shown = $vendor; if (-not $shown) { $shown = '(not identified)' }
        Write-ToolLog route info ("network keyword(s) " + ($matched -join ', ') + " matched -> network, vendor $shown")
        return @('network', $vendor)
    }
    Write-ToolLog route info 'no server or network keyword matched the file/benchmark names'
    return @($null, $null)
}

# =========================================================================
# NCM: reports (one per benchmark), console/wire XML, node selection
# =========================================================================
function Get-DeterministicGuid([string]$Seed) {
    # RFC 4122 version-5 UUID in the URL namespace - byte-identical to Python's
    # uuid.uuid5(uuid.NAMESPACE_URL, seed), so both editions of this tool derive
    # the same RuleId for the same STIG rule.
    $nsBytes = [byte[]](0x6b, 0xa7, 0xb8, 0x11, 0x9d, 0xad, 0x11, 0xd1,
                        0x80, 0xb4, 0x00, 0xc0, 0x4f, 0xd4, 0x30, 0xc8)
    $seedBytes = [System.Text.Encoding]::UTF8.GetBytes($Seed)
    $all = New-Object byte[] ($nsBytes.Length + $seedBytes.Length)
    [Array]::Copy($nsBytes, $all, $nsBytes.Length)
    [Array]::Copy($seedBytes, 0, $all, $nsBytes.Length, $seedBytes.Length)
    $hash = [System.Security.Cryptography.SHA1]::Create().ComputeHash($all)
    $b = $hash[0..15]
    $b[6] = ($b[6] -band 0x0F) -bor 0x50
    $b[8] = ($b[8] -band 0x3F) -bor 0x80
    # uuid text fields are big-endian; [guid]::new(byte[]) treats the first
    # three groups as little-endian, so format the hex string directly.
    $hex = -join ($b | ForEach-Object { $_.ToString('x2') })
    return ('{0}-{1}-{2}-{3}-{4}' -f $hex.Substring(0, 8), $hex.Substring(8, 4),
        $hex.Substring(12, 4), $hex.Substring(16, 4), $hex.Substring(20, 12))
}

function Get-PickerVendor([string]$Where) {
    # The Vendor value a WHERE fragment compares with ('' doubled quotes undone, one
    # leading and trailing % dropped), or $null (Python picker_vendor).
    $m = [regex]::Match([string]$Where, "\bVendor\s*(?:=|LIKE)\s*'((?:[^']|'')*)'",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $m.Success) { return $null }
    $value = $m.Groups[1].Value.Replace("''", "'")
    if ($value.StartsWith('%')) { $value = $value.Substring(1) }
    if ($value.EndsWith('%')) { $value = $value.Substring(0, $value.Length - 1) }
    if (-not $value -or $value.Contains('%')) { return $null }
    return $value
}

function ConvertTo-XmlText([string]$Value) {
    # Escape a value for XML element text (&, <, >), as XmlSerializer writes it.
    return $Value.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
}

function New-NodeSelectionString([string]$Where) {
    # The format real 2026.2.2 console exports carry: WebCriteria:<picker
    # XML>SQL:Where (...) - bare column names (Vendor, not Nodes.Vendor).
    # Joined with explicit LF so the bytes match the Python edition whatever
    # line endings this file is checked out with.
    # The picker state is Vendor-only by design: a MachineType condition (the Cisco
    # platform scope) lives in the SQL part alone, which is what NCM filters on.
    $w = ($Where -replace '\bNodes\.', '').Trim()
    if (-not $w.ToLower().StartsWith('(')) { $w = "($w)" }
    $criteria = ''
    $vendor = Get-PickerVendor $w
    if ($vendor) {
        $id = Get-DeterministicGuid ("stig2ncm-criteria:" + $vendor)
        $criteria = (@(
            '<?xml version="1.0" encoding="utf-16"?>',
            '<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
            '  <WebSelectionCriteria>',
            "    <Id>$id</Id>",
            '    <LogicalCondition />',
            '    <SelectedColumn>Vendor</SelectedColumn>',
            '    <MatchType>=</MatchType>',
            "    <SelectedValue>$(ConvertTo-XmlText $vendor)</SelectedValue>",
            '  </WebSelectionCriteria>',
            '</ArrayOfWebSelectionCriteria>') -join "`n")
    }
    return "WebCriteria:${criteria}SQL:Where $w "
}

function New-NodeSelectionCriterias([string]$Where) {
    # Python make_node_selection_criterias: the typed twin of the string form, as
    # the 2026.4.0 server returns it from GetPolicy (CriteriaType 2 = web picker, the
    # same Vendor criterion and Id as the XML). AddPolicy with this member null
    # failed on that server behind an opaque NcmFaultContract. $null without a vendor.
    $w = ($Where -replace '\bNodes\.', '').Trim()
    if (-not $w.ToLower().StartsWith('(')) { $w = "($w)" }
    $vendor = Get-PickerVendor $w
    if (-not $vendor) { return $null }
    return [ordered]@{
        DesktopSelectionCriteriasDbString = $null
        WebSelectionCriterias = @([ordered]@{
            Id = Get-DeterministicGuid ("stig2ncm-criteria:" + $vendor)
            LogicalCondition = ''
            SelectedColumn = 'Vendor'
            MatchType = '='
            SelectedValue = $vendor
        })
        AssignedNodesList = @()
        AssignedNodesDesktopSQL = $null
        CriteriaType = 2
    }
}

# XCCDF severity -> NCM ErrorLevel. The console's default names for 2/1/0 are
# critical/warning/info, but the names are editable per server.
$script:SeverityToErrorLevel = @{ high = 2; medium = 1; low = 0 }
# Generated text that must match the Python edition byte for byte but cannot be
# written literally in this ASCII-only file.
$script:EmDash = [string][char]0x2014

function Limit-Text([string]$Text, [int]$Max = 250) {
    # Python's text[:Max]: counts code points, not UTF-16 units, so a surrogate pair
    # is never split and both editions cut a name at the same character (2.0.0).
    if ($null -eq $Text) { return '' }
    if ($Text.Length -le $Max) { return $Text }
    $units = 0; $points = 0
    while ($units -lt $Text.Length -and $points -lt $Max) {
        if ([char]::IsHighSurrogate($Text[$units]) -and $units + 1 -lt $Text.Length -and
            [char]::IsLowSurrogate($Text[$units + 1])) { $units += 2 } else { $units += 1 }
        $points++
    }
    return $Text.Substring(0, $units)
}

function Get-NcmPolicyId($Benchmark, [string]$Suffix = '_v1') {
    # Same seed as the Python edition: the benchmark id, or the title when the
    # benchmark has no id, then the version suffix. Builds before this one
    # concatenated id + title; builds before 2.0.0 had no suffix.
    $key = $Benchmark.BenchmarkId; if (-not $key) { $key = $Benchmark.Title }
    return Get-DeterministicGuid ('stig2ncm-policy:' + $key + $Suffix)
}

function Get-ScmPolicyUniqueId($Benchmark, [string]$Suffix = '_v1') {
    $key = $Benchmark.BenchmarkId; if (-not $key) { $key = $Benchmark.Title }
    return Get-DeterministicGuid ('stig2ncm-scm:' + $key + $Suffix)
}

function Get-ScmRuleUniqueId($Rule, [string]$Suffix = '_v1') {
    return Get-DeterministicGuid ('stig2ncm-scm-rule:' + $Rule.RuleId + $Suffix)
}

function Get-ScmPolicyName($Benchmark, [string]$Suffix = '_v1') {
    return Get-SuffixedName "$($Benchmark.Title) V$($Benchmark.Version) ($($Benchmark.Release))" $Suffix
}

# Python POLICY_NAME_LIMIT / ncm_policy_name: an NCM policy name longer than this is
# shortened to "<title> V<version> R<release>" before the suffix; names that fit are
# unchanged. The column's width is not published; SolarWinds' longest shipped name is 64.
$script:PolicyNameLimit = 100

function Get-NcmSafeName([string]$Text) {
    # Python ncm_safe_name: NCM's AddPolicyRule refuses a name holding a comma
    # ("Policy name contains comma character"); every comma becomes " -" and runs
    # of spaces are collapsed.
    $cleaned = ([string]$Text) -replace '\s*,', ' -'
    return (($cleaned -replace ' {2,}', ' ')).Trim()
}

function Get-NcmPolicyName($Benchmark, [string]$Suffix = '_v1') {
    $title = Get-NcmSafeName $Benchmark.Title
    $full = Get-SuffixedName "$title V$($Benchmark.Version) ($(Get-NcmSafeName $Benchmark.Release))" $Suffix
    if ($full.Length -le $script:PolicyNameLimit) { return $full }
    $m = [regex]::Match([string]$Benchmark.Release, 'Release:\s*(\d+)')
    $short = "$title V$($Benchmark.Version)"
    if ($m.Success) { $short += " R$($m.Groups[1].Value)" }
    return Get-SuffixedName $short $Suffix $script:PolicyNameLimit
}

function Get-ReportBaseName([string]$SourcePath, [string]$ReportName) {
    # Python build_reports: an explicit name wins; otherwise a zip's file name;
    # otherwise nothing, so each report is named after its benchmark title.
    if ($ReportName) { return $ReportName }
    if ($SourcePath -and $SourcePath.ToLower().EndsWith('.zip')) {
        # Split on both separators: .NET on Linux/macOS treats a backslash as an
        # ordinary character, and a Windows-style path can still reach PowerShell 7 there.
        $leaf = ($SourcePath -split '[\\/]')[-1]
        return $leaf.Substring(0, $leaf.Length - 4)
    }
    return ''
}
$script:ConfigTokens = @('aaa ', 'ip ', 'ipv6 ', 'line ', 'snmp-server ', 'ntp ', 'logging ',
    'login ', 'banner ', 'crypto ', 'interface ', 'router ', 'access-list ', 'username ',
    'service ', 'no ', 'hostname ', 'enable ', 'archive', 'clock ', 'boot ', 'transport ')

# NCM reads a `Like` pattern literally unless the advanced setting
# ComplianceRulesWildcardsEnabled is turned on, which it is not by default
# (NCM 2023.1.1 and later), so a pattern carrying * or ? means one thing on a
# stock server and another on a tuned one. Such patterns are emitted as an
# escaped Regex instead. The escaping is written out explicitly rather than
# using [regex]::Escape so it matches the Python edition byte for byte.
$script:RegexMetacharacters = '\^$.|?*+()[]{}'

function ConvertTo-EscapedRegex([string]$Text) {
    $out = New-Object System.Text.StringBuilder
    foreach ($ch in $Text.ToCharArray()) {
        if ($script:RegexMetacharacters.IndexOf($ch) -ge 0) { [void]$out.Append('\') }
        [void]$out.Append($ch)
    }
    return $out.ToString()
}

# SolarWinds documents one flat limit on the whole feature: a policy report
# cannot be run against a config that was downloaded in XML format. Palo Alto is
# the vendor that hits it by default, and the failure is silent - the rules
# import, cache, and then report nothing at all - so it is worth saying before
# the import rather than after a day of empty results.
function Get-XmlConfigWarning([string]$Where) {
    $lowered = ([string]$Where).ToLower()
    foreach ($v in @('palo alto', 'paloalto', 'panorama')) {
        if ($lowered.Contains($v)) {
            Write-ToolLog scope warn ("node scope $Where selects devices whose configs back up as " +
                'XML; NCM policy reports cannot evaluate XML configs')
            return '[NCM] warning: NCM policy reports cannot be run against ' +
                'configurations downloaded in XML format, which is how Palo Alto ' +
                'devices back up unless the config type is changed. The report will ' +
                'import and cache normally and then report no violations at all, ' +
                'which reads like compliance. Confirm those nodes have a text config ' +
                'of the selected type, or route this benchmark to SCM instead.'
        }
    }
    return $null
}

# -Mode heuristic (2.0.0): a draft pattern is emitted only when the check text says
# plainly whether a config line must be present or absent. The expressions are the
# Python edition's (_HX_*), so both editions draft the same rules.
$script:HxOptions = [System.Text.RegularExpressions.RegexOptions]'IgnoreCase, CultureInvariant'
$script:HxLines = '\r\n|\r|\n'
$script:HxSentenceSplit = '(?<=[.!?])\s+(?=[A-Z"''(])'
$script:HxPlaceholder = '<[^<>]*>'
$script:HxFinding = '\bthis is a finding\b'
$script:HxIfClause = '\bif\b(.*?)\bthis is a finding\b'
$script:HxNegCue = '\bmust not\b|\b(?:is|are) not permitted\b'
$script:HxNegation = '\bnot\b|n''t\b|\bmissing\b|\babsent\b|\bwithout\b|\bfails?\b'
$script:HxDisabling = '\bdisabled?\b|\bremoved?\b|\bdeleted?\b|\bturned off\b|\bshut ?down\b'
$script:HxQuoted = '["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]|''([^'']+)'''
$script:HxSubject = '^\s*(?:the\s+)?(?:command\s+)?(.+?)\s+(?:is|are)\b'

function Get-HxConfigLine([string]$Text) {
    # Python _hx_config_line: the text stripped when it reads as one config command.
    $t = ([string]$Text).Trim()
    if (-not $t -or $t.Length -gt 200) { return $null }
    foreach ($end in @(':', '.', '?', ',', ';')) { if ($t.EndsWith($end, [StringComparison]::Ordinal)) { return $null } }
    if ([regex]::IsMatch($t, $script:HxPlaceholder) -or $t.Contains('\*') -or $t.Contains('"')) { return $null }
    foreach ($tok in $script:ConfigTokens) {
        if ($t.StartsWith($tok, [StringComparison]::Ordinal)) { return $t }
    }
    return $null
}

function Get-HxNorm([string]$Text) {
    return [regex]::Replace(([string]$Text).ToLowerInvariant(), '[^a-z0-9./]+', ' ').Trim()
}

function Get-HxSentences([string]$Text) {
    $out = New-Object System.Collections.ArrayList
    foreach ($line in [regex]::Split([string]$Text, $script:HxLines)) {
        foreach ($part in [regex]::Split($line.Trim(), $script:HxSentenceSplit)) {
            if ($part.Trim()) { [void]$out.Add($part.Trim()) }
        }
    }
    return , @($out)
}

function Get-HxPolarity([string]$Sentence) {
    # Python _hx_polarity: @{ Polarity = 'absent' | 'present' | $null; Cond }.
    if ([regex]::IsMatch($Sentence, $script:HxFinding, $script:HxOptions)) {
        $m = [regex]::Match($Sentence, $script:HxIfClause, $script:HxOptions)
        if (-not $m.Success) { return @{ Polarity = $null; Cond = $null } }
        $cond = $m.Groups[1].Value
        if ([regex]::IsMatch($cond, $script:HxDisabling, $script:HxOptions)) { return @{ Polarity = $null; Cond = $cond } }
        $p = 'absent'; if ([regex]::IsMatch($cond, $script:HxNegation, $script:HxOptions)) { $p = 'present' }
        return @{ Polarity = $p; Cond = $cond }
    }
    if ([regex]::IsMatch($Sentence, $script:HxNegCue, $script:HxOptions)) {
        $rest = [regex]::Replace($Sentence, $script:HxNegCue, ' ', $script:HxOptions)
        if ([regex]::IsMatch($rest, $script:HxDisabling, $script:HxOptions) -or
            [regex]::IsMatch($rest, $script:HxNegation, $script:HxOptions)) { return @{ Polarity = $null; Cond = $null } }
        return @{ Polarity = 'absent'; Cond = $null }
    }
    return @{ Polarity = $null; Cond = $null }
}

function Get-HxReferent([string]$Sentence, $Cond, $Candidates) {
    # Python _hx_referent: @{ Line; How } for the config line the sentence is about.
    foreach ($m in [regex]::Matches($Sentence, $script:HxQuoted)) {
        $inner = $m.Groups[2].Value; if ($m.Groups[1].Success) { $inner = $m.Groups[1].Value }
        $line = Get-HxConfigLine $inner
        if ($line) { return @{ Line = $line; How = 'quoted in the sentence' } }
    }
    if ($null -ne $Cond) {
        $sm = [regex]::Match([string]$Cond, $script:HxSubject, $script:HxOptions)
        if ($sm.Success) {
            $line = Get-HxConfigLine $sm.Groups[1].Value
            if ($line) { return @{ Line = $line; How = 'named in the sentence' } }
        }
    }
    $padded = ' ' + (Get-HxNorm $Sentence) + ' '
    $hits = @(@($Candidates) | Where-Object { $n = Get-HxNorm $_; $n -and $padded.Contains(' ' + $n + ' ') })
    if ($hits.Count -gt 0) {
        $longest = ($hits | ForEach-Object { (Get-HxNorm $_).Length } | Measure-Object -Maximum).Maximum
        $best = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
        foreach ($h in $hits) { if ((Get-HxNorm $h).Length -eq $longest) { [void]$best.Add($h) } }
        if ($best.Count -eq 1) { return @{ Line = @($best)[0]; How = 'a config line the sentence mentions' } }
        return @{ Line = $null; How = 'the sentence mentions more than one config line' }
    }
    $distinct = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
    foreach ($c in @($Candidates)) { [void]$distinct.Add($c) }
    if ($distinct.Count -eq 1) { return @{ Line = @($distinct)[0]; How = 'the only config line in the check text' } }
    return @{ Line = $null; How = $null }
}

# -Mode blocks (Python extract_config_blocks / blocks_draft, 2.1.0): the configuration
# example blocks a STIG check text shows become an Advanced Config Search, one "must
# contain" block each, AND-joined, alerting when a block is not found.
$script:CfgProseMarkers = @('this is a finding', ' must ', ' should ', 'verify', 'review', 'ensure',
    'determine', 'configure', 'for example', 'example below', 'as shown', 'note:', 'step ',
    'if the ', 'if a ', 'if an ', 'if any', 'if it ', 'if there', 'the following', 'such as')
$script:CfgKeywords = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
foreach ($kw in @(('interface ip ipv6 no router line access-list deny permit service logging ntp snmp-server aaa ' +
    'username hostname banner crypto class-map policy-map class match set priority bandwidth ' +
    'police control-plane mpls neighbor network vlan spanning-tree switchport shutdown description ' +
    'login exec-timeout transport enable archive boot clock key address-family route-map ' +
    'prefix-list vrf tacacs tacacs-server radius radius-server cns call-home version mls ' +
    'storm-control errdisable cdp lldp vtp dot1x tunnel zone object nat http ssh domain host ' +
    'name-server standby vrrp bgp ospf eigrp isis rip queue shape random-detect management system ' +
    'security password encapsulation lacp channel-group port-channel mac arp dhcp auto exec ' +
    'privilege parser file memory process platform redundancy license ethernet fastethernet ' +
    'gigabitethernet tengigabitethernet loopback end exit ! dns ftp tftp scp sftp telnet ' +
    'object-group route static monitor flow sampler ipv4 pim igmp mld multicast cef mtu speed ' +
    'duplex negotiation auto-cost area passive-interface distribute-list timers authentication ' +
    'accounting authorization session-limit access-class ntp-server source destination permit-all') -split '\s+')) {
    if ($kw) { [void]$script:CfgKeywords.Add($kw) }
}

function Get-ConfigLine([string]$Line) {
    # Python _config_line: the line as a config example line (indentation kept), or $null.
    if ($null -eq $Line -or -not $Line.Trim() -or $Line -match '^\s*(?:\u2026|\.\.\.|\.\s*\.\s*\.)\s*$') { return $null }
    $text = ($Line.TrimEnd()) -replace '\s*(?:\u2026|\.\.\.)\s*$', ''
    $stripped = $text.Trim()
    $lower = $stripped.ToLowerInvariant()
    if ($stripped.EndsWith('.') -or $stripped.EndsWith(':') -or $stripped.EndsWith('?')) { return $null }
    foreach ($m in $script:CfgProseMarkers) { if ($lower.Contains($m)) { return $null } }
    $m = [regex]::Match($text, '^\s*(!|[A-Za-z][A-Za-z0-9-]*)')
    if (-not $m.Success) { return $null }
    $first = $m.Groups[1].Value
    $known = $script:CfgKeywords.Contains($first.ToLowerInvariant())
    $words = @($stripped -split '\s+' | Where-Object { $_ }).Count
    $isLower = ($first -ceq $first.ToLowerInvariant())
    if (-not $known -and -not ($isLower -and $words -le 10)) { return $null }
    if (@('end', 'exit', '!') -contains $first.ToLowerInvariant() -and $words -eq 1) { return $null }
    return $text
}

function Get-ConfigBlocks([string]$CheckContent, [int]$Limit = 10) {
    # Python extract_config_blocks: runs of consecutive config lines, broken by a blank
    # line or prose; identical blocks once; at most $Limit. Each block is a string[].
    $blocks = New-Object System.Collections.ArrayList
    $current = New-Object System.Collections.ArrayList
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    $flush = {
        if ($current.Count -gt 0) {
            $key = (@($current | ForEach-Object { $_.Trim() }) -join "`n")
            if ($seen.Add($key)) { [void]$blocks.Add([string[]]@($current)) }
            $current.Clear()
        }
    }
    foreach ($raw in (([string]$CheckContent) -replace "`r`n", "`n") -split "`n") {
        $line = Get-ConfigLine $raw
        if ($null -eq $line) { & $flush } else { [void]$current.Add($line) }
    }
    & $flush
    if ($blocks.Count -gt $Limit) { return , @($blocks[0..($Limit - 1)]) }
    return , @($blocks)
}

function New-MultiLinePattern([string]$Pattern, [string]$PatternType = 'Like', [bool]$MustContain = $true, [string]$Condition = '') {
    # Python multi_line_pattern: one MultiLineRulePattern in the console's member order.
    return [ordered]@{ EndBracket = ''; PatternType = $PatternType; Condition = $Condition; Pattern = $Pattern
                       Criteria = $MustContain; BeginBracket = ''; IsRegEx = ($PatternType -eq 'Regex') }
}

function New-BlocksDraft([string]$CheckContent) {
    # Python blocks_draft: @{ Patterns; Blocks }.
    $patterns = New-Object System.Collections.ArrayList
    $i = 0
    $all = Get-ConfigBlocks $CheckContent   # one array object; assign, do not wrap in @()
    foreach ($block in @($all)) {
        $cond = ''; if ($i -gt 0) { $cond = 'AND' }
        [void]$patterns.Add((New-MultiLinePattern (@($block) -join "`n") 'Like' $true $cond))
        $i++
    }
    return @{ Patterns = @($patterns); Blocks = $patterns.Count }
}

$script:PatternDraftsSchema = 'disa-stig-tool/pattern-drafts/1'

function Read-PatternDrafts([string]$Path) {
    # Python load_pattern_drafts: @{ <rule id> = @{ MustExist; Note; Patterns | Pattern, Type } }
    # from a pattern-drafts JSON file, validated; $null without a path.
    if (-not $Path) { return $null }
    $raw = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    try { $doc = ConvertFrom-Json $raw } catch { throw "${Path}: not JSON ($($_.Exception.Message))" }
    if ($null -eq $doc -or -not $doc.PSObject.Properties['rules']) { throw "${Path}: not a pattern-drafts file (an object with a `"rules`" object)" }
    if ($doc.PSObject.Properties['schema'] -and $doc.schema -and $doc.schema -ne $script:PatternDraftsSchema) {
        throw "${Path}: schema '$($doc.schema)' is not $($script:PatternDraftsSchema)"
    }
    $drafts = @{}
    foreach ($prop in $doc.rules.PSObject.Properties) {
        $rid = $prop.Name; $d = $prop.Value
        if ($null -eq $d -or $d -is [string]) { throw "${Path}: rule ${rid}: the draft must be an object" }
        if ($d.PSObject.Properties['skip'] -and $d.skip) { continue }
        $mustExist = $true; if ($d.PSObject.Properties['must_exist']) { $mustExist = [bool]$d.must_exist }
        $note = ''; if ($d.PSObject.Properties['note'] -and $d.note) { $note = [string]$d.note }
        $entry = @{ MustExist = $mustExist; Note = $note }
        $hasPatterns = $d.PSObject.Properties['patterns'] -and $null -ne $d.patterns
        $advanced = ($d.PSObject.Properties['advanced'] -and $d.advanced) -or $hasPatterns
        if ($advanced) {
            $pats = @($d.patterns)
            if ($pats.Count -eq 0) { throw "${Path}: rule ${rid}: `"patterns`" must be a non-empty list" }
            $entry.Patterns = New-Object System.Collections.ArrayList
            $i = 0
            foreach ($p in $pats) {
                $pat = ''; if ($p.PSObject.Properties['pattern']) { $pat = [string]$p.pattern }
                if (-not $pat.Trim()) { throw "${Path}: rule ${rid}: pattern $($i + 1) needs a `"pattern`"" }
                $ptype = 'Like'; if ($p.PSObject.Properties['type'] -and $p.type) { $ptype = [string]$p.type }
                $cond = ''; if ($i -gt 0) { $cond = 'AND' }
                if ($p.PSObject.Properties['condition'] -and $p.condition) { $cond = ([string]$p.condition).ToUpperInvariant() }
                if (@('Like', 'Regex') -notcontains $ptype -or @('', 'AND', 'OR') -notcontains $cond) {
                    throw "${Path}: rule ${rid}: pattern $($i + 1): type must be Like or Regex and condition AND, OR or empty"
                }
                $mustContain = $true; if ($p.PSObject.Properties['must_contain']) { $mustContain = [bool]$p.must_contain }
                if ($i -eq 0) { $cond = '' }
                [void]$entry.Patterns.Add((New-MultiLinePattern $pat $ptype $mustContain $cond))
                $i++
            }
            $entry.Patterns = @($entry.Patterns)
        } else {
            $pat = ''; if ($d.PSObject.Properties['pattern']) { $pat = ([string]$d.pattern).Trim() }
            $ptype = 'Like'; if ($d.PSObject.Properties['type'] -and $d.type) { $ptype = [string]$d.type }
            if (-not $pat -or @('Like', 'Regex') -notcontains $ptype) { throw "${Path}: rule ${rid}: needs a `"pattern`" (type Like or Regex) or `"patterns`"" }
            $entry.Pattern = $pat; $entry.Type = $ptype
        }
        $drafts[[string]$rid] = $entry
    }
    Write-ToolLog build info "pattern drafts: $($drafts.Count) rule(s) from $Path"
    return $drafts
}

function Get-RuleDraftOrigin($RuleObj, $Drafts) {
    # Python rule_draft_origin: drafts, blocks, heuristic or sentinel.
    if ($Drafts -and ($Drafts.ContainsKey([string]$RuleObj._vuln_id) -or $Drafts.ContainsKey([string]$RuleObj._display_id))) { return 'drafts' }
    if ($RuleObj.AdvancedMode) { return 'blocks' }
    if (([string]$RuleObj.SimplePatternText).StartsWith('STIG-MANUAL-REVIEW-', [StringComparison]::Ordinal)) { return 'sentinel' }
    return 'heuristic'
}

function Write-PatternDrafts([string]$Path, $Benchmarks, $Reports, $Drafts, [scriptblock]$Log) {
    # Python write_pattern_drafts: every built rule with its id, title, check text, where
    # its pattern came from and the pattern itself, to edit and pass back with -PatternDrafts.
    $source = @{}
    foreach ($b in @($Benchmarks)) { foreach ($r in @($b.Rules)) { $source[[string]$r.VulnId] = $r } }
    $rules = [ordered]@{}
    $counts = @{}
    foreach ($rep in @($Reports)) {
        foreach ($pol in @($rep.AssignedPolicies)) {
            foreach ($ro in @($pol.AssignedPolicyRules)) {
                $src = $source[[string]$ro._vuln_id]
                $key = [string]$ro._display_id; if (-not $key) { $key = [string]$ro._vuln_id }
                $origin = Get-RuleDraftOrigin $ro $Drafts
                $counts[$origin] = 1 + $(if ($counts.ContainsKey($origin)) { $counts[$origin] } else { 0 })
                $entry = [ordered]@{
                    title = [string]$(if ($src) { $src.Title } else { '' })
                    stig_id = [string]$(if ($src) { $src.StigId } else { '' })
                    check_content = [string]$(if ($src) { $src.CheckContent } else { '' })
                    fix_text = [string]$(if ($src) { $src.FixText } else { '' })
                    origin = $origin
                    must_exist = [bool]$ro.PatternMustExist
                    advanced = [bool]$ro.AdvancedMode
                }
                if ($ro.AdvancedMode) {
                    $entry.patterns = @(foreach ($p in @($ro.MultiLineRulePatterns)) {
                        [ordered]@{ pattern = [string]$p.Pattern; type = [string]$p.PatternType; must_contain = [bool]$p.Criteria; condition = [string]$p.Condition } })
                } else {
                    $entry.pattern = [string]$ro.SimplePatternText
                    $entry.type = [string]$ro.PatternType
                }
                $rules[$key] = $entry
            }
        }
    }
    $doc = [ordered]@{
        schema = $script:PatternDraftsSchema
        about = ('Edit a rule''s pattern or patterns (and must_exist), set "skip": true to leave a rule to the run''s own mode, ' +
                 'and pass the file back with --pattern-drafts. Values in the patterns are the STIG''s examples until reviewed.')
        rules = $rules
    }
    [System.IO.File]::WriteAllText($Path, ((ConvertTo-Json -InputObject $doc -Depth 8) -replace "`r`n", "`n") + "`n", $script:Utf8NoBom)
    Add-ToolLogStat 'FilesWritten'
    $summary = (@($counts.Keys | Sort-Object | ForEach-Object { "$($counts[$_]) $_" }) -join ', ')
    Send-Log $Log 'file' 'info' "wrote $([System.IO.Path]::GetFullPath($Path)): pattern drafts for $($rules.Count) rule(s) ($summary); edit and pass back with -PatternDrafts"
    return $Path
}

function Get-HeuristicDraft([string]$CheckContent) {
    # Python heuristic_draft: @{ Pattern; MustExist; Source; How } when one sentence
    # names a config line and says plainly whether it must be present or absent, else
    # @{ Pattern = $null; Reason }, and the rule keeps the manual-review sentinel.
    $candidates = @([regex]::Split([string]$CheckContent, $script:HxLines) |
        ForEach-Object { Get-HxConfigLine $_ } | Where-Object { $_ })
    $stated = $false
    foreach ($sentence in (Get-HxSentences $CheckContent)) {
        $pol = Get-HxPolarity $sentence
        if ($null -eq $pol.Polarity) { continue }
        $stated = $true
        $ref = Get-HxReferent $sentence $pol.Cond $candidates
        if (-not $ref.Line) { continue }
        $line = $ref.Line; $how = $ref.How
        $mustExist = $pol.Polarity -eq 'present'
        if ($line.StartsWith('no ', [StringComparison]::Ordinal)) {
            if (-not $mustExist) { continue }
            $line = Get-HxConfigLine $line.Substring(3)
            $mustExist = $false
            $how += ', inverted from its "no" form'
            if (-not $line) { continue }
        }
        return @{ Pattern = $line; MustExist = $mustExist; Source = $sentence; How = $how }
    }
    if ($candidates.Count -eq 0) { $reason = 'no config line in the check text (only prose, placeholders or escaped *)' }
    elseif (-not $stated) { $reason = 'the check text does not say plainly whether its config line must be present or absent' }
    else { $reason = 'no sentence that states a finding names one config line unambiguously' }
    return @{ Pattern = $null; Reason = $reason }
}

function Test-RuleField($Rule, [string]$Field) {
    # Whether a rule carries a field that older callers (and tests) may leave out,
    # for a hashtable and for an object read from JSON alike (Set-StrictMode 2 refuses
    # a missing property, so it is tested before it is read).
    if ($Rule -is [System.Collections.IDictionary]) { return ($Rule.Contains($Field) -and $null -ne $Rule[$Field]) }
    $prop = $Rule.PSObject.Properties[$Field]
    return ($null -ne $prop -and $null -ne $prop.Value)
}

function Get-RuleReferenceLine($Rule) {
    # Python rule_reference_line.
    $line = "$($Rule.VulnId) / $($Rule.RuleId) / STIG ID $($Rule.StigId)"
    if ($Rule.Ccis.Count -gt 0) { $line += ' / ' + ($Rule.Ccis -join ', ') }
    if ((Test-RuleField $Rule 'SrgId') -and $Rule.SrgId) { $line += ' / SRG ' + $Rule.SrgId }
    if (Test-RuleField $Rule 'LegacyIds') {
        $legacy = @($Rule.LegacyIds | Where-Object { $_ })
        if ($legacy.Count -gt 0) { $line += ' / legacy ' + ($legacy -join ', ') }
    }
    return $line
}

function Get-RuleSections($Rule) {
    # Python rule_sections: @(label, text) pairs; a rule built without Sections falls
    # back to its discussion.
    if (-not (Test-RuleField $Rule 'Sections')) {
        if ($Rule.Discussion) { return , @(, @('Discussion', [string]$Rule.Discussion)) }
        return , @()
    }
    return , @($Rule.Sections | ForEach-Object { , @([string]$_[0], [string]$_[1]) })
}

function New-NcmRule($Rule, [string]$RuleGrouping, [string]$PatternMode, [string]$Suffix = '_v1', $Drafts = $null) {
    $pattern = 'STIG-MANUAL-REVIEW-' + $Rule.VulnId
    $display = $Rule.VulnId; if ((Test-RuleField $Rule 'DisplayId') -and $Rule.DisplayId) { $display = $Rule.DisplayId }
    $patternType = 'Like'
    $mustExist = $true
    $multi = @()
    $note = 'PATTERN NOT SET: this sentinel never matches, so the rule flags every ' +
            'node as a violation until you replace it with a real pattern for this check.'
    $draftEntry = $null
    if ($Drafts) {
        if ($Drafts.ContainsKey([string]$display)) { $draftEntry = $Drafts[[string]$display] }
        elseif ($Drafts.ContainsKey([string]$Rule.VulnId)) { $draftEntry = $Drafts[[string]$Rule.VulnId] }
    }
    if ($draftEntry) {
        $mustExist = [bool]$draftEntry.MustExist
        if ($draftEntry.ContainsKey('Patterns') -and @($draftEntry.Patterns).Count -gt 0) {
            $multi = @(foreach ($p in @($draftEntry.Patterns)) { [ordered]@{} + $p })
            $pattern = ''
        } else {
            $pattern = $draftEntry.Pattern; $patternType = $draftEntry.Type
        }
        $why = $draftEntry.Note
        if (-not $why) { $why = 'supplied for this rule by a reviewer or an automated task; verify it before trusting this rule''s results.' }
        $note = 'PATTERN FROM DRAFTS FILE: ' + $why
        $n = @($multi).Count; if ($n -eq 0) { $n = 1 }
        Write-ToolLog build debug "${display}: pattern from the drafts file ($n pattern(s), must exist $mustExist)"
    } elseif ($PatternMode -eq 'blocks') {
        $draft = New-BlocksDraft $Rule.CheckContent
        if ($draft.Blocks -gt 0) {
            $multi = @($draft.Patterns)
            $pattern = ''
            $note = "DRAFT BLOCKS: $($draft.Blocks) configuration example block(s) from the STIG check text, as an " +
                    'Advanced Config Search (every block must be found, AND). The values are the STIG''s examples ' +
                    '(addresses, names, numbers): replace them with yours and verify before trusting this rule''s results.'
            Write-ToolLog build debug "$display blocks: $($draft.Blocks) example block(s) extracted"
        } else {
            $note += ' Blocks mode kept the sentinel: the check text shows no configuration lines.'
            Write-ToolLog build debug "$display blocks: sentinel kept (no configuration lines)"
        }
    } elseif ($PatternMode -eq 'heuristic') {
        $draft = Get-HeuristicDraft $Rule.CheckContent
        if (-not $draft.Pattern) {
            $note += ' Heuristic mode kept the sentinel: ' + $draft.Reason + '.'
            Write-ToolLog build debug "$display heuristic: sentinel kept ($($draft.Reason))"
        } else {
            $found = $draft.Pattern
            $mustExist = [bool]$draft.MustExist
            $pattern = $found
            $note = 'DRAFT PATTERN extracted automatically from the STIG check ' +
                    'text ' + $script:EmDash + ' verify it before trusting this rule''s results.'
            if ($mustExist) {
                $note += ' Polarity: the check text says this line must be present ' +
                         '(PatternMustExist true), from: "' + $draft.Source + '"'
            } else {
                $note += ' Polarity: the check text says this line must not be present ' +
                         '(PatternMustExist false: the rule reports a violation when the ' +
                         'pattern is found), from: "' + $draft.Source + '". Unverified: ' +
                         'whether NCM matches a pattern inside a longer line, so an explicit ' +
                         '"no ' + $found + '" line may also match; run the rule through ' +
                         'the test command against a compliant config before trusting it.'
            }
            $mustWord = 'exist'; if (-not $mustExist) { $mustWord = 'not exist' }
            Write-ToolLog build debug ("$display heuristic: pattern '$found' must $mustWord ($($draft.How)) " +
                "from '$($draft.Source)'")
            if ($found.Contains('*') -or $found.Contains('?')) {
                $patternType = 'Regex'
                $pattern = ConvertTo-EscapedRegex $found
                $note += ' Emitted as an escaped Regex rather than a Like pattern because ' +
                         'the extracted text contains * or ?, which a Like pattern only ' +
                         'treats as wildcards when the server''s ' +
                         'ComplianceRulesWildcardsEnabled advanced setting is on ' +
                         '(NCM 2023.1.1 and later; off by default).'
            }
        }
    }
    $parts = New-Object System.Collections.ArrayList
    [void]$parts.Add((Get-RuleReferenceLine $Rule)); [void]$parts.Add($note)
    foreach ($pair in (Get-RuleSections $Rule)) { [void]$parts.Add($pair[0] + ":`n" + $pair[1]) }
    if ($Rule.CheckContent) { [void]$parts.Add("Check:`n" + $Rule.CheckContent) }
    elseif ($Rule.OvalRef) {
        [void]$parts.Add('Machine check (SCAP edition): OVAL definition ' + $Rule.OvalRef +
            ' ' + $script:EmDash + ' no manual check text in this edition; the manual ' +
            'STIG for this product carries the prose.')
    }
    # The Check Content and the Fix Text go into the rule's Remediation field as prose
    # (Python remediation_text, 2.1.0); ExecuteScriptAutomatically stays false.
    $remediation = Get-RemediationText $Rule
    # NCM_PolicyRules.Name is nvarchar(100): a 2026.4.0 server refused a longer name
    # with SQL error 2628 (Python RULE_NAME_LIMIT). The full title stays in Comments.
    $name = Limit-Text (Get-NcmSafeName "$display [$($Rule.Severity)] $($Rule.Title)") $script:RuleNameLimit
    $lvl = 1
    if ($script:SeverityToErrorLevel.ContainsKey($Rule.Severity)) {
        $lvl = $script:SeverityToErrorLevel[$Rule.Severity]
    }
    return [ordered]@{
        RuleId = Get-DeterministicGuid ('stig2ncm:' + $Rule.RuleId + $Suffix)  # matches the Python edition (ncm_rule_id)
        RuleName = $name
        Comments = ($parts -join "`n`n")
        Grouping = $RuleGrouping
        SimplePatternText = $pattern
        PatternType = $patternType
        PatternMustExist = $mustExist
        AdvancedMode = (@($multi).Count -gt 0)
        MultiLineRulePatterns = @($multi)
        ConfigBlockStart = ''
        ConfigBlockEnd = ''
        ConfigBlockPatternType = 'Like'
        ConfigBlockMustExist = $false
        IsConfigBlockPatternRegEx = $false
        ErrorLevel = $lvl
        # No remediation script (2.0.0): the Fix Text is prose and goes into Comments.
        # Sent empty rather than omitted (the contract marks no member optional and
        # the audited exports carry it on every rule), with RemediateScriptType CLI
        # as every audited rule has. Nothing is ever auto-executed.
        RemediateScript = $remediation
        RemediateScriptType = 'CLI'
        ExecuteScriptAutomatically = $false
        ExecuteRemediationScriptPerBlock = $false
        ExecuteScriptInConfigMode = $false
        Owner = 'DISA STIG Conversion Tool'
        # Bookkeeping for the pattern-drafts file, not contract members (Python _vuln_id).
        _vuln_id = [string]$Rule.VulnId
        _display_id = [string]$display
    }
}

function Get-RemediationText($Rule) {
    # Python remediation_text: the STIG's Check Content and Fix Text as prose under
    # "Check Content:" and "Fix Text:" headings, the CCIs last; '' with neither.
    $parts = New-Object System.Collections.ArrayList
    if ($Rule.FixText) { [void]$parts.Add("Fix Text:`n" + ([string]$Rule.FixText).Trim()) }
    if ($parts.Count -gt 0 -and $Rule.Ccis -and @($Rule.Ccis).Count -gt 0) { [void]$parts.Add('CCI: ' + (@($Rule.Ccis) -join ', ')) }
    return ($parts -join "`n`n")
}

function Write-NcmBuildCounts([string]$ReportName, $SourceRules, $Rules, [string]$PatternMode) {
    # Python log_build_counts: where the Fix Text went and, in heuristic mode, how many
    # rules got a draft of each polarity.
    $withFix = @(@($SourceRules) | Where-Object { $_.FixText }).Count
    Write-ToolLog build info ("report `"$ReportName`": Fix Text of $withFix rule(s) placed in the rule's Remediation field " +
        'as prose ("Fix Text:", CCIs last); ExecuteScriptAutomatically false')
    $advanced = @(@($Rules) | Where-Object { $_.AdvancedMode })
    if ($advanced.Count -gt 0) {
        $blocks = 0; foreach ($r in $advanced) { $blocks += @($r.MultiLineRulePatterns).Count }
        Write-ToolLog build info ("report `"$ReportName`": $($advanced.Count) of $(@($Rules).Count) rule(s) carry an Advanced Config " +
            "Search ($blocks pattern block(s) in all); the rest keep the sentinel")
    }
    if ($PatternMode -ne 'heuristic') { return }
    $all = @($Rules)
    $drafted = @($all | Where-Object { -not ([string]$_.SimplePatternText).StartsWith('STIG-MANUAL-REVIEW-', [StringComparison]::Ordinal) })
    $absent = @($drafted | Where-Object { -not $_.PatternMustExist }).Count
    Write-ToolLog build info ("report `"$ReportName`": heuristic drafted $($drafted.Count) of $($all.Count) " +
        "rule(s) ($($drafted.Count - $absent) must exist, $absent must not exist); " +
        "$($all.Count - $drafted.Count) kept the sentinel")
}

function New-NcmReports($Benchmarks, [string]$BaseName, [string]$Where,
                        [string]$PatternMode, [string]$Folder, [bool]$Enabled = $true,
                        [string]$ConfigTypes = 'Any', [string]$Suffix = '_v1', $Drafts = $null) {
    # One report per benchmark (matching the console's own one-policy-per-report
    # exports): the router zip yields NDM (35 rules) and RTR (92 rules) reports.
    # $BaseName comes from Get-ReportBaseName, mirroring Python's `name`. $Suffix
    # ends every report and policy name and seeds the PolicyId and RuleIds.
    if (-not $ConfigTypes) { $ConfigTypes = 'Any' }
    $Suffix = Test-Suffix $Suffix
    $reports = New-Object System.Collections.ArrayList
    foreach ($b in $Benchmarks) {
        $ruleGroup = $Folder
        if ($b.BenchmarkId) { $ruleGroup = "$Folder/$($b.BenchmarkId)" }
        $rules = @($b.Rules | ForEach-Object { New-NcmRule $_ $ruleGroup $PatternMode $Suffix $Drafts })
        $policy = [ordered]@{
            PolicyId = Get-NcmPolicyId $b $Suffix
            PolicyName = Get-NcmPolicyName $b $Suffix
            Comments = ("Imported by the DISA STIG Conversion Tool from $($b.Source) " +
                        "(benchmark $($b.BenchmarkId), status date $($b.StatusDate)).")
            Grouping = $Folder
            NodeSelectionString = New-NodeSelectionString $Where
            NodeSelectionCriterias = New-NodeSelectionCriterias $Where
            ConfigTypes = $ConfigTypes
            AssignedPolicyRules = $rules
            AssignedRulesList = @($rules | ForEach-Object { $_.RuleId })
        }
        $name = $b.Title
        if ($BaseName) {
            $name = $BaseName
            if ($b.BenchmarkId) { $name = "$BaseName - $($b.BenchmarkId)" }
        }
        [void]$reports.Add([ordered]@{
            ID = [guid]::NewGuid().ToString()
            Name = Get-SuffixedName (Get-NcmSafeName $name) $Suffix
            Comments = "DISA STIG imported by the DISA STIG Conversion Tool from $($b.Source) ($($b.Release))."
            Group = $Folder
            ShowSummaryFlag = $true
            ShowRulesWithoutViolationFlag = $true
            AssignedPolicies = @($policy)
            AssignedPoliciesList = @($policy.PolicyId)
            ReportStatus = $(if ($Enabled) { 'Enabled' } else { 'Disabled' })
        })
        $last = $reports[$reports.Count - 1]
        Write-ToolLog build info ("report `"$($last.Name)`": policy `"$($policy.PolicyName)`" " +
            "(PolicyId $($policy.PolicyId)), $($rules.Count) rule(s), mode $PatternMode, " +
            "ReportStatus $($last.ReportStatus), ConfigTypes $ConfigTypes, grouping $ruleGroup, suffix $Suffix")
        Write-NcmBuildCounts $last.Name $b.Rules $rules $PatternMode
    }
    return , @($reports)   # unary comma: stay an array even with one report
}

function Add-El($Xml, $Parent, [string]$Name, [string]$Text) {
    $el = $Xml.CreateElement($Name)
    if ($Text) { $el.InnerText = $Text }
    [void]$Parent.AppendChild($el)
    return $el
}
function B([bool]$Value) { if ($Value) { 'true' } else { 'false' } }

# Python SIMPLE_MODE_PLACEHOLDER_PATTERN / console_rule_patterns (2.1.0): every real
# console export gives a simple-mode rule one MultiLineRulePattern with an empty Regex
# pattern, never an empty list, so the console file does the same. The API contract
# payloads are unchanged (the list stays empty there).
$script:SimpleModePlaceholderPattern = @{ PatternType = 'Regex'; Pattern = ''; Criteria = $true;
                                          Condition = ''; BeginBracket = ''; EndBracket = '' }
function Get-ConsoleRulePatterns($Rule) {
    $own = @($Rule.MultiLineRulePatterns)
    if ($own.Count -gt 0 -or $Rule.AdvancedMode) { return , $own }
    return , @($script:SimpleModePlaceholderPattern)
}

function ConvertTo-ConsoleReportXml($Report) {
    # Element order copied from real console exports - the receiving .NET XML
    # deserializer is order-sensitive; IsConfigBlockPatternRegEx is computed
    # and therefore omitted, exactly as the console omits it.
    $x = New-Object System.Xml.XmlDocument
    $root = $x.CreateElement('PolicyReport')
    $root.SetAttribute('xmlns:xsd', 'http://www.w3.org/2001/XMLSchema')
    $root.SetAttribute('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    [void]$x.AppendChild($root)
    Add-El $x $root 'ID' $Report.ID | Out-Null
    Add-El $x $root 'Name' $Report.Name | Out-Null
    Add-El $x $root 'Comments' $Report.Comments | Out-Null
    Add-El $x $root 'Group' $Report.Group | Out-Null
    Add-El $x $root 'ShowSummaryFlag' (B $Report.ShowSummaryFlag) | Out-Null
    Add-El $x $root 'ShowRulesWithoutViolationFlag' (B $Report.ShowRulesWithoutViolationFlag) | Out-Null
    $pols = Add-El $x $root 'AssignedPolicies' ''
    foreach ($p in $Report.AssignedPolicies) {
        $pe = Add-El $x $pols 'Policy' ''
        Add-El $x $pe 'NodeSelectionString' $p.NodeSelectionString | Out-Null
        Add-El $x $pe 'ConfigTypes' $p.ConfigTypes | Out-Null
        $rulesEl = Add-El $x $pe 'AssignedPolicyRules' ''
        foreach ($r in $p.AssignedPolicyRules) {
            $re = Add-El $x $rulesEl 'PolicyRule' ''
            $patsEl = Add-El $x $re 'MultiLineRulePatterns' ''
            foreach ($mp in (Get-ConsoleRulePatterns $r)) {
                # Member order as the console writes it (and as Python _rule_xml_into does).
                $me = Add-El $x $patsEl 'MultiLineRulePattern' ''
                Add-El $x $me 'EndBracket' $mp.EndBracket | Out-Null
                $mpType = $mp.PatternType; if (-not $mpType) { $mpType = 'Like' }
                Add-El $x $me 'PatternType' ([string]$mpType) | Out-Null
                Add-El $x $me 'Condition' $mp.Condition | Out-Null
                Add-El $x $me 'Pattern' $mp.Pattern | Out-Null
                Add-El $x $me 'Criteria' (B $mp.Criteria) | Out-Null
                Add-El $x $me 'BeginBracket' $mp.BeginBracket | Out-Null
            }
            Add-El $x $re 'RuleId' $r.RuleId | Out-Null
            Add-El $x $re 'RuleName' $r.RuleName | Out-Null
            Add-El $x $re 'Comments' $r.Comments | Out-Null
            Add-El $x $re 'Grouping' $r.Grouping | Out-Null
            Add-El $x $re 'RemediateScript' $r.RemediateScript | Out-Null
            Add-El $x $re 'ConfigBlockStart' $r.ConfigBlockStart | Out-Null
            Add-El $x $re 'ConfigBlockEnd' $r.ConfigBlockEnd | Out-Null
            Add-El $x $re 'ConfigBlockPatternType' $r.ConfigBlockPatternType | Out-Null
            Add-El $x $re 'ConfigBlockMustExist' (B $r.ConfigBlockMustExist) | Out-Null
            Add-El $x $re 'PatternType' $r.PatternType | Out-Null
            Add-El $x $re 'PatternMustExist' (B $r.PatternMustExist) | Out-Null
            Add-El $x $re 'AdvancedMode' (B $r.AdvancedMode) | Out-Null
            Add-El $x $re 'ErrorLevel' ([string]$r.ErrorLevel) | Out-Null
            Add-El $x $re 'SimplePatternText' $r.SimplePatternText | Out-Null
            Add-El $x $re 'ExecuteScriptAutomatically' (B $r.ExecuteScriptAutomatically) | Out-Null
            Add-El $x $re 'Owner' $r.Owner | Out-Null
            Add-El $x $re 'RemediateScriptType' $r.RemediateScriptType | Out-Null
            Add-El $x $re 'ExecuteRemediationScriptPerBlock' (B $r.ExecuteRemediationScriptPerBlock) | Out-Null
            Add-El $x $re 'ExecuteScriptInConfigMode' (B $r.ExecuteScriptInConfigMode) | Out-Null
        }
        Add-El $x $pe 'Grouping' $p.Grouping | Out-Null
        Add-El $x $pe 'Comments' $p.Comments | Out-Null
        Add-El $x $pe 'PolicyName' $p.PolicyName | Out-Null
    }
    Add-El $x $root 'ReportStatus' $Report.ReportStatus | Out-Null
    $sw = New-Object System.IO.StringWriter
    $xw = New-Object System.Xml.XmlTextWriter($sw)
    $xw.Formatting = 'Indented'; $xw.Indentation = 2
    $x.DocumentElement.WriteTo($xw); $xw.Flush()
    return $sw.ToString()
}

function Write-ConsoleReportFile($Report, [string]$Folder) {
    # Byte-matched to real console exports: UTF-8 without BOM, CRLF line
    # endings, and the (lying) utf-16 declaration.
    $out = Join-Path $Folder (Get-SafeFileName $Report.Name '.ncm-report.xml')
    $body = '<?xml version="1.0" encoding="utf-16"?>' + "`r`n" +
            ((ConvertTo-ConsoleReportXml $Report) -replace "(?<!`r)`n", "`r`n")
    return Write-GeneratedFile $out $body
}

function Write-GeneratedFile([string]$FilePath, [string]$Text) {
    # Write one generated file (UTF-8, no BOM) and log it.
    [System.IO.File]::WriteAllText($FilePath, $Text, $script:Utf8NoBom)
    Add-ToolLogStat 'FilesWritten'
    $full = [System.IO.Path]::GetFullPath($FilePath)
    Write-ToolLog file info "wrote $full ($((Get-Item -LiteralPath $FilePath).Length) bytes)"
    return $FilePath
}

# =========================================================================
# SCM: XCCDF -> .scm-profile (the !policy YAML ImportPolicy takes verbatim)
# =========================================================================
function Y([string]$Value) {
    # JSON string quoting is valid YAML - keeps the emitter dependency-free.
    if ($null -eq $Value) { $Value = '' }
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.Append('"')
    foreach ($ch in $Value.ToCharArray()) {
        # Switch on the code point, not the character: PowerShell compares strings with
        # culture rules, and under ICU (PowerShell 7 on Linux) control characters are
        # ignorable, so "`b" would also match U+0001 and every other control character.
        switch ([int]$ch) {
            34 { [void]$sb.Append('\"') }
            92 { [void]$sb.Append('\\') }
            10 { [void]$sb.Append('\n') }
            13 { [void]$sb.Append('\r') }
            9  { [void]$sb.Append('\t') }
            8  { [void]$sb.Append('\b') }   # json.dumps spells these two out
            12 { [void]$sb.Append('\f') }
            default {
                # Control characters as JSON writes them, plus what JSON leaves raw but a
                # YAML double-quoted scalar must not hold: DEL and the C1 controls (U+0085
                # among them), U+2028/U+2029, U+FEFF, U+FFFE/U+FFFF (Python _YAML_ESCAPES).
                $code = [int]$ch
                if ($code -lt 32 -or ($code -ge 0x7f -and $code -le 0x9f) -or $code -eq 0x2028 -or
                    $code -eq 0x2029 -or $code -eq 0xfeff -or $code -eq 0xfffe -or $code -eq 0xffff) {
                    [void]$sb.AppendFormat('\u{0:x4}', $code)
                }
                else { [void]$sb.Append($ch) }
            }
        }
    }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Get-ScmRuleDescription($Rule) {
    # Python scm_rule_description: the pseudo-sections (the discussion unlabeled, the
    # others under their labels), then the identifier line.
    $parts = New-Object System.Collections.ArrayList
    foreach ($pair in (Get-RuleSections $Rule)) {
        if ($pair[0] -ceq 'Discussion') { [void]$parts.Add($pair[1]) }
        else { [void]$parts.Add($pair[0] + ":`n" + $pair[1]) }
    }
    [void]$parts.Add((Get-RuleReferenceLine $Rule))
    return ($parts -join "`n`n")
}

function ConvertTo-ScmPolicyYaml($Benchmark, [string]$Suffix = '_v1', [string]$OsFamily = 'windows', $ProbeTemplate = $null) {
    # $Suffix ends the policy name and seeds every uniqueId; $OsFamily picks the
    # probe from $script:ScmProbes; $ProbeTemplate (Read-ProbeTemplate) replaces the
    # probe's source block. Same output as Python xccdf_to_scm_yaml.
    $Suffix = Test-Suffix $Suffix
    $name = Get-ScmPolicyName $Benchmark $Suffix
    $uid = Get-ScmPolicyUniqueId $Benchmark $Suffix
    $desc = 'DISA STIG imported by the DISA STIG Conversion Tool from ' + $Benchmark.Source +
        '. Every rule is a manual-review attestation: it reports failed, with the STIG ' +
        'check and fix text attached, until an engineer verifies the setting and replaces ' +
        'or disables the rule. Nothing in this policy changes server configuration.'
    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add('!policy')
    [void]$lines.Add('name: ' + (Y $name))
    [void]$lines.Add("uniqueId: $uid")
    [void]$lines.Add('pluginName: SCM')
    [void]$lines.Add('description: ' + (Y $desc))
    [void]$lines.Add('version: 2')
    [void]$lines.Add('builtIn: false')
    [void]$lines.Add('rules:')
    foreach ($r in $Benchmark.Rules) {
        $check = $r.CheckContent
        if (-not $check -and $r.OvalRef) {
            $check = "Machine check (SCAP edition): OVAL definition $($r.OvalRef). " +
                     'The manual STIG for this product carries the prose check text.'
        }
        $sev = $r.Severity.Substring(0, 1).ToUpper() + $r.Severity.Substring(1)
        # Unverified: SCM's !translate (SolarWinds' shipped policies use it to map Failed
        # to Unknown) is not emitted. The repository describes that node only in prose
        # (scm-policy-portability-audit.md), not as an exact serialized example, and
        # Unknown is also what a polling error looks like, so an un-reviewed rule stays
        # Failed (same as the Python edition).
        $displayId = $r.VulnId; if ((Test-RuleField $r 'DisplayId') -and $r.DisplayId) { $displayId = $r.DisplayId }
        [void]$lines.Add('- displayId: ' + (Y $displayId))
        [void]$lines.Add('  uniqueId: ' + (Get-ScmRuleUniqueId $r $Suffix))
        $title = Limit-Text $r.Title 250
        [void]$lines.Add('  name: ' + (Y $title))
        [void]$lines.Add("  severity: $sev")
        [void]$lines.Add('  description: ' + (Y (Get-ScmRuleDescription $r)))
        [void]$lines.Add('  remediationDescription: ' + (Y $r.FixText))
        [void]$lines.Add('  checkText: ' + (Y $check))
        # The probe runs as PowerShell on every assigned node: the id is validated
        # and the whole text is a single-quoted literal, so no STIG content can
        # expand ($(...), $var) or escape (backtick or ") inside the script source.
        # A probe template receives the same validated id, inside a quoted scalar only.
        $probeId = Get-ScmProbeId $r.VulnId $r.RuleId
        [void]$lines.Add('  condition: !matches')
        [void]$lines.Add('    expression: ' + (Y ($probeId + ' reviewed: True')))
        foreach ($probeLine in (Get-ScmProbeLines $probeId $r.StigId $ProbeTemplate)) { [void]$lines.Add($probeLine) }
    }
    $probeShown = 'default'; if ($ProbeTemplate) { $probeShown = 'template ' + $ProbeTemplate[0] }
    Write-ToolLog build info ("SCM policy `"$name`" uniqueId ${uid}: $(@($Benchmark.Rules).Count) manual-review rule(s), " +
        "OS family $OsFamily, probe $probeShown")
    return ($lines -join "`n") + "`n"
}

# SCM policy output extension. SolarWinds' published policy files are plain
# .yaml and the docs name no dedicated extension, so .scm-policy.yaml is used.
# .scm-profile belongs to SCM collection-profile exports (UTF-16 JSON); older
# builds of this tool wrote policy YAML under it, which is still accepted.
$script:ScmPolicySuffix = '.scm-policy.yaml'
$script:LegacyScmPolicySuffix = '.scm-profile'
$script:ScmInputPattern = '\.(yaml|yml|scm-profile)$'

function Write-ScmPolicyFile($Benchmark, [string]$Folder, [string]$Suffix = '_v1', [string]$OsFamily = 'windows', $ProbeTemplate = $null) {
    # The version suffix is part of the file name, so a _v2 conversion does not
    # overwrite the _v1 file.
    $base = $Benchmark.BenchmarkId; if (-not $base) { $base = $Benchmark.Title }
    $out = Join-Path $Folder (Get-SafeFileName ($base + $Suffix) $script:ScmPolicySuffix)
    return Write-GeneratedFile $out (ConvertTo-ScmPolicyYaml $Benchmark $Suffix $OsFamily $ProbeTemplate)
}

function Test-ScmPolicyText([string]$Text) {
    # Same test as Python is_scm_policy_text: a document tagged !policy, or one
    # carrying pluginName: SCM near the top and a rules list.
    if ($null -eq $Text) { return $false }
    $t = $Text.TrimStart([char]0xFEFF).TrimStart()
    $head = $t; if ($head.Length -gt 2000) { $head = $head.Substring(0, 2000) }
    return ($head.StartsWith('!policy') -or ($head.Contains('pluginName: SCM') -and $Text.Contains('rules:')))
}

function Get-ScmPolicyInfo([string]$Yaml) {
    # Name and uniqueId for the collision check. Line endings are normalized
    # first: in .NET a multiline `$` matches only before `n, so `\S+$` fails on
    # every CRLF line. The text sent to ImportPolicy is never altered.
    $norm = ([string]$Yaml) -replace "`r`n", "`n" -replace "`r", "`n"
    $info = @{ Name = ''; UniqueId = ''; IsPolicy = (Test-ScmPolicyText $Yaml) }
    $m = [regex]::Match($norm, '(?m)^name:[ \t]*(.+)$')
    if ($m.Success) { $info.Name = $m.Groups[1].Value.Trim().Trim("'", '"') }
    $m = [regex]::Match($norm, '(?m)^uniqueId:[ \t]*(\S+)')
    if ($m.Success) { $info.UniqueId = $m.Groups[1].Value.Trim().Trim("'", '"') }
    return $info
}

function ConvertFrom-TextBytes([byte[]]$Bytes) {
    # Decode by the bytes: UTF-16 by BOM or NUL-interleaved ASCII (SCM exports
    # are UTF-16LE), else UTF-8 with or without a BOM.
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        return [System.Text.Encoding]::Unicode.GetString($Bytes, 2, $Bytes.Length - 2)
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFE -and $Bytes[1] -eq 0xFF) {
        return [System.Text.Encoding]::BigEndianUnicode.GetString($Bytes, 2, $Bytes.Length - 2)
    }
    if ($Bytes.Length -ge 4 -and $Bytes[1] -eq 0 -and $Bytes[3] -eq 0) {
        return [System.Text.Encoding]::Unicode.GetString($Bytes)
    }
    if ($Bytes.Length -ge 4 -and $Bytes[0] -eq 0 -and $Bytes[2] -eq 0) {
        return [System.Text.Encoding]::BigEndianUnicode.GetString($Bytes)
    }
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        return [System.Text.Encoding]::UTF8.GetString($Bytes, 3, $Bytes.Length - 3)
    }
    return [System.Text.Encoding]::UTF8.GetString($Bytes)
}

function Get-ScmTextKind([string]$Text) {
    # 'policy' (tagged-YAML compliance policy), 'profile' (JSON, the SCM
    # collection-profile export format) or 'unknown'.
    if (Test-ScmPolicyText $Text) { return 'policy' }
    $t = ([string]$Text).TrimStart([char]0xFEFF).Trim()
    if ($t.StartsWith('{')) {
        try { [void](ConvertFrom-Json $t); return 'profile' } catch { }
    }
    return 'unknown'
}

function Read-ScmPolicyFile([string]$FilePath, [scriptblock]$Log) {
    # Returns the policy text. A .scm-profile holding policy YAML (written by an
    # older build of this tool) is accepted with a note; a JSON collection
    # profile is refused, since that extension belongs to SCM profiles.
    $raw = [System.IO.File]::ReadAllBytes($FilePath)
    $text = ConvertFrom-TextBytes $raw
    $kind = Get-ScmTextKind $text
    if ($kind -eq 'profile') {
        Write-ToolLog scm warn "refused ${FilePath}: JSON SCM collection profile, not a policy"
        throw ("[SCM] ${FilePath}: this is an SCM collection profile (JSON, the format SCM " +
            'profile exports use), not a tagged-YAML compliance policy. Collection profiles ' +
            'define what SCM collects; they carry no compliance rules, and this tool does ' +
            'not import them. Import a profile through SCM''s own profile import workflow ' +
            'or Orion.SCM.Profiles.ImportProfile(profileJson), after the review described ' +
            'in docs/modules/scm-profile-portability-audit.md.')
    }
    if ($kind -ne 'policy') {
        Write-ToolLog scm warn "refused ${FilePath}: not a tagged-YAML SCM compliance policy"
        throw "[SCM] ${FilePath}: not an SCM compliance policy (expected a YAML document tagged !policy with pluginName: SCM)"
    }
    Write-ToolLog scm info "read SCM policy file $FilePath ($($raw.Length) bytes)"
    if ($FilePath.ToLower().EndsWith($script:LegacyScmPolicySuffix)) {
        Send-Log $Log 'scm' 'warn' ("[SCM] note: $(Split-Path -Leaf $FilePath) is SCM policy YAML written by an " +
            "older build of this tool under the $($script:LegacyScmPolicySuffix) extension, " +
            'which belongs to SCM collection profiles (JSON). It is read as a compliance policy; ' +
            "new conversions write $($script:ScmPolicySuffix), so rename the file to avoid confusion.")
    }
    return $text
}

function Read-ScmPolicyZip([string]$FilePath, [scriptblock]$Log) {
    # Python read_scm_policy_zip (2.1.0): the SCM policies inside a zip of policy
    # YAML, as SolarWinds delivers policy packs (one .yaml per policy, no XCCDF).
    # Returns an array of @{ Label; Member; Text; Raw } (base name, full name in the
    # archive, the text ImportPolicy takes verbatim, the original bytes), or $null
    # when the zip has no .yaml/.yml member at all (a STIG package, then). A zip
    # mixing policy YAML with .xml or nested .zip members is refused: one input is
    # one module. A YAML member that is not a policy is skipped with a warning, and
    # the input is refused when no member is a policy. The STIG reader's size limits
    # apply; nested zips are not opened.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($FilePath)
    try {
        $names = [string[]]@($zip.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName })
        [Array]::Sort($names, [System.StringComparer]::Ordinal)
        $entries = @(foreach ($n in $names) { $zip.GetEntry($n) })
        $members = @($entries | Where-Object { $_.Name -match '\.(yaml|yml)$' })
        if ($members.Count -eq 0) { return $null }
        $others = @($entries | Where-Object { $_.Name -match '\.(xml|zip)$' } | ForEach-Object { $_.FullName })
        if ($others.Count -gt 0) {
            $shown = @($others | Select-Object -First 3) -join ', '
            if ($others.Count -gt 3) { $shown += ', ...' }
            $reason = ("${FilePath}: mixes SCM policy YAML with XCCDF or nested zip members ($shown); " +
                'one input is one module, so split it into a policy zip and a STIG package')
            Write-ToolLog parse warn $reason
            throw $reason
        }
        Write-ToolLog parse info ("input ${FilePath}: zip of SCM policy YAML ($($members.Count) .yaml/.yml member(s), " +
            "$((Get-Item -LiteralPath $FilePath).Length) bytes)")
        $out = New-Object System.Collections.ArrayList
        $budget = [long]0
        foreach ($entry in $members) {
            $label = $entry.FullName
            if ($entry.Length -gt $script:ZipMemberMax) {
                Skip-ZipMember $label "refused: $($entry.Length) bytes uncompressed is over the $($script:ZipMemberMax)-byte member limit"
                continue
            }
            if ($budget + $entry.Length -gt $script:ZipTotalMax) {
                $reason = "refused: reading $label would take the input past the $($script:ZipTotalMax)-byte total limit for zip members"
                Write-ToolLog parse warn $reason
                throw $reason
            }
            try { $raw = Read-ZipEntryBytes $entry ([long]$entry.Length) }
            catch {
                Skip-ZipMember $label "the member cannot be read ($($_.Exception.Message))"
                continue
            }
            $budget += $raw.Length
            $text = ConvertFrom-TextBytes $raw
            $kind = Get-ScmTextKind $text
            if ($kind -eq 'profile') { Skip-ZipMember $label 'a JSON SCM collection profile, not a compliance policy'; continue }
            if ($kind -ne 'policy') { Skip-ZipMember $label 'not a tagged-YAML SCM compliance policy'; continue }
            Write-ToolLog scm info "read SCM policy member $label ($($raw.Length) bytes)"
            [void]$out.Add(@{ Label = $entry.Name; Member = $entry.FullName; Text = $text; Raw = $raw })
        }
        if ($out.Count -eq 0) {
            $reason = ("${FilePath}: none of its $($members.Count) .yaml/.yml member(s) is an SCM compliance " +
                'policy (expected YAML documents tagged !policy with pluginName: SCM)')
            Write-ToolLog parse warn $reason
            throw $reason
        }
        foreach ($it in $out) {
            $info = Get-ScmPolicyInfo $it.Text
            $n = ([regex]::Matches($it.Text, '(?m)^- displayId:')).Count
            Send-Log $Log 'scm' 'info' "[SCM] $($it.Member): SCM policy `"$($info.Name)`" - $n rule(s)"
        }
        return , @($out)
    } finally { $zip.Dispose() }
}

function Get-ScmInputs([string]$FilePath, [scriptblock]$Log) {
    # Python scm_inputs: every ready-made SCM policy an input carries, or $null when
    # the input is XCCDF. A .yaml/.yml (or legacy .scm-profile) file is one policy
    # (Member and Raw are $null); a zip of policy YAML is one per member.
    # The result is always one array object (the comma), so a caller assigns it and
    # indexes it: $items = Get-ScmInputs ...; $items[0].Member. Wrapping the call in
    # @(...) would nest that array instead.
    if ($FilePath -match $script:ScmInputPattern) {
        $text = Read-ScmPolicyFile $FilePath $Log
        return , @(@{ Label = (Split-Path -Leaf $FilePath); Member = $null; Text = $text; Raw = $null })
    }
    if ($FilePath -match '\.zip$') {
        $items = Read-ScmPolicyZip $FilePath $Log
        if ($null -eq $items) { return $null }
        return , @($items)
    }
    return $null
}

function Write-ScmPolicyMembers($Items, [string]$Folder, [scriptblock]$Log) {
    # Python write_scm_policy_members: offline conversion of a policy zip writes every
    # member into $Folder byte for byte (it is already the import payload) under a
    # sanitized copy of its own name. Returns the paths written.
    $written = New-Object System.Collections.ArrayList
    foreach ($it in $Items) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($it.Label)
        $ext = [System.IO.Path]::GetExtension($it.Label).ToLowerInvariant()
        if (-not $ext) { $ext = '.yaml' }
        $out = Join-Path $Folder (Get-SafeFileName $stem $ext)
        [System.IO.File]::WriteAllBytes($out, $it.Raw)
        Add-ToolLogStat 'FilesWritten'
        Write-ToolLog file info "wrote $([System.IO.Path]::GetFullPath($out)) ($($it.Raw.Length) bytes, member $($it.Member) unchanged)"
        $info = Get-ScmPolicyInfo $it.Text
        $n = ([regex]::Matches($it.Text, '(?m)^- displayId:')).Count
        Send-Log $Log 'file' 'info' "[SCM] wrote ${out}: SCM policy `"$($info.Name)`" - $n rules (bytes unchanged)"
        [void]$written.Add($out)
    }
    return , @($written)
}

# =========================================================================
# SWIS client - built-in Invoke-RestMethod (HttpClient for a PS 7 pin)
# =========================================================================
# Certificate pinning fails closed in both PowerShell generations:
#  - Windows PowerShell 5.1: Invoke-RestMethod, with the process-wide
#    ServicePointManager callback set only for the duration of each call and the
#    previous callback restored afterwards.
#  - PowerShell 7: Invoke-RestMethod has no server-certificate callback (its
#    -CertificateThumbprint selects a *client* certificate, and
#    ServicePointManager does not reach its HttpClient), so a pinned connection
#    goes through an HttpClient whose handler checks the pin on every new TLS
#    connection. -SkipCertificateCheck is used only for -Insecure without a pin.
# The pin check is compiled C# (Add-Type): a PowerShell script block cannot run
# as a TLS callback on the .NET thread pool, where no runspace exists. If the
# type cannot be compiled, the connection is refused rather than left unchecked.
$script:PinCheckSource = @'
using System;
using System.Net.Security;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
namespace DisaStigTool {
    public sealed class PinCheck {
        private readonly string pin;
        public bool AcceptAny;
        public int Calls;
        public string LastSeen = "";
        public PinCheck(string pin) { this.pin = (pin ?? "").Replace(":", "").ToUpperInvariant(); }
        public bool Matches(X509Certificate cert) {
            Calls++;
            if (AcceptAny) { return true; }
            if (cert == null || pin.Length == 0) { return false; }
            using (SHA256 sha = SHA256.Create()) {
                LastSeen = BitConverter.ToString(sha.ComputeHash(cert.GetRawCertData())).Replace("-", "");
            }
            return string.Equals(LastSeen, pin, StringComparison.Ordinal);
        }
        public bool ValidateSender(object sender, X509Certificate cert, X509Chain chain, SslPolicyErrors errors) {
            return Matches(cert);
        }
        public Func<T, X509Certificate2, X509Chain, SslPolicyErrors, bool> For<T>() {
            return (request, cert, chain, errors) => Matches(cert);
        }
    }
}
'@
# Tests set this to exercise the HttpClient path on Windows PowerShell 5.1.
$script:ForceHttpClient = $false

function New-PinCheck([string]$Thumb, [bool]$AcceptAny = $false) {
    if (-not ('DisaStigTool.PinCheck' -as [type])) {
        try { Add-Type -TypeDefinition $script:PinCheckSource -Language CSharp }
        catch {
            $msg = ('certificate checking could not be set up (Add-Type failed: ' + $_.Exception.Message +
                '); refusing to connect, because the pin must fail closed')
            Write-ToolLog swis error $msg
            throw $msg
        }
    }
    $check = New-Object DisaStigTool.PinCheck($Thumb)
    $check.AcceptAny = $AcceptAny
    return $check
}

function New-SwisConnection([string]$SwisServer, [int]$SwisPort, [string]$User,
                            [string]$Password, [bool]$UseWindowsAuth,
                            [bool]$AllowInsecure, [string]$PinnedThumb,
                            [string]$Token = '') {
    # A SWIS API token (platform 2026.4+) is a bearer secret: it is sent on every
    # call as "Authorization: Bearer <token>" and identifies the account it was
    # created for, so no user name travels with it.
    if ($Token -and ($User -or $Password -or $UseWindowsAuth)) {
        throw 'an API token and a username/password (or Windows login) are mutually exclusive; pass one or the other'
    }
    if ($Token) { Register-Secret $Token }
    if ($Password) {
        Register-Secret $Password
        # The Basic token carries the password too, so it is redacted as well.
        Register-Secret ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($User + ':' + $Password)))
    }
    $base = "https://${SwisServer}:${SwisPort}/SolarWinds/InformationService/v3/Json"
    $tls = 'verified against the system trust store'
    if ($PinnedThumb) { $tls = 'pinned server certificate' }
    elseif ($AllowInsecure) { $tls = 'NOT verified (-Insecure, lab only)' }
    $who = "as user '$User' (basic auth)"
    if ($UseWindowsAuth) { $who = "as the current Windows user '$([Environment]::UserName)' (Negotiate)" }
    if ($Token) { $who = 'with an API token (bearer)' }
    Write-ToolLog swis info "SWIS endpoint $base $who; TLS $tls"
    if ($AllowInsecure -and -not $PinnedThumb) { Write-ToolLog swis warn 'TLS verification is off for this session' }
    if ($AllowInsecure -and $PinnedThumb) { Write-ToolLog swis info '-Insecure is ignored: a pinned certificate is always checked' }
    return @{
        Base = $base
        User = $User; Password = $Password; WindowsAuth = $UseWindowsAuth; Token = $Token
        Insecure = $AllowInsecure; PinnedThumb = $PinnedThumb
        HttpClient = $null; PinCheck = $null; PlanLogged = $false
    }
}

function Get-SwisTransportPlan($Conn, [bool]$IsCore) {
    # How one call is made. Path: 'RestMethod' or 'HttpClient'. A pinned
    # connection never gets SkipCertificateCheck; the pin is checked on every new
    # TLS connection, by the scoped callback (5.1) or the HttpClient handler (7).
    $pinned = [bool]$Conn.PinnedThumb
    $plan = @{ Path = 'RestMethod'; SkipCertificateCheck = $false; ScopedCallback = $false; Check = 'system trust store' }
    if ($pinned -and ($IsCore -or $script:ForceHttpClient)) {
        $plan.Path = 'HttpClient'; $plan.Check = 'pin (HttpClient handler callback, per connection)'
    } elseif ($pinned) {
        $plan.ScopedCallback = $true; $plan.Check = 'pin (ServicePointManager callback, scoped to the call)'
    } elseif ($script:ForceHttpClient) {
        $plan.Path = 'HttpClient'
        if ($Conn.Insecure) { $plan.Check = 'none (-Insecure)' }
    } elseif ($Conn.Insecure -and $IsCore) {
        $plan.SkipCertificateCheck = $true; $plan.Check = 'none (-Insecure, SkipCertificateCheck)'
    } elseif ($Conn.Insecure) {
        $plan.ScopedCallback = $true; $plan.Check = 'none (-Insecure, scoped callback)'
    }
    if ($pinned -and $plan.SkipCertificateCheck) { throw 'internal error: a pinned connection must never skip the certificate check' }
    return $plan
}

function New-SwisRequestBody($Body) {
    # The request body as UTF-8 bytes with the charset said explicitly. A string
    # body would be encoded by Invoke-RestMethod as ISO-8859-1 on Windows
    # PowerShell 5.1 when the content type names no charset, mangling any STIG
    # text outside Latin-1.
    if ($null -eq $Body) { return $null }
    $text = ConvertTo-Json $Body -Depth 20 -Compress
    return @{ Text = $text; Bytes = $script:Utf8NoBom.GetBytes($text); ContentType = 'application/json; charset=utf-8' }
}

function Get-SwisErrorDetail([string]$Text) {
    # SWIS error bodies carry a Message member (docs/swis/rest-api.md); fall back to the raw text.
    if (-not $Text) { return '' }
    # At debug level the whole fault document is kept (ExceptionDetail, StackTrace,
    # inner faults), not only the Message the error line carries.
    if (Test-ToolLogDebug) { Write-ToolLog swis debug ('error body: ' + (Limit-LogBody $Text)) }
    try {
        $parsed = ConvertFrom-Json $Text
        if ($null -ne $parsed -and $parsed.PSObject.Properties['Message']) { return [string]$parsed.Message }
    } catch { }
    return $Text
}

function Get-SwisAuthHeader($Conn) {
    # The Authorization header value every call carries: Bearer for an API token,
    # Basic for a username and password; $null for the Windows login (the handler
    # negotiates it). The Python edition's SwisClient.auth_header.
    if ($Conn.Token) { return 'Bearer ' + $Conn.Token }
    if ($Conn.WindowsAuth) { return $null }
    return 'Basic ' + [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Conn.User + ':' + $Conn.Password))
}

function Invoke-SwisHttpClient($Conn, [string]$Method, [string]$Uri, $Request) {
    # One request through a System.Net.Http.HttpClient kept on the connection.
    # Returns @{ Status; Ok; Text }; transport failures throw.
    if ($null -eq $Conn.HttpClient) {
        Add-Type -AssemblyName System.Net.Http
        $handler = New-Object System.Net.Http.HttpClientHandler
        if ($Conn.PinnedThumb -or $Conn.Insecure) {
            $check = New-PinCheck $Conn.PinnedThumb (-not $Conn.PinnedThumb)
            $handler.ServerCertificateCustomValidationCallback =
                $check.GetType().GetMethod('For').MakeGenericMethod([System.Net.Http.HttpRequestMessage]).Invoke($check, @())
            $Conn.PinCheck = $check
        }
        if ($Conn.WindowsAuth) { $handler.UseDefaultCredentials = $true }
        $client = New-Object System.Net.Http.HttpClient($handler)
        $client.Timeout = [TimeSpan]::FromSeconds(300)
        $Conn.HttpClient = $client
    }
    $message = New-Object System.Net.Http.HttpRequestMessage((New-Object System.Net.Http.HttpMethod($Method.ToUpperInvariant())), $Uri)
    [void]$message.Headers.Accept.Add((New-Object System.Net.Http.Headers.MediaTypeWithQualityHeaderValue('application/json')))
    $auth = Get-SwisAuthHeader $Conn
    if ($auth) {
        $message.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::Parse($auth)
    }
    if ($null -ne $Request) {
        $content = New-Object System.Net.Http.ByteArrayContent(, [byte[]]$Request.Bytes)
        $content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($Request.ContentType)
        $message.Content = $content
    }
    try {
        $response = $Conn.HttpClient.SendAsync($message).GetAwaiter().GetResult()
        $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return @{ Status = [int]$response.StatusCode; Ok = [bool]$response.IsSuccessStatusCode; Text = $text }
    } finally { $message.Dispose() }
}

function Invoke-SwisRest($Conn, [string]$Method, [string]$RestPath, $Body) {
    $uri = $Conn.Base + '/' + $RestPath
    $isCore = (Get-Command Invoke-RestMethod).Parameters.ContainsKey('SkipCertificateCheck')
    $plan = Get-SwisTransportPlan $Conn $isCore
    if (-not $Conn.PlanLogged) {
        Write-ToolLog swis info "transport: $($plan.Path); certificate check: $($plan.Check)"
        $Conn.PlanLogged = $true
    }
    $request = New-SwisRequestBody $Body
    $previous = $null; $swapped = $false
    try {
        if ($plan.Path -eq 'HttpClient') {
            $r = Invoke-SwisHttpClient $Conn $Method $uri $request
            if (-not $r.Ok) { throw ("SWIS HTTP $($r.Status) from $RestPath`n" + (Get-SwisErrorDetail $r.Text)) }
            if (-not $r.Text -or -not $r.Text.Trim()) { return $null }
            try { return (ConvertFrom-Json $r.Text) }
            catch { throw ("SWIS transport error calling ${RestPath}: the response is not JSON: " + $_.Exception.Message) }
        }
        $params = @{ Method = $Method; Uri = $uri; TimeoutSec = 300 }
        if ($Conn.WindowsAuth) { $params.UseDefaultCredentials = $true }
        else { $params.Headers = @{ Authorization = (Get-SwisAuthHeader $Conn) } }
        if ($null -ne $request) { $params.Body = [byte[]]$request.Bytes; $params.ContentType = $request.ContentType }
        if ($plan.SkipCertificateCheck) { $params.SkipCertificateCheck = $true }
        if ($plan.ScopedCallback) {
            if ($null -eq $Conn.PinCheck) { $Conn.PinCheck = New-PinCheck $Conn.PinnedThumb (-not $Conn.PinnedThumb) }
            $callback = [Delegate]::CreateDelegate([System.Net.Security.RemoteCertificateValidationCallback], $Conn.PinCheck, 'ValidateSender')
            $previous = [System.Net.ServicePointManager]::ServerCertificateValidationCallback
            [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $callback
            $swapped = $true
        }
        return Invoke-RestMethod @params
    }
    catch {
        $failure = $_.Exception
        if ($failure.Message -like 'SWIS *') { throw }
        $code = ''
        try { if ($failure.Response) { $code = [int]$failure.Response.StatusCode } } catch { }
        if ($code) {
            $detail = $failure.Message
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = Get-SwisErrorDetail $_.ErrorDetails.Message }
            throw ("SWIS HTTP $code from $RestPath`n" + $detail)
        }
        $base = $failure.GetBaseException()
        $msg = "SWIS transport error calling ${RestPath}: $($base.GetType().Name): $($base.Message)"
        if ($Conn.PinnedThumb -and $Conn.PinCheck -and $Conn.PinCheck.LastSeen -and $Conn.PinCheck.LastSeen -ne ($Conn.PinnedThumb -replace ':', '').ToUpperInvariant()) {
            $msg = ("SWIS certificate pin mismatch calling ${RestPath}: the server presented SHA-256 " +
                "$($Conn.PinCheck.LastSeen), not the pinned $($Conn.PinnedThumb); the connection was refused")
            Write-ToolLog swis error $msg
        }
        throw $msg
    }
    finally {
        # Restore whatever was there before, so the process-wide callback never
        # outlives the call that needed it.
        if ($swapped) { [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $previous }
    }
}

function Get-ServerCertThumbprint([string]$SwisServer, [int]$SwisPort) {
    # Fetch the certificate SWIS presents (the stock self-signed
    # 'SolarWinds-Orion' one) for explicit trust. Returns SHA-256 hex.
    $client = New-Object System.Net.Sockets.TcpClient($SwisServer, $SwisPort)
    try {
        # Accept-any is right here and only here: this fetch is what the operator
        # inspects before pinning. The callback is the compiled check, not a script
        # block, so it also runs where no runspace exists (PowerShell 7).
        $acceptAny = New-PinCheck '' $true
        $ssl = New-Object System.Net.Security.SslStream($client.GetStream(), $false,
            [Delegate]::CreateDelegate([System.Net.Security.RemoteCertificateValidationCallback], $acceptAny, 'ValidateSender'))
        $ssl.AuthenticateAsClient($SwisServer)
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
        $thumb = [BitConverter]::ToString(
            [System.Security.Cryptography.SHA256]::Create().ComputeHash($cert.RawData)) -replace '-', ''
        $stock = $cert.Subject -match 'SolarWinds-Orion'
        $ssl.Dispose()
        return @{ Thumbprint = $thumb; Subject = $cert.Subject; Stock = $stock }
    } finally { $client.Dispose() }
}

function Format-LogValue($Value, [int]$Width = 60) {
    # A short, log-safe description of one SWIS argument or result (the same
    # shapes as the Python _summarize_value).
    if ($null -eq $Value) { return 'null' }
    if ($Value -is [bool]) { if ($Value) { return 'true' } else { return 'false' } }
    if ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) { return [string]$Value }
    if ($Value -is [string]) {
        if ($Value.Length -le $Width -and -not $Value.Contains("`n") -and -not $Value.Contains("`r")) { return '"' + $Value + '"' }
        return "<string $($Value.Length) chars>"
    }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($k in @('RuleName', 'PolicyName', 'Name')) {
            if ($Value.Contains($k) -and $Value[$k]) { return '<object ' + (Limit-Text ([string]$Value[$k]) $Width) + '>' }
        }
        return "<object $($Value.Count) keys>"
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        foreach ($k in @('RuleName', 'PolicyName', 'Name')) {
            if ($Value.PSObject.Properties[$k] -and $Value.$k) { return '<object ' + (Limit-Text ([string]$Value.$k) $Width) + '>' }
        }
        return "<object $(@($Value.PSObject.Properties).Count) keys>"
    }
    if ($Value -is [System.Collections.IEnumerable]) { return "[$(@($Value).Count) item(s)]" }
    return '<' + $Value.GetType().Name + '>'
}

function ConvertTo-LogJson($Value) {
    try { return Limit-LogBody (ConvertTo-Json -InputObject $Value -Depth 20 -Compress) }
    catch { return '(not serializable: ' + $_.Exception.Message + ')' }
}

function Start-SwisCallLog([string]$Label, $Body) {
    Add-ToolLogStat 'SwisCalls'
    if (Test-ToolLogDebug) { Write-ToolLog swis debug ('request ' + $Label + ' body ' + (ConvertTo-LogJson $Body)) }
    return [System.Diagnostics.Stopwatch]::StartNew()
}

function Stop-SwisCallLog([string]$Label, $Watch, [string]$Outcome, $Result, [string]$ErrorMessage) {
    # One line per SWIS call: the call, its duration, and ok or the error.
    $ms = [int]$Watch.ElapsedMilliseconds
    if ($ErrorMessage) {
        Add-ToolLogStat 'SwisFailed'
        Write-ToolLog swis warn "$Label -> error $ms ms: $ErrorMessage"
        return
    }
    Write-ToolLog swis info "$Label -> ok $ms ms, $Outcome"
    if (Test-ToolLogDebug) { Write-ToolLog swis debug ('response ' + $Label + ' body ' + (ConvertTo-LogJson $Result)) }
}

function Invoke-SwisQuery($Conn, [string]$Swql, $Parameters) {
    $body = @{ query = $Swql }
    if ($Parameters) { $body.parameters = $Parameters }
    $label = 'query ' + (Limit-OneLine $Swql 160)
    if ($Parameters) {
        $label += ' params {' + (@($Parameters.Keys | ForEach-Object { "$_=" + (Format-LogValue $Parameters[$_]) }) -join ', ') + '}'
    }
    $watch = Start-SwisCallLog $label $body
    try { $result = Invoke-SwisRest $Conn 'Post' 'Query' $body }
    catch { Stop-SwisCallLog $label $watch '' $null $_.Exception.Message; throw }
    $rows = @()
    if ($null -ne $result) { $rows = @($result.results) }
    Stop-SwisCallLog $label $watch "$($rows.Count) row(s)" $result ''
    if ($null -eq $result) { return @() }
    return $rows
}

function Invoke-SwisVerbCall($Conn, [string]$Entity, [string]$SwisVerb, [array]$Arguments) {
    $summary = New-Object System.Collections.ArrayList
    if ($null -ne $Arguments) { foreach ($a in $Arguments) { [void]$summary.Add((Format-LogValue $a)) } }
    $label = "$Entity.$SwisVerb(" + ($summary -join ', ') + ')'
    $watch = Start-SwisCallLog $label $Arguments
    try { $result = Invoke-SwisRest $Conn 'Post' "Invoke/$Entity/$SwisVerb" $Arguments }
    catch { Stop-SwisCallLog $label $watch '' $null $_.Exception.Message; throw }
    Stop-SwisCallLog $label $watch (Format-LogValue $result) $result ''
    return $result
}

function Limit-OneLine([string]$Text, [int]$Width) {
    $t = (([string]$Text) -split '\s+' | Where-Object { $_ }) -join ' '
    if ($t.Length -le $Width) { return $t }
    return (Limit-Text $t $Width) + '...'
}

# =========================================================================
# NCM import: wire-format probe -> bottom-up -> nested console XML -> files
# =========================================================================
function ConvertTo-DcXml($Report, [string]$Ns, [string]$Kind, $Item, $IdList) {
    # DataContract shapes: alphabetical members; $Ns '' for the no-namespace try.
    $x = New-Object System.Xml.XmlDocument
    $mk = { param($n) if ($Ns) { $x.CreateElement($n, $Ns) } else { $x.CreateElement($n) } }
    $add = { param($p, $n, $t) $e = & $mk $n; if ($t) { $e.InnerText = $t }; [void]$p.AppendChild($e); $e }
    $addList = { param($p, $n, $ids)
        $holder = & $add $p $n ''
        foreach ($id in $ids) {
            $s = $x.CreateElement('string', 'http://schemas.microsoft.com/2003/10/Serialization/Arrays')
            $s.InnerText = $id; [void]$holder.AppendChild($s)
        } }
    switch ($Kind) {
        'rule' {
            $r = $Item
            $root = & $mk 'PolicyRule'; [void]$x.AppendChild($root)
            & $add $root 'AdvancedMode' (B $r.AdvancedMode) | Out-Null
            & $add $root 'Comments' $r.Comments | Out-Null
            & $add $root 'ConfigBlockEnd' $r.ConfigBlockEnd | Out-Null
            & $add $root 'ConfigBlockMustExist' (B $r.ConfigBlockMustExist) | Out-Null
            & $add $root 'ConfigBlockPatternType' $r.ConfigBlockPatternType | Out-Null
            & $add $root 'ConfigBlockStart' $r.ConfigBlockStart | Out-Null
            & $add $root 'ErrorLevel' ([string]$r.ErrorLevel) | Out-Null
            & $add $root 'ExecuteRemediationScriptPerBlock' (B $r.ExecuteRemediationScriptPerBlock) | Out-Null
            & $add $root 'ExecuteScriptAutomatically' (B $r.ExecuteScriptAutomatically) | Out-Null
            & $add $root 'ExecuteScriptInConfigMode' (B $r.ExecuteScriptInConfigMode) | Out-Null
            & $add $root 'Grouping' $r.Grouping | Out-Null
            & $add $root 'IsConfigBlockPatternRegEx' (B $r.IsConfigBlockPatternRegEx) | Out-Null
            & $add $root 'MultiLineRulePatterns' '' | Out-Null
            & $add $root 'Owner' $r.Owner | Out-Null
            & $add $root 'PatternMustExist' (B $r.PatternMustExist) | Out-Null
            & $add $root 'PatternType' $r.PatternType | Out-Null
            & $add $root 'RemediateScript' $r.RemediateScript | Out-Null
            & $add $root 'RemediateScriptType' $r.RemediateScriptType | Out-Null
            & $add $root 'RuleId' $r.RuleId | Out-Null
            & $add $root 'RuleName' $r.RuleName | Out-Null
            & $add $root 'SimplePatternText' $r.SimplePatternText | Out-Null
        }
        'policy' {
            $p = $Item
            $root = & $mk 'Policy'; [void]$x.AppendChild($root)
            & $add $root 'AssignedPolicyRules' '' | Out-Null
            & $addList $root 'AssignedRulesList' $IdList
            & $add $root 'Comments' $p.Comments | Out-Null
            & $add $root 'ConfigTypes' $p.ConfigTypes | Out-Null
            & $add $root 'Grouping' $p.Grouping | Out-Null
            & $add $root 'NodeSelectionString' $p.NodeSelectionString | Out-Null
            & $add $root 'PolicyId' $p.PolicyId | Out-Null
            & $add $root 'PolicyName' $p.PolicyName | Out-Null
        }
        'report' {
            $rep = $Item
            $root = & $mk 'PolicyReport'; [void]$x.AppendChild($root)
            & $add $root 'AssignedPolicies' '' | Out-Null
            & $addList $root 'AssignedPoliciesList' $IdList
            & $add $root 'Comments' $rep.Comments | Out-Null
            & $add $root 'Group' $rep.Group | Out-Null
            & $add $root 'ID' $rep.ID | Out-Null
            & $add $root 'Name' $rep.Name | Out-Null
            & $add $root 'ReportStatus' $rep.ReportStatus | Out-Null
            & $add $root 'ShowRulesWithoutViolationFlag' (B $rep.ShowRulesWithoutViolationFlag) | Out-Null
            & $add $root 'ShowSummaryFlag' (B $rep.ShowSummaryFlag) | Out-Null
        }
    }
    return $x.OuterXml
}

$script:DcNs = 'http://schemas.datacontract.org/2004/07/SolarWinds.NCM.Contracts.Compliance'

# The server's own shape of each NCM contract type (Python NCM_SHAPES, 2.1.0),
# learned once per run from an existing rule, policy and report. A 2026.4 server
# deserialized the JSON PolicyRule, ran AddPolicyRule and threw
# ArgumentNullException from Regex.IsMatch: a string member the published 2026.2
# contract does not list stayed null. JSON objects are therefore sent in the
# server's member order with every member it shows, missing ones filled empty.
$script:NcmShapes = @{}

function Initialize-NcmShapes($Conn, [scriptblock]$Log) {
    if ($script:NcmShapes.ContainsKey('learned')) { return }
    $script:NcmShapes['learned'] = $true
    $plan = @(
        @{ Kind = 'rule'; Query = 'SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules'; Column = 'PolicyRuleID'; Verb = 'GetPolicyRule'; Extra = @() },
        @{ Kind = 'policy'; Query = 'SELECT TOP 1 PolicyID FROM Cirrus.Policies'; Column = 'PolicyID'; Verb = 'GetPolicy'; Extra = @($false) },
        @{ Kind = 'report'; Query = 'SELECT TOP 1 PolicyReportID FROM Cirrus.PolicyReports'; Column = 'PolicyReportID'; Verb = 'GetPolicyReport'; Extra = @($false) })
    foreach ($p in $plan) {
        try {
            $rows = @(Invoke-SwisQuery $Conn $p.Query $null)
            if ($rows.Count -eq 0) {
                Write-ToolLog import info "server $($p.Kind) shape: no existing $($p.Kind) to read; the published contract is used"
                continue
            }
            $id = Get-RowValue $rows[0] $p.Column
            $sample = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' $p.Verb (@($id) + @($p.Extra))
            if ($sample -is [string]) { try { $sample = ConvertFrom-Json $sample } catch { } }
            if ($null -eq $sample -or $sample -is [string] -or $sample -is [System.ValueType]) {
                Write-ToolLog import warn "server $($p.Kind) shape: $($p.Verb) returned $(Format-LogValue $sample), not an object; the published contract is used"
                continue
            }
            $shape = [ordered]@{}
            if ($sample -is [System.Collections.IDictionary]) { foreach ($k in $sample.Keys) { $shape[[string]$k] = $sample[$k] } }
            else { foreach ($prop in $sample.PSObject.Properties) { $shape[$prop.Name] = $prop.Value } }
            $script:NcmShapes[$p.Kind] = $shape
            Write-ToolLog import info "server $($p.Kind) shape ($($p.Verb) on $id): $($shape.Count) member(s): $(@($shape.Keys) -join ', ')"
        } catch {
            Send-Log $Log 'import' 'warn' "[NCM] server $($p.Kind) shape could not be read ($($_.Exception.Message)); the published contract is used"
        }
    }
}

function Get-DefaultLike($Sample) {
    if ($Sample -is [bool]) { return $false }
    if ($Sample -is [int] -or $Sample -is [long] -or $Sample -is [double] -or $Sample -is [decimal]) { return 0 }
    if ($Sample -is [array]) { return @() }
    if ($Sample -is [System.Management.Automation.PSCustomObject] -or $Sample -is [System.Collections.IDictionary]) { return $null }
    return ''
}

# Python member_stem: the 2026.4.0 server names its JSON members differently from
# the published contract (rule ID/Name, policy AssgnedPolicyRulesList (sic),
# report Policies). Two members match when their stems agree: lower case, with
# these qualifying prefixes stripped repeatedly.
$script:MemberPrefixes = @('assigned', 'assgned', 'node', 'rule', 'policy')

function Get-MemberStem([string]$Name) {
    $stem = ([string]$Name).ToLowerInvariant()
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($p in $script:MemberPrefixes) {
            if ($stem.StartsWith($p) -and $stem.Length -gt $p.Length) { $stem = $stem.Substring($p.Length); $changed = $true }
        }
    }
    return $stem
}

function ConvertTo-ServerShape($Obj, [string]$Kind) {
    # Python conform_to_shape: the object in the server's member order. Every member
    # the server shows gets the tool's value by name (any case) or, failing that, by
    # stem (RuleId -> ID, PolicyName -> Name, AssignedPolicies -> Policies); a member
    # the tool has no value for is sent empty; the tool's members the server does not
    # show are dropped. Without a learned shape the object is returned as it is.
    if (-not $script:NcmShapes.ContainsKey($Kind)) { return $Obj }
    $shape = $script:NcmShapes[$Kind]
    $unused = [ordered]@{}
    $byLower = @{}
    $byStem = @{}
    foreach ($k in $Obj.Keys) {
        $unused[[string]$k] = $Obj[$k]
        $byLower[([string]$k).ToLowerInvariant()] = [string]$k
        $stem = Get-MemberStem $k
        if (-not $byStem.ContainsKey($stem)) { $byStem[$stem] = [string]$k }
    }
    $out = [ordered]@{}
    $renamed = New-Object System.Collections.ArrayList
    $missing = New-Object System.Collections.ArrayList
    foreach ($k in $shape.Keys) {
        $key = [string]$k
        $mine = $null
        if ($byLower.ContainsKey($key.ToLowerInvariant())) { $mine = $byLower[$key.ToLowerInvariant()] }
        if ($null -eq $mine) {
            $stem = Get-MemberStem $key
            if ($byStem.ContainsKey($stem) -and $unused.Contains($byStem[$stem])) { $mine = $byStem[$stem]; [void]$renamed.Add("$mine -> $key") }
        }
        if ($null -ne $mine -and $unused.Contains($mine)) { $out[$key] = $unused[$mine]; $unused.Remove($mine) }
        else { $out[$key] = Get-DefaultLike $shape[$k]; [void]$missing.Add($key) }
    }
    $dropped = @($unused.Keys)
    if (-not $script:NcmShapes.ContainsKey("logged:$Kind")) {
        $script:NcmShapes["logged:$Kind"] = $true
        $parts = New-Object System.Collections.ArrayList
        [void]$parts.Add("JSON $Kind objects follow the server's $($shape.Count)-member shape")
        if ($renamed.Count -gt 0) { [void]$parts.Add("renamed to the server's members: $($renamed -join ', ')") }
        if ($missing.Count -gt 0) { [void]$parts.Add("members the tool has no value for, sent empty: $($missing -join ', ')") }
        if ($dropped.Count -gt 0) { [void]$parts.Add("the tool's members the server does not show, dropped: $($dropped -join ', ')") }
        $lvl = 'info'; if ($missing.Count -gt 0) { $lvl = 'warn' }
        Write-ToolLog import $lvl ($parts -join '; ')
    }
    return $out
}

function Get-WireArgument([string]$Format, [string]$Kind, $Item, $IdList) {
    switch ($Format) {
        'json' {
            switch ($Kind) {
                'rule' { return (ConvertTo-ServerShape $Item 'rule') }
                'policy' {
                    $c = [ordered]@{} + $Item
                    $c.AssignedPolicyRules = @(); $c.AssignedRulesList = @($IdList)
                    return (ConvertTo-ServerShape $c 'policy')
                }
                'report' {
                    $c = [ordered]@{} + $Item
                    $c.AssignedPolicies = @(); $c.AssignedPoliciesList = @($IdList)
                    return (ConvertTo-ServerShape $c 'report')
                }
            }
        }
        'xml-dc'    { return ConvertTo-DcXml $null $script:DcNs $Kind $Item $IdList }
        'xml-plain' { return ConvertTo-DcXml $null '' $Kind $Item $IdList }
    }
}

function Get-CleanId($Value, [string]$Fallback) {
    if ($Value -is [string]) {
        $c = $Value.Trim().Trim('"').Trim('{', '}').Trim()
        if ($c) { return $c }
    }
    if ($null -ne $Value) { return [string]$Value }
    return $Fallback
}

function Get-NormId($Value) {
    # Compare GUIDs from verb results and SWQL rows on equal terms.
    if ($null -eq $Value) { return '' }
    return ([string]$Value).Trim().Trim('"').Trim('{', '}').Trim().ToLower()
}

function Invoke-SwisQueryIds($Conn, [string]$Swql, $Ids) {
    # Run an `IN @ids` query over a list of ids in bounded chunks.
    $list = @(@($Ids) | Where-Object { $_ })
    $rows = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $list.Count; $i += 100) {
        $chunk = @($list[$i..([Math]::Min($i + 99, $list.Count - 1))])
        foreach ($row in @(Invoke-SwisQuery $Conn $Swql @{ ids = $chunk })) { [void]$rows.Add($row) }
    }
    return @($rows)   # callers wrap the call in @() to keep an array
}

function Get-RowValue($Row, [string]$Column) {
    if ($null -eq $Row) { return $null }
    if ($Row -is [System.Collections.IDictionary]) { return $Row[$Column] }
    if ($Row.PSObject.Properties[$Column]) { return $Row.$Column }
    return $null
}

function Get-HttpStatus([string]$Text) {
    # The HTTP status an error message names ('SWIS HTTP 403 from ...'), or 0.
    if ($Text -match '\bHTTP (\d{3})\b') { return [int]$Matches[1] }
    return 0
}

# The two HTTP 400 rejections docs/modules/ncm-compliance-reports.md records for
# the NCM contract types over JSON REST (a field observation on 2026.2.2). Only
# these mean "this wire format was refused, try the next one"; any other 400, and
# every 401, 403, 409 or 500, stops that report with the server's message, rolls
# back, and writes no console file. Unverified: a server on another .NET runtime
# may word the null-argument rejection differently; that is treated as an
# undocumented 400 (the report stops) rather than guessed at. Same as Python.
$script:WireRejectionPatterns = @('(?i)Value cannot be null\.?\s*Parameter name:\s*input',
                                  '(?i)\bcannot unpackage parameter \d+')

function Test-WireRejection([string]$Text) {
    if ((Get-HttpStatus $Text) -ne 400) { return $false }
    foreach ($p in $script:WireRejectionPatterns) { if ($Text -match $p) { return $true } }
    return $false
}

# The NCM role each Cirrus.PolicyReports verb this tool calls needs, from the
# 2026.2 verb descriptions (python tools/schema_query.py verb Cirrus.PolicyReports
# <verb>). With the server's "compliance only for administrators" option on, all
# of them are valid only for Orion administrators.
$script:NcmVerbRoles = @(
    @{ Role = 'WebDownloader'; Verbs = @('AddPolicyRule', 'AddPolicy', 'AddPolicyReport', 'GetPolicyReport',
        'DeletePolicyRules', 'DeletePolicies', 'DeletePolicyReports', 'TestRule', 'TestRuleOnBackedUpConfig') },
    @{ Role = 'WebUploader'; Verbs = @('StartCaching', 'UpdateReportStatus') })
$script:RoleHint = ('Check that the account has at least the WebDownloader NCM role (WebUploader for ' +
    'StartCaching and UpdateReportStatus), or is an Orion administrator when the server restricts ' +
    'compliance to administrators.')
$script:NilGuid = '00000000-0000-0000-0000-000000000000'

function Invoke-NcmPreflight($Conn, [scriptblock]$Log) {
    # Before anything is written: logs the role each verb needs, then calls
    # GetPolicyReport (WebDownloader, like every write the import makes) for the
    # nil GUID. Any answer confirms access; 401, 403 or a permission message stops
    # the run before anything is created. Unverified: the answer for an id that
    # does not exist is not documented, so other errors are inconclusive and the
    # import goes ahead. Returns 'ok' or 'inconclusive'. Same as Python ncm_preflight.
    foreach ($entry in $script:NcmVerbRoles) {
        Write-ToolLog import info ("NCM role needed (2026.2 verb descriptions): $($entry.Role) or higher for " + ($entry.Verbs -join ', '))
    }
    Write-ToolLog import info ("when the server's 'compliance only for administrators' option is on, every one of " +
        'those verbs is valid only for Orion administrators')
    try {
        $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'GetPolicyReport' @($script:NilGuid, $false)
    } catch {
        $text = $_.Exception.Message
        $status = Get-HttpStatus $text
        $denied = $text -match '(?i)access (is )?denied|not authori[sz]ed|permission|forbidden|only for (orion )?admin'
        if ($status -eq 401 -or $status -eq 403 -or ($status -gt 0 -and $denied)) {
            $last = @($text -split "`n")[-1]
            $msg = ("[NCM] permission preflight: this account may not call Cirrus.PolicyReports GetPolicyReport " +
                "(HTTP $status): $last. The import needs at least the WebDownloader NCM role (WebUploader to " +
                'start caching or change ReportStatus), or an Orion administrator when the server restricts ' +
                'compliance to administrators. Nothing was created.')
            Write-ToolLog import error $msg
            throw $msg
        }
        if ($status -eq 0) { throw }
        Send-Log $Log 'import' 'warn' ("[NCM] permission preflight inconclusive: GetPolicyReport for the nil GUID answered " +
            "HTTP $status (Unverified: the answer for an id that does not exist is not documented); continuing")
        return 'inconclusive'
    }
    Write-ToolLog import info ("permission preflight ok: GetPolicyReport answered $(Format-LogValue $result) for an " +
        'id that does not exist, so the account may call the compliance verbs')
    return 'ok'
}

# IN @ids sanity probe. docs/swis/rest-api.md documents the array binding with
# integers; whether every server binds an array of GUID strings the same way is
# Unverified. Before any decision based on such a query (the existing-id
# snapshot, a removal or nested-rollback plan), the query is run for one id known
# to exist and exactly one matching row is required. Same as Python.
$script:InIdsProbes = @{
    report = @('SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids', 'PolicyReportID')
    policy = @('SELECT PolicyID FROM Cirrus.Policies WHERE PolicyID IN @ids', 'PolicyID')
    rule   = @('SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids', 'PolicyRuleID')
}

function Confirm-InIds($Conn, [string]$Kind, [string]$KnownId, [string]$Purpose, [string]$Component = 'import') {
    $probe = $script:InIdsProbes[$Kind]
    $rows = @(Invoke-SwisQuery $Conn $probe[0] @{ ids = @($KnownId) })
    $matched = @($rows | Where-Object { (Get-NormId (Get-RowValue $_ $probe[1])) -eq (Get-NormId $KnownId) })
    if ($rows.Count -ne 1 -or $matched.Count -ne 1) {
        $msg = ("[NCM] IN @ids sanity probe failed before ${Purpose}: querying the $Kind $KnownId, which is known " +
            "to exist, returned $($rows.Count) row(s) instead of exactly 1. This server does not bind a GUID array " +
            'to IN @ids the way the tool expects, so a decision based on it could delete the wrong objects; ' +
            'stopping instead. Nothing was deleted by this step.')
        Write-ToolLog $Component error $msg
        $err = New-Object System.Exception $msg
        $err.Data['InIdsProbe'] = $true
        throw $err
    }
    Write-ToolLog $Component info "IN @ids sanity probe ok before ${Purpose}: the $Kind $KnownId returned exactly one row"
}

function Get-ExistingNcmIds($Conn, $Report) {
    # RuleIds are uuid5-derived from the DISA rule id, so a second import of the
    # same STIG release submits ids an earlier import already created. Those
    # must survive a rollback, so they are recorded before anything is created.
    # Unverified: whether AddPolicyRule/AddPolicy honour a submitted id is not
    # documented; the returned id is used either way. Each lookup follows the
    # IN @ids sanity probe on a row SELECT TOP 1 returns; an empty table needs none.
    $ruleIds = @($Report.AssignedPolicies | ForEach-Object { $_.AssignedPolicyRules } | ForEach-Object { $_.RuleId })
    $policyIds = @($Report.AssignedPolicies | ForEach-Object { $_.PolicyId } | Where-Object { $_ })
    $found = @{ rule = @{}; policy = @{} }
    $cases = @(
        @{ Kind = 'rule'; Ids = $ruleIds; Sample = 'SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules' },
        @{ Kind = 'policy'; Ids = $policyIds; Sample = 'SELECT TOP 1 PolicyID FROM Cirrus.Policies' })
    foreach ($case in $cases) {
        if ($case.Ids.Count -eq 0) { continue }
        $probe = $script:InIdsProbes[$case.Kind]
        $sample = @(Invoke-SwisQuery $Conn $case.Sample $null)
        $known = $null
        if ($sample.Count -gt 0) { $known = Get-RowValue $sample[0] $probe[1] }
        if (-not $known) {
            Write-ToolLog import info "the server returned no $($case.Kind) rows, so none of the $($case.Ids.Count) submitted $($case.Kind) id(s) can already exist"
            continue
        }
        Confirm-InIds $Conn $case.Kind ([string]$known) "the existing-$($case.Kind)-id snapshot"
        foreach ($row in @(Invoke-SwisQueryIds $Conn $probe[0] $case.Ids)) {
            $found[$case.Kind][(Get-NormId (Get-RowValue $row $probe[1]))] = $true
        }
    }
    return @{ Rules = $found.rule; Policies = $found.policy }
}

function Undo-NcmImport($Conn, $RuleIds, $PolicyIds, [string]$ReportId, [scriptblock]$Log,
                        $Preexisting = $null) {
    # A STIG report is built from the bottom up, so a failure at the policy or
    # report step leaves every rule already created sitting in the NCM rules
    # library with nothing pointing at it: invisible in the Compliance view,
    # deleted by nothing, and duplicated by the next attempt. Children are
    # removed by their own verbs rather than with DeletePolicyReports
    # -deleteChildren, which would also reach rules other reports share.
    # Ids that existed before this run ($Preexisting, from Get-ExistingNcmIds)
    # are skipped, so a rollback deletes only what this run created.
    if ($null -eq $Preexisting) { $Preexisting = @{ Rules = @{}; Policies = @{} } }
    $split = {
        param($Ids, $Known)
        $ours = New-Object System.Collections.ArrayList
        $kept = New-Object System.Collections.ArrayList
        $seen = @{}
        foreach ($id in @($Ids)) {
            $key = Get-NormId $id
            if (-not $key -or $seen.ContainsKey($key)) { continue }
            $seen[$key] = $true
            if ($Known.ContainsKey($key)) { [void]$kept.Add($id) } else { [void]$ours.Add($id) }
        }
        return @{ Ours = @($ours); Kept = @($kept) }
    }
    $drop = {
        # Every failure is caught (a transport error as much as an HTTP error),
        # logged, and the rollback carries on with the next level.
        param($SwisVerb, $Arguments)
        try { [void](Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' $SwisVerb $Arguments) }
        catch { Send-Log $Log 'rollbk' 'error' "[NCM] rollback: $SwisVerb failed, clean up by hand - $($_.Exception.Message)" }
    }
    $pol = & $split $PolicyIds $Preexisting.Policies
    $rul = & $split $RuleIds $Preexisting.Rules
    $shownReport = $ReportId; if (-not $shownReport) { $shownReport = '(none created)' }
    Write-ToolLog rollbk info ("rollback plan: report $shownReport, $($pol.Ours.Count) policy id(s) and " +
        "$($rul.Ours.Count) rule id(s) to delete; $($pol.Kept.Count) policy id(s) and $($rul.Kept.Count) " +
        'rule id(s) kept because they existed before this run')
    if ($ReportId) {
        Send-Log $Log 'rollbk' 'info' "[NCM] rollback: deleting report $ReportId"
        & $drop 'DeletePolicyReports' @(@($ReportId), $false)
    }
    if ($pol.Ours.Count -gt 0) {
        Send-Log $Log 'rollbk' 'info' "[NCM] rollback: deleting $($pol.Ours.Count) policy/policies"
        & $drop 'DeletePolicies' @(@($pol.Ours), $false)
    }
    if ($rul.Ours.Count -gt 0) {
        Send-Log $Log 'rollbk' 'info' "[NCM] rollback: deleting $($rul.Ours.Count) rule(s)"
        & $drop 'DeletePolicyRules' @(, @($rul.Ours))
    }
    foreach ($id in $pol.Kept) {
        Send-Log $Log 'rollbk' 'info' "[NCM] rollback: skipped policy $id - it existed on the server before this import, so this run did not create it"
    }
    foreach ($id in $rul.Kept) {
        Send-Log $Log 'rollbk' 'info' "[NCM] rollback: skipped rule $id - it existed on the server before this import (an earlier import of the same STIG release?), so this run did not create it"
    }
}

function Test-NcmRule($Conn, $Rule, [string]$ConfigText, [string]$ConfigId, [string]$Format) {
    # TestRule / TestRuleOnBackedUpConfig evaluate an unsaved rule against a real
    # configuration and create nothing, so this is the one way to see what a
    # generated pattern does before a whole benchmark is imported on the strength
    # of it. The rule travels as the same contract type AddPolicyRule takes, so
    # the same wire-format ambiguity applies. SolarWinds documents the result as
    # a string without documenting its shape, so it is returned verbatim.
    $candidates = if ($Format) { @($Format) } else { @('json', 'xml-dc', 'xml-plain') }
    $rejections = New-Object System.Collections.ArrayList
    foreach ($f in $candidates) {
        try {
            $arg = Get-WireArgument $f 'rule' $Rule $null
            if ($ConfigId) {
                $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' `
                    'TestRuleOnBackedUpConfig' @($arg, $ConfigId)
            } else {
                $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'TestRule' `
                    @($arg, $ConfigText)
            }
            return @{ Result = $result; Format = $f }
        } catch {
            if (-not (Test-WireRejection $_.Exception.Message)) {
                Write-ToolLog verify error "TestRule stopped: $f failed with an error that is not a documented wire-format rejection"
                throw
            }
            [void]$rejections.Add($f)
        }
    }
    throw ('[NCM] this server accepted none of the wire formats for TestRule: ' +
        ($rejections -join ', '))
}

# Read-back comparison: policy count, rule count and per-policy rule names (the
# comparison Porter 0.3.0 makes). Compare-NcmReportTree returns the same text as
# the Python compare_report_trees; the parity test checks it.
function Get-ExpectedReportTree($Report) {
    $tree = New-Object System.Collections.ArrayList
    foreach ($p in @($Report.AssignedPolicies)) {
        $names = @(@($p.AssignedPolicyRules) | Where-Object { $null -ne $_ } | ForEach-Object { [string]$_.RuleName })
        [void]$tree.Add([pscustomobject]@{ Policy = [string]$p.PolicyName; Rules = [string[]]$names })
    }
    return @{ Policies = $tree }
}

function Test-ToolObject($Value) {
    return ($Value -is [System.Collections.IDictionary] -or $Value -is [System.Management.Automation.PSCustomObject])
}

function Get-ReadBackTree($Stored) {
    # @{ Policies = ... } from a GetPolicyReport(id, true) result, or $null when it
    # cannot be compared: not an object, an entry that is not an object, or the
    # nested AssignedPolicies absent while AssignedPoliciesList names policies.
    if (-not (Test-ToolObject $Stored)) { return $null }
    # The 2026.4.0 server answers with its own member names (Policies, Name,
    # AssgnedPolicyRules); the published ones are accepted too (Python _member).
    $policies = Get-FirstMember $Stored @('AssignedPolicies', 'Policies')
    $tree = New-Object System.Collections.ArrayList
    if ($null -eq $policies -or $policies -is [string]) {
        $listed = @(Get-RowValue $Stored 'AssignedPoliciesList' | Where-Object { $null -ne $_ })
        if ($listed.Count -gt 0) { return $null }
        return @{ Policies = $tree }
    }
    foreach ($p in @($policies)) {
        if (-not (Test-ToolObject $p)) { return $null }
        $names = New-Object System.Collections.ArrayList
        foreach ($r in @(Get-FirstMember $p @('AssignedPolicyRules', 'AssgnedPolicyRules'))) {
            if ($null -eq $r) { continue }
            if (-not (Test-ToolObject $r)) { return $null }
            [void]$names.Add([string](Get-FirstMember $r @('RuleName', 'Name')))
        }
        [void]$tree.Add([pscustomobject]@{ Policy = [string](Get-FirstMember $p @('PolicyName', 'Name')); Rules = [string[]]@($names) })
    }
    return @{ Policies = $tree }
}

function Get-FirstMember($Obj, [string[]]$Names) {
    # Python _member: the first of $Names present on $Obj (any case), else $null.
    foreach ($n in $Names) {
        if ($Obj -is [System.Collections.IDictionary]) {
            foreach ($k in $Obj.Keys) { if ([string]$k -ieq $n) { return $Obj[$k] } }
        } else {
            foreach ($prop in $Obj.PSObject.Properties) { if ($prop.Name -ieq $n) { return $prop.Value } }
        }
    }
    return $null
}

function Get-StoredScopeSql($Stored) {
    # Python stored_scope_sql: the "SQL:Where ..." part of the first stored policy's
    # NodeSelectionString, or $null. The server rebuilds that SQL from the typed
    # SelectionCriterias, so a condition that lived only in the submitted SQL is gone.
    if (-not (Test-ToolObject $Stored)) { return $null }
    $policies = Get-FirstMember $Stored @('AssignedPolicies', 'Policies')
    if ($null -eq $policies -or $policies -is [string] -or @($policies).Count -eq 0) { return $null }
    $text = [string](Get-FirstMember @($policies)[0] @('NodeSelectionString'))
    if ($text -notmatch 'SQL:') { return $null }
    return $text.Substring($text.IndexOf('SQL:') + 4).Trim()
}

function Compare-NcmReportTree($Expected, $Actual) {
    $diffs = New-Object System.Collections.ArrayList
    $nExpected = 0; foreach ($p in $Expected.Policies) { $nExpected += @($p.Rules).Count }
    $nActual = 0; foreach ($p in $Actual.Policies) { $nActual += @($p.Rules).Count }
    if ($Expected.Policies.Count -ne $Actual.Policies.Count) {
        [void]$diffs.Add("policies: expected $($Expected.Policies.Count), stored $($Actual.Policies.Count)")
    }
    if ($nExpected -ne $nActual) { [void]$diffs.Add("rules: expected $nExpected, stored $nActual") }
    $stored = New-Object 'System.Collections.Generic.Dictionary[string,System.Collections.ArrayList]' ([StringComparer]::Ordinal)
    foreach ($p in $Actual.Policies) {
        if (-not $stored.ContainsKey($p.Policy)) { $stored[$p.Policy] = New-Object System.Collections.ArrayList }
        [void]$stored[$p.Policy].Add(@($p.Rules))
    }
    foreach ($p in $Expected.Policies) {
        if (-not $stored.ContainsKey($p.Policy) -or $stored[$p.Policy].Count -eq 0) {
            [void]$diffs.Add("policy `"$($p.Policy)`" missing"); continue
        }
        $match = @($stored[$p.Policy][0]); $stored[$p.Policy].RemoveAt(0)
        $have = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
        foreach ($r in $match) { [void]$have.Add([string]$r) }
        $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
        $missing = New-Object System.Collections.ArrayList
        foreach ($r in @($p.Rules)) { if (-not $have.Contains([string]$r) -and $seen.Add([string]$r)) { [void]$missing.Add([string]$r) } }
        if ($match.Count -ne @($p.Rules).Count -or $missing.Count -gt 0) {
            $text = "policy `"$($p.Policy)`": expected $(@($p.Rules).Count) rules, stored $($match.Count)"
            if ($missing.Count -gt 0) {
                $shown = @($missing | Select-Object -First 3)
                $text += ' (missing "' + ($shown -join '", "') + '"'
                if ($missing.Count -gt 3) { $text += ', ...' }
                $text += ')'
            }
            [void]$diffs.Add($text)
        }
    }
    return @($diffs)
}

function New-NcmVerificationError([string]$Message) {
    Write-ToolLog verify error $Message
    $err = New-Object System.Exception $Message
    $err.Data['Verification'] = $true
    return $err
}

function Test-NcmImport($Conn, [string]$ReportId, $Report, [scriptblock]$Log) {
    # Read the report back and compare it with what was submitted: the import is
    # only done when the stored tree has the same policies, rule count and rule
    # names per policy. A partial tree or a result that is not a report object
    # throws with Data['Verification'] set; callers treat it as a failed import.
    $expected = Get-ExpectedReportTree $Report
    $nPolicies = $expected.Policies.Count
    $nRules = 0; foreach ($p in $expected.Policies) { $nRules += @($p.Rules).Count }
    Write-ToolLog verify info "reading report $ReportId back (expecting $nPolicies policies and $nRules rules)"
    $stored = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'GetPolicyReport' @($ReportId, $true)
    if ($null -eq $stored -or ($stored -is [string] -and -not $stored.Trim())) {
        throw (New-NcmVerificationError "[NCM] No Data Returned from GetPolicyReport for report $ReportId - the import cannot be confirmed")
    }
    $actual = Get-ReadBackTree $stored
    if ($null -eq $actual) {
        $diffs = @("GetPolicyReport(id, true) returned $(Format-LogValue $stored) instead of a readable report object")
    } else {
        $diffs = @(Compare-NcmReportTree $expected $actual)
    }
    if ($diffs.Count -gt 0) {
        $held = 'nothing readable'
        if ($null -ne $actual) {
            $n = 0; foreach ($p in $actual.Policies) { $n += @($p.Rules).Count }
            $held = "$($actual.Policies.Count) policies / $n rules"
        }
        $msg = ("[NCM] verification failed: report $ReportId was created but the server holds $held; the import " +
            "carried $nPolicies policies / $nRules rules - " + (@($diffs | Select-Object -First 5) -join '; '))
        if ($diffs.Count -gt 5) { $msg += "; ... and $($diffs.Count - 5) more" }
        throw (New-NcmVerificationError ($msg + '. ' + $script:RoleHint))
    }
    Send-Log $Log 'verify' 'info' "[NCM] verified: report holds $($actual.Policies.Count) policies and $nRules rules, matching the import (policy names and rule names compared)"
    $sentSql = $null
    foreach ($p in @($Report.AssignedPolicies)) {
        $text = [string]$p.NodeSelectionString
        if ($text -match 'SQL:') { $sentSql = $text.Substring($text.IndexOf('SQL:') + 4).Trim() }
        break
    }
    $storedSql = Get-StoredScopeSql $stored
    if ($sentSql -and $storedSql -and (($sentSql -replace '\s+', ' ') -ne ($storedSql -replace '\s+', ' '))) {
        Send-Log $Log 'verify' 'warn' ("[NCM] warning: the server stored the node scope as `"$storedSql`", not the submitted `"$sentSql`": " +
            'it rebuilds the SQL from the typed selection criteria, which carry the Vendor condition only. Add the ' +
            'remaining condition (the MachineType pattern) in the console under the report''s node selection, or it ' +
            'scopes every node of that vendor.')
    }
    return @{ ReportId = $ReportId; Policies = $actual.Policies.Count; Rules = $nRules }
}

function Write-UnknownOutcome([scriptblock]$Log, [string]$Kind, [string]$SubmittedId, $Preexisting) {
    # A call that failed below HTTP (a timeout, a reset) may still have run server side.
    $known = $Preexisting.Rules; if ($Kind -eq 'policy') { $known = $Preexisting.Policies }
    if ($known.ContainsKey((Get-NormId $SubmittedId))) { return }
    Send-Log $Log 'import' 'warn' ("[NCM] warning: the outcome of the failed call is unknown (no HTTP status): if the " +
        "server created the $Kind anyway, it is not in the rollback list. Check for $Kind id $SubmittedId " +
        '(Unverified: whether the server keeps a submitted id is not documented).')
}

function Undo-NcmNestedImport($Conn, [string]$ReportId, $Preexisting, [scriptblock]$Log) {
    # Delete what a nested AddPolicyReport created: the report row, then the
    # policies and rules nothing else uses (the plan -Remove makes), skipping every
    # id that existed before this run. The IN @ids probe in Get-NcmRemovalPlan
    # runs first; when it fails, nothing is deleted and the error stops the report.
    Send-Log $Log 'rollbk' 'info' "[NCM] rollback: removing the nested import's report $ReportId and what only it uses"
    $plan = Get-NcmRemovalPlan $Conn @($ReportId) $Log
    $keptPolicies = @($plan.DeletePolicies | Where-Object { $Preexisting.Policies.ContainsKey((Get-NormId $_)) })
    $keptRules = @($plan.DeleteRules | Where-Object { $Preexisting.Rules.ContainsKey((Get-NormId $_)) })
    $plan.DeletePolicies = @($plan.DeletePolicies | Where-Object { -not $Preexisting.Policies.ContainsKey((Get-NormId $_)) })
    $plan.DeleteRules = @($plan.DeleteRules | Where-Object { -not $Preexisting.Rules.ContainsKey((Get-NormId $_)) })
    foreach ($i in $keptPolicies) { Send-Log $Log 'rollbk' 'info' "[NCM] rollback: skipped policy $i - it existed on the server before this import" }
    foreach ($i in $keptRules) { Send-Log $Log 'rollbk' 'info' "[NCM] rollback: skipped rule $i - it existed on the server before this import" }
    Write-NcmRemovalPlan $plan $Log
    try { $left = Remove-NcmReports $Conn $plan $Log }
    catch {
        Send-Log $Log 'rollbk' 'error' "[NCM] rollback: deleting the nested import failed, clean up by hand (report $ReportId) - $($_.Exception.Message)"
        return
    }
    if ($left.reports.Count + $left.policies.Count + $left.rules.Count -gt 0) {
        Send-Log $Log 'rollbk' 'error' "[NCM] rollback: some objects of report $ReportId are still present; clean up by hand"
    }
}

# How each report reached the server, by report name (Python NCM_IMPORT_ROUTES, 2.1.0):
# set by Import-NcmReport, read by Get-NcmImportSummary for the log view.
$script:NcmImportRoutes = @{}

function Get-ReportCounts($Report) {
    $pols = @($Report.AssignedPolicies)
    $rules = 0; foreach ($p in $pols) { $rules += @($p.AssignedPolicyRules).Count }
    return @{ Policies = $pols.Count; Rules = $rules }
}

function Get-NcmImportSummary($Reports, $Imported, $Remaining, [bool]$ConsoleFiles = $false) {
    # Python ncm_import_summary: how each report was imported (route, server id,
    # policy and rule counts), which were not, then the totals against the package.
    $lines = New-Object System.Collections.ArrayList
    $gotPol = 0; $gotRules = 0
    foreach ($i in @($Imported)) {
        $c = Get-ReportCounts $i.Report
        $route = 'API'; if ($script:NcmImportRoutes.ContainsKey($i.Report.Name)) { $route = $script:NcmImportRoutes[$i.Report.Name] }
        [void]$lines.Add("imported via ${route}: `"$($i.Report.Name)`" ($($i.ReportId)) - $($c.Policies) policy(ies), $($i.Rules) rules")
        $gotPol += $c.Policies; $gotRules += [int]$i.Rules
    }
    foreach ($rep in @($Remaining)) {
        $c = Get-ReportCounts $rep
        $how = 'not imported'; if ($ConsoleFiles) { $how = 'console-importable file written; import it through the web console' }
        [void]$lines.Add("${how}: `"$($rep.Name)`" - $($c.Policies) policy(ies), $($c.Rules) rules")
    }
    $totalPol = 0; $totalRules = 0
    foreach ($rep in @($Reports)) { $c = Get-ReportCounts $rep; $totalPol += $c.Policies; $totalRules += $c.Rules }
    [void]$lines.Add("NCM totals: $(@($Imported).Count) of $(@($Reports).Count) report(s), $gotPol of $totalPol policy(ies), " +
        "$gotRules of $totalRules rule(s) imported and verified on the server")
    return , @($lines)
}

function Get-NcmOfflineSummary($Reports, $Files) {
    $totalPol = 0; $totalRules = 0
    foreach ($rep in @($Reports)) { $c = Get-ReportCounts $rep; $totalPol += $c.Policies; $totalRules += $c.Rules }
    return ("NCM totals: $(@($Files).Count) console file(s) written for $(@($Reports).Count) report(s), " +
        "$totalPol policy(ies), $totalRules rule(s); nothing was sent to a server")
}

function Get-ScmImportSummary($Entries, [string]$What = 'imported') {
    # Python scm_import_summary: each policy's name and rule count, then the totals.
    # $Entries: array of @{ Name; PolicyId ($null when offline); Rules }.
    $lines = New-Object System.Collections.ArrayList
    $total = 0
    foreach ($e in @($Entries)) {
        $id = ''; if ($null -ne $e.PolicyId) { $id = " (PolicyID $($e.PolicyId))" }
        [void]$lines.Add("SCM policy `"$($e.Name)`"$id - $($e.Rules) rules defined")
        $total += [int]$e.Rules
    }
    [void]$lines.Add("SCM totals: $(@($Entries).Count) policy(ies), $total rule(s) $What")
    return , @($lines)
}

function Get-ScmRuleCount([string]$Yaml) {
    $norm = ([string]$Yaml) -replace "`r`n", "`n"
    return ([regex]::Matches($norm, '(?m)^- displayId:')).Count
}

function Import-NcmReport($Conn, $Report, [scriptblock]$Log, [bool]$Rollback = $true) {
    # Probe with one cheap AddPolicyRule per wire format (JSON object,
    # DataContract XML, plain XML), then run bottom-up in the accepted format.
    # Only a documented 400 moves on to the next format; any other error stops
    # this report. Falls back to a nested console-format AddPolicyReport, verified
    # and rolled back like the rest; if everything is refused, throws with
    # WireFailure=$true so the caller writes console files.
    $labels = @{ 'json' = 'JSON contract objects'; 'xml-dc' = 'DataContract XML strings'
                 'xml-plain' = 'plain XML strings (no namespace)' }
    $preexisting = Get-ExistingNcmIds $Conn $Report
    Write-ToolLog import info ("existing-id snapshot for `"$($Report.Name)`": $($preexisting.Rules.Count) " +
        "rule id(s) and $($preexisting.Policies.Count) policy id(s) already on the server")
    if ($preexisting.Rules.Count -gt 0 -or $preexisting.Policies.Count -gt 0) {
        Send-Log $Log 'import' 'info' ("[NCM] note: $($preexisting.Rules.Count) rule id(s) and $($preexisting.Policies.Count) " +
            'policy id(s) this report submits already exist on the server; a rollback will leave those alone')
    }
    $probeRule = $Report.AssignedPolicies[0].AssignedPolicyRules[0]
    Initialize-NcmShapes $Conn $Log
    $format = $null; $firstId = $null
    $rejections = New-Object System.Collections.ArrayList
    foreach ($f in @('json', 'xml-dc', 'xml-plain')) {
        try {
            $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyRule' `
                @((Get-WireArgument $f 'rule' $probeRule $null))
            $firstId = Get-CleanId $result $probeRule.RuleId
            $format = $f
            $script:NcmImportRoutes[$Report.Name] = "API, per item ($($labels[$f]))"
            Send-Log $Log 'import' 'info' "[NCM] server accepts $($labels[$f])"
            break
        } catch {
            $text = $_.Exception.Message
            if (-not (Test-WireRejection $text)) {
                $status = Get-HttpStatus $text; $shown = 'none'; if ($status) { $shown = $status }
                Write-ToolLog import error ("wire-format probe stopped: $($labels[$f]) failed with an error that is not a " +
                    "documented wire-format rejection (HTTP $shown), so no other format is tried and no console file is written for it")
                if ($status -eq 0) { Write-UnknownOutcome $Log 'rule' $probeRule.RuleId $preexisting }
                throw
            }
            [void]$rejections.Add("$($labels[$f]): " + @($text -split "`n")[-1])
            Send-Log $Log 'import' 'warn' "[NCM] server rejected $($labels[$f]); trying the next wire format"
        }
    }
    if ($format) {
        $policyIds = New-Object System.Collections.ArrayList
        $allRuleIds = New-Object System.Collections.ArrayList
        [void]$allRuleIds.Add($firstId)
        $reportId = ''
        $first = $true
        $pending = $null
        try {
            foreach ($p in $Report.AssignedPolicies) {
                $ruleIds = New-Object System.Collections.ArrayList
                $i = 0
                foreach ($r in $p.AssignedPolicyRules) {
                    $i++
                    if ($first) { [void]$ruleIds.Add($firstId); $first = $false; continue }
                    $pending = @('rule', $r.RuleId)
                    $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyRule' `
                        @((Get-WireArgument $format 'rule' $r $null))
                    $newRuleId = Get-CleanId $result $r.RuleId
                    [void]$ruleIds.Add($newRuleId)
                    [void]$allRuleIds.Add($newRuleId)
                    if ($i % 25 -eq 0) { Send-Log $Log 'import' 'info' "[NCM]   $i/$($p.AssignedPolicyRules.Count) rules created" }
                }
                $pending = @('policy', $p.PolicyId)
                $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicy' `
                    @((Get-WireArgument $format 'policy' $p @($ruleIds)), $false)
                [void]$policyIds.Add((Get-CleanId $result $p.PolicyId))
                Send-Log $Log 'import' 'info' "[NCM] created policy `"$($p.PolicyName)`" with $($ruleIds.Count) rules"
            }
            $pending = @('report', '')
            $reportId = Get-CleanId (Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyReport' `
                @((Get-WireArgument $format 'report' $Report @($policyIds)), $false)) ''
            $pending = $null
            if (-not $reportId) { throw '[NCM] No Data Returned from AddPolicyReport - no report id' }
            Write-ToolLog import info "AddPolicyReport returned report id $reportId"
            return Test-NcmImport $Conn $reportId $Report $Log
        } catch {
            # Every failure is logged and rolled back the same way, then rethrown
            # for Import-NcmReports to record.
            $text = $_.Exception.Message
            Write-ToolLog import error "import of `"$($Report.Name)`" failed: $text"
            if ($pending -and (Get-HttpStatus $text) -eq 0 -and -not $_.Exception.Data['Verification']) {
                if ($pending[0] -eq 'report') {
                    Send-Log $Log 'import' 'warn' ("[NCM] warning: the outcome of the failed AddPolicyReport is unknown (no HTTP " +
                        "status); if the server created the report anyway, look for `"$($Report.Name)`" and remove it")
                } else { Write-UnknownOutcome $Log $pending[0] $pending[1] $preexisting }
            }
            if ($Rollback) {
                Send-Log $Log 'import' 'info' '[NCM] import failed part way through; removing what it created'
                Undo-NcmImport $Conn @($allRuleIds) @($policyIds) $reportId $Log $preexisting
            } else {
                Send-Log $Log 'import' 'warn' ("[NCM] import failed part way through; $($allRuleIds.Count) rule(s) and " +
                    "$($policyIds.Count) policy/policies were left on the server (-NoRollback)")
            }
            throw
        }
    }
    $script:NcmImportRoutes[$Report.Name] = 'API, one nested AddPolicyReport (console-format XML)'
    Send-Log $Log 'import' 'warn' '[NCM] no per-item wire format accepted; trying one nested console-format AddPolicyReport'
    $reportId = ''
    try {
        $reportId = Get-CleanId (Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyReport' `
            @((ConvertTo-ConsoleReportXml $Report), $true)) ''
        if (-not $reportId) {
            # The collision check ran before the import, so a report with this name
            # now can only be the one this call created without returning its id.
            $found = @(Invoke-SwisQuery $Conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = $Report.Name })
            if ($found.Count -gt 0) {
                $reportId = [string](Get-RowValue $found[0] 'PolicyReportID')
                Send-Log $Log 'import' 'warn' "[NCM] nested AddPolicyReport returned no id, but a report named `"$($Report.Name)`" now exists ($reportId); verifying it"
            } else {
                [void]$rejections.Add('console-format XML: no report id returned and no report was created')
            }
        }
    } catch {
        if (-not (Test-WireRejection $_.Exception.Message)) {
            Write-ToolLog import error 'nested AddPolicyReport failed with an error that is not a documented wire-format rejection; stopping this report'
            if ((Get-HttpStatus $_.Exception.Message) -eq 0) {
                Send-Log $Log 'import' 'warn' ("[NCM] warning: the outcome of the failed AddPolicyReport is unknown (no HTTP " +
                    "status); if the server created the report anyway, look for `"$($Report.Name)`" and remove it")
            }
            throw
        }
        [void]$rejections.Add('console-format XML: ' + @($_.Exception.Message -split "`n")[-1])
    }
    if ($reportId) {
        Write-ToolLog import info "nested AddPolicyReport created report $reportId"
        try {
            return Test-NcmImport $Conn $reportId $Report $Log
        } catch {
            $failure = $_.Exception
            Write-ToolLog import error "nested import of `"$($Report.Name)`" failed verification: $($failure.Message)"
            if ($Rollback) { Undo-NcmNestedImport $Conn $reportId $preexisting $Log }
            else {
                Send-Log $Log 'import' 'warn' "[NCM] report $reportId was left on the server (-NoRollback); delete it before importing the console file, or the names collide"
            }
            if (-not $failure.Data['Verification']) { throw }
            [void]$rejections.Add('console-format XML: accepted, but ' + ($failure.Message -replace '^\[NCM\] ', ''))
        }
    }
    Write-ToolLog import error ("no wire format accepted for `"$($Report.Name)`": " + ($rejections -join '; ') +
        '; console-importable files will be written')
    $err = New-Object System.Exception ('[NCM] this server accepted none of the wire formats: ' +
        ($rejections -join '; ') + '. Console-importable files will be written instead - ' +
        'import them under Compliance -> Manage Policy Reports -> Import.')
    $err.Data['WireFailure'] = $true
    throw $err
}

function Import-NcmReports($Conn, $Reports, [scriptblock]$Log, [bool]$Rollback = $true) {
    # Import several reports in turn, stopping at the first failure. Returns
    # Imported (Report/ReportId/Rules per verified import), Failure (the
    # exception that stopped the run, or $null) and Remaining (reports not
    # imported, the failed one first). Reports imported before a failure stay
    # on the server and are still the caller's to cache or disable.
    $imported = New-Object System.Collections.ArrayList
    $all = @($Reports)
    for ($i = 0; $i -lt $all.Count; $i++) {
        $r = $all[$i]
        $n = 0; foreach ($p in $r.AssignedPolicies) { $n += @($p.AssignedPolicyRules).Count }
        Send-Log $Log 'import' 'info' "[NCM] importing `"$($r.Name)`" - $n rules"
        try {
            $res = Import-NcmReport $Conn $r $Log $Rollback
        } catch {
            Write-ToolLog import error ("stopping at `"$($r.Name)`": $($imported.Count) of $($all.Count) " +
                "report(s) imported, $($all.Count - $i) not imported ($($_.Exception.Message))")
            return @{ Imported = @($imported); Failure = $_.Exception; Remaining = @($all[$i..($all.Count - 1)]) }
        }
        Add-ToolLogStat 'Imported'
        [void]$imported.Add(@{ Report = $r; ReportId = $res.ReportId; Rules = $res.Rules })
        Send-Log $Log 'import' 'info' "[NCM] imported: `"$($r.Name)`" ($($res.ReportId)) - $($res.Rules) rules"
    }
    return @{ Imported = @($imported); Failure = $null; Remaining = @() }
}

function Complete-NcmImport($Conn, $ReportIds, [bool]$Disabled, [bool]$SkipCache, [scriptblock]$Log) {
    # Disable or start caching the reports a run imported. Returns $true when
    # the requested end state was confirmed (or nothing was asked of the server).
    # StartCaching and UpdateReportStatus need WebUploader, one step above the
    # import itself, so a refusal is logged with that role and the run carries on
    # (the caller still writes the console files that are due); $false is returned.
    $ids = @(@($ReportIds) | Where-Object { $_ })
    if ($ids.Count -eq 0) { return $true }
    if ($Disabled) {
        # ReportStatus travels in the payload, but UpdateReportStatus is the verb
        # that owns the field, so say it explicitly and read it back.
        try { [void](Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'UpdateReportStatus' @('Disabled', $ids)) }
        catch {
            Send-Log $Log 'verify' 'error' ("[NCM] warning: UpdateReportStatus('Disabled') failed - $($_.Exception.Message). It needs " +
                'the WebUploader NCM role (an Orion administrator when compliance is restricted to administrators). The ' +
                'reports may still be Enabled, and the nightly policy cache job would then evaluate them; disable them in the console.')
            return $false
        }
        $stored = @(Invoke-SwisQuery $Conn 'SELECT Name, ReportStatus FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids' @{ ids = $ids })
        if ($stored.Count -eq 0) {
            Send-Log $Log 'verify' 'warn' '[NCM] warning: No Data Returned reading ReportStatus back after UpdateReportStatus; confirm the reports are disabled in the console'
            return $false
        }
        $stillOn = @($stored | Where-Object { Get-RowValue $_ 'ReportStatus' } | ForEach-Object { Get-RowValue $_ 'Name' })
        if ($stillOn.Count -gt 0) {
            Send-Log $Log 'verify' 'warn' ('[NCM] warning: still enabled after UpdateReportStatus: ' + ($stillOn -join ', '))
            return $false
        }
        Send-Log $Log 'import' 'info' ("[NCM] $($ids.Count) report(s) imported Disabled and not cached. Enable them in the " +
            "console, or with UpdateReportStatus('Enabled', [ids]), once the rules have been reviewed.")
        return $true
    }
    if ($SkipCache) {
        Send-Log $Log 'import' 'info' ('[NCM] compliance caching not started (-NoCache); the reports show no data until ' +
            'you run Update Violations in the console or invoke StartCaching.')
        return $true
    }
    # Always pass the specific GUIDs: an empty array would re-cache every report.
    try { $started = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'StartCaching' @(, $ids) }
    catch {
        Send-Log $Log 'import' 'error' ("[NCM] warning: StartCaching failed - $($_.Exception.Message). It needs the WebUploader " +
            'NCM role (an Orion administrator when compliance is restricted to administrators). The reports are imported ' +
            'and verified but show no data until they are cached: run Update Violations in the console, or wait for the ' +
            'nightly policy cache job if it is enabled.')
        return $false
    }
    # The contract declares a boolean result; what false means is not documented.
    Write-ToolLog import info "StartCaching returned $(Format-LogValue $started)"
    if ($started -is [bool] -and -not $started) {
        Send-Log $Log 'import' 'warn' ('[NCM] warning: StartCaching returned false. Unverified: SolarWinds does not document ' +
            'what false means; watch CacheStatus on Cirrus.PolicyReports for these reports.')
        return $false
    }
    Send-Log $Log 'import' 'info' "[NCM] compliance caching started for $($ids.Count) report(s)"
    return $true
}

# =========================================================================
# Removing an imported report: report, then unshared policies, then rules
# =========================================================================
# DeletePolicyReports(ids, deleteChildren=false) on its own leaves the report's
# policies and rules behind with nothing pointing at them; deleteChildren=true
# also reaches children other reports share. The clean path reads the tree,
# deletes the report row, then DeletePolicies(ids, false), then
# DeletePolicyRules, skipping anything another report or policy still uses
# (Cirrus.PolicyAssignment / Cirrus.PolicyRuleAssignment). Same as Python.
function Get-NcmRemovalPlan($Conn, $ReportIds, [scriptblock]$Log) {
    # Every membership and sharing lookup below is an IN @ids query over GUIDs,
    # so the sanity probe runs first on the first report, which is known to
    # exist; when it fails, nothing is planned and nothing is deleted.
    if (@($ReportIds).Count -gt 0) { Confirm-InIds $Conn 'report' ([string]@($ReportIds)[0]) 'planning the removal' 'remove' }
    $reportKeys = @{}
    foreach ($r in @($ReportIds)) { $reportKeys[(Get-NormId $r)] = $true }
    $policies = [ordered]@{}; $rules = [ordered]@{}; $names = @{}
    $add = {
        param($Store, $Value, $Label)
        $key = Get-NormId $Value
        if (-not $key) { return }
        if (-not $Store.Contains($key)) { $Store[$key] = ([string]$Value).Trim().Trim('{', '}') }
        if ($Label -and -not $names.ContainsKey($Store[$key])) { $names[$Store[$key]] = $Label }
    }
    foreach ($rid in @($ReportIds)) {
        $tree = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'GetPolicyReport' @($rid, $true)
        if (-not (Test-ToolObject $tree)) {
            $what = 'No Data Returned'
            if ($null -ne $tree -and -not ($tree -is [string] -and -not $tree)) { $what = "a result that is not a report object ($(Format-LogValue $tree)) came back" }
            Send-Log $Log 'remove' 'warn' "[NCM] note: $what from GetPolicyReport for $rid; its policies and rules are taken from Cirrus.PolicyAssignment alone"
            continue
        }
        foreach ($polId in @(Get-RowValue $tree 'AssignedPoliciesList')) { & $add $policies $polId $null }
        foreach ($pol in @(Get-RowValue $tree 'AssignedPolicies')) {
            if (-not (Test-ToolObject $pol)) { continue }
            & $add $policies (Get-RowValue $pol 'PolicyId') (Get-RowValue $pol 'PolicyName')
            foreach ($x in @(Get-RowValue $pol 'AssignedRulesList')) { & $add $rules $x $null }
            foreach ($rule in @(Get-RowValue $pol 'AssignedPolicyRules')) {
                if (-not (Test-ToolObject $rule)) { continue }
                & $add $rules (Get-RowValue $rule 'RuleId') (Get-RowValue $rule 'RuleName')
            }
        }
    }
    # The export tree is not documented to carry PolicyId, so the SWQL link
    # tables are read as well.
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyReportID IN @ids' @($ReportIds))) {
        & $add $policies (Get-RowValue $row 'PolicyID') $null
    }
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyID IN @ids' @($policies.Values))) {
        & $add $rules (Get-RowValue $row 'PolicyRuleID') $null
    }
    $keepPolicies = [ordered]@{}
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyReportID, PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyID IN @ids' @($policies.Values))) {
        $other = Get-NormId (Get-RowValue $row 'PolicyReportID')
        $key = Get-NormId (Get-RowValue $row 'PolicyID')
        if ($policies.Contains($key) -and $other -and -not $reportKeys.ContainsKey($other)) {
            if (-not $keepPolicies.Contains($key)) { $keepPolicies[$key] = New-Object System.Collections.ArrayList }
            [void]$keepPolicies[$key].Add([string](Get-RowValue $row 'PolicyReportID'))
        }
    }
    $deletePolicyKeys = @{}
    foreach ($k in $policies.Keys) { if (-not $keepPolicies.Contains($k)) { $deletePolicyKeys[$k] = $true } }
    $keepRules = [ordered]@{}
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids' @($rules.Values))) {
        $other = Get-NormId (Get-RowValue $row 'PolicyID')
        $key = Get-NormId (Get-RowValue $row 'PolicyRuleID')
        if ($rules.Contains($key) -and $other -and -not $deletePolicyKeys.ContainsKey($other)) {
            if (-not $keepRules.Contains($key)) { $keepRules[$key] = New-Object System.Collections.ArrayList }
            [void]$keepRules[$key].Add([string](Get-RowValue $row 'PolicyID'))
        }
    }
    $deleteRuleCount = @($rules.Keys | Where-Object { -not $keepRules.Contains($_) }).Count
    Write-ToolLog remove info ("removal plan for $(@($ReportIds).Count) report(s): $($policies.Count) " +
        "policy/policies and $($rules.Count) rule(s) found; $($deletePolicyKeys.Count) policy/policies and " +
        "$deleteRuleCount rule(s) to delete, $($keepPolicies.Count) policy/policies and $($keepRules.Count) " +
        'rule(s) kept because something else still uses them')
    $keepP = [ordered]@{}; foreach ($k in $keepPolicies.Keys) { $keepP[$policies[$k]] = @($keepPolicies[$k]) }
    $keepR = [ordered]@{}; foreach ($k in $keepRules.Keys) { $keepR[$rules[$k]] = @($keepRules[$k]) }
    return @{
        Reports        = @($ReportIds)
        DeletePolicies = @($policies.Keys | Where-Object { $deletePolicyKeys.ContainsKey($_) } | ForEach-Object { $policies[$_] })
        KeepPolicies   = $keepP
        DeleteRules    = @($rules.Keys | Where-Object { -not $keepRules.Contains($_) } | ForEach-Object { $rules[$_] })
        KeepRules      = $keepR
        Names          = $names
    }
}

function Write-NcmRemovalPlan($Plan, [scriptblock]$Log) {
    $label = { param($i) if ($Plan.Names.ContainsKey($i)) { "$i `"$($Plan.Names[$i])`"" } else { $i } }
    Send-Log $Log 'remove' 'info' ("  report(s): $($Plan.Reports.Count)  " + ($Plan.Reports -join ', '))
    Send-Log $Log 'remove' 'info' "  policies to delete: $($Plan.DeletePolicies.Count)"
    foreach ($i in $Plan.DeletePolicies) { Send-Log $Log 'remove' 'info' ('    - ' + (& $label $i)) }
    Send-Log $Log 'remove' 'info' "  rules to delete: $($Plan.DeleteRules.Count)"
    foreach ($k in $Plan.KeepPolicies.Keys) {
        Send-Log $Log 'remove' 'info' ("  kept policy $(& $label $k): still assigned to another report (" + ($Plan.KeepPolicies[$k] -join ', ') + ')')
    }
    foreach ($k in $Plan.KeepRules.Keys) {
        Send-Log $Log 'remove' 'info' ("  kept rule $(& $label $k): still assigned to a policy that is not being deleted (" + ($Plan.KeepRules[$k] -join ', ') + ')')
    }
}

function Remove-NcmReports($Conn, $Plan, [scriptblock]$Log) {
    # deleteChildren is false on both delete verbs that take it: the children
    # that may go are named explicitly instead. Returns what is still present.
    [void](Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'DeletePolicyReports' @(@($Plan.Reports), $false))
    Send-Log $Log 'remove' 'info' "[NCM] deleted $($Plan.Reports.Count) report(s)"
    if ($Plan.DeletePolicies.Count -gt 0) {
        [void](Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'DeletePolicies' @(@($Plan.DeletePolicies), $false))
        Send-Log $Log 'remove' 'info' "[NCM] deleted $($Plan.DeletePolicies.Count) policy/policies"
    }
    if ($Plan.DeleteRules.Count -gt 0) {
        [void](Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'DeletePolicyRules' @(, @($Plan.DeleteRules)))
        Send-Log $Log 'remove' 'info' "[NCM] deleted $($Plan.DeleteRules.Count) rule(s)"
    }
    $left = @{
        reports  = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE PolicyReportID IN @ids' $Plan.Reports)
        policies = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID FROM Cirrus.Policies WHERE PolicyID IN @ids' $Plan.DeletePolicies)
        rules    = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyRuleID FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids' $Plan.DeleteRules)
    }
    foreach ($k in @('reports', 'policies', 'rules')) {
        if ($left[$k].Count -gt 0) { Send-Log $Log 'remove' 'warn' "[NCM] warning: $($left[$k].Count) $k still present after the delete call" }
    }
    return $left
}

function Get-ScmPolicyCollision($Conn, $Info) {
    # Python scm_policy_collision: the refusal message when a policy with $Info's
    # name OR uniqueId already exists, else $null. SolarWinds rejects both
    # collisions server side; this tool never overwrites or duplicates, and its own
    # message is the legible one. The uniqueId matters because converted STIGs derive
    # it deterministically, so a re-import under a new name still collides.
    $name = $Info.Name
    $uniqueId = $Info.UniqueId
    $clauses = New-Object System.Collections.ArrayList
    $swqlParams = @{}
    if ($name) { [void]$clauses.Add('Name = @n'); $swqlParams['n'] = $name }
    if ($uniqueId) { [void]$clauses.Add('UniqueId = @u'); $swqlParams['u'] = $uniqueId }
    if ($clauses.Count -eq 0) { return $null }
    $existing = @(Invoke-SwisQuery $Conn ('SELECT PolicyID, Name, UniqueId, BuiltIn ' +
        'FROM Orion.PolicyEngine.Policy WHERE ' + ($clauses -join ' OR ')) $swqlParams)
    if ($existing.Count -eq 0) { return $null }
    $why = if ($existing[0].Name -eq $name) { 'the same name' } else { 'the same uniqueId' }
    $builtIn = ''; if ($existing[0].BuiltIn) { $builtIn = ', built in' }
    $msg = ("[SCM] a policy with $why already exists: ""$($existing[0].Name)"" " +
        "(PolicyID $($existing[0].PolicyID), UniqueId $($existing[0].UniqueId)$builtIn); " +
        'refusing to duplicate. SolarWinds rejects an import that matches either field.')
    $parts = Split-NameSuffix $name
    if ($null -ne $parts.N) {
        $msg += ' ' + (Get-SuffixAdvice $Conn @(, @('Orion.PolicyEngine.Policy', $parts.Base)) "_v$($parts.N)")
    }
    return $msg
}

function Import-ScmPolicyItems($Conn, $Items, [scriptblock]$Log, [scriptblock]$OnSuccess) {
    # Python import_scm_policy_items: import ready-made SCM policies (Get-ScmInputs)
    # one by one. Every member's name and uniqueId are checked before the first
    # ImportPolicy call, so a policy pack that collides with the server is refused
    # whole. ImportPolicy has no transaction and this tool does not delete SCM
    # policies, so a later failure stops the run and names what was created;
    # $OnSuccess receives each verified import's result. Returns the results.
    $items = @($Items)
    if ($items.Count -gt 1) {
        Write-ToolLog scm info "collision check for $($items.Count) policies before the first import"
        foreach ($it in $items) {
            $msg = Get-ScmPolicyCollision $Conn (Get-ScmPolicyInfo $it.Text)
            if ($msg) {
                $msg = "[SCM] $($it.Label): $($msg -replace '^\[SCM\] ', '') Nothing was imported."
                Write-ToolLog scm error $msg
                throw $msg
            }
        }
        Send-Log $Log 'scm' 'info' "[SCM] collision check: none of the $($items.Count) policies exists yet"
    }
    $imported = New-Object System.Collections.ArrayList
    $entries = New-Object System.Collections.ArrayList
    foreach ($it in $items) {
        try { $r = Import-ScmPolicyYaml $Conn $it.Text $Log }
        catch {
            if ($imported.Count -gt 0) {
                $names = @($imported | ForEach-Object { """$($_.Name)"" (PolicyID $($_.PolicyId))" }) -join '; '
                $msg = ("[SCM] stopping at $($it.Label): $($_.Exception.Message) $($imported.Count) of $($items.Count) " +
                    "policies were imported before it and stay on the server: $names. Fix the cause and import " +
                    'the remaining files one at a time.')
                Write-ToolLog scm error $msg
                throw $msg
            }
            throw
        }
        [void]$imported.Add($r)
        $from = ''; if ($it.Member) { $from = " from $($it.Member)" }
        $n = Get-ScmRuleCount $it.Text
        [void]$entries.Add(@{ Name = $r.Name; PolicyId = $r.PolicyId; Rules = $n })
        Send-Log $Log 'scm' 'info' "[SCM] imported SCM policy `"$($r.Name)`" (PolicyID $($r.PolicyId)) - $n rules defined$from"
        if ($OnSuccess) { & $OnSuccess $r $it }
    }
    foreach ($line in (Get-ScmImportSummary @($entries))) { Send-Log $Log 'scm' 'info' "[SCM] $line" }
    return , @($imported)
}

function Import-ScmPolicyYaml($Conn, [string]$Yaml, [scriptblock]$Log) {
    # Refuses a name OR uniqueId collision (Get-ScmPolicyCollision) before the
    # ImportPolicy call, then reads the rules back to verify the import.
    $info = Get-ScmPolicyInfo $Yaml
    if (-not $info.IsPolicy) {
        throw ('[SCM] not an SCM compliance policy (expected a YAML document tagged !policy ' +
            'with pluginName: SCM); nothing was sent to ImportPolicy')
    }
    $name = $info.Name
    $shownUid = $info.UniqueId; if (-not $shownUid) { $shownUid = '(none)' }
    Write-ToolLog scm info "SCM policy `"$name`" uniqueId $shownUid; checking for a name/uniqueId collision"
    $msg = Get-ScmPolicyCollision $Conn $info
    if ($msg) {
        Write-ToolLog scm error $msg
        throw $msg
    }
    $policyId = Invoke-SwisVerbCall $Conn 'Orion.PolicyEngine.Policy' 'ImportPolicy' @($Yaml)
    if ($null -eq $policyId) {
        Write-ToolLog scm error 'ImportPolicy returned no PolicyID; the policy was not created'
        throw '[SCM] No Data Returned from Orion.PolicyEngine.Policy.ImportPolicy - the policy was not created'
    }
    Write-ToolLog scm info "ImportPolicy returned PolicyID $policyId; reading the rules back"
    $stored = Invoke-SwisQuery $Conn `
        'SELECT COUNT(RuleID) AS N FROM Orion.PolicyEngine.Rule WHERE PolicyID = @p' @{ p = $policyId }
    $storedRules = 0
    if ($stored.Count -gt 0 -and $stored[0].N) { $storedRules = [int]$stored[0].N }
    if ($storedRules -eq 0) {
        $msg = ("[SCM] No Data Returned reading rules back for PolicyID $policyId - the policy " +
            'row exists but holds no rules, so the import cannot be confirmed.')
        Write-ToolLog verify error $msg
        throw $msg
    }
    Add-ToolLogStat 'Imported'
    Send-Log $Log 'verify' 'info' "[SCM] verified: PolicyID $policyId holds $storedRules rule(s)"
    return @{ PolicyId = $policyId; Name = $name; Rules = $storedRules }
}

function Import-ScmBenchmark($Conn, $Benchmark, [scriptblock]$Log, [string]$Suffix = '_v1',
                             [string]$OsFamily = 'windows', $ProbeTemplate = $null) {
    # Callers run Test-ScmCollision for the whole batch first, so a collision refuses
    # before any policy is created; Import-ScmPolicyYaml still checks name/uniqueId.
    $yaml = ConvertTo-ScmPolicyYaml $Benchmark $Suffix $OsFamily $ProbeTemplate
    $result = Import-ScmPolicyYaml $Conn $yaml $Log
    Send-Log $Log 'scm' 'info' "[SCM] imported policy ""$($result.Name)"" (PolicyID $($result.PolicyId)) - $($Benchmark.Rules.Count) manual-review rules"
    return $result
}

# =========================================================================
# Connection test: green / yellow / red semantics
# =========================================================================
function Test-SwisConnection($Conn) {
    # Returns @{ Status = 'green'|'yellow'|'red'; Detail = ... }
    try {
        $rows = Invoke-SwisQuery $Conn 'SELECT TOP 1 EngineVersion FROM Orion.Engines' $null
    } catch {
        return @{ Status = 'red'; Detail = ('connection failed: ' + $_.Exception.Message) }
    }
    if ($rows.Count -eq 0) {
        return @{ Status = 'yellow'
                  Detail = 'No Data Returned from the Orion.Engines query - connected, but the account may lack read access' }
    }
    $version = $rows[0].EngineVersion
    $ncm = (Invoke-SwisQuery $Conn "SELECT COUNT(FullName) AS C FROM Metadata.Entity WHERE FullName LIKE 'Cirrus.%'" $null)[0].C
    $scm = (Invoke-SwisQuery $Conn "SELECT COUNT(FullName) AS C FROM Metadata.Entity WHERE FullName LIKE 'Orion.PolicyEngine.%'" $null)[0].C
    $problems = New-Object System.Collections.ArrayList
    $major = 0
    if ($version -match '^(\d+)') { $major = [int]$Matches[1] }
    if ($major -gt 0 -and $major -lt 2023) {
        [void]$problems.Add("SWIS version mismatch: platform $version predates 2023.1 - the REST port is 17778 there, not 17774")
    }
    if ($ncm -eq 0) { [void]$problems.Add('[NCM] Cirrus entities not present - NCM is not installed or not readable by this account') }
    if ($scm -eq 0) { [void]$problems.Add('[SCM] Orion.PolicyEngine entities not present - SCM is not installed or not readable by this account') }
    foreach ($problem in $problems) { Write-ToolLog swis warn $problem }
    if ($problems.Count -gt 0) {
        return @{ Status = 'yellow'; Version = $version
                  Detail = ("connected - platform $version; " + ($problems -join '; ')) }
    }
    return @{ Status = 'green'; Version = $version
              Detail = "connected - platform $version; NCM present, SCM policy engine present" }
}

# =========================================================================
# Module lock: a batch is NCM or SCM, never both
# =========================================================================
function Get-FileModule([string]$FilePath, [string]$TargetChoice = 'auto') {
    # SCM policy files are always SCM (and a JSON collection profile is refused
    # here, before anything runs). XCCDF sources follow -Target like Python's
    # --target: network forces NCM, server forces SCM, auto detects.
    if ($null -ne (Get-ScmInputs $FilePath $null)) { return 'SCM' }
    $benchmarks = Get-StigBenchmarks $FilePath
    $leaf = Split-Path -Leaf $FilePath
    if ($TargetChoice -eq 'network') {
        Write-ToolLog route info "decision: NCM for $leaf (forced by -Target network)"
        return 'NCM'
    }
    if ($TargetChoice -eq 'server') {
        Write-ToolLog route info "decision: SCM for $leaf (forced by -Target server)"
        return 'SCM'
    }
    $t = Resolve-StigTarget $benchmarks $leaf
    if ($t[0] -eq 'server') {
        Write-ToolLog route info "decision: SCM for $leaf (-Target auto, detected server: $($t[1][0]))"
        return 'SCM'
    }
    if ($t[0] -eq 'network') {
        Write-ToolLog route info "decision: NCM for $leaf (-Target auto, detected network)"
    } else {
        Write-ToolLog route warn "decision: NCM for $leaf by default (-Target auto, nothing recognized in the name; use -Target server if this is a server STIG)"
    }
    return 'NCM'
}

# =========================================================================
# NCM node scope: Vendor, and for Cisco the platform by MachineType
# =========================================================================
# Tentative: MachineType values to be verified against a live server. The
# patterns are what Cisco nodes are expected to report in Orion.Nodes.MachineType;
# no export or schema in this repository records the actual strings. The platform
# is read from the package file name plus each benchmark's title and source member
# name, with -, _ and white space treated alike ("IOS-XE", "IOS_XE", "IOS XE" and
# "IOSXE" all match), and the specific platforms are tried before classic IOS.
# '%IOS%' also matches a MachineType containing IOS-XE or IOS-XR; that overlap is
# part of what the live check has to settle. Same table as Python CISCO_PLATFORMS.
$script:CiscoPlatforms = @(
    @('IOS-XE', '\bios ?xe\b', '%IOS-XE%'),
    @('IOS-XR', '\bios ?xr\b', '%IOS-XR%'),
    @('NX-OS', '\bnx ?os\b', '%NX-OS%'),
    @('ASA', '\basa\b', '%ASA%'),
    @('IOS', '\bios\b', '%IOS%'))
$script:TentativeNote = 'Tentative: MachineType values to be verified against a live server'
$script:ScopeValueMax = 200
$script:ScopeSampleSwql = ('SELECT TOP 25 Vendor, MachineType, COUNT(NodeID) AS N FROM Orion.Nodes ' +
    'WHERE Vendor = @vendor GROUP BY Vendor, MachineType ORDER BY MachineType')

function New-ScopeError([string]$Message) {
    $e = New-Object System.Exception $Message
    $e.Data['ScopeError'] = $true
    return $e
}

function ConvertTo-SqlLiteral([string]$Value) {
    # A single-quoted SQL/SWQL string literal (a ' inside is doubled).
    return "'" + ([string]$Value).Replace("'", "''") + "'"
}

function Test-ScopeValue([string]$Value, [string]$Option) {
    # -Vendor / -MachineType: one line of printable text, at most 200 characters.
    $v = ([string]$Value).Trim()
    if (-not $v -or $v.Length -gt $script:ScopeValueMax -or $v -match '[\x00-\x1f\x7f]') {
        throw (New-ScopeError "$Option must be 1 to $($script:ScopeValueMax) printable characters")
    }
    return $v
}

function Get-PlatformText([string]$Text) {
    # Lower case, with every run of '-', '_' and white space made one space.
    return (([string]$Text).ToLowerInvariant() -replace '[\s_\-]+', ' ')
}

function Get-CiscoPlatform([string]$Text) {
    # @(platform, MachineType pattern) for the first table entry that matches.
    $norm = Get-PlatformText $Text
    foreach ($p in $script:CiscoPlatforms) {
        if ($norm -cmatch $p[1]) { return @($p[0], $p[2]) }
    }
    return @($null, $null)
}

function Get-NodeWhere([string]$VendorName, [string]$Pattern) {
    # The NCM SQL fragment (bare column names, as real console exports carry it).
    if ($Pattern) { return "(Vendor = $(ConvertTo-SqlLiteral $VendorName) AND MachineType LIKE $(ConvertTo-SqlLiteral $Pattern))" }
    return "(Vendor = $(ConvertTo-SqlLiteral $VendorName))"
}

function Resolve-NcmScope($Benchmarks, [string]$SourcePath, [string]$Where, [string]$VendorOverride,
                          [string]$MachineTypeOverride) {
    # Python resolve_ncm_scope. An explicit -NodeWhere is used as written; otherwise
    # the vendor is -Vendor, else the detected one, and with no vendor the STIG is
    # refused (an SRG, ESXi or unrecognized network STIG no longer defaults to Cisco).
    # For Cisco the platform's MachineType pattern is added (-MachineType overrides
    # it, and applies to any vendor when given); an unrecognized Cisco platform, or
    # a package naming different platforms, is refused. Throws an exception with
    # Data['ScopeError'] set; returns @{ Where; Vendor; MachineType; Platform; Explicit; How }.
    $leaf = Split-Path -Leaf $SourcePath
    $explicit = $Where -and -not $Where.ToLower().StartsWith('auto') -and -not $Where.StartsWith('(auto')
    if ($explicit) {
        if ($VendorOverride -or $MachineTypeOverride) { throw (New-ScopeError 'give either -NodeWhere or -Vendor/-MachineType, not both') }
        Write-ToolLog scope info "NCM node scope $Where (explicit -NodeWhere)"
        return @{ Where = $Where; Vendor = (Get-PickerVendor $Where); MachineType = $null; Platform = $null
                  Explicit = $true; How = 'explicit -NodeWhere' }
    }
    $how = New-Object System.Collections.ArrayList
    $vendorName = $null
    if ($VendorOverride) {
        $vendorName = Test-ScopeValue $VendorOverride '-Vendor'
        [void]$how.Add('-Vendor')
    } else {
        $t = Resolve-StigTarget $Benchmarks $leaf
        if ($t[0] -eq 'network' -and $t[1]) { $vendorName = $t[1]; [void]$how.Add('vendor detected from the names') }
    }
    if (-not $vendorName) {
        $msg = ("[NCM] ${leaf}: no network vendor was recognized in the file or benchmark names (an SRG such as " +
            'the Router or NDM SRG, ESXi, or an unlisted product), so there is no safe node scope; the tool no ' +
            'longer assumes Cisco. Pass -Vendor NAME (the Vendor value your nodes report, with -MachineType ' +
            'PATTERN for Cisco) or -NodeWhere "(...)".')
        Write-ToolLog scope error $msg
        throw (New-ScopeError $msg)
    }
    $platform = $null
    $pattern = $null
    if ($MachineTypeOverride) {
        $pattern = Test-ScopeValue $MachineTypeOverride '-MachineType'
        [void]$how.Add('-MachineType')
    } elseif ($vendorName.ToLower() -eq 'cisco') {
        $found = New-Object System.Collections.ArrayList
        foreach ($b in $Benchmarks) {
            $bid = $b.BenchmarkId; if (-not $bid) { $bid = $b.Title }
            $hit = Get-CiscoPlatform ($leaf + ' ' + $b.Title + ' ' + $b.Source)
            [void]$found.Add(@{ Id = $bid; Platform = $hit[0]; Pattern = $hit[1] })
            if ($hit[0]) { Write-ToolLog scope info "Cisco platform for ${bid}: $($hit[0]) -> MachineType LIKE '$($hit[1])' ($($script:TentativeNote))" }
            else { Write-ToolLog scope info "Cisco platform for ${bid}: not recognized" }
        }
        $names = @($found | ForEach-Object { if ($_.Platform) { $_.Platform } else { 'not recognized' } } | Sort-Object -Unique)
        if ($names.Count -gt 1) {
            $listed = (@($found | ForEach-Object { $n = $_.Platform; if (-not $n) { $n = 'not recognized' }; "$($_.Id): $n" }) -join ', ')
            $msg = ("[NCM] ${leaf}: the benchmarks name different Cisco platforms ($listed); one run uses one node " +
                'scope, so convert or import them separately, or pass -MachineType PATTERN or -NodeWhere "(...)".')
            Write-ToolLog scope error $msg
            throw (New-ScopeError $msg)
        }
        if ($found.Count -gt 0) { $platform = $found[0].Platform; $pattern = $found[0].Pattern }
        if (-not $platform) {
            $msg = ("[NCM] ${leaf}: a Cisco STIG, but no platform (IOS-XE, IOS-XR, NX-OS, ASA, IOS) was recognized " +
                'in the file or benchmark names, so the node scope would be every Cisco node. Pass -MachineType ' +
                "PATTERN (for example '%IOS-XE%', or '%' for every Cisco node that reports a MachineType) or " +
                '-NodeWhere "(...)".')
            Write-ToolLog scope error $msg
            throw (New-ScopeError $msg)
        }
        [void]$how.Add("platform $platform detected ($($script:TentativeNote))")
    }
    $w = Get-NodeWhere $vendorName $pattern
    Write-ToolLog scope info ("NCM node scope $w (" + ($how -join ', ') + '); the console node picker shows ' +
        'Vendor only, the MachineType condition is in the SQL part')
    return @{ Where = $w; Vendor = $vendorName; MachineType = $pattern; Platform = $platform
              Explicit = $false; How = ($how -join ', ') }
}

function Get-ScopeSwql($Scope) {
    # Python scope_swql: a generated scope is counted with bound parameters; an
    # explicit -NodeWhere (the operator's own NCM SQL) is used as written, Nodes.
    # prefix dropped, in a read-only query that can fail if it is not valid SWQL.
    if ($Scope.Vendor -and -not $Scope.Explicit) {
        if ($Scope.MachineType) {
            return @{ Swql = 'SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor AND MachineType LIKE @machineType'
                      Params = @{ vendor = $Scope.Vendor; machineType = $Scope.MachineType } }
        }
        return @{ Swql = 'SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE Vendor = @vendor'
                  Params = @{ vendor = $Scope.Vendor } }
    }
    $w = ($Scope.Where -replace '\bNodes\.', '').Trim()
    return @{ Swql = ('SELECT COUNT(NodeID) AS N FROM Orion.Nodes WHERE ' + $w); Params = $null }
}

function Invoke-ScopePreflight($Conn, $Scope, [bool]$AllowEmpty, [scriptblock]$Log) {
    # Python scope_preflight: count the nodes the scope selects before anything is
    # written, log both forms of the condition and a MachineType sample for the
    # vendor; zero nodes refuses unless -AllowEmptyScope; a count that cannot be run
    # is inconclusive and the import goes on. Returns the count, or $null.
    $q = Get-ScopeSwql $Scope
    $shownParams = ''
    if ($q.Params) { $shownParams = ' params {' + (@($q.Params.Keys | ForEach-Object { "$_='$($q.Params[$_])'" }) -join ', ') + '}' }
    Write-ToolLog scope info "scope preflight: NCM SQL Where $($Scope.Where); SWQL $($q.Swql)$shownParams"
    try {
        $rows = @(Invoke-SwisQuery $Conn $q.Swql $q.Params)
        $count = 0
        if ($rows.Count -gt 0) { $n = Get-RowValue $rows[0] 'N'; if ($n) { $count = [int]$n } }
    } catch {
        Send-Log $Log 'scope' 'warn' ("[NCM] warning: the node scope could not be counted ($($_.Exception.Message)); the " +
            'import goes on without the empty-scope check, so check the scope in the console')
        return $null
    }
    if ($Scope.Vendor) {
        try {
            $sample = @(Invoke-SwisQuery $Conn $script:ScopeSampleSwql @{ vendor = $Scope.Vendor })
            $seen = (@($sample | ForEach-Object { "$(Get-RowValue $_ 'MachineType') ($(Get-RowValue $_ 'N'))" }) -join '; ')
            if (-not $seen) { $seen = 'none' }
            $tail = ''; if ($Scope.Platform) { $tail = " - $($script:TentativeNote)" }
            Write-ToolLog scope info "MachineType values reported by Vendor '$($Scope.Vendor)' nodes (up to 25): $seen$tail"
        } catch { Write-ToolLog scope warn "could not sample MachineType values: $($_.Exception.Message)" }
    }
    if ($count -gt 0) {
        Send-Log $Log 'scope' 'info' "[NCM] node scope selects $count node(s): $($Scope.Where)"
        return $count
    }
    $msg = "the node scope $($Scope.Where) matches no node on this server"
    if ($Scope.Platform) { $msg += " ($($script:TentativeNote); the MachineType values Vendor '$($Scope.Vendor)' nodes report are in the run log)" }
    $msg += '. A report scoped to no node evaluates nothing, which reads like compliance.'
    if ($AllowEmpty) {
        Send-Log $Log 'scope' 'warn' "[NCM] warning: $msg Importing anyway (-AllowEmptyScope)."
        return 0
    }
    Write-ToolLog scope error "$msg Refused; nothing was created."
    throw (New-ScopeError ("[NCM] $msg Nothing was created. Correct -MachineType, -Vendor or -NodeWhere, or pass " +
        '-AllowEmptyScope to import it anyway.'))
}

# =========================================================================
# Collision check: refuse before anything is written, suggest the next suffix
# =========================================================================
# Every generated name ends in (and every id is seeded with) the version suffix,
# so a collision means this STIG was already imported with that suffix. The run is
# refused before the first write, naming what collided, with the next free suffix
# found by listing the names that share the base. Get-ExistingNcmIds inside
# Import-NcmReport stays as defense in depth. Same as the Python edition.
$script:NameLikeQueries = @{
    'Cirrus.PolicyReports'      = 'SELECT TOP 200 Name FROM Cirrus.PolicyReports WHERE Name LIKE @p'
    'Cirrus.Policies'           = 'SELECT TOP 200 Name FROM Cirrus.Policies WHERE Name LIKE @p'
    'Orion.PolicyEngine.Policy' = 'SELECT TOP 200 Name FROM Orion.PolicyEngine.Policy WHERE Name LIKE @p'
}
$script:InIdsProbes['scmrule'] = @('SELECT UniqueId FROM Orion.PolicyEngine.Rule WHERE UniqueId IN @ids', 'UniqueId')

function Get-LikePrefix([string]$Text) {
    # A LIKE pattern matching every name starting with $Text: cut at the first '['
    # (a character class in SQL Server LIKE; Unverified whether SWIS passes LIKE
    # through unchanged); _ and % stay wildcards, so callers filter exactly.
    $i = $Text.IndexOf('[')
    if ($i -ge 0) { $Text = $Text.Substring(0, $i) }
    return $Text + '%'
}

function Get-SuffixAdvice($Conn, $Bases, [string]$CurrentSuffix) {
    # 're-run with -Suffix _vN' text; $Bases is a list of @(entity, base name).
    $names = New-Object System.Collections.ArrayList
    foreach ($pair in @($Bases)) {
        try {
            foreach ($row in @(Invoke-SwisQuery $Conn $script:NameLikeQueries[$pair[0]] @{ p = (Get-LikePrefix $pair[1]) })) {
                [void]$names.Add(@($pair[1], [string](Get-RowValue $row 'Name')))
            }
        } catch { Write-ToolLog import warn "could not list $($pair[0]) names starting with `"$($pair[1])`": $($_.Exception.Message)" }
    }
    [long]$highest = [long]$CurrentSuffix.Substring(2) + 1
    foreach ($base in @($Bases | ForEach-Object { $_[1] } | Sort-Object -Unique)) {
        $candidate = Get-NextFreeSuffix @($names | Where-Object { $_[0] -ceq $base } | ForEach-Object { $_[1] }) $base $CurrentSuffix
        if ([long]$candidate.Substring(2) -gt $highest) { $highest = [long]$candidate.Substring(2) }
    }
    $suggestion = "_v$highest"
    $used = (@($names | ForEach-Object { $_[1] } | Sort-Object -Unique) -join ', '); if (-not $used) { $used = 'none listed' }
    Write-ToolLog import info "names already using these bases: $used; next free suffix $suggestion"
    return ("The next free suffix is ${suggestion}: re-run with -Suffix $suggestion (Python: --suffix $suggestion) " +
        'to import alongside, or remove the existing import first.')
}

function New-CollisionError([string]$Message) {
    $e = New-Object System.Exception $Message
    $e.Data['Collision'] = $true
    return $e
}

function Test-NcmCollision($Conn, $Reports, [string]$Suffix, [scriptblock]$Log) {
    # Throws (Data['Collision']) before anything is written when a report name,
    # policy name, PolicyId or RuleId the reports would create already exists.
    $Suffix = Test-Suffix $Suffix
    $hits = New-Object System.Collections.ArrayList
    foreach ($r in $Reports) {
        $found = @(Invoke-SwisQuery $Conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = $r.Name })
        if ($found.Count -gt 0) { [void]$hits.Add("report `"$($r.Name)`" ($(Get-RowValue $found[0] 'PolicyReportID'))") }
        foreach ($p in $r.AssignedPolicies) {
            $found = @(Invoke-SwisQuery $Conn 'SELECT PolicyID, Name FROM Cirrus.Policies WHERE Name = @n' @{ n = $p.PolicyName })
            if ($found.Count -gt 0) { [void]$hits.Add("policy `"$($p.PolicyName)`" ($(Get-RowValue $found[0] 'PolicyID'))") }
        }
        $existing = Get-ExistingNcmIds $Conn $r
        if ($existing.Policies.Count -gt 0) {
            [void]$hits.Add("$($existing.Policies.Count) PolicyId(s) of `"$($r.Name)`" (" + ((@($existing.Policies.Keys) | Sort-Object | Select-Object -First 3) -join ', ') + ')')
        }
        if ($existing.Rules.Count -gt 0) {
            $more = ''; if ($existing.Rules.Count -gt 3) { $more = ', ...' }
            [void]$hits.Add("$($existing.Rules.Count) RuleId(s) of `"$($r.Name)`" (" + ((@($existing.Rules.Keys) | Sort-Object | Select-Object -First 3) -join ', ') + "$more)")
        }
    }
    if ($hits.Count -eq 0) {
        Write-ToolLog import info "collision check: none of the $(@($Reports).Count) report(s), their policies or ids exist yet (suffix $Suffix)"
        return
    }
    $bases = New-Object System.Collections.ArrayList
    foreach ($r in $Reports) {
        [void]$bases.Add(@('Cirrus.PolicyReports', (Split-NameSuffix $r.Name).Base))
        foreach ($p in $r.AssignedPolicies) { [void]$bases.Add(@('Cirrus.Policies', (Split-NameSuffix $p.PolicyName).Base)) }
    }
    $msg = ("[NCM] already on the server with suffix ${Suffix}: " + ($hits -join '; ') +
        '. Nothing was imported; this tool never overwrites. ' + (Get-SuffixAdvice $Conn @($bases) $Suffix))
    Write-ToolLog import error ('collision: ' + $msg)
    throw (New-CollisionError $msg)
}

function Test-ScmCollision($Conn, $Benchmarks, [string]$Suffix, [scriptblock]$Log) {
    # Python scm_collision_check: every converted policy's name, uniqueId and rule
    # uniqueIds are checked before any of them is imported. Whether the server
    # rejects a rule uniqueId another policy uses is Unverified; it is checked so a
    # new suffix really means fresh ids, after the IN @ids sanity probe.
    $Suffix = Test-Suffix $Suffix
    $hits = New-Object System.Collections.ArrayList
    foreach ($b in $Benchmarks) {
        $found = @(Invoke-SwisQuery $Conn ('SELECT PolicyID, Name, UniqueId, BuiltIn FROM Orion.PolicyEngine.Policy ' +
            'WHERE Name = @n OR UniqueId = @u') @{ n = (Get-ScmPolicyName $b $Suffix); u = (Get-ScmPolicyUniqueId $b $Suffix) })
        foreach ($row in $found) {
            [void]$hits.Add("policy `"$(Get-RowValue $row 'Name')`" (PolicyID $(Get-RowValue $row 'PolicyID'), UniqueId $(Get-RowValue $row 'UniqueId'))")
        }
    }
    $ruleIds = @($Benchmarks | ForEach-Object { $bench = $_; @($bench.Rules) | ForEach-Object { Get-ScmRuleUniqueId $_ $Suffix } })
    if ($ruleIds.Count -gt 0) {
        $sample = @(Invoke-SwisQuery $Conn 'SELECT TOP 1 UniqueId FROM Orion.PolicyEngine.Rule' $null)
        $known = $null
        if ($sample.Count -gt 0) { $known = Get-RowValue $sample[0] 'UniqueId' }
        if ($known) {
            Confirm-InIds $Conn 'scmrule' ([string]$known) 'the SCM rule uniqueId check' 'scm'
            $rows = @(Invoke-SwisQueryIds $Conn $script:InIdsProbes['scmrule'][0] $ruleIds)
            if ($rows.Count -gt 0) {
                $ids = @($rows | ForEach-Object { Get-NormId (Get-RowValue $_ 'UniqueId') } | Sort-Object -Unique)
                $more = ''; if ($ids.Count -gt 3) { $more = ', ...' }
                [void]$hits.Add("$($ids.Count) rule uniqueId(s) (" + (($ids | Select-Object -First 3) -join ', ') + "$more)")
            }
        } else {
            Write-ToolLog scm info "the server returned no SCM rule rows, so none of the $($ruleIds.Count) rule uniqueId(s) can already exist"
        }
    }
    if ($hits.Count -eq 0) {
        Write-ToolLog scm info "collision check: none of the $(@($Benchmarks).Count) SCM policy name(s), uniqueId(s) or rule uniqueId(s) exist yet (suffix $Suffix)"
        return
    }
    $bases = @($Benchmarks | ForEach-Object { , @('Orion.PolicyEngine.Policy', (Split-NameSuffix (Get-ScmPolicyName $_ $Suffix)).Base) })
    $msg = ("[SCM] already on the server with suffix ${Suffix}: " + ($hits -join '; ') +
        '. Nothing was imported; this tool never overwrites. ' + (Get-SuffixAdvice $Conn $bases $Suffix))
    Write-ToolLog scm error ('collision: ' + $msg)
    throw (New-CollisionError $msg)
}

function Get-SimilarReportNames($Conn, [string]$ReportName) {
    # For a -Remove -Name that matched nothing: the report names starting with it
    # (typically the same name with its version suffix), as text to append.
    try {
        $rows = @(Invoke-SwisQuery $Conn 'SELECT TOP 50 PolicyReportID, Name FROM Cirrus.PolicyReports WHERE Name LIKE @p' @{ p = (Get-LikePrefix $ReportName) })
    } catch { return '' }
    $names = @($rows | ForEach-Object { [string](Get-RowValue $_ 'Name') } | Where-Object { $_.StartsWith($ReportName, [System.StringComparison]::Ordinal) } | Sort-Object -Unique)
    $shown = $names -join ', '; if (-not $shown) { $shown = 'none' }
    Write-ToolLog remove info "no report named `"$ReportName`"; names starting with it: $shown"
    if ($names.Count -eq 0) { return '' }
    return ('; reports whose names start with it (since 2.0.0 every name ends in a version suffix such as _v1): ' +
        ((@($names | Select-Object -First 10) | ForEach-Object { '"' + $_ + '"' }) -join ', '))
}

function Get-ScmOsFamily($Benchmarks, [string]$SourcePath) {
    # 'windows', 'linux' or 'unknown' (forced to SCM without a recognized OS).
    $t = Resolve-StigTarget $Benchmarks (Split-Path -Leaf $SourcePath)
    if ($t[0] -eq 'server') { return $t[1][2] }
    return 'unknown'
}

# =========================================================================
# CLI driver
# =========================================================================
function Resolve-CliAuthMode([bool]$UseApiToken, [string]$User, [bool]$UseWindowsAuth) {
    # Which credential a CLI run uses: 'token', 'basic' or 'windows'. The three are
    # mutually exclusive; the same rule is auth_mode() in the Python edition.
    $chosen = @()
    if ($UseApiToken) { $chosen += '-ApiToken' }
    if ($User) { $chosen += '-Username' }
    if ($UseWindowsAuth) { $chosen += '-WindowsAuth' }
    if ($chosen.Count -gt 1) { throw (($chosen -join ' and ') + ' are mutually exclusive; pass one of them') }
    if ($chosen.Count -eq 0) {
        throw 'pass -Username (password from SWIS_PASSWORD or a prompt), -ApiToken (token from SWIS_API_TOKEN or a prompt) or -WindowsAuth'
    }
    return @{ '-ApiToken' = 'token'; '-Username' = 'basic'; '-WindowsAuth' = 'windows' }[$chosen[0]]
}

function Read-SecretPrompt([string]$Prompt) {
    $sec = Read-Host -Prompt $Prompt -AsSecureString
    return [System.Runtime.InteropServices.Marshal]::PtrToStringUni(
        [System.Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($sec))
}

function New-CliConnection {
    # Shared by import, -Test and -Remove: password from $env:SWIS_PASSWORD (or the
    # API token from $env:SWIS_API_TOKEN) or a prompt, never a parameter; optional
    # certificate pin; connection check.
    if (-not $Server) { throw 'pass -Server (and -Username, -ApiToken or -WindowsAuth)' }
    $mode = Resolve-CliAuthMode $ApiToken.IsPresent $Username $WindowsAuth.IsPresent
    $pw = ''; $token = ''
    if ($mode -eq 'token') {
        $token = $env:SWIS_API_TOKEN
        $source = 'prompted for'; if ($token) { $source = 'from SWIS_API_TOKEN' }
        Write-ToolLog swis info "connecting to ${Server}:$Port with an API token (bearer); token $source"
        if (-not $token) { $token = Read-SecretPrompt "API token for $Server" }
        if (-not $token) { throw 'the API token is empty' }
        Register-Secret $token
    }
    elseif ($mode -eq 'basic') {
        $pw = $env:SWIS_PASSWORD
        $source = 'prompted for'; if ($pw) { $source = 'from SWIS_PASSWORD' }
        Write-ToolLog swis info "connecting to ${Server}:$Port as user '$Username' (basic auth); password $source"
        if (-not $pw) { $pw = Read-SecretPrompt "password for $Username" }
        Register-Secret $pw
    }
    $pin = $null
    if ($PinServerCert) {
        $info = Get-ServerCertThumbprint $Server $Port
        $pin = $info.Thumbprint
        $stockNote = ''
        if ($info.Stock) { $stockNote = ' (stock SolarWinds-Orion certificate)' }
        Write-ToolLog swis info "pinned the certificate ${Server}:$Port presents: SHA-256 $($info.Thumbprint)$stockNote"
        Write-Host "pinned the server certificate - SHA-256 $($info.Thumbprint)$stockNote"
    }
    $conn = New-SwisConnection $Server $Port $Username $pw $WindowsAuth.IsPresent $Insecure.IsPresent $pin $token
    $status = Test-SwisConnection $conn
    Write-Host (Hide-Secrets $status.Detail)
    if ($status.Status -eq 'red') { throw $status.Detail }
    return $conn
}

$script:RuleOwner = 'DISA STIG Conversion Tool'

function Get-NcmServerAudit($Conn, $ReportNames, $PolicyNames, $PolicyIds, $RuleIds, $RuleNames) {
    # Python ncm_server_audit: read-only, what each NCM compliance table holds for the
    # given names and ids, plus the orphan rules this tool created (by Owner) that no
    # policy references. The name lookups catch rules a server stored under its own
    # GUID, which the id-based collision check cannot see.
    $out = [ordered]@{}
    $reports = New-Object System.Collections.ArrayList
    foreach ($n in @($ReportNames)) {
        foreach ($row in @(Invoke-SwisQuery $Conn ('SELECT PolicyReportID, Name, Grouping, ReportStatus, CacheStatus, LastError ' +
                'FROM Cirrus.PolicyReports WHERE Name = @n') @{ n = $n })) { [void]$reports.Add($row) }
    }
    $out.reports = @($reports)
    $reportIds = @($out.reports | ForEach-Object { Get-RowValue $_ 'PolicyReportID' })
    $out.assignments = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyReportID, PolicyID FROM Cirrus.PolicyAssignment WHERE PolicyReportID IN @ids' $reportIds)
    $linked = @($out.assignments | ForEach-Object { Get-RowValue $_ 'PolicyID' })
    $policies = New-Object System.Collections.ArrayList
    $seen = @{}
    foreach ($n in @($PolicyNames)) {
        foreach ($row in @(Invoke-SwisQuery $Conn 'SELECT PolicyID, Name FROM Cirrus.Policies WHERE Name = @n' @{ n = $n })) {
            $seen[([string](Get-RowValue $row 'PolicyID')).ToLowerInvariant()] = $true; [void]$policies.Add($row)
        }
    }
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID, Name, Grouping, ConfigType FROM Cirrus.Policies WHERE PolicyID IN @ids' (@($PolicyIds) + $linked))) {
        $k = ([string](Get-RowValue $row 'PolicyID')).ToLowerInvariant()
        if (-not $seen.ContainsKey($k)) { $seen[$k] = $true; [void]$policies.Add($row) }
    }
    $out.policies = @($policies)
    $out.rule_assignments = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyID IN @ids' `
        @($out.policies | ForEach-Object { Get-RowValue $_ 'PolicyID' }))
    $out.rules_by_id = @(Invoke-SwisQueryIds $Conn 'SELECT PolicyRuleID, Name, Owner, Grouping FROM Cirrus.PolicyRules WHERE PolicyRuleID IN @ids' @($RuleIds))
    $byName = New-Object System.Collections.ArrayList
    foreach ($n in @($RuleNames)) {
        foreach ($row in @(Invoke-SwisQuery $Conn 'SELECT PolicyRuleID, Name, Owner FROM Cirrus.PolicyRules WHERE Name = @n' @{ n = $n })) { [void]$byName.Add($row) }
    }
    $out.rules_by_name = @($byName)
    $out.rules_by_owner = @(Invoke-SwisQuery $Conn 'SELECT PolicyRuleID, Name, Grouping FROM Cirrus.PolicyRules WHERE Owner = @o' @{ o = $script:RuleOwner })
    # A console import rewrites Owner to the importing account (seen live), so the
    # tool's grouping is the second mark of a tool-created rule; both sets are merged.
    $out.rules_by_grouping = @(Invoke-SwisQuery $Conn 'SELECT PolicyRuleID, Name, Grouping, Owner FROM Cirrus.PolicyRules WHERE Grouping LIKE @g' @{ g = 'DISA STIG%' })
    $toolMade = New-Object System.Collections.ArrayList
    $seenIds = @{}
    foreach ($row in @($out.rules_by_owner) + @($out.rules_by_grouping)) {
        $rid = ([string](Get-RowValue $row 'PolicyRuleID')).ToLowerInvariant()
        if (-not $seenIds.ContainsKey($rid)) { $seenIds[$rid] = $true; [void]$toolMade.Add($row) }
    }
    $referenced = @{}
    foreach ($row in @(Invoke-SwisQueryIds $Conn 'SELECT PolicyID, PolicyRuleID FROM Cirrus.PolicyRuleAssignment WHERE PolicyRuleID IN @ids' @($toolMade | ForEach-Object { Get-RowValue $_ 'PolicyRuleID' }))) {
        $referenced[([string](Get-RowValue $row 'PolicyRuleID')).ToLowerInvariant()] = $true
    }
    $out.orphans = @($toolMade | Where-Object { -not $referenced.ContainsKey(([string](Get-RowValue $_ 'PolicyRuleID')).ToLowerInvariant()) })
    return $out
}

function Invoke-CliAudit {
    # Python `audit`: read-only, which NCM compliance tables hold rows from a STIG
    # package (-Path) or a report (-Name), including rules failed API imports left.
    if (-not $Name -and (-not $Path -or $Path.Count -eq 0)) { throw '-Audit needs -Path <package>, -Name <exact report name>, or both' }
    $runSuffix = Test-Suffix $Suffix
    $reportNames = New-Object System.Collections.ArrayList
    if ($Name) { [void]$reportNames.Add($Name) }
    $policyNames = New-Object System.Collections.ArrayList
    $policyIds = New-Object System.Collections.ArrayList
    $ruleIds = New-Object System.Collections.ArrayList
    $ruleNames = New-Object System.Collections.ArrayList
    foreach ($p in @($Path)) {
        $benchmarks = Get-StigBenchmarks $p
        # The scope affects no name or id, so the default one is used.
        $reports = New-NcmReports $benchmarks (Get-ReportBaseName $p '') "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $true 'Any' $runSuffix
        foreach ($rep in $reports) {
            [void]$reportNames.Add($rep.Name)
            foreach ($pol in $rep.AssignedPolicies) {
                [void]$policyNames.Add($pol.PolicyName); [void]$policyIds.Add($pol.PolicyId)
                foreach ($r in $pol.AssignedPolicyRules) { [void]$ruleIds.Add($r.RuleId); [void]$ruleNames.Add($r.RuleName) }
            }
        }
        Write-Host ("$(Split-Path -Leaf $p): $(@($reports).Count) report(s), $($policyNames.Count) policy(ies), " +
            "$($ruleIds.Count) rule(s) would be generated with suffix ${runSuffix}; looking each up on the server")
    }
    Write-ToolLog verify info "audit: $($reportNames.Count) report name(s), $($policyNames.Count) policy name(s), $($ruleIds.Count) rule id(s), owner `"$($script:RuleOwner)`""
    $conn = New-CliConnection
    $found = Get-NcmServerAudit $conn @($reportNames) @($policyNames) @($policyIds) @($ruleIds) @($ruleNames)
    $section = {
        param([string]$Title, $Rows, [string[]]$Columns)
        $rows = @($Rows)
        Write-Host ''
        Write-Host "${Title}: $($rows.Count) row(s)"
        Write-ToolLog verify info "audit ${Title}: $($rows.Count) row(s)"
        $shown = 0
        foreach ($row in $rows) {
            $cells = @(foreach ($c in $Columns) { $v = Get-RowValue $row $c; if ($null -ne $v -and "$v" -ne '') { "$c=" + (Limit-OneLine "$v" 70) } })
            if ($shown -lt 50) { Write-Host ('  ' + ($cells -join '  ')) }
            $shown++
            Write-ToolLog verify debug ('  ' + (@(foreach ($c in $Columns) { "$c=" + (Get-RowValue $row $c) }) -join '; '))
        }
        if ($rows.Count -gt 50) { Write-Host "  ... $($rows.Count - 50) more in the run log" }
    }
    & $section 'Cirrus.PolicyReports (by name)' $found.reports @('PolicyReportID', 'Name', 'Grouping', 'ReportStatus', 'CacheStatus', 'LastError')
    & $section 'Cirrus.PolicyAssignment (report -> policy)' $found.assignments @('PolicyReportID', 'PolicyID')
    & $section 'Cirrus.Policies (by name, by generated id, by assignment)' $found.policies @('PolicyID', 'Name', 'Grouping', 'ConfigType')
    & $section 'Cirrus.PolicyRuleAssignment (policy -> rule)' $found.rule_assignments @('PolicyID', 'PolicyRuleID')
    & $section 'Cirrus.PolicyRules (by generated id)' $found.rules_by_id @('PolicyRuleID', 'Name', 'Owner', 'Grouping')
    & $section 'Cirrus.PolicyRules (by generated name)' $found.rules_by_name @('PolicyRuleID', 'Name', 'Owner')
    & $section "Cirrus.PolicyRules (Owner = `"$($script:RuleOwner)`", any run)" $found.rules_by_owner @('PolicyRuleID', 'Name', 'Grouping')
    & $section 'Cirrus.PolicyRules (Grouping under "DISA STIG", any run; a console import rewrites Owner)' $found.rules_by_grouping @('PolicyRuleID', 'Name', 'Grouping', 'Owner')
    & $section 'orphan rules: created by this tool, referenced by no policy' $found.orphans @('PolicyRuleID', 'Name', 'Grouping', 'Owner')
    if (@($found.orphans).Count -gt 0) {
        $msg = ("$(@($found.orphans).Count) rule(s) this tool created sit in the NCM rules library without a policy: a failed " +
            'API import left them (the server kept the rule although the HTTP answer was an error, or a rollback could ' +
            'not reach them). They are visible under Compliance -> Manage Policy Rules and can be deleted there, or with ' +
            'Cirrus.PolicyReports.DeletePolicyRules(ids).')
        Write-Host ''; Write-Host $msg -ForegroundColor Yellow
        Write-ToolLog verify warn $msg
    }
    Write-Host ''; Write-Host 'audit is read-only: nothing was created, changed or deleted.'
    return $found
}

function Invoke-CliRemove {
    # Same semantics as Python `remove`: read the tree, delete the report row,
    # then its unshared policies (DeletePolicies, deleteChildren false), then its
    # unshared rules (DeletePolicyRules). -DryRun prints the plan only.
    if (-not $Name) { throw '-Remove needs -Name <exact report name>' }
    $conn = New-CliConnection
    $log = { param($m) Write-Host (Hide-Secrets $m) }
    Write-ToolLog remove info "remove requested for report name `"$Name`" (dry run: $([bool]$DryRun), -Yes: $([bool]$Yes))"
    $found = @(Invoke-SwisQuery $conn 'SELECT PolicyReportID, Name, Grouping FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = $Name })
    if ($found.Count -eq 0) { throw ("no policy report named `"$Name`" on this server" + (Get-SimilarReportNames $conn $Name)) }
    $ids = @($found | ForEach-Object { Get-RowValue $_ 'PolicyReportID' })
    Write-ToolLog remove info ("$($ids.Count) report(s) named `"$Name`": " + ($ids -join ', '))
    if (-not $DryRun) { [void](Invoke-NcmPreflight $conn $log) }
    $plan = Get-NcmRemovalPlan $conn $ids $log
    $verb = 'about to delete'; if ($DryRun) { $verb = 'would delete' }
    Write-Host "$verb $($ids.Count) report(s) named `"$Name`":"
    Write-NcmRemovalPlan $plan $log
    if ($DryRun) {
        Write-Host 'dry run: nothing was deleted.'
        Write-ToolLog remove info 'dry run: nothing was deleted'
        return
    }
    if (-not $Yes) { throw 'refusing to delete without -Yes (preview with -DryRun)' }
    $left = Remove-NcmReports $conn $plan $log
    Write-ToolLog remove info ("done: deleted $($ids.Count) report(s), $($plan.DeletePolicies.Count) " +
        "policy/policies and $($plan.DeleteRules.Count) rule(s)")
    Write-Host ("done: deleted $($ids.Count) report(s), $($plan.DeletePolicies.Count) policy/policies " +
        "and $($plan.DeleteRules.Count) rule(s); kept $($plan.KeepPolicies.Count) shared " +
        "policy/policies and $($plan.KeepRules.Count) shared rule(s).")
    if ($left.reports.Count + $left.policies.Count + $left.rules.Count -gt 0) {
        throw 'some objects were still present after deletion; see the warnings above'
    }
}

function Invoke-CliTest($Conn, [string]$SourcePath) {
    # Python `test`: TestRule / TestRuleOnBackedUpConfig per generated rule.
    # Creates nothing; SolarWinds documents the result as a string without a
    # documented shape, so it is echoed verbatim.
    $configText = ''
    if ($ConfigFile) { $configText = [System.IO.File]::ReadAllText($ConfigFile) }
    if (-not $configText -and -not $ConfigId) {
        throw ('give -ConfigFile <path> or -ConfigId <NCM config GUID>. Find one with: ' +
            'SELECT ConfigID, NodeID, ConfigType, DownloadTime FROM NCM.ConfigArchive ORDER BY DownloadTime DESC')
    }
    $benchmarks = Get-StigBenchmarks $SourcePath
    $scope = Resolve-NcmScope $benchmarks $SourcePath $NodeWhere $Vendor $MachineType
    $cliDrafts = Read-PatternDrafts $PatternDrafts
    $reports = New-NcmReports $benchmarks (Get-ReportBaseName $SourcePath $Name) $scope.Where $Mode $Grouping `
        (-not $ImportDisabled) $ConfigType $Suffix $cliDrafts
    if ($WritePatternDrafts) { [void](Write-PatternDrafts $WritePatternDrafts $benchmarks $reports $cliDrafts { param($m) Write-Host $m }) }
    $rules = @($reports | ForEach-Object { $_.AssignedPolicies } | ForEach-Object { $_.AssignedPolicyRules })
    $total = $rules.Count
    if ($Limit -gt 0 -and $rules.Count -gt $Limit) { $rules = @($rules[0..($Limit - 1)]) }
    $source = 'the supplied config text'; if ($ConfigId) { $source = "backed-up config $ConfigId" }
    Write-Host "[NCM] testing $($rules.Count) of $total rule(s) against $source (nothing is created on the server)"
    Write-ToolLog verify info "testing $($rules.Count) of $total rule(s) against $source (nothing is created on the server)"
    $format = $null; $withOutput = 0
    foreach ($rule in $rules) {
        $res = Test-NcmRule $Conn $rule $configText $ConfigId $format
        $format = $res.Format
        $text = ''; if ($null -ne $res.Result) { $text = ([string]$res.Result).Trim() }
        if ($text) { $withOutput++ }
        $first = '(no output)'
        if ($text) { $first = Limit-Text (($text -split "`n")[0]) 160 }
        Write-Host ('  ' + (Limit-Text $rule.RuleName 70) + " -> $first")
        Write-ToolLog verify info ('  ' + (Limit-Text $rule.RuleName 70) + " -> $first")
    }
    Write-ToolLog verify info "$($rules.Count) rule(s) tested, $withOutput returned output"
    Write-Host ("$($rules.Count) rule(s) tested, $withOutput returned output. SolarWinds does not " +
        'document the shape of the TestRule result, so it is echoed above exactly as the server ' +
        'sent it and not interpreted here.')
}

function Invoke-CliRun {
    if ($Path.Count -gt $script:MaxZipFiles) {
        throw "up to $($script:MaxZipFiles) files per run"
    }
    foreach ($p in $Path) {
        if (-not (Test-Path -LiteralPath $p)) {
            throw ("file not found: $p`n" +
                   "Run with no arguments to open the GUI, or:`n" +
                   "  -Convert -Path <files>                       Local File Conversion Only`n" +
                   "  -Server <host> -Username <u> -Path <files>   import over SWIS`n" +
                   "  -Test -Server <host> ... -Path <file> -ConfigId <id>   dry-run rules`n" +
                   "  -Remove -Name <report> -Server <host> ...    undo an import")
        }
    }
    # module lock across the batch
    $modules = @($Path | ForEach-Object { Get-FileModule $_ $Target } | Sort-Object -Unique)
    if ($modules.Count -gt 1) {
        throw "a run imports into one module only - this selection mixes NCM and SCM files; split it into two runs"
    }
    $module = $modules[0]
    Write-Host "module for this run: $module"
    Write-ToolLog route info "module for this run: $module ($($Path.Count) file(s))"
    $log = { param($m) Write-Host (Hide-Secrets $m) }
    # Validated before anything is converted or sent, like the Python edition.
    $runSuffix = Test-Suffix $Suffix
    $template = $null
    if ($ScmProbeTemplate) { $template = Read-ProbeTemplate $ScmProbeTemplate }

    if ($Convert) {
        foreach ($p in $Path) {
            $folder = Split-Path -Parent (Resolve-Path $p)
            $scmItems = Get-ScmInputs $p $log
            if ($null -ne $scmItems) {
                if ($null -eq $scmItems[0].Member) {
                    Write-Host "[SCM] $p is already an importable SCM policy - nothing to convert"
                    Write-ToolLog scm info "$p is already an importable SCM policy - nothing to convert"
                    continue
                }
                # A policy zip: the members are already import payloads, so offline
                # conversion unpacks them unchanged for the console or a later import.
                [void](Write-ScmPolicyMembers $scmItems $folder $log)
                Write-Host ('import with:  disa_stig_tool.ps1 -Path <the zip or one file> -Server ...  or through ' +
                    'the web console: Settings -> SCM Settings -> Policies -> Import')
                continue
            }
            $benchmarks = Get-StigBenchmarks $p
            if ($module -eq 'SCM') {
                $family = Get-ScmOsFamily $benchmarks $p
                Write-ScmProbePlan $family $template $ScmProbeTemplate $log
                foreach ($b in $benchmarks) {
                    $out = Write-ScmPolicyFile $b $folder $runSuffix $family $template
                    Write-Host "[SCM] wrote $out - $($b.Rules.Count) rules"
                }
            } else {
                # An undecidable scope is refused offline too: the console file carries it.
                $scope = Resolve-NcmScope $benchmarks $p $NodeWhere $Vendor $MachineType
                $xmlWarning = Get-XmlConfigWarning $scope.Where
                if ($xmlWarning) { Write-Host $xmlWarning -ForegroundColor Yellow }
                $cliDrafts = Read-PatternDrafts $PatternDrafts
                $reports = New-NcmReports $benchmarks (Get-ReportBaseName $p $Name) $scope.Where $Mode `
                    $Grouping (-not $ImportDisabled) $ConfigType $runSuffix $cliDrafts
                if ($WritePatternDrafts) { [void](Write-PatternDrafts $WritePatternDrafts $benchmarks $reports $cliDrafts $log) }
                $written = New-Object System.Collections.ArrayList
                foreach ($r in $reports) {
                    $out = Write-ConsoleReportFile $r $folder
                    [void]$written.Add($out)
                    $c = Get-ReportCounts $r
                    Write-Host "[NCM] wrote $out - $($c.Policies) policy(ies), $($c.Rules) rules"
                }
                Send-Log $log 'file' 'info' ('[NCM] ' + (Get-NcmOfflineSummary $reports $written))
            }
        }
        return
    }

    if ($Test) {
        if ($module -eq 'SCM') {
            throw ('rule testing is an NCM feature; an SCM policy has no equivalent server-side dry ' +
                'run. Import it and use Orion.PolicyEngine.Policy.PollNowAndEvaluate against one node, ' +
                'or force NCM with -Target network.')
        }
        $conn = New-CliConnection
        foreach ($p in $Path) { Invoke-CliTest $conn $p }
        return
    }

    $conn = New-CliConnection
    foreach ($p in $Path) {
        if ($module -eq 'SCM') {
            $scmItems = Get-ScmInputs $p $log
            if ($null -ne $scmItems) {
                [void](Import-ScmPolicyItems $conn $scmItems $log {
                    param($r, $it)
                    Write-Host "SUCCESS [SCM] imported policy `"$($r.Name)`" (PolicyID $($r.PolicyId))" -ForegroundColor Green
                })
            } else {
                $benchmarks = Get-StigBenchmarks $p
                $family = Get-ScmOsFamily $benchmarks $p
                Write-ScmProbePlan $family $template $ScmProbeTemplate $log
                Test-ScmCollision $conn $benchmarks $runSuffix $log
                $entries = New-Object System.Collections.ArrayList
                foreach ($b in $benchmarks) {
                    $r = Import-ScmBenchmark $conn $b $log $runSuffix $family $template
                    [void]$entries.Add(@{ Name = $r.Name; PolicyId = $r.PolicyId; Rules = @($b.Rules).Count })
                    Write-Host "SUCCESS [SCM] `"$($r.Name)`" (PolicyID $($r.PolicyId)) - $(@($b.Rules).Count) rules defined" -ForegroundColor Green
                }
                foreach ($line in (Get-ScmImportSummary @($entries))) { Send-Log $log 'scm' 'info' "[SCM] $line" }
            }
        } else {
            $benchmarks = Get-StigBenchmarks $p
            $scope = Resolve-NcmScope $benchmarks $p $NodeWhere $Vendor $MachineType
            $xmlWarning = Get-XmlConfigWarning $scope.Where
            if ($xmlWarning) { Write-Host $xmlWarning -ForegroundColor Yellow }
            $cliDrafts = Read-PatternDrafts $PatternDrafts
            $reports = New-NcmReports $benchmarks (Get-ReportBaseName $p $Name) $scope.Where $Mode $Grouping `
                (-not $ImportDisabled) $ConfigType $runSuffix $cliDrafts
            if ($WritePatternDrafts) { [void](Write-PatternDrafts $WritePatternDrafts $benchmarks $reports $cliDrafts $log) }
            [void](Invoke-NcmPreflight $conn $log)
            # Before the first write: the scope must select nodes, and nothing this run
            # would create (names, PolicyIds, RuleIds) may exist already.
            [void](Invoke-ScopePreflight $conn $scope $AllowEmptyScope.IsPresent $log)
            Test-NcmCollision $conn $reports $runSuffix $log
            $run = Import-NcmReports $conn $reports $log (-not $NoRollback)
            foreach ($i in $run.Imported) {
                Write-Host "SUCCESS [NCM] `"$($i.Report.Name)`" - $($i.Rules) rules ($($i.ReportId))" -ForegroundColor Green
            }
            # Reports verified before a failure still get caching / disabling. A
            # refused StartCaching / UpdateReportStatus does not stop the run: the
            # console files that are due below are still written.
            $confirmed = Complete-NcmImport $conn @($run.Imported | ForEach-Object { $_.ReportId }) `
                $ImportDisabled.IsPresent $NoCache.IsPresent $log
            $sumLevel = 'info'; if ($null -ne $run.Failure) { $sumLevel = 'warn' }
            foreach ($line in (Get-NcmImportSummary $reports $run.Imported $run.Remaining ([bool]($run.Failure -and $run.Failure.Data['WireFailure'])))) {
                Send-Log $log 'import' $sumLevel "[NCM] $line"
            }
            if ($null -eq $run.Failure -and -not $confirmed) {
                $state = 'caching'; if ($ImportDisabled) { $state = 'disabled state' }
                throw "[NCM] the reports were imported and verified, but the requested $state could not be confirmed; see the warning above"
            }
            if ($null -ne $run.Failure) {
                if ($run.Imported.Count -gt 0) {
                    Write-Host ("[NCM] $($run.Imported.Count) of $($reports.Count) report(s) were imported " +
                        'before the failure and remain on the server') -ForegroundColor Yellow
                }
                if ($run.Failure.Data['WireFailure']) {
                    Write-Host (Hide-Secrets $run.Failure.Message) -ForegroundColor Yellow
                    Write-ToolLog import warn "writing console-importable files for $($run.Remaining.Count) report(s) the API did not accept"
                    $folder = Split-Path -Parent (Resolve-Path $p)
                    foreach ($rep in $run.Remaining) {
                        Write-Host ('[NCM] wrote ' + (Write-ConsoleReportFile $rep $folder))
                    }
                    throw '[NCM] import the files written above through the web console: Compliance > Manage Policy Reports > Import'
                }
                Write-Host ('[NCM] not imported: ' + (($run.Remaining | ForEach-Object { '"' + $_.Name + '"' }) -join ', '))
                throw $run.Failure
            }
        }
    }
}

# =========================================================================
# GUI (Windows only - WinForms, built into .NET; nothing to install)
# =========================================================================
function Show-StigGui {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    # ---- startup disclaimer: must acknowledge to proceed --------------------
    $gate = New-Object System.Windows.Forms.Form
    $gate.Text = 'DISA STIG Conversion Tool'
    $gate.Size = New-Object System.Drawing.Size(640, 320)
    $gate.StartPosition = 'CenterScreen'
    $gate.FormBorderStyle = 'FixedDialog'; $gate.MaximizeBox = $false
    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = "This is not built by SolarWinds Inc. or DISA. All Code is visible for Code Audit and documentation is available for SWIS calls."
    $lbl.Location = New-Object System.Drawing.Point(16, 16)
    $lbl.Size = New-Object System.Drawing.Size(592, 60)
    $gate.Controls.Add($lbl)
    $ack = New-Object System.Windows.Forms.CheckBox
    $ack.Text = "I Acknowledge that I will check the Reports Imported and Understand that DISA STIG Reports do not always include explicit instructions to resolve. Resolution falls on Agency application of the standards set by the DISA STIG System"
    $ack.Location = New-Object System.Drawing.Point(16, 84)
    $ack.Size = New-Object System.Drawing.Size(592, 110)
    $ack.CheckAlign = 'TopLeft'; $ack.TextAlign = 'TopLeft'
    $gate.Controls.Add($ack)
    $proceed = New-Object System.Windows.Forms.Button
    $proceed.Text = 'Proceed'; $proceed.Enabled = $false
    $proceed.Location = New-Object System.Drawing.Point(500, 240)
    $proceed.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $gate.Controls.Add($proceed)
    $ack.Add_CheckedChanged({ $proceed.Enabled = $ack.Checked })
    $gate.AcceptButton = $proceed
    if ($gate.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        Write-ToolLog gui info 'the disclaimer was not acknowledged; the GUI closed'
        return
    }
    Write-ToolLog gui info 'disclaimer acknowledged; main window opened'

    # ---- main window --------------------------------------------------------
    $green  = [System.Drawing.Color]::FromArgb(198, 239, 206)
    $yellow = [System.Drawing.Color]::FromArgb(255, 235, 156)
    $red    = [System.Drawing.Color]::FromArgb(255, 199, 206)
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'DISA STIG Conversion Tool'
    $form.Size = New-Object System.Drawing.Size(760, 810)
    $form.StartPosition = 'CenterScreen'

    $script:y = 12
    $mk = { param($ctrl, $x, $w, $h) $ctrl.Location = New-Object System.Drawing.Point($x, $script:y)
            $ctrl.Size = New-Object System.Drawing.Size($w, $h); $form.Controls.Add($ctrl); $ctrl }
    function L([string]$t, [int]$x, [int]$w) {
        $l = New-Object System.Windows.Forms.Label; $l.Text = $t
        & $mk $l $x $w 18 | Out-Null; $l
    }

    L 'Server IP/FQDN' 12 140 | Out-Null
    L 'SWIS Port' 470 80 | Out-Null
    $script:y += 18
    $serverBox = & $mk (New-Object System.Windows.Forms.TextBox) 12 440 24
    $portBox = & $mk (New-Object System.Windows.Forms.TextBox) 470 70 24; $portBox.Text = '17774'
    $script:y += 32
    L 'Username' 12 140 | Out-Null; L 'Password' 300 140 | Out-Null
    $script:y += 18
    $userBox = & $mk (New-Object System.Windows.Forms.TextBox) 12 270 24
    $passBox = & $mk (New-Object System.Windows.Forms.TextBox) 300 270 24
    $passBox.UseSystemPasswordChar = $true
    $script:y += 32
    L 'API token (2026.4+, instead of username/password)' 12 440 | Out-Null
    $script:y += 18
    $tokenBox = & $mk (New-Object System.Windows.Forms.TextBox) 12 558 24
    $tokenBox.UseSystemPasswordChar = $true
    $script:y += 32
    $winAuth = & $mk (New-Object System.Windows.Forms.CheckBox) 12 330 22
    $winAuth.Text = 'Login with current Windows user'
    $verifyTls = & $mk (New-Object System.Windows.Forms.CheckBox) 360 240 22
    $verifyTls.Text = 'Verify TLS certificate (default)'; $verifyTls.Checked = $true
    $script:y += 24
    # connection status line, updated live, sits under the login controls
    $connStatus = & $mk (New-Object System.Windows.Forms.Label) 12 540 20
    $connStatus.Text = 'Connection: not tested'
    $trustBtn = & $mk (New-Object System.Windows.Forms.Button) 560 170 24
    $trustBtn.Text = 'Trust server certificate'
    $script:y += 32

    L "STIG files (up to $($script:MaxZipFiles); one module per batch - NCM or SCM, never both)" 12 700 | Out-Null
    $script:y += 18
    $fileList = & $mk (New-Object System.Windows.Forms.ListBox) 12 620 84
    $browse = & $mk (New-Object System.Windows.Forms.Button) 640 90 26
    $browse.Text = 'Browse'
    $script:y += 88
    $moduleNotice = & $mk (New-Object System.Windows.Forms.Label) 12 700 20
    $moduleNotice.Text = 'Module: (select a file - the batch locks to NCM or SCM based on the first file)'
    $script:y += 26

    L 'Compliance target' 12 140 | Out-Null; L 'NCM node scope' 380 200 | Out-Null
    $script:y += 18
    $targetBox = & $mk (New-Object System.Windows.Forms.ComboBox) 12 350 24
    $targetBox.DropDownStyle = 'DropDownList'
    [void]$targetBox.Items.AddRange(@(
        'Auto Compliance Assignment', 'Network Compliance (NCM)', 'Server Compliance (SCM)'))
    $targetBox.SelectedIndex = 0
    $whereBox = & $mk (New-Object System.Windows.Forms.TextBox) 380 350 24
    $whereBox.Text = 'auto'
    function Get-GuiTarget {
        switch ($targetBox.SelectedIndex) { 1 { return 'network' } 2 { return 'server' } default { return 'auto' } }
    }
    $script:y += 30
    $importDisabledBox = & $mk (New-Object System.Windows.Forms.CheckBox) 12 718 22
    $importDisabledBox.Text = 'Import the NCM report disabled (no caching) so it can be reviewed first'
    $importDisabledBox.Checked = [bool]$ImportDisabled
    $script:y += 26
    # The version suffix ends every generated name and seeds every id (-Suffix).
    L 'Name suffix' 12 90 | Out-Null
    $suffixBox = & $mk (New-Object System.Windows.Forms.TextBox) 104 60 22
    $suffixBox.Text = $Suffix
    $emptyScopeBox = & $mk (New-Object System.Windows.Forms.CheckBox) 190 540 22
    $emptyScopeBox.Text = 'Import even when the NCM node scope matches no node'
    $emptyScopeBox.Checked = [bool]$AllowEmptyScope
    $script:y += 30

    $testBtn = & $mk (New-Object System.Windows.Forms.Button) 12 150 30
    $testBtn.Text = 'Test Connection'
    $importBtn = & $mk (New-Object System.Windows.Forms.Button) 172 150 30
    $importBtn.Text = 'Import'
    $convertBtn = & $mk (New-Object System.Windows.Forms.Button) 332 210 30
    $convertBtn.Text = 'Local File Conversion Only'
    $detailsBtn = & $mk (New-Object System.Windows.Forms.Button) 552 178 30
    $detailsBtn.Text = 'Show detailed log'
    $script:y += 38

    # summary (always visible) + detailed log (auto-hidden, expands on issues)
    $summary = & $mk (New-Object System.Windows.Forms.RichTextBox) 12 718 120
    $summary.ReadOnly = $true
    $script:y += 126
    # where the run log is written (the same file format as the CLI and Python)
    $logPathLabel = & $mk (New-Object System.Windows.Forms.Label) 12 718 20
    $shownLog = $script:LogState.Path; if (-not $shownLog) { $shownLog = '(not written)' }
    $logPathLabel.Text = "Log file: $shownLog"
    $script:y += 24
    $detail = & $mk (New-Object System.Windows.Forms.TextBox) 12 718 220
    $detail.Multiline = $true; $detail.ScrollBars = 'Vertical'; $detail.ReadOnly = $true
    $detail.Visible = $false

    $state = @{ Pinned = $null; Module = $null }
    function Add-Summary([string]$Text, $Color) {
        $level = 'info'
        if ($null -ne $Color -and $Color -eq $red) { $level = 'error' }
        elseif ($null -ne $Color -and $Color -eq $yellow) { $level = 'warn' }
        Write-ToolLog gui $level $Text
        $summary.SelectionStart = $summary.TextLength
        if ($Color) { $summary.SelectionColor = $Color }
        $summary.AppendText((Hide-Secrets $Text) + "`r`n")
        $summary.SelectionColor = $summary.ForeColor
    }
    function Add-Detail([string]$Text) {
        $detail.AppendText((Hide-Secrets $Text) + "`r`n")
    }
    $logBlock = { param($m) Add-Detail $m }
    $detailsBtn.Add_Click({
        $detail.Visible = -not $detail.Visible
        if ($detail.Visible) { $detailsBtn.Text = 'Hide detailed log' }
        else { $detailsBtn.Text = 'Show detailed log' }
    })
    function Show-Issue { $detail.Visible = $true; $detailsBtn.Text = 'Hide detailed log' }

    $winAuth.Add_CheckedChanged({
        $userBox.Enabled = -not $winAuth.Checked
        $passBox.Enabled = -not $winAuth.Checked
        $tokenBox.Enabled = -not $winAuth.Checked
    })

    $browse.Add_Click({
        $dlg = New-Object System.Windows.Forms.OpenFileDialog
        $dlg.Multiselect = $true
        # *.scm-profile only for policy YAML from older builds; a JSON collection
        # profile is refused by Get-FileModule when it is added.
        $dlg.Filter = 'STIG content|*.zip;*.xml;*.xsl;*.yaml;*.yml;*.scm-profile|All files|*.*'
        if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return }
        foreach ($f in $dlg.FileNames) {
            if ($fileList.Items.Count -ge $script:MaxZipFiles) {
                Add-Summary "at most $($script:MaxZipFiles) files per batch" $yellow; break
            }
            try { $m = Get-FileModule $f (Get-GuiTarget) } catch { Add-Summary ("skipped " + $f + ": " + $_.Exception.Message) $red; continue }
            if ($null -eq $state.Module) {
                $state.Module = $m
                $moduleNotice.Text = "Module: locked to $m for this batch (from the first file selected)"
                Add-Summary "notice: this batch is now a $m import" $null
            } elseif ($m -ne $state.Module) {
                Add-Summary "skipped $(Split-Path -Leaf $f): it is a $m file, but this batch is locked to $($state.Module) - run it in a separate batch" $yellow
                continue
            }
            [void]$fileList.Items.Add($f)
        }
        if ($fileList.Items.Count -eq 0) { $state.Module = $null }
    })

    $trustBtn.Add_Click({
        try {
            $info = Get-ServerCertThumbprint $serverBox.Text.Trim() ([int]$portBox.Text)
            Write-ToolLog swis info "pinned the certificate $($serverBox.Text.Trim()):$($portBox.Text) presents: SHA-256 $($info.Thumbprint)"
            $state.Pinned = $info.Thumbprint
            $stockNote = ''
            if ($info.Stock) { $stockNote = ' (stock SolarWinds-Orion certificate)' }
            Add-Summary ("trusted the server certificate - SHA-256 " + $info.Thumbprint + $stockNote) $null
            Add-Detail ("subject: " + $info.Subject)
        } catch { Add-Summary ('certificate fetch failed: ' + $_.Exception.Message) $red; Show-Issue }
    })

    function New-GuiConnection {
        Register-Secret $passBox.Text
        Register-Secret $tokenBox.Text.Trim()
        if ($tokenBox.Text.Trim() -and -not $winAuth.Checked -and ($userBox.Text.Trim() -or $passBox.Text)) {
            throw 'enter either a username and password or an API token, not both'
        }
        $guiToken = ''; if (-not $winAuth.Checked) { $guiToken = $tokenBox.Text.Trim() }
        New-SwisConnection $serverBox.Text.Trim() ([int]$portBox.Text) $userBox.Text.Trim() `
            $passBox.Text $winAuth.Checked (-not $verifyTls.Checked) $state.Pinned $guiToken
    }

    $testBtn.Add_Click({
        Write-ToolLog gui info 'Test Connection pressed'
        $testBtn.BackColor = [System.Drawing.Color]::Empty
        $connStatus.Text = 'Connection: testing'
        try {
            $r = Test-SwisConnection (New-GuiConnection)
            Add-Detail $r.Detail
            switch ($r.Status) {
                'green'  { $testBtn.BackColor = $green;  $connStatus.Text = 'Connection: OK - ' + $r.Version
                           Add-Summary $r.Detail $null }
                'yellow' { $testBtn.BackColor = $yellow; $connStatus.Text = 'Connection: limited - see log'
                           Add-Summary $r.Detail $null; Show-Issue }
                'red'    { $testBtn.BackColor = $red;    $connStatus.Text = 'Connection: FAILED'
                           Add-Summary $r.Detail $red; Show-Issue }
            }
        } catch {
            $testBtn.BackColor = $red; $connStatus.Text = 'Connection: FAILED'
            Add-Summary ('connection failed: ' + $_.Exception.Message) $red; Show-Issue
        }
    })

    function Invoke-Batch([bool]$Offline) {
        $btn = $importBtn; if ($Offline) { $btn = $convertBtn }
        $btn.BackColor = [System.Drawing.Color]::Empty
        if ($fileList.Items.Count -eq 0) { Add-Summary 'select at least one file' $yellow; return }
        $action = 'Import'; if ($Offline) { $action = 'Local File Conversion Only' }
        Write-ToolLog gui info ("$action pressed: $($fileList.Items.Count) $($state.Module) file(s): " + (@($fileList.Items) -join ', '))
        $ok = 0; $fail = 0
        $conn = $null
        if (-not $Offline) {
            try { $conn = New-GuiConnection } catch { Add-Summary $_.Exception.Message $red; $btn.BackColor = $red; return }
        }
        foreach ($f in @($fileList.Items)) {
            $prefix = '[' + $state.Module + '] '
            try {
                if ($state.Module -eq 'SCM') {
                    $scmItems = Get-ScmInputs $f $logBlock
                    if ($null -ne $scmItems) {
                        if ($Offline) {
                            if ($null -eq $scmItems[0].Member) {
                                Add-Summary ($prefix + (Split-Path -Leaf $f) + ' is already importable - nothing to convert') $null; $ok++; continue
                            }
                            foreach ($out in (Write-ScmPolicyMembers $scmItems (Split-Path -Parent $f) $logBlock)) {
                                Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out) + ' (policy member, bytes unchanged)') ([System.Drawing.Color]::Green)
                            }
                            $ok++; continue
                        }
                        $packEntries = New-Object System.Collections.ArrayList
                        [void](Import-ScmPolicyItems $conn $scmItems $logBlock {
                            param($r, $it)
                            $n = Get-ScmRuleCount $it.Text
                            [void]$packEntries.Add(@{ Name = $r.Name; PolicyId = $r.PolicyId; Rules = $n })
                            Add-Summary ("SUCCESS " + $prefix + '"' + $r.Name + '"' + " (PolicyID $($r.PolicyId)) - $n rules defined") ([System.Drawing.Color]::Green)
                        })
                        Add-Summary ($prefix + (Get-ScmImportSummary @($packEntries))[-1]) ([System.Drawing.Color]::Green)
                        $ok++
                    } else {
                        $guiSuffix = Test-Suffix $suffixBox.Text.Trim()
                        $benchmarks = Get-StigBenchmarks $f
                        $family = Get-ScmOsFamily $benchmarks $f
                        Write-ScmProbePlan $family $null '' $logBlock
                        if (-not $Offline) { Test-ScmCollision $conn $benchmarks $guiSuffix $logBlock }
                        $scmEntries = New-Object System.Collections.ArrayList
                        foreach ($b in $benchmarks) {
                            if ($Offline) {
                                $out = Write-ScmPolicyFile $b (Split-Path -Parent $f) $guiSuffix $family
                                $polName = Get-ScmPolicyName $b $guiSuffix
                                [void]$scmEntries.Add(@{ Name = $polName; PolicyId = $null; Rules = @($b.Rules).Count })
                                Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out) + " - SCM policy `"$polName`", $(@($b.Rules).Count) rules defined") ([System.Drawing.Color]::Green)
                            } else {
                                $r = Import-ScmBenchmark $conn $b $logBlock $guiSuffix $family
                                [void]$scmEntries.Add(@{ Name = $r.Name; PolicyId = $r.PolicyId; Rules = @($b.Rules).Count })
                                Add-Summary ("SUCCESS " + $prefix + '"' + $r.Name + "`" (PolicyID $($r.PolicyId)) - $(@($b.Rules).Count) rules defined") ([System.Drawing.Color]::Green)
                            }
                        }
                        $scmWhat = 'imported'; if ($Offline) { $scmWhat = 'written' }
                        $scmTotals = (Get-ScmImportSummary @($scmEntries) $scmWhat)[-1]
                        Add-Summary ($prefix + $scmTotals) ([System.Drawing.Color]::Green)
                        Write-ToolLog scm info $scmTotals
                        if ($family -eq 'linux') {
                            Add-Summary ($prefix + "Linux: the SCM probe is Unverified on Linux nodes; see README 'Testing Linux STIGs in SCM'") $yellow
                        }
                        $ok++
                    }
                } else {
                    $guiSuffix = Test-Suffix $suffixBox.Text.Trim()
                    $benchmarks = Get-StigBenchmarks $f
                    $scope = Resolve-NcmScope $benchmarks $f $whereBox.Text.Trim() '' ''
                    $xmlWarning = Get-XmlConfigWarning $scope.Where
                    if ($xmlWarning) { Add-Summary $xmlWarning $yellow; Show-Issue }
                    $reportEnabled = -not $importDisabledBox.Checked
                    $reports = New-NcmReports $benchmarks (Get-ReportBaseName $f '') $scope.Where 'manual' 'DISA STIG' $reportEnabled 'Any' $guiSuffix
                    if ($Offline) {
                        $written = New-Object System.Collections.ArrayList
                        foreach ($r in $reports) {
                            $out = Write-ConsoleReportFile $r (Split-Path -Parent $f)
                            [void]$written.Add($out)
                            $c = Get-ReportCounts $r
                            Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out) + " - $($c.Policies) policy(ies), $($c.Rules) rules") ([System.Drawing.Color]::Green)
                        }
                        $offlineTotals = Get-NcmOfflineSummary $reports $written
                        Add-Summary ($prefix + $offlineTotals) $null
                        Write-ToolLog file info $offlineTotals
                        $ok++
                    } else {
                        [void](Invoke-NcmPreflight $conn $logBlock)
                        [void](Invoke-ScopePreflight $conn $scope $emptyScopeBox.Checked $logBlock)
                        Test-NcmCollision $conn $reports $guiSuffix $logBlock
                        $run = Import-NcmReports $conn $reports $logBlock $true
                        foreach ($i in $run.Imported) {
                            Add-Summary ("SUCCESS " + $prefix + '"' + $i.Report.Name + '" - ' + $i.Rules + ' rules') ([System.Drawing.Color]::Green)
                        }
                        # Reports verified before a failure are still cached or disabled.
                        $confirmed = Complete-NcmImport $conn @($run.Imported | ForEach-Object { $_.ReportId }) `
                            (-not $reportEnabled) $false $logBlock
                        if (-not $confirmed) {
                            $wanted = 'cached (StartCaching)'; if (-not $reportEnabled) { $wanted = 'Disabled' }
                            Add-Summary ($prefix + "the imported reports could not be confirmed as $wanted; see the detailed log") $yellow
                            Show-Issue
                        }
                        $sumColor = [System.Drawing.Color]::Green; $sumLevel = 'info'
                        if ($null -ne $run.Failure) { $sumColor = $null; $sumLevel = 'warn' }
                        foreach ($line in (Get-NcmImportSummary $reports $run.Imported $run.Remaining ([bool]($run.Failure -and $run.Failure.Data['WireFailure'])))) {
                            Add-Summary ($prefix + $line) $sumColor
                            Write-ToolLog import $sumLevel $line
                        }
                        if ($null -ne $run.Failure) {
                            if ($run.Imported.Count -gt 0) {
                                Add-Summary ($prefix + "$($run.Imported.Count) report(s) were imported before the failure and remain on the server") $yellow
                            }
                            if ($run.Failure.Data['WireFailure']) {
                                Add-Summary ($prefix + $run.Failure.Message) $null
                                foreach ($rep in $run.Remaining) {
                                    $out = Write-ConsoleReportFile $rep (Split-Path -Parent $f)
                                    Add-Summary ($prefix + 'wrote ' + (Split-Path -Leaf $out)) $null
                                }
                                Show-Issue
                                throw ($prefix + 'API import refused; console files written for WebUI import')
                            }
                            throw $run.Failure
                        }
                        $ok++
                    }
                }
            } catch {
                $fail++
                Add-Summary ($prefix + 'FAILED ' + (Split-Path -Leaf $f) + ': ' + $_.Exception.Message) $red
                Add-Detail ($prefix + $_.Exception.ToString())
                Show-Issue
            }
        }
        if ($fail -eq 0) { $btn.BackColor = $green }
        elseif ($ok -gt 0) { $btn.BackColor = $yellow }
        else { $btn.BackColor = $red }
        $batchLevel = 'info'; if ($fail -gt 0) { $batchLevel = 'warn' }
        Write-ToolLog gui $batchLevel "batch finished: $ok file(s) succeeded, $fail failed"
        if ($script:LogState.Path) { Add-Summary "details are in the log file: $($script:LogState.Path)" $null }
    }
    $importBtn.Add_Click({ Invoke-Batch $false })
    $convertBtn.Add_Click({ Invoke-Batch $true })

    if ($script:LogState.Path) { Add-Summary "log file: $($script:LogState.Path)" $null }
    [void]$form.ShowDialog()
    Write-ToolLog gui info 'main window closed'
}

# =========================================================================
# Entry point
# =========================================================================
function Start-ToolRun([string]$Mode) {
    # Registered before anything is logged, so the start-of-run command line and
    # every later line are redacted even when the password or token was never used.
    Register-Secret $env:SWIS_PASSWORD
    Register-Secret $env:SWIS_API_TOKEN
    $p = Initialize-ToolLog $LogFile $LogLevel
    Write-Host "log file: $p"
    Write-ToolLogStart $Mode
}

function Complete-ToolRun([int]$ExitCode) {
    Write-ToolLogEnd $ExitCode
    if ($script:LogState.Path) { Write-Host "log file: $($script:LogState.Path)" }
}

function Complete-ToolRunWithError($ErrorRecord) {
    # Logs the failure and the end-of-run summary; returns the redacted message.
    $msg = Hide-Secrets $ErrorRecord.Exception.Message
    Write-ToolLog main error "error: $msg"
    Complete-ToolRun 1
    return $msg
}

if ($Audit) {
    try { Start-ToolRun 'cli'; [void](Invoke-CliAudit) }
    catch { $runError = Complete-ToolRunWithError $_; Write-Error $runError; exit 1 }
    Complete-ToolRun 0
} elseif ($Remove) {
    try { Start-ToolRun 'cli'; Invoke-CliRemove }
    catch { $runError = Complete-ToolRunWithError $_; Write-Error $runError; exit 1 }
    Complete-ToolRun 0
} elseif ($Path -and $Path.Count -gt 0) {
    try { Start-ToolRun 'cli'; Invoke-CliRun }
    catch { $runError = Complete-ToolRunWithError $_; Write-Error $runError; exit 1 }
    Complete-ToolRun 0
} elseif (-not $NoGui) {
    if ($env:OS -ne 'Windows_NT') {
        Write-Error 'the GUI needs Windows (WinForms); on this platform pass -Path (and -Convert or -Server)'
        exit 1
    }
    try { Start-ToolRun 'gui'; Show-StigGui }
    catch {
        $msg = Hide-Secrets ($_.Exception.Message + "`n`n" + $_.ScriptStackTrace)
        Write-ToolLog main error "startup error: $msg"
        Write-ToolLogEnd 1
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show($msg,
                'DISA STIG Conversion Tool - startup error')
        } catch { }
        Write-Error $msg
        exit 1
    }
    Complete-ToolRun 0
}
