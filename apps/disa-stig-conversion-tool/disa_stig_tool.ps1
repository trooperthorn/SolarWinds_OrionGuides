<#
.SYNOPSIS
DISA STIG Conversion Tool — PowerShell edition.

.DESCRIPTION
Converts and imports DISA STIG content into SolarWinds NCM compliance policy
reports and Server Configuration Monitor compliance policies over the SWIS API,
or converts to console-importable files with no server connection at all.

Built-in only: Windows PowerShell 5.1+ / PowerShell 7+, .NET framework classes,
no modules (SwisPowerShell and orionsdk are NOT required), no gallery installs.
All code is visible in this one file for audit; the SWIS calls executed are
documented in README.md next to it.

Security rules: TLS verification on by default (the stock self-signed
'SolarWinds-Orion' certificate is trusted by explicit fetch-and-pin);
credentials live in memory only and are redacted from every log line; empty
read-backs report "No Data Returned"; SCM configuration content
(Orion.SCM.Results.ElementContents) is never read.

.EXAMPLE
.\disa_stig_tool.ps1
Opens the GUI (Windows).

.EXAMPLE
.\disa_stig_tool.ps1 -Convert -Path .\U_Cisco_IOS_Router_Y26M07_STIG.zip
Local file conversion only — writes .ncm-report.xml / .scm-profile files.

.EXAMPLE
.\disa_stig_tool.ps1 -Path .\stig.zip -Server orion.example.com -Username admin
Imports over SWIS (password prompted, or set $env:SWIS_PASSWORD).
#>
[CmdletBinding()]
param(
    [string[]]$Path,
    [switch]$Convert,
    [string]$Server,
    [int]$Port = 17774,
    [string]$Username,
    [switch]$WindowsAuth,
    [switch]$Insecure,
    [switch]$PinServerCert,
    [ValidateSet('auto', 'network', 'server')][string]$Target = 'auto',
    [string]$NodeWhere = 'auto',
    [ValidateSet('manual', 'heuristic')][string]$Mode = 'manual',
    [string]$Grouping = 'DISA STIG',
    [switch]$NoGui
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

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

function ConvertFrom-BenchmarkXml([byte[]]$Bytes, [string]$SourceName) {
    # Returns a list of benchmark hashtables; empty when the XML is not XCCDF.
    $doc = New-Object System.Xml.XmlDocument
    try { $doc.LoadXml([System.Text.Encoding]::UTF8.GetString($Bytes).TrimStart([char]0xFEFF)) }
    catch {
        try {
            $ms = New-Object System.IO.MemoryStream(, $Bytes); $doc.Load($ms)
        } catch { return @() }
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
    return @($found)
}

function Read-OneBenchmark($Root, [string]$Ns, [string]$SourceName) {
    $release = ''
    foreach ($pt in $Root.ChildNodes) {
        if ($pt.LocalName -eq 'plain-text' -and $pt.GetAttribute('id') -eq 'release-info') {
            $release = ('' + $pt.InnerText).Trim()
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
    return @{
        Source      = $SourceName
        BenchmarkId = Remove-ScapPrefix $Root.GetAttribute('id')
        Title       = Get-XmlText $Root 'title' $Ns
        Version     = Get-XmlText $Root 'version' $Ns
        Release     = $release
        Edition     = $edition
        Rules       = @($rules)
    }
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
        foreach ($f in Get-ChildItem -LiteralPath $SourcePath -Recurse -Filter '*.xml') {
            & $addXml ([System.IO.File]::ReadAllBytes($f.FullName)) $f.Name
        }
    } elseif ($SourcePath -match '\.(zip)$') {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($SourcePath)
        try {
            foreach ($entry in ($zip.Entries | Sort-Object FullName)) {
                if ($entry.Name -match '\.xml$') {
                    $ms = New-Object System.IO.MemoryStream
                    $s = $entry.Open(); $s.CopyTo($ms); $s.Dispose()
                    & $addXml $ms.ToArray() $entry.Name
                } elseif ($entry.Name -match '\.zip$') {
                    $ms = New-Object System.IO.MemoryStream
                    $s = $entry.Open(); $s.CopyTo($ms); $s.Dispose()
                    $ms.Position = 0
                    $inner = New-Object System.IO.Compression.ZipArchive($ms)
                    foreach ($ie in ($inner.Entries | Sort-Object FullName)) {
                        if ($ie.Name -match '\.xml$') {
                            $ims = New-Object System.IO.MemoryStream
                            $is2 = $ie.Open(); $is2.CopyTo($ims); $is2.Dispose()
                            & $addXml $ims.ToArray() $ie.Name
                        }
                    }
                }
            }
        } finally { $zip.Dispose() }
    } elseif ($SourcePath -match '\.xml$') {
        & $addXml ([System.IO.File]::ReadAllBytes($SourcePath)) (Split-Path -Leaf $SourcePath)
    } elseif ($SourcePath -match '\.xsl$') {
        foreach ($f in Get-ChildItem -LiteralPath (Split-Path -Parent $SourcePath) -Filter '*.xml') {
            & $addXml ([System.IO.File]::ReadAllBytes($f.FullName)) $f.Name
        }
    } else {
        throw "$SourcePath is not a zip, directory, or XCCDF .xml file"
    }
    # dedupe: manual edition wins over scap for the same benchmark id
    $byId = [ordered]@{}
    foreach ($b in $benchmarks) {
        $key = $b.BenchmarkId; if (-not $key) { $key = $b.Title }
        if (-not $byId.Contains($key) -or
            ($byId[$key].Edition -eq 'scap' -and $b.Edition -eq 'manual')) {
            $byId[$key] = $b
        }
    }
    if ($byId.Count -eq 0) { throw "$SourcePath contains no XCCDF benchmark" }
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
        if ($text.Contains($kw)) { return @('server', $script:ServerOses[$kw]) }
    }
    $vendor = ''
    $matched = $false
    foreach ($kw in $script:NetworkVendors.Keys) {
        if ($text.Contains($kw)) {
            $matched = $true
            if ($script:NetworkVendors[$kw]) { $vendor = $script:NetworkVendors[$kw]; break }
        }
    }
    if ($matched) { return @('network', $vendor) }
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
    # XML>SQL:Where (…) — bare column names (Vendor, not Nodes.Vendor).
    $w = ($Where -replace '\bNodes\.', '').Trim()
    if (-not $w.StartsWith('(')) { $w = "($w)" }
    $criteria = ''
    $m = [regex]::Match($w, "Vendor\s*(=|LIKE)\s*'%?([^%']+)%?'",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if ($m.Success) {
        $vendor = $m.Groups[2].Value
        $id = Get-DeterministicGuid ("stig2ncm-criteria:" + $vendor)
        $criteria = @"
<?xml version="1.0" encoding="utf-16"?>
<ArrayOfWebSelectionCriteria xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <WebSelectionCriteria>
    <Id>$id</Id>
    <LogicalCondition />
    <SelectedColumn>Vendor</SelectedColumn>
    <MatchType>=</MatchType>
    <SelectedValue>$vendor</SelectedValue>
  </WebSelectionCriteria>
</ArrayOfWebSelectionCriteria>
"@.Trim()
    }
    return "WebCriteria:${criteria}SQL:Where $w "
}

$script:SeverityToErrorLevel = @{ high = 2; medium = 1; low = 0 }
$script:ConfigTokens = @('aaa ', 'ip ', 'ipv6 ', 'line ', 'snmp-server ', 'ntp ', 'logging ',
    'login ', 'banner ', 'crypto ', 'interface ', 'router ', 'access-list ', 'username ',
    'service ', 'no ', 'hostname ', 'enable ', 'archive', 'clock ', 'boot ')

function New-NcmRule($Rule, [string]$RuleGrouping, [string]$PatternMode) {
    $pattern = 'STIG-MANUAL-REVIEW-' + $Rule.VulnId
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
                            'text - verify it before trusting this rule''s results.'
                    break
                }
            }
            if ($note.StartsWith('DRAFT')) { break }
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
            ' - no manual check text in this edition.')
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
        PatternType = 'Like'
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
                        [string]$PatternMode, [string]$Folder) {
    # One report per benchmark (matching the console's own one-policy-per-report
    # exports): the router zip yields NDM (35 rules) and RTR (92 rules) reports.
    $reports = New-Object System.Collections.ArrayList
    foreach ($b in $Benchmarks) {
        $ruleGroup = $Folder
        if ($b.BenchmarkId) { $ruleGroup = "$Folder/$($b.BenchmarkId)" }
        $rules = @($b.Rules | ForEach-Object { New-NcmRule $_ $ruleGroup $PatternMode })
        $policy = [ordered]@{
            PolicyId = Get-DeterministicGuid ('stig2ncm-policy:' + $b.BenchmarkId + $b.Title)
            PolicyName = "$($b.Title) V$($b.Version) ($($b.Release))"
            Comments = "Imported by the DISA STIG Conversion Tool from $($b.Source)."
            Grouping = $Folder
            NodeSelectionString = New-NodeSelectionString $Where
            ConfigTypes = 'Any'
            AssignedPolicyRules = $rules
            AssignedRulesList = @($rules | ForEach-Object { $_.RuleId })
        }
        $name = $b.Title
        if ($BaseName) { $name = "$BaseName - $($b.BenchmarkId)" }
        [void]$reports.Add([ordered]@{
            ID = [guid]::NewGuid().ToString()
            Name = $name
            Comments = "DISA STIG imported by the DISA STIG Conversion Tool from $($b.Source) ($($b.Release))."
            Group = $Folder
            ShowSummaryFlag = $true
            ShowRulesWithoutViolationFlag = $true
            AssignedPolicies = @($policy)
            AssignedPoliciesList = @($policy.PolicyId)
            ReportStatus = 'Enabled'
        })
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
    $name = ($Report.Name -replace '[^\w.-]+', '_') + '.ncm-report.xml'
    $out = Join-Path $Folder $name
    $body = '<?xml version="1.0" encoding="utf-16"?>' + "`r`n" +
            ((ConvertTo-ConsoleReportXml $Report) -replace "(?<!`r)`n", "`r`n")
    [System.IO.File]::WriteAllText($out, $body, (New-Object System.Text.UTF8Encoding($false)))
    return $out
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
        switch ($ch) {
            '"'  { [void]$sb.Append('\"') }
            '\'  { [void]$sb.Append('\\') }
            "`n" { [void]$sb.Append('\n') }
            "`r" { [void]$sb.Append('\r') }
            "`t" { [void]$sb.Append('\t') }
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
    $name = "$($Benchmark.Title) V$($Benchmark.Version) ($($Benchmark.Release))"
    $uid = Get-DeterministicGuid ('stig2ncm-scm:' + $Benchmark.BenchmarkId + $Benchmark.Title)
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
            $check = "Machine check (SCAP edition): OVAL definition $($r.OvalRef)."
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
        [void]$lines.Add('  condition: !matches')
        [void]$lines.Add('    expression: ' + (Y ($r.VulnId + ' reviewed: True')))
        [void]$lines.Add('    source: !scm.powershell')
        [void]$lines.Add('      description: ' + (Y ('STIG ' + $r.StigId + ' manual-review attestation')))
        [void]$lines.Add('      script: ' + (Y ('Write-Host "' + $r.VulnId + ' reviewed: False"')))
    }
    return ($lines -join "`n") + "`n"
}

function Write-ScmProfileFile($Benchmark, [string]$Folder) {
    $base = $Benchmark.BenchmarkId; if (-not $base) { $base = $Benchmark.Title }
    $out = Join-Path $Folder (($base -replace '[^\w.-]+', '_') + '.scm-profile')
    [System.IO.File]::WriteAllText($out, (ConvertTo-ScmPolicyYaml $Benchmark),
        (New-Object System.Text.UTF8Encoding($false)))
    return $out
}

# =========================================================================
# SWIS client - built-in Invoke-RestMethod, basic or Windows auth
# =========================================================================
function New-SwisConnection([string]$SwisServer, [int]$SwisPort, [string]$User,
                            [string]$Password, [bool]$UseWindowsAuth,
                            [bool]$AllowInsecure, [string]$PinnedThumb) {
    if ($Password) { Register-Secret $Password }
    return @{
        Base = "https://${SwisServer}:${SwisPort}/SolarWinds/InformationService/v3/Json"
        User = $User; Password = $Password; WindowsAuth = $UseWindowsAuth
        Insecure = $AllowInsecure; PinnedThumb = $PinnedThumb
    }
}

function Get-ServerCertThumbprint([string]$SwisServer, [int]$SwisPort) {
    # Fetch the certificate SWIS presents (the stock self-signed
    # 'SolarWinds-Orion' one) for explicit trust. Returns SHA-256 hex.
    $client = New-Object System.Net.Sockets.TcpClient($SwisServer, $SwisPort)
    try {
        $ssl = New-Object System.Net.Security.SslStream($client.GetStream(), $false,
            { param($s, $c, $ch, $e) $true })
        $ssl.AuthenticateAsClient($SwisServer)
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
        $thumb = [BitConverter]::ToString(
            [System.Security.Cryptography.SHA256]::Create().ComputeHash($cert.RawData)) -replace '-', ''
        $stock = $cert.Subject -match 'SolarWinds-Orion'
        $ssl.Dispose()
        return @{ Thumbprint = $thumb; Subject = $cert.Subject; Stock = $stock }
    } finally { $client.Dispose() }
}

function Invoke-SwisRest($Conn, [string]$Method, [string]$RestPath, $Body) {
    $params = @{ Method = $Method; Uri = ($Conn.Base + '/' + $RestPath)
                 ContentType = 'application/json'; TimeoutSec = 300 }
    if ($Conn.WindowsAuth) { $params.UseDefaultCredentials = $true }
    else {
        $token = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes(
            $Conn.User + ':' + $Conn.Password))
        $params.Headers = @{ Authorization = "Basic $token" }
    }
    if ($null -ne $Body) { $params.Body = (ConvertTo-Json $Body -Depth 20 -Compress) }
    $skipOk = (Get-Command Invoke-RestMethod).Parameters.ContainsKey('SkipCertificateCheck')
    if ($Conn.Insecure -or $Conn.PinnedThumb) {
        if ($skipOk) { $params.SkipCertificateCheck = $true }  # pin was verified at fetch
        else {
            # Windows PowerShell 5.1: per-process callback honouring the pin
            $pin = $Conn.PinnedThumb
            [System.Net.ServicePointManager]::ServerCertificateValidationCallback = {
                param($s, $cert, $chain, $errors)
                if ($errors -eq [System.Net.Security.SslPolicyErrors]::None) { return $true }
                if (-not $pin) { return $true }  # explicit -Insecure
                $c2 = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cert)
                $t = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash($c2.RawData)) -replace '-', ''
                return $t -eq $pin
            }.GetNewClosure()
        }
    }
    try { return Invoke-RestMethod @params }
    catch {
        $detail = $_.Exception.Message
        try {
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                $parsed = ConvertFrom-Json $_.ErrorDetails.Message
                if ($parsed.PSObject.Properties['Message']) { $detail = $parsed.Message }
            }
        } catch { }
        $code = ''
        try { $code = [int]$_.Exception.Response.StatusCode } catch { }
        throw ("SWIS HTTP $code from $RestPath`n" + $detail)
    }
}

function Invoke-SwisQuery($Conn, [string]$Swql, $Parameters) {
    $body = @{ query = $Swql }
    if ($Parameters) { $body.parameters = $Parameters }
    $result = Invoke-SwisRest $Conn 'Post' 'Query' $body
    if ($null -eq $result) { return @() }
    return @($result.results)
}

function Invoke-SwisVerbCall($Conn, [string]$Entity, [string]$SwisVerb, [array]$Arguments) {
    return Invoke-SwisRest $Conn 'Post' "Invoke/$Entity/$SwisVerb" $Arguments
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

function Import-NcmReport($Conn, $Report, [scriptblock]$Log) {
    # Probe with one cheap AddPolicyRule per wire format (JSON object,
    # DataContract XML, plain XML), then run bottom-up in the accepted format.
    # Falls back to a nested console-format AddPolicyReport; if everything is
    # refused, throws with WireFailure=$true so the caller writes console files.
    $labels = @{ 'json' = 'JSON contract objects'; 'xml-dc' = 'DataContract XML strings'
                 'xml-plain' = 'plain XML strings (no namespace)' }
    $probeRule = $Report.AssignedPolicies[0].AssignedPolicyRules[0]
    $format = $null; $firstId = $null
    $rejections = New-Object System.Collections.ArrayList
    foreach ($f in @('json', 'xml-dc', 'xml-plain')) {
        try {
            $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyRule' `
                @((Get-WireArgument $f 'rule' $probeRule $null))
            $firstId = Get-CleanId $result $probeRule.RuleId
            $format = $f
            & $Log "[NCM] server accepts $($labels[$f])"
            break
        } catch {
            if ($_.Exception.Message -notmatch 'HTTP 400') { throw }
            [void]$rejections.Add("$($labels[$f]): rejected")
            & $Log "[NCM] server rejected $($labels[$f]); trying the next wire format"
        }
    }
    if ($format) {
        $policyIds = New-Object System.Collections.ArrayList
        $total = 0
        $first = $true
        foreach ($p in $Report.AssignedPolicies) {
            $ruleIds = New-Object System.Collections.ArrayList
            $i = 0
            foreach ($r in $p.AssignedPolicyRules) {
                $i++
                if ($first) { [void]$ruleIds.Add($firstId); $first = $false; continue }
                $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyRule' `
                    @((Get-WireArgument $format 'rule' $r $null))
                [void]$ruleIds.Add((Get-CleanId $result $r.RuleId))
                if ($i % 25 -eq 0) { & $Log "[NCM]   $i/$($p.AssignedPolicyRules.Count) rules created" }
            }
            $total += $ruleIds.Count
            $result = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicy' `
                @((Get-WireArgument $format 'policy' $p @($ruleIds)), $false)
            [void]$policyIds.Add((Get-CleanId $result $p.PolicyId))
            & $Log "[NCM] created policy `"$($p.PolicyName)`" with $($ruleIds.Count) rules"
        }
        $reportId = Get-CleanId (Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyReport' `
            @((Get-WireArgument $format 'report' $Report @($policyIds)), $false)) ''
        if (-not $reportId) { throw '[NCM] No Data Returned from AddPolicyReport - no report id' }
        return Test-NcmImport $Conn $reportId $policyIds.Count $total $Log
    }
    & $Log '[NCM] no per-item wire format accepted; trying one nested console-format AddPolicyReport'
    try {
        $reportId = Get-CleanId (Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'AddPolicyReport' `
            @((ConvertTo-ConsoleReportXml $Report), $true)) ''
        if ($reportId) {
            $n = ($Report.AssignedPolicies | ForEach-Object { $_.AssignedPolicyRules.Count } |
                  Measure-Object -Sum).Sum
            return Test-NcmImport $Conn $reportId $Report.AssignedPolicies.Count $n $Log
        }
        [void]$rejections.Add('console-format XML: no report id returned')
    } catch {
        if ($_.Exception.Message -notmatch 'HTTP 400') { throw }
        [void]$rejections.Add('console-format XML: rejected')
    }
    $err = New-Object System.Exception ('[NCM] this server accepted none of the wire formats: ' +
        ($rejections -join '; ') + '. Console-importable files will be written instead - ' +
        'import them under Compliance -> Manage Policy Reports -> Import.')
    $err.Data['WireFailure'] = $true
    throw $err
}

function Test-NcmImport($Conn, [string]$ReportId, [int]$ExpectedPolicies,
                        [int]$ExpectedRules, [scriptblock]$Log) {
    $stored = Invoke-SwisVerbCall $Conn 'Cirrus.PolicyReports' 'GetPolicyReport' @($ReportId, $true)
    if ($null -eq $stored) {
        throw "[NCM] No Data Returned from GetPolicyReport for report $ReportId - the import cannot be confirmed"
    }
    $pols = @(); if ($stored.PSObject.Properties['AssignedPolicies'] -and $stored.AssignedPolicies) {
        $pols = @($stored.AssignedPolicies) }
    $ruleCount = 0
    foreach ($p in $pols) {
        if ($p.PSObject.Properties['AssignedPolicyRules'] -and $p.AssignedPolicyRules) {
            $ruleCount += @($p.AssignedPolicyRules).Count
        }
    }
    if ($pols.Count -eq 0 -or $ruleCount -eq 0) {
        throw "[NCM] verification failed: report $ReportId was created but holds $($pols.Count) policies and $ruleCount rules (expected $ExpectedPolicies and $ExpectedRules)"
    }
    & $Log "[NCM] verified: report holds $($pols.Count) policies and $ruleCount rules"
    return @{ ReportId = $ReportId; Policies = $pols.Count; Rules = $ruleCount }
}

function Import-ScmBenchmark($Conn, $Benchmark, [scriptblock]$Log) {
    $yaml = ConvertTo-ScmPolicyYaml $Benchmark
    $name = "$($Benchmark.Title) V$($Benchmark.Version) ($($Benchmark.Release))"
    $existing = Invoke-SwisQuery $Conn `
        'SELECT PolicyID FROM Orion.PolicyEngine.Policy WHERE Name = @n' @{ n = $name }
    if ($existing.Count -gt 0) {
        throw "[SCM] a policy named `"$name`" already exists (PolicyID $($existing[0].PolicyID)); refusing to duplicate"
    }
    $policyId = Invoke-SwisVerbCall $Conn 'Orion.PolicyEngine.Policy' 'ImportPolicy' @($yaml)
    if ($null -eq $policyId) {
        throw '[SCM] No Data Returned from Orion.PolicyEngine.Policy.ImportPolicy - the policy was not created'
    }
    & $Log "[SCM] imported policy `"$name`" (PolicyID $policyId) - $($Benchmark.Rules.Count) manual-review rules"
    return @{ PolicyId = $policyId; Name = $name; Rules = $Benchmark.Rules.Count }
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
function Get-FileModule([string]$FilePath) {
    if ($FilePath -match '\.(yaml|yml|scm-profile)$') { return 'SCM' }
    $benchmarks = Get-StigBenchmarks $FilePath
    $t = Resolve-StigTarget $benchmarks (Split-Path -Leaf $FilePath)
    if ($t[0] -eq 'server') { return 'SCM' }
    return 'NCM'
}

# =========================================================================
# CLI driver
# =========================================================================
function Invoke-CliRun {
    if ($Path.Count -gt $script:MaxZipFiles) {
        throw "up to $($script:MaxZipFiles) files per run"
    }
    foreach ($p in $Path) {
        if (-not (Test-Path -LiteralPath $p)) {
            throw ("file not found: $p`n" +
                   "Run with no arguments to open the GUI, or:`n" +
                   "  -Convert -Path <files>                Local File Conversion Only`n" +
                   "  -Server <host> -Username <u> -Path <files>   import over SWIS")
        }
    }
    # module lock across the batch
    $modules = @($Path | ForEach-Object { Get-FileModule $_ } | Sort-Object -Unique)
    if ($modules.Count -gt 1) {
        throw "a run imports into one module only - this selection mixes NCM and SCM files; split it into two runs"
    }
    $module = $modules[0]
    Write-Host "module for this run: $module"

    if ($Convert) {
        foreach ($p in $Path) {
            $folder = Split-Path -Parent (Resolve-Path $p)
            if ($p -match '\.(yaml|yml|scm-profile)$') {
                Write-Host "[SCM] $p is already an importable SCM policy - nothing to convert"
                continue
            }
            $benchmarks = Get-StigBenchmarks $p
            if ($module -eq 'SCM') {
                foreach ($b in $benchmarks) {
                    $out = Write-ScmProfileFile $b $folder
                    Write-Host "[SCM] wrote $out - $($b.Rules.Count) rules"
                }
            } else {
                $t = Resolve-StigTarget $benchmarks (Split-Path -Leaf $p)
                $where = $NodeWhere
                if ($where -eq 'auto') {
                    $where = "(Vendor = 'Cisco')"
                    if ($t[1]) { $where = "(Vendor = '$($t[1])')" }
                }
                $base = [System.IO.Path]::GetFileNameWithoutExtension($p)
                foreach ($r in (New-NcmReports $benchmarks $base $where $Mode $Grouping)) {
                    $out = Write-ConsoleReportFile $r $folder
                    Write-Host "[NCM] wrote $out"
                }
            }
        }
        return
    }

    if (-not $Server) { throw 'pass -Server (and -Username, or -WindowsAuth) to import, or -Convert for local file conversion only' }
    $pw = ''
    if (-not $WindowsAuth) {
        $pw = $env:SWIS_PASSWORD
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
        Write-Host "pinned the server certificate - SHA-256 $($info.Thumbprint)$stockNote"
    }
    $conn = New-SwisConnection $Server $Port $Username $pw $WindowsAuth.IsPresent $Insecure.IsPresent $pin
    $log = { param($m) Write-Host (Hide-Secrets $m) }

    $status = Test-SwisConnection $conn
    Write-Host (Hide-Secrets $status.Detail)
    if ($status.Status -eq 'red') { throw $status.Detail }

    foreach ($p in $Path) {
        if ($module -eq 'SCM') {
            if ($p -match '\.(yaml|yml|scm-profile)$') {
                $text = [System.IO.File]::ReadAllText($p)
                $m = [regex]::Match($text, '(?m)^name:\s*(.+)$')
                $name = ''; if ($m.Success) { $name = $m.Groups[1].Value.Trim().Trim('"', "'") }
                $existing = Invoke-SwisQuery $conn 'SELECT PolicyID FROM Orion.PolicyEngine.Policy WHERE Name = @n' @{ n = $name }
                if ($existing.Count -gt 0) { throw "[SCM] a policy named `"$name`" already exists" }
                $policyId = Invoke-SwisVerbCall $conn 'Orion.PolicyEngine.Policy' 'ImportPolicy' @($text)
                if ($null -eq $policyId) { throw '[SCM] No Data Returned from ImportPolicy' }
                Write-Host "SUCCESS [SCM] imported policy `"$name`" (PolicyID $policyId)" -ForegroundColor Green
            } else {
                foreach ($b in (Get-StigBenchmarks $p)) {
                    $r = Import-ScmBenchmark $conn $b $log
                    Write-Host "SUCCESS [SCM] `"$($r.Name)`" (PolicyID $($r.PolicyId))" -ForegroundColor Green
                }
            }
        } else {
            $benchmarks = Get-StigBenchmarks $p
            $t = Resolve-StigTarget $benchmarks (Split-Path -Leaf $p)
            $where = $NodeWhere
            if ($where -eq 'auto') {
                $where = "(Vendor = 'Cisco')"
                if ($t[1]) { $where = "(Vendor = '$($t[1])')" }
            }
            $base = [System.IO.Path]::GetFileNameWithoutExtension($p)
            $reports = New-NcmReports $benchmarks $base $where $Mode $Grouping
            $newIds = New-Object System.Collections.ArrayList
            foreach ($r in $reports) {
                $existing = Invoke-SwisQuery $conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = $r.Name }
                if ($existing.Count -gt 0) { throw "[NCM] a report named `"$($r.Name)`" already exists - delete or rename it first" }
            }
            foreach ($r in $reports) {
                try {
                    $res = Import-NcmReport $conn $r $log
                    [void]$newIds.Add($res.ReportId)
                    Write-Host "SUCCESS [NCM] `"$($r.Name)`" - $($res.Rules) rules ($($res.ReportId))" -ForegroundColor Green
                } catch {
                    if ($_.Exception.Data['WireFailure']) {
                        Write-Host (Hide-Secrets $_.Exception.Message) -ForegroundColor Yellow
                        $folder = Split-Path -Parent (Resolve-Path $p)
                        foreach ($rep in $reports) {
                            Write-Host ("[NCM] wrote " + (Write-ConsoleReportFile $rep $folder))
                        }
                        break
                    }
                    throw
                }
            }
            if ($newIds.Count -gt 0) {
                [void](Invoke-SwisVerbCall $conn 'Cirrus.PolicyReports' 'StartCaching' @(, @($newIds)))
                Write-Host "[NCM] compliance caching started for $($newIds.Count) report(s)"
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
    if ($gate.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return }

    # ---- main window --------------------------------------------------------
    $green  = [System.Drawing.Color]::FromArgb(198, 239, 206)
    $yellow = [System.Drawing.Color]::FromArgb(255, 235, 156)
    $red    = [System.Drawing.Color]::FromArgb(255, 199, 206)
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'DISA STIG Conversion Tool'
    $form.Size = New-Object System.Drawing.Size(760, 700)
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
    $script:y += 34

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
    $detail = & $mk (New-Object System.Windows.Forms.TextBox) 12 718 220
    $detail.Multiline = $true; $detail.ScrollBars = 'Vertical'; $detail.ReadOnly = $true
    $detail.Visible = $false

    $state = @{ Pinned = $null; Module = $null }
    function Add-Summary([string]$Text, $Color) {
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
        $dlg.Filter = 'STIG content|*.zip;*.xml;*.xsl;*.yaml;*.yml;*.scm-profile|All files|*.*'
        if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return }
        foreach ($f in $dlg.FileNames) {
            if ($fileList.Items.Count -ge $script:MaxZipFiles) {
                Add-Summary "at most $($script:MaxZipFiles) files per batch" $yellow; break
            }
            try { $m = Get-FileModule $f } catch { Add-Summary ("skipped " + $f + ": " + $_.Exception.Message) $red; continue }
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
        $ok = 0; $fail = 0
        $conn = $null
        if (-not $Offline) {
            try { $conn = New-GuiConnection } catch { Add-Summary $_.Exception.Message $red; $btn.BackColor = $red; return }
        }
        foreach ($f in @($fileList.Items)) {
            $prefix = '[' + $state.Module + '] '
            try {
                if ($state.Module -eq 'SCM') {
                    if ($f -match '\.(yaml|yml|scm-profile)$') {
                        if ($Offline) { Add-Summary ($prefix + (Split-Path -Leaf $f) + ' is already importable - nothing to convert') $null; $ok++; continue }
                        $text = [System.IO.File]::ReadAllText($f)
                        $policyId = Invoke-SwisVerbCall $conn 'Orion.PolicyEngine.Policy' 'ImportPolicy' @($text)
                        if ($null -eq $policyId) { throw ($prefix + 'No Data Returned from ImportPolicy') }
                        Add-Summary ("SUCCESS " + $prefix + (Split-Path -Leaf $f) + " (PolicyID $policyId)") ([System.Drawing.Color]::Green); $ok++
                    } else {
                        foreach ($b in (Get-StigBenchmarks $f)) {
                            if ($Offline) {
                                $out = Write-ScmProfileFile $b (Split-Path -Parent $f)
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
                    $t = Resolve-StigTarget $benchmarks (Split-Path -Leaf $f)
                    $where = $whereBox.Text.Trim()
                    if (-not $where -or $where -eq 'auto') {
                        $where = "(Vendor = 'Cisco')"
                        if ($t[1]) { $where = "(Vendor = '$($t[1])')" }
                    }
                    $base = [System.IO.Path]::GetFileNameWithoutExtension($f)
                    $reports = New-NcmReports $benchmarks $base $where 'manual' 'DISA STIG'
                    if ($Offline) {
                        foreach ($r in $reports) {
                            $out = Write-ConsoleReportFile $r (Split-Path -Parent $f)
                            Add-Summary ("SUCCESS " + $prefix + "wrote " + (Split-Path -Leaf $out)) ([System.Drawing.Color]::Green)
                        }
                        $ok++
                    } else {
                        $newIds = New-Object System.Collections.ArrayList
                        foreach ($r in $reports) {
                            try {
                                $res = Import-NcmReport $conn $r $logBlock
                                [void]$newIds.Add($res.ReportId)
                                Add-Summary ("SUCCESS " + $prefix + '"' + $r.Name + '" - ' + $res.Rules + ' rules') ([System.Drawing.Color]::Green)
                            } catch {
                                if ($_.Exception.Data['WireFailure']) {
                                    Add-Summary ($prefix + $_.Exception.Message) $null
                                    foreach ($rep in $reports) {
                                        $out = Write-ConsoleReportFile $rep (Split-Path -Parent $f)
                                        Add-Summary ($prefix + 'wrote ' + (Split-Path -Leaf $out)) $null
                                    }
                                    Show-Issue
                                    throw ($prefix + 'API import refused; console files written for WebUI import')
                                }
                                throw
                            }
                        }
                        if ($newIds.Count -gt 0) {
                            [void](Invoke-SwisVerbCall $conn 'Cirrus.PolicyReports' 'StartCaching' @(, @($newIds)))
                            Add-Detail ($prefix + 'compliance caching started')
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
    }
    $importBtn.Add_Click({ Invoke-Batch $false })
    $convertBtn.Add_Click({ Invoke-Batch $true })

    [void]$form.ShowDialog()
}

# =========================================================================
# Entry point
# =========================================================================
if ($Path -and $Path.Count -gt 0) {
    try { Invoke-CliRun }
    catch { Write-Error (Hide-Secrets $_.Exception.Message); exit 1 }
} elseif (-not $NoGui) {
    if ($env:OS -ne 'Windows_NT') {
        Write-Error 'the GUI needs Windows (WinForms); on this platform pass -Path (and -Convert or -Server)'
        exit 1
    }
    try { Show-StigGui }
    catch {
        $msg = Hide-Secrets ($_.Exception.Message + "`n`n" + $_.ScriptStackTrace)
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show($msg,
                'DISA STIG Conversion Tool - startup error')
        } catch { }
        Write-Error $msg
        exit 1
    }
}
