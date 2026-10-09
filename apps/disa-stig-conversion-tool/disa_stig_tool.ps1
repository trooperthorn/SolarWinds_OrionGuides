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
.\disa_stig_tool.ps1 -Test -Path .\stig.zip -Server orion.example.com -Username admin -ConfigId <ConfigID>
Dry-runs the generated rules with TestRuleOnBackedUpConfig; creates nothing.

.EXAMPLE
.\disa_stig_tool.ps1 -Remove -Name "<report name>" -Server orion.example.com -Username admin -DryRun
Shows what removing that report would delete and keep; add -Yes instead of -DryRun to delete.
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
    [switch]$WindowsAuth,
    [switch]$Insecure,
    [switch]$PinServerCert,
    [ValidateSet('auto', 'network', 'server')][string]$Target = 'auto',
    [string]$NodeWhere = 'auto',
    [ValidateSet('manual', 'heuristic')][string]$Mode = 'manual',
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
    [string]$LogFile,
    [ValidateSet('debug', 'info', 'warn')][string]$LogLevel = 'info'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

# One version for the tool, shared by both editions (disa_stig_tool.py carries the
# same number). It is written into every log file's start-of-run line.
$script:ToolVersion = '2.0.0'
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
$script:LogBodyLimit = 4096   # debug-level request/response bodies are cut to this many chars
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
    if ($Text.Length -le $script:LogBodyLimit) { return $Text }
    return $Text.Substring(0, $script:LogBodyLimit) + "... [truncated, $($Text.Length) chars]"
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
        Write-ToolLog parse info "skipped ${SourceName}: does not look like XML"
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
        Write-ToolLog parse info "skipped ${SourceName}: no XCCDF Benchmark element found (root is $rootName)"
    } else {
        Write-ToolLog parse info "parsed ${SourceName}: $($found.Count) benchmark(s)"
    }
    return @($found)
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
    $mgr = New-Object System.Xml.XmlNamespaceManager($Root.OwnerDocument.NameTable)
    $mgr.AddNamespace('x', $Ns)
    foreach ($group in $Root.SelectNodes('.//x:Group', $mgr)) {
        $rule = $group.SelectSingleNode('x:Rule', $mgr)
        if ($null -eq $rule) { continue }
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
        foreach ($ident in $rule.SelectNodes('x:ident', $mgr)) {
            if (('' + $ident.GetAttribute('system')).EndsWith('/cci')) {
                [void]$ccis.Add(('' + $ident.InnerText).Trim())
            }
        }
        $sev = ('' + $rule.GetAttribute('severity')).ToLower()
        if (-not $sev) { $sev = 'medium' }
        [void]$rules.Add(@{
            VulnId       = Remove-ScapPrefix $group.GetAttribute('id')
            RuleId       = Remove-ScapPrefix $rule.GetAttribute('id')
            StigId       = Get-XmlText $rule 'version' $Ns
            Severity     = $sev
            Title        = Get-XmlText $rule 'title' $Ns
            Discussion   = Get-PseudoTag $desc 'VulnDiscussion'
            CheckContent = $checkContent
            OvalRef      = $ovalRef
            FixText      = Get-XmlText $rule 'fixtext' $Ns
            Ccis         = @($ccis)
        })
    }
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

function Get-StigBenchmarks([string]$SourcePath) {
    # Zip, directory, .xml, or .xsl (resolves the benchmark XML next to it).
    # Discovery is by content, not filename; both editions of one benchmark
    # dedupe to the manual one (richer: check prose; fix text is identical).
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
            } else {
                Write-ToolLog parse info "skipped $($f.Name): not an .xml file"
            }
        }
    } elseif ($SourcePath -match '\.(zip)$') {
        Write-ToolLog parse info "input ${SourcePath}: zip ($((Get-Item -LiteralPath $SourcePath).Length) bytes)"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($SourcePath)
        try {
            foreach ($entry in ($zip.Entries | Sort-Object FullName)) {
                if (-not $entry.Name) { continue }   # a directory entry
                if ($entry.Name -match '\.xml$') {
                    $ms = New-Object System.IO.MemoryStream
                    $s = $entry.Open(); $s.CopyTo($ms); $s.Dispose()
                    & $addXml $ms.ToArray() $entry.Name
                } elseif ($entry.Name -match '\.zip$') {
                    Write-ToolLog parse info "nested zip $($entry.FullName): reading its members"
                    $ms = New-Object System.IO.MemoryStream
                    $s = $entry.Open(); $s.CopyTo($ms); $s.Dispose()
                    $ms.Position = 0
                    $inner = New-Object System.IO.Compression.ZipArchive($ms)
                    foreach ($ie in ($inner.Entries | Sort-Object FullName)) {
                        if (-not $ie.Name) { continue }
                        if ($ie.Name -match '\.xml$') {
                            $ims = New-Object System.IO.MemoryStream
                            $is2 = $ie.Open(); $is2.CopyTo($ims); $is2.Dispose()
                            & $addXml $ims.ToArray() $ie.Name
                        } else {
                            Write-ToolLog parse info "skipped $($entry.FullName)/$($ie.FullName): not an .xml member"
                        }
                    }
                } else {
                    Write-ToolLog parse info "skipped $($entry.FullName): not an .xml or .zip member (stylesheet, document or other content)"
                }
            }
        } finally { $zip.Dispose() }
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
    # dedupe: manual edition wins over scap for the same benchmark id
    $byId = [ordered]@{}
    foreach ($b in $benchmarks) {
        $key = $b.BenchmarkId; if (-not $key) { $key = $b.Title }
        if (-not $byId.Contains($key)) {
            $byId[$key] = $b
        } elseif ($byId[$key].Edition -eq 'scap' -and $b.Edition -eq 'manual') {
            Write-ToolLog parse info ("dedupe ${key}: kept the manual edition from $($b.Source), " +
                "dropped the SCAP edition from $($byId[$key].Source)")
            $byId[$key] = $b
        } else {
            Write-ToolLog parse info ("dedupe ${key}: kept the $($byId[$key].Edition) edition from " +
                "$($byId[$key].Source), dropped the $($b.Edition) edition from $($b.Source)")
        }
    }
    if ($byId.Count -eq 0) {
        Write-ToolLog parse warn "${SourcePath}: no XCCDF benchmark found inside"
        throw "$SourcePath contains no XCCDF benchmark"
    }
    Write-ToolLog parse info "${SourcePath}: $($byId.Count) benchmark(s) after dedupe"
    return , @($byId.Values)   # unary comma: stay an array even with one benchmark
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
$script:ServerOses = [ordered]@{
    'red hat'    = @('Red Hat Enterprise Linux', "MachineType LIKE '%Red Hat%'")
    'rhel'       = @('Red Hat Enterprise Linux', "MachineType LIKE '%Red Hat%'")
    'ubuntu'     = @('Ubuntu', "MachineType LIKE '%Ubuntu%'")
    'debian'     = @('Debian', "MachineType LIKE '%Debian%'")
    'centos'     = @('CentOS', "MachineType LIKE '%CentOS%'")
    'linux'      = @('Linux', "MachineType LIKE '%Linux%'")
    'windows'    = @('Windows', "MachineType LIKE '%Windows%'")
    'sql server' = @('Windows', "MachineType LIKE '%Windows%'")
    'iis'        = @('Windows', "MachineType LIKE '%Windows%'")
    'exchange'   = @('Windows', "MachineType LIKE '%Windows%'")
}

function Resolve-StigTarget($Benchmarks, [string]$SourceName) {
    $text = ($SourceName + ' ' + (($Benchmarks | ForEach-Object { $_.Title + ' ' + $_.Source }) -join ' ')).ToLower()
    foreach ($kw in $script:ServerOses.Keys) {
        if ($text.Contains($kw)) {
            Write-ToolLog route info "server keyword '$kw' matched in the file/benchmark names -> server ($($script:ServerOses[$kw][0]))"
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

function New-NodeSelectionString([string]$Where) {
    # The format real 2026.2.2 console exports carry: WebCriteria:<picker
    # XML>SQL:Where (...) - bare column names (Vendor, not Nodes.Vendor).
    # Joined with explicit LF so the bytes match the Python edition whatever
    # line endings this file is checked out with.
    $w = ($Where -replace '\bNodes\.', '').Trim()
    if (-not $w.ToLower().StartsWith('(')) { $w = "($w)" }
    $criteria = ''
    $m = [regex]::Match($w, "Vendor\s*(?:=|LIKE)\s*'%?([^%']+)%?'",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) {
        $vendor = $m.Groups[1].Value
        $id = Get-DeterministicGuid ("stig2ncm-criteria:" + $vendor)
        $criteria = (@(
            '<?xml version="1.0" encoding="utf-16"?>',
            '<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
            '  <WebSelectionCriteria>',
            "    <Id>$id</Id>",
            '    <LogicalCondition />',
            '    <SelectedColumn>Vendor</SelectedColumn>',
            '    <MatchType>=</MatchType>',
            "    <SelectedValue>$vendor</SelectedValue>",
            '  </WebSelectionCriteria>',
            '</ArrayOfWebSelectionCriteria>') -join "`n")
    }
    return "WebCriteria:${criteria}SQL:Where $w "
}

# XCCDF severity -> NCM ErrorLevel. The console's default names for 2/1/0 are
# critical/warning/info, but the names are editable per server.
$script:SeverityToErrorLevel = @{ high = 2; medium = 1; low = 0 }
# Generated text that must match the Python edition byte for byte but cannot be
# written literally in this ASCII-only file.
$script:EmDash = [string][char]0x2014

function Limit-Text([string]$Text, [int]$Max = 250) {
    # Python's text[:250]: names are capped at 250 characters in both editions.
    if ($null -eq $Text) { return '' }
    if ($Text.Length -gt $Max) { return $Text.Substring(0, $Max) }
    return $Text
}

function Get-NcmPolicyId($Benchmark) {
    # Same seed as the Python edition: the benchmark id, or the title when the
    # benchmark has no id. Builds before this one concatenated id + title.
    $key = $Benchmark.BenchmarkId; if (-not $key) { $key = $Benchmark.Title }
    return Get-DeterministicGuid ('stig2ncm-policy:' + $key)
}

function Get-ScmPolicyUniqueId($Benchmark) {
    $key = $Benchmark.BenchmarkId; if (-not $key) { $key = $Benchmark.Title }
    return Get-DeterministicGuid ('stig2ncm-scm:' + $key)
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
    'service ', 'no ', 'hostname ', 'enable ', 'archive', 'clock ', 'boot ')

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

function New-NcmRule($Rule, [string]$RuleGrouping, [string]$PatternMode) {
    $pattern = 'STIG-MANUAL-REVIEW-' + $Rule.VulnId
    $patternType = 'Like'
    $note = 'PATTERN NOT SET: this sentinel never matches, so the rule flags every ' +
            'node as a violation until you replace it with a real pattern for this check.'
    if ($PatternMode -eq 'heuristic' -and $Rule.CheckContent) {
        foreach ($line in ($Rule.CheckContent -split "`n")) {
            $t = $line.Trim()
            if (-not $t -or $t -match '[:?.]$') { continue }
            $lower = $t.ToLower()
            foreach ($tok in $script:ConfigTokens) {
                if ($lower.StartsWith($tok)) {
                    $pattern = $t
                    $note = 'DRAFT PATTERN extracted automatically from the STIG check ' +
                            'text ' + $script:EmDash + ' verify it before trusting this rule''s results.'
                    break
                }
            }
            if ($note.StartsWith('DRAFT')) { break }
        }
        if ($note.StartsWith('DRAFT') -and ($pattern.Contains('*') -or $pattern.Contains('?'))) {
            $patternType = 'Regex'
            $pattern = ConvertTo-EscapedRegex $pattern
            $note += ' Emitted as an escaped Regex rather than a Like pattern because ' +
                     'the extracted text contains * or ?, which a Like pattern only ' +
                     'treats as wildcards when the server''s ' +
                     'ComplianceRulesWildcardsEnabled advanced setting is on ' +
                     '(NCM 2023.1.1 and later; off by default).'
        }
    }
    $parts = New-Object System.Collections.ArrayList
    $ids = "$($Rule.VulnId) / $($Rule.RuleId) / STIG ID $($Rule.StigId)"
    if ($Rule.Ccis.Count -gt 0) { $ids += ' / ' + ($Rule.Ccis -join ', ') }
    [void]$parts.Add($ids); [void]$parts.Add($note)
    if ($Rule.Discussion) { [void]$parts.Add("Discussion:`n" + $Rule.Discussion) }
    if ($Rule.CheckContent) { [void]$parts.Add("Check:`n" + $Rule.CheckContent) }
    elseif ($Rule.OvalRef) {
        [void]$parts.Add('Machine check (SCAP edition): OVAL definition ' + $Rule.OvalRef +
            ' ' + $script:EmDash + ' no manual check text in this edition; the manual ' +
            'STIG for this product carries the prose.')
    }
    $name = "$($Rule.VulnId) [$($Rule.Severity)] $($Rule.Title)"
    if ($name.Length -gt 250) { $name = $name.Substring(0, 250) }
    $lvl = 1
    if ($script:SeverityToErrorLevel.ContainsKey($Rule.Severity)) {
        $lvl = $script:SeverityToErrorLevel[$Rule.Severity]
    }
    return [ordered]@{
        RuleId = Get-DeterministicGuid ('stig2ncm:' + $Rule.RuleId)  # matches the Python edition
        RuleName = $name
        Comments = ($parts -join "`n`n")
        Grouping = $RuleGrouping
        SimplePatternText = $pattern
        PatternType = $patternType
        PatternMustExist = $true
        AdvancedMode = $false
        MultiLineRulePatterns = @()
        ConfigBlockStart = ''
        ConfigBlockEnd = ''
        ConfigBlockPatternType = 'Like'
        ConfigBlockMustExist = $false
        IsConfigBlockPatternRegEx = $false
        ErrorLevel = $lvl
        RemediateScript = $Rule.FixText   # never auto-executed
        RemediateScriptType = 'CLI'
        ExecuteScriptAutomatically = $false
        ExecuteRemediationScriptPerBlock = $false
        ExecuteScriptInConfigMode = $false
        Owner = 'DISA STIG Conversion Tool'
    }
}

function New-NcmReports($Benchmarks, [string]$BaseName, [string]$Where,
                        [string]$PatternMode, [string]$Folder, [bool]$Enabled = $true,
                        [string]$ConfigTypes = 'Any') {
    # One report per benchmark (matching the console's own one-policy-per-report
    # exports): the router zip yields NDM (35 rules) and RTR (92 rules) reports.
    # $BaseName comes from Get-ReportBaseName, mirroring Python's `name`.
    if (-not $ConfigTypes) { $ConfigTypes = 'Any' }
    $reports = New-Object System.Collections.ArrayList
    foreach ($b in $Benchmarks) {
        $ruleGroup = $Folder
        if ($b.BenchmarkId) { $ruleGroup = "$Folder/$($b.BenchmarkId)" }
        $rules = @($b.Rules | ForEach-Object { New-NcmRule $_ $ruleGroup $PatternMode })
        $policy = [ordered]@{
            PolicyId = Get-NcmPolicyId $b
            PolicyName = Limit-Text "$($b.Title) V$($b.Version) ($($b.Release))"
            Comments = ("Imported by the DISA STIG Conversion Tool from $($b.Source) " +
                        "(benchmark $($b.BenchmarkId), status date $($b.StatusDate)).")
            Grouping = $Folder
            NodeSelectionString = New-NodeSelectionString $Where
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
            Name = Limit-Text $name
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
            "ReportStatus $($last.ReportStatus), ConfigTypes $ConfigTypes, grouping $ruleGroup")
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
            Add-El $x $re 'MultiLineRulePatterns' '' | Out-Null
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
                if ([int]$ch -lt 32) { [void]$sb.AppendFormat('\u{0:x4}', [int]$ch) }
                else { [void]$sb.Append($ch) }
            }
        }
    }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function ConvertTo-ScmPolicyYaml($Benchmark) {
    $name = Limit-Text "$($Benchmark.Title) V$($Benchmark.Version) ($($Benchmark.Release))"
    $uid = Get-ScmPolicyUniqueId $Benchmark
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
        [void]$lines.Add('- displayId: ' + (Y $r.VulnId))
        [void]$lines.Add('  uniqueId: ' + (Get-DeterministicGuid ('stig2ncm-scm-rule:' + $r.RuleId)))
        $title = $r.Title; if ($title.Length -gt 250) { $title = $title.Substring(0, 250) }
        [void]$lines.Add('  name: ' + (Y $title))
        [void]$lines.Add("  severity: $sev")
        [void]$lines.Add('  description: ' + (Y $r.Discussion))
        [void]$lines.Add('  remediationDescription: ' + (Y $r.FixText))
        [void]$lines.Add('  checkText: ' + (Y $check))
        # The probe runs as PowerShell on every assigned node: the id is validated
        # and the whole text is a single-quoted literal, so no STIG content can
        # expand ($(...), $var) or escape (backtick or ") inside the script source.
        $probeId = Get-ScmProbeId $r.VulnId $r.RuleId
        [void]$lines.Add('  condition: !matches')
        [void]$lines.Add('    expression: ' + (Y ($probeId + ' reviewed: True')))
        [void]$lines.Add('    source: !scm.powershell')
        [void]$lines.Add('      description: ' + (Y ('STIG ' + $r.StigId + ' manual-review attestation')))
        [void]$lines.Add('      script: ' + (Y ('Write-Host ' + (ConvertTo-PsSingleQuoted ($probeId + ' reviewed: False')))))
    }
    Write-ToolLog build info "SCM policy `"$name`" uniqueId ${uid}: $(@($Benchmark.Rules).Count) manual-review rule(s)"
    return ($lines -join "`n") + "`n"
}

# SCM policy output extension. SolarWinds' published policy files are plain
# .yaml and the docs name no dedicated extension, so .scm-policy.yaml is used.
# .scm-profile belongs to SCM collection-profile exports (UTF-16 JSON); older
# builds of this tool wrote policy YAML under it, which is still accepted.
$script:ScmPolicySuffix = '.scm-policy.yaml'
$script:LegacyScmPolicySuffix = '.scm-profile'
$script:ScmInputPattern = '\.(yaml|yml|scm-profile)$'

function Write-ScmPolicyFile($Benchmark, [string]$Folder) {
    $base = $Benchmark.BenchmarkId; if (-not $base) { $base = $Benchmark.Title }
    $out = Join-Path $Folder (Get-SafeFileName $base $script:ScmPolicySuffix)
    return Write-GeneratedFile $out (ConvertTo-ScmPolicyYaml $Benchmark)
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
                            [bool]$AllowInsecure, [string]$PinnedThumb) {
    if ($Password) {
        Register-Secret $Password
        # The Basic token carries the password too, so it is redacted as well.
        Register-Secret ([Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($User + ':' + $Password)))
    }
    $base = "https://${SwisServer}:${SwisPort}/SolarWinds/InformationService/v3/Json"
    $tls = 'verified against the system trust store'
    if ($PinnedThumb) { $tls = 'pinned server certificate' }
    elseif ($AllowInsecure) { $tls = 'NOT verified (-Insecure, lab only)' }
    $who = "user '$User' (basic auth)"
    if ($UseWindowsAuth) { $who = "the current Windows user '$([Environment]::UserName)' (Negotiate)" }
    Write-ToolLog swis info "SWIS endpoint $base as $who; TLS $tls"
    if ($AllowInsecure -and -not $PinnedThumb) { Write-ToolLog swis warn 'TLS verification is off for this session' }
    if ($AllowInsecure -and $PinnedThumb) { Write-ToolLog swis info '-Insecure is ignored: a pinned certificate is always checked' }
    return @{
        Base = $base
        User = $User; Password = $Password; WindowsAuth = $UseWindowsAuth
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
    try {
        $parsed = ConvertFrom-Json $Text
        if ($null -ne $parsed -and $parsed.PSObject.Properties['Message']) { return [string]$parsed.Message }
    } catch { }
    return $Text
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
    if (-not $Conn.WindowsAuth) {
        $token = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Conn.User + ':' + $Conn.Password))
        $message.Headers.Authorization = New-Object System.Net.Http.Headers.AuthenticationHeaderValue('Basic', $token)
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
        else {
            $token = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes(
                $Conn.User + ':' + $Conn.Password))
            $params.Headers = @{ Authorization = "Basic $token" }
        }
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
    return $t.Substring(0, $Width) + '...'
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

function Get-WireArgument([string]$Format, [string]$Kind, $Item, $IdList) {
    switch ($Format) {
        'json' {
            switch ($Kind) {
                'rule' { return $Item }
                'policy' {
                    $c = [ordered]@{} + $Item
                    $c.AssignedPolicyRules = @(); $c.AssignedRulesList = @($IdList); return $c
                }
                'report' {
                    $c = [ordered]@{} + $Item
                    $c.AssignedPolicies = @(); $c.AssignedPoliciesList = @($IdList); return $c
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
    $policies = Get-RowValue $Stored 'AssignedPolicies'
    $tree = New-Object System.Collections.ArrayList
    if ($null -eq $policies -or $policies -is [string]) {
        $listed = @(Get-RowValue $Stored 'AssignedPoliciesList' | Where-Object { $null -ne $_ })
        if ($listed.Count -gt 0) { return $null }
        return @{ Policies = $tree }
    }
    foreach ($p in @($policies)) {
        if (-not (Test-ToolObject $p)) { return $null }
        $names = New-Object System.Collections.ArrayList
        foreach ($r in @(Get-RowValue $p 'AssignedPolicyRules')) {
            if ($null -eq $r) { continue }
            if (-not (Test-ToolObject $r)) { return $null }
            [void]$names.Add([string](Get-RowValue $r 'RuleName'))
        }
        [void]$tree.Add([pscustomobject]@{ Policy = [string](Get-RowValue $p 'PolicyName'); Rules = [string[]]@($names) })
    }
    return @{ Policies = $tree }
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
    $format = $null; $firstId = $null
    $rejections = New-Object System.Collections.ArrayList
    foreach ($f in @('json', 'xml-dc', 'xml-plain')) {
        try {
            $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyRule' `
                @((Get-WireArgument $f 'rule' $probeRule $null))
            $firstId = Get-CleanId $result $probeRule.RuleId
            $format = $f
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

function Import-ScmPolicyYaml($Conn, [string]$Yaml, [scriptblock]$Log) {
    # SolarWinds rejects an import whose name OR uniqueId matches an existing
    # policy. Both are checked here because this tool derives the uniqueId
    # deterministically from the benchmark, so re-importing a STIG under a new
    # name still collides, and the server-side rejection is far less legible.
    $info = Get-ScmPolicyInfo $Yaml
    if (-not $info.IsPolicy) {
        throw ('[SCM] not an SCM compliance policy (expected a YAML document tagged !policy ' +
            'with pluginName: SCM); nothing was sent to ImportPolicy')
    }
    $name = $info.Name
    $uniqueId = $info.UniqueId
    $shownUid = $uniqueId; if (-not $shownUid) { $shownUid = '(none)' }
    Write-ToolLog scm info "SCM policy `"$name`" uniqueId $shownUid; checking for a name/uniqueId collision"

    $clauses = New-Object System.Collections.ArrayList
    $swqlParams = @{}
    if ($name) { [void]$clauses.Add('Name = @n'); $swqlParams['n'] = $name }
    if ($uniqueId) { [void]$clauses.Add('UniqueId = @u'); $swqlParams['u'] = $uniqueId }
    if ($clauses.Count -gt 0) {
        $existing = Invoke-SwisQuery $Conn ('SELECT PolicyID, Name, UniqueId, BuiltIn ' +
            'FROM Orion.PolicyEngine.Policy WHERE ' + ($clauses -join ' OR ')) $swqlParams
        if ($existing.Count -gt 0) {
            $why = if ($existing[0].Name -eq $name) { 'the same name' } else { 'the same uniqueId' }
            $msg = ("[SCM] a policy with $why already exists: ""$($existing[0].Name)"" " +
                "(PolicyID $($existing[0].PolicyID), UniqueId $($existing[0].UniqueId)); " +
                'refusing to duplicate. SolarWinds rejects an import that matches either field.')
            Write-ToolLog scm error $msg
            throw $msg
        }
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

function Import-ScmBenchmark($Conn, $Benchmark, [scriptblock]$Log) {
    $yaml = ConvertTo-ScmPolicyYaml $Benchmark
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
    if ($FilePath -match $script:ScmInputPattern) {
        [void](Read-ScmPolicyFile $FilePath $null)
        return 'SCM'
    }
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

function Resolve-NcmWhere($Benchmarks, [string]$SourcePath, [string]$Where) {
    # 'auto' (or empty) derives the scope from the detected vendor, as Python's
    # node_where_for does; anything else is used as given.
    if ($Where -and -not $Where.ToLower().StartsWith('auto') -and -not $Where.StartsWith('(auto')) {
        Write-ToolLog scope info "NCM node scope $Where (explicit -NodeWhere)"
        return $Where
    }
    $t = Resolve-StigTarget $Benchmarks (Split-Path -Leaf $SourcePath)
    if ($t[0] -eq 'network' -and $t[1]) {
        $w = "(Vendor = '$($t[1])')"
        Write-ToolLog scope info "NCM node scope $w (derived from vendor $($t[1]))"
        return $w
    }
    Write-ToolLog scope warn "no vendor identified; the node scope defaults to (Vendor = 'Cisco')"
    return "(Vendor = 'Cisco')"
}

# =========================================================================
# CLI driver
# =========================================================================
function New-CliConnection {
    # Shared by import, -Test and -Remove: password from $env:SWIS_PASSWORD or a
    # prompt (never a parameter), optional certificate pin, connection check.
    if (-not $Server) { throw 'pass -Server (and -Username, or -WindowsAuth)' }
    $pw = ''
    if (-not $WindowsAuth) {
        $pw = $env:SWIS_PASSWORD
        $source = 'prompted for'; if ($pw) { $source = 'from SWIS_PASSWORD' }
        Write-ToolLog swis info "connecting to ${Server}:$Port as user '$Username'; password $source"
        if (-not $pw) {
            $sec = Read-Host -Prompt "password for $Username" -AsSecureString
            $pw = [System.Runtime.InteropServices.Marshal]::PtrToStringUni(
                [System.Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($sec))
        }
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
    $conn = New-SwisConnection $Server $Port $Username $pw $WindowsAuth.IsPresent $Insecure.IsPresent $pin
    $status = Test-SwisConnection $conn
    Write-Host (Hide-Secrets $status.Detail)
    if ($status.Status -eq 'red') { throw $status.Detail }
    return $conn
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
    if ($found.Count -eq 0) { throw "no policy report named `"$Name`" on this server" }
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
    $where = Resolve-NcmWhere $benchmarks $SourcePath $NodeWhere
    $reports = New-NcmReports $benchmarks (Get-ReportBaseName $SourcePath $Name) $where $Mode $Grouping `
        (-not $ImportDisabled) $ConfigType
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

    if ($Convert) {
        foreach ($p in $Path) {
            $folder = Split-Path -Parent (Resolve-Path $p)
            if ($p -match $script:ScmInputPattern) {
                Write-Host "[SCM] $p is already an importable SCM policy - nothing to convert"
                Write-ToolLog scm info "$p is already an importable SCM policy - nothing to convert"
                continue
            }
            $benchmarks = Get-StigBenchmarks $p
            if ($module -eq 'SCM') {
                foreach ($b in $benchmarks) {
                    $out = Write-ScmPolicyFile $b $folder
                    Write-Host "[SCM] wrote $out - $($b.Rules.Count) rules"
                }
            } else {
                $where = Resolve-NcmWhere $benchmarks $p $NodeWhere
                $xmlWarning = Get-XmlConfigWarning $where
                if ($xmlWarning) { Write-Host $xmlWarning -ForegroundColor Yellow }
                $reports = New-NcmReports $benchmarks (Get-ReportBaseName $p $Name) $where $Mode `
                    $Grouping (-not $ImportDisabled) $ConfigType
                foreach ($r in $reports) {
                    $out = Write-ConsoleReportFile $r $folder
                    Write-Host "[NCM] wrote $out"
                }
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
            if ($p -match $script:ScmInputPattern) {
                $text = Read-ScmPolicyFile $p $log
                $r = Import-ScmPolicyYaml $conn $text $log
                Write-ToolLog scm info "imported SCM policy `"$($r.Name)`" (PolicyID $($r.PolicyId))"
                Write-Host "SUCCESS [SCM] imported policy `"$($r.Name)`" (PolicyID $($r.PolicyId))" -ForegroundColor Green
            } else {
                foreach ($b in (Get-StigBenchmarks $p)) {
                    $r = Import-ScmBenchmark $conn $b $log
                    Write-Host "SUCCESS [SCM] `"$($r.Name)`" (PolicyID $($r.PolicyId))" -ForegroundColor Green
                }
            }
        } else {
            $benchmarks = Get-StigBenchmarks $p
            $where = Resolve-NcmWhere $benchmarks $p $NodeWhere
            $xmlWarning = Get-XmlConfigWarning $where
            if ($xmlWarning) { Write-Host $xmlWarning -ForegroundColor Yellow }
            $reports = New-NcmReports $benchmarks (Get-ReportBaseName $p $Name) $where $Mode $Grouping `
                (-not $ImportDisabled) $ConfigType
            [void](Invoke-NcmPreflight $conn $log)
            foreach ($r in $reports) {
                $existing = @(Invoke-SwisQuery $conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = $r.Name })
                if ($existing.Count -gt 0) { Write-ToolLog import error "name collision: report `"$($r.Name)`" already exists; nothing was imported"; throw "[NCM] a report named `"$($r.Name)`" already exists - rename with -Name, delete it with -Remove, or remove it in the console; this tool never overwrites" }
            }
            $run = Import-NcmReports $conn $reports $log (-not $NoRollback)
            foreach ($i in $run.Imported) {
                Write-Host "SUCCESS [NCM] `"$($i.Report.Name)`" - $($i.Rules) rules ($($i.ReportId))" -ForegroundColor Green
            }
            # Reports verified before a failure still get caching / disabling. A
            # refused StartCaching / UpdateReportStatus does not stop the run: the
            # console files that are due below are still written.
            $confirmed = Complete-NcmImport $conn @($run.Imported | ForEach-Object { $_.ReportId }) `
                $ImportDisabled.IsPresent $NoCache.IsPresent $log
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
    $form.Size = New-Object System.Drawing.Size(760, 730)
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
        New-SwisConnection $serverBox.Text.Trim() ([int]$portBox.Text) $userBox.Text.Trim() `
            $passBox.Text $winAuth.Checked (-not $verifyTls.Checked) $state.Pinned
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
                    if ($f -match $script:ScmInputPattern) {
                        if ($Offline) { Add-Summary ($prefix + (Split-Path -Leaf $f) + ' is already importable - nothing to convert') $null; $ok++; continue }
                        $text = Read-ScmPolicyFile $f $logBlock
                        $scmResult = Import-ScmPolicyYaml $conn $text $logBlock
                        $policyId = $scmResult.PolicyId
                        Add-Summary ("SUCCESS " + $prefix + (Split-Path -Leaf $f) + " (PolicyID $policyId)") ([System.Drawing.Color]::Green); $ok++
                    } else {
                        foreach ($b in (Get-StigBenchmarks $f)) {
                            if ($Offline) {
                                $out = Write-ScmPolicyFile $b (Split-Path -Parent $f)
                                Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out)) ([System.Drawing.Color]::Green)
                            } else {
                                $r = Import-ScmBenchmark $conn $b $logBlock
                                Add-Summary ("SUCCESS " + $prefix + '"' + $r.Name + '"') ([System.Drawing.Color]::Green)
                            }
                        }
                        $ok++
                    }
                } else {
                    $benchmarks = Get-StigBenchmarks $f
                    $where = Resolve-NcmWhere $benchmarks $f $whereBox.Text.Trim()
                    $xmlWarning = Get-XmlConfigWarning $where
                    if ($xmlWarning) { Add-Summary $xmlWarning $yellow; Show-Issue }
                    $reportEnabled = -not $importDisabledBox.Checked
                    $reports = New-NcmReports $benchmarks (Get-ReportBaseName $f '') $where 'manual' 'DISA STIG' $reportEnabled
                    if ($Offline) {
                        foreach ($r in $reports) {
                            $out = Write-ConsoleReportFile $r (Split-Path -Parent $f)
                            Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out)) ([System.Drawing.Color]::Green)
                        }
                        $ok++
                    } else {
                        [void](Invoke-NcmPreflight $conn $logBlock)
                        $run = Import-NcmReports $conn $reports $logBlock $true
                        foreach ($i in $run.Imported) {
                            Add-Summary ("SUCCESS " + $prefix + '"' + $i.Report.Name + '" - ' + $i.Rules + ' rules') ([System.Drawing.Color]::Green)
                        }
                        # Reports verified before a failure are still cached or disabled.
                        $confirmed = Complete-NcmImport $conn @($run.Imported | ForEach-Object { $_.ReportId }) `
                            (-not $reportEnabled) $false $logBlock
                        if (-not $confirmed) {
                            $state = 'cached (StartCaching)'; if (-not $reportEnabled) { $state = 'Disabled' }
                            Add-Summary ($prefix + "the imported reports could not be confirmed as $state; see the detailed log") $yellow
                            Show-Issue
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
    # every later line are redacted even when the password was never used.
    Register-Secret $env:SWIS_PASSWORD
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

if ($Remove) {
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
