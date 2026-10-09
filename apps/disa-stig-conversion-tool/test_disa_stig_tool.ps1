<#
.SYNOPSIS
Offline tests for disa_stig_tool.ps1. No network, no Pester, no modules.

.DESCRIPTION
Parses the tool with the PowerShell language parser, dot-sources it with -NoGui
(which defines its functions and runs nothing), then exercises the pure
functions and, with Invoke-SwisQuery / Invoke-SwisVerbCall replaced by an
in-memory stub, the removal plan, rollback filtering and multi-report flow.

    powershell -NoProfile -ExecutionPolicy Bypass -File test_disa_stig_tool.ps1

With -ParityJson <in> -ParityOut <out> it instead reads conversion cases written
by test_disa_stig_tool.py, runs them through this edition, and writes the
results as UTF-8 JSON so the Python test can compare both editions byte for
byte. Exit code 0 means every check passed.
#>
param(
    [string]$ParityJson,
    [string]$ParityOut
)

$testsHere = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolFile = Join-Path $testsHere 'disa_stig_tool.ps1'

# --- 1. the tool must parse with no errors ---------------------------------
$parseTokens = $null; $parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($toolFile, [ref]$parseTokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) {
    foreach ($e in $parseErrors) { Write-Output ("PARSE ERROR line {0}: {1}" -f $e.Extent.StartLineNumber, $e.Message) }
    exit 1
}

# Defines the tool's functions in this scope. -NoGui with no -Path runs nothing.
. $toolFile -NoGui

# --- parity mode: run Python-supplied cases, write results -----------------
if ($ParityJson) {
    $spec = ConvertFrom-Json ([System.IO.File]::ReadAllText($ParityJson))
    $out = [ordered]@{ files = @(); memory = @() }
    $fileResults = New-Object System.Collections.ArrayList
    foreach ($c in @($spec.files)) {
        $benches = Get-StigBenchmarks $c.path
        $reports = New-NcmReports $benches (Get-ReportBaseName $c.path $c.name) $c.where $c.mode `
            $c.folder ([bool]$c.enabled) $c.configType
        [void]$fileResults.Add([ordered]@{
            reports = @($reports)
            scm     = @($benches | ForEach-Object { ConvertTo-ScmPolicyYaml $_ })
            scmIds  = @($benches | ForEach-Object { Get-ScmPolicyUniqueId $_ })
        })
    }
    $memResults = New-Object System.Collections.ArrayList
    foreach ($c in @($spec.memory)) {
        $benches = @($c.benchmarks)
        $reports = New-NcmReports $benches $c.baseName $c.where $c.mode $c.folder ([bool]$c.enabled) $c.configType
        [void]$memResults.Add([ordered]@{
            reports = @($reports)
            scm     = @($benches | ForEach-Object { ConvertTo-ScmPolicyYaml $_ })
            scmIds  = @($benches | ForEach-Object { Get-ScmPolicyUniqueId $_ })
        })
    }
    $out.files = @($fileResults)
    $out.memory = @($memResults)
    # Helpers that must give the same answer as their Python counterparts.
    $out['names'] = @(@($spec.names) | ForEach-Object { Get-SafeFileName $_.stem $_.suffix })
    $out['quoted'] = @(@($spec.quotes) | ForEach-Object { ConvertTo-PsSingleQuoted $_ })
    $out['probeIds'] = @(@($spec.probeIds) | ForEach-Object { Get-ScmProbeId $_ '' })
    # Import decisions that must match: which 400s are wire-format rejections, and
    # the read-back comparison text (one string per case, lines joined by LF).
    $out['wire'] = @(@($spec.wire) | ForEach-Object { Test-WireRejection $_ })
    $toTree = { param($Pairs) @{ Policies = @(@($Pairs) | ForEach-Object { [pscustomobject]@{ Policy = [string]$_[0]; Rules = [string[]]@($_[1]) } }) } }
    $out['trees'] = @(@($spec.trees) | ForEach-Object {
        (@(Compare-NcmReportTree (& $toTree $_.expected) (& $toTree $_.actual)) -join "`n") })
    # XML the Python edition refuses must be refused here too, with a logged reason.
    if ($spec.logFile) { [void](Initialize-ToolLog $spec.logFile 'info') }
    $out['refused'] = @(@($spec.refuse) | ForEach-Object {
        @(ConvertFrom-BenchmarkXml ([System.IO.File]::ReadAllBytes($_)) (Split-Path -Leaf $_)).Count })
    $json = ConvertTo-Json $out -Depth 30
    [System.IO.File]::WriteAllText($ParityOut, $json, (New-Object System.Text.UTF8Encoding($false)))
    exit 0
}

# --- harness ---------------------------------------------------------------
$script:Failures = New-Object System.Collections.ArrayList
$script:Passes = 0
function Assert-True($Condition, [string]$Label) {
    if ($Condition) { $script:Passes++ } else { [void]$script:Failures.Add($Label); Write-Output "FAIL: $Label" }
}
function Assert-Equal($Expected, $Actual, [string]$Label) {
    if ($Expected -ceq $Actual) { $script:Passes++ }
    else { [void]$script:Failures.Add($Label); Write-Output "FAIL: $Label`n  expected: $Expected`n  actual:   $Actual" }
}
function Assert-Throws([scriptblock]$Block, [string]$Pattern, [string]$Label) {
    try { & $Block; [void]$script:Failures.Add($Label); Write-Output "FAIL: $Label (no exception)" }
    catch {
        if ($_.Exception.Message -match $Pattern) { $script:Passes++ }
        else { [void]$script:Failures.Add($Label); Write-Output "FAIL: $Label`n  message: $($_.Exception.Message)" }
    }
}
$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ('disa-stig-ps-test-' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $scratch)
$utf8 = New-Object System.Text.UTF8Encoding($false)
$noteLog = New-Object System.Collections.ArrayList
$captureLog = { param($m) [void]$noteLog.Add($m) }

try {
    # --- 2. the tool file is pure ASCII (PS 5.1 reads BOM-less files as ANSI)
    $bytes = [System.IO.File]::ReadAllBytes($toolFile)
    $nonAscii = @($bytes | Where-Object { $_ -gt 127 }).Count
    Assert-Equal 0 $nonAscii 'disa_stig_tool.ps1 contains only ASCII bytes'

    # --- 2a. run log: line format, redaction, default path, override --------
    # The same expression test_disa_stig_tool.py checks the Python edition with.
    $lineRe = '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z (DEBUG|INFO |WARN |ERROR) (main  |parse |route |scope |build |swis  |import|verify|rollbk|remove|scm   |file  |gui   ) .*$'
    $fixed = [datetime]::new(2026, 10, 9, 12, 3, 7, 123, [System.DateTimeKind]::Utc)
    Assert-Equal "2026-10-09T12:03:07.123Z WARN  rollbk two\nlines\nhere" (Format-ToolLogLine $fixed 'warn' 'rollbk' "two`r`nlines`nhere") 'log line format matches the contract'
    foreach ($lvl in @('debug', 'info', 'warn', 'error')) {
        foreach ($comp in $script:LogComponents) {
            Assert-True ((Format-ToolLogLine $fixed $lvl $comp 'm') -cmatch $lineRe) "log line regex: $lvl $comp"
        }
    }
    $winPath = Get-DefaultLogPath -NowUtc ([datetime]::new(1970, 1, 1, 0, 0, 0, [System.DateTimeKind]::Utc)) -Platform 'windows' -Environment @{ LOCALAPPDATA = 'C:\L' } -HomeDir 'C:\H'
    Assert-Equal ([System.IO.Path]::Combine('C:\L', 'DisaStigTool', 'logs', 'disa-stig-tool_19700101-000000.log')) $winPath 'default log path on Windows'
    $winNoEnv = Get-DefaultLogPath -NowUtc ([datetime]::new(1970, 1, 1, 0, 0, 0, [System.DateTimeKind]::Utc)) -Platform 'windows' -Environment @{} -HomeDir 'H'
    Assert-Equal ([System.IO.Path]::Combine('H', 'AppData', 'Local', 'DisaStigTool', 'logs', 'disa-stig-tool_19700101-000000.log')) $winNoEnv 'default log path without LOCALAPPDATA'
    $otherPath = Get-DefaultLogPath -NowUtc ([datetime]::new(1970, 1, 1, 0, 0, 0, [System.DateTimeKind]::Utc)) -Platform 'linux' -Environment @{} -HomeDir '/home/u'
    Assert-Equal ([System.IO.Path]::Combine('/home/u', '.local', 'state', 'disa-stig-tool', 'logs', 'disa-stig-tool_19700101-000000.log')) $otherPath 'default log path elsewhere'
    $logOverride = Join-Path $scratch 'nested\run.log'
    Assert-Equal $logOverride (Initialize-ToolLog $logOverride 'info') '-LogFile overrides the default path'
    Register-Secret 'PsSecret-Log-9182'
    Write-ToolLog main error 'server echoed PsSecret-Log-9182 back'
    Write-ToolLog swis debug 'dropped at info level'
    Write-ToolLog 'bogus' warn 'falls back to main'
    $logged = @([System.IO.File]::ReadAllText($logOverride) -split "`n" | Where-Object { $_ })
    Assert-Equal 2 $logged.Count 'info level drops debug lines'
    Assert-True (@($logged | Where-Object { $_ -cnotmatch $lineRe }).Count -eq 0) 'every written line matches the contract'
    Assert-True (-not ([System.IO.File]::ReadAllText($logOverride)).Contains('PsSecret-Log-9182')) 'a registered secret never reaches the log'
    Assert-True ($logged[1] -like '* WARN  main   falls back to main') 'unknown component logs as main'

    # --- 2b. one log line per SWIS call (Invoke-SwisRest stubbed) ------------
    $swisLog = Join-Path $scratch 'swis.log'
    [void](Initialize-ToolLog $swisLog 'debug')
    $script:RestCalls = 0
    $realRest = ${function:Invoke-SwisRest}
    function Invoke-SwisRest($Conn, [string]$Method, [string]$RestPath, $Body) {
        $script:RestCalls++
        if ($RestPath -like '*Fail*') { throw 'SWIS HTTP 400 from Invoke/X/Fail' }
        if ($RestPath -eq 'Query') { return [pscustomobject]@{ results = @([pscustomobject]@{ N = 1 }, [pscustomobject]@{ N = 2 }) } }
        return 'ok-id'
    }
    $conn = New-SwisConnection 'orion.example.com' 17774 'admin' 'PsSecret-Conn-4471' $false $false $null
    [void](Invoke-SwisQuery $conn 'SELECT PolicyReportID FROM Cirrus.PolicyReports WHERE Name = @n' @{ n = 'x' })
    [void](Invoke-SwisVerbCall $conn 'Cirrus.PolicyReports' 'AddPolicyRule' @([ordered]@{ RuleName = 'V-1 [high] rule'; RuleId = 'a' }))
    [void](Invoke-SwisVerbCall $conn 'Orion.PolicyEngine.Policy' 'ImportPolicy' @(('y' * 10000)))
    try { [void](Invoke-SwisVerbCall $conn 'X' 'Fail' @(1, $true)) } catch { }
    $swisText = [System.IO.File]::ReadAllText($swisLog)
    $swisLines = @($swisText -split "`n" | Where-Object { $_ -match ' swis   ' -and ($_ -match ' -> ok ' -or $_ -match ' -> error ') })
    Assert-Equal $script:RestCalls $swisLines.Count 'one log line per SWIS call'
    Assert-True ($swisLines[0] -match 'query SELECT .* params \{n="x"\} -> ok \d+ ms, 2 row\(s\)') 'query line carries the row count'
    Assert-True ($swisLines[1] -like '*Cirrus.PolicyReports.AddPolicyRule(<object V-1 `[high`] rule>) -> ok *') 'verb line names entity.verb and the rule'
    Assert-True ($swisLines[3] -like '* WARN  swis   X.Fail(1, true) -> error *SWIS HTTP 400*') 'failed call logged with the error'
    Assert-True ($swisText.Contains('[truncated, ')) 'debug bodies are cut to 4 KB'
    Assert-True ($swisText.Contains("as user 'admin'") -and -not $swisText.Contains('PsSecret-Conn-4471')) 'user and host logged, password never'
    Assert-True (@($swisText -split "`n" | Where-Object { $_ -and $_ -cnotmatch $lineRe }).Count -eq 0) 'debug lines match the contract too'
    Set-Item -Path function:Invoke-SwisRest -Value $realRest

    # --- 2c. XML: DTD/XXE refused with a logged reason; declared encoding ----
    $xmlLog = Join-Path $scratch 'xml.log'
    [void](Initialize-ToolLog $xmlLog 'info')
    $xxe = [System.Text.Encoding]::UTF8.GetBytes('<?xml version="1.0" encoding="UTF-8"?>' + "`n" +
        '<!DOCTYPE Benchmark [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>' + "`n" +
        '<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="XXE_STIG"><title>&xxe;</title></Benchmark>')
    $dtdOnly = [System.Text.Encoding]::UTF8.GetBytes('<?xml version="1.0"?><!DOCTYPE Benchmark [<!ENTITY a "aaaa">]>' +
        '<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="DTD_STIG"><title>&a;</title></Benchmark>')
    Assert-Equal 0 @(ConvertFrom-BenchmarkXml $xxe 'evil-xccdf.xml').Count 'external-entity document is refused'
    Assert-Equal 0 @(ConvertFrom-BenchmarkXml $dtdOnly 'dtd-xccdf.xml').Count 'any DTD is refused'
    $xmlText = [System.IO.File]::ReadAllText($xmlLog)
    Assert-True ($xmlText -match 'WARN  parse  skipped evil-xccdf\.xml: refused: the document declares a DTD') 'the refusal reason is logged'
    $eacute = [string][char]0xE9
    $cp1252 = [System.Text.Encoding]::GetEncoding(1252).GetBytes('<?xml version="1.0" encoding="windows-1252"?>' +
        '<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="Enc_STIG"><title>Caf' + $eacute + ' STIG</title></Benchmark>')
    Assert-Equal ('Caf' + $eacute + ' STIG') @(ConvertFrom-BenchmarkXml $cp1252 'enc.xml')[0].Title 'declared windows-1252 encoding is honoured'
    $utf16 = [System.Text.Encoding]::Unicode.GetPreamble() + [System.Text.Encoding]::Unicode.GetBytes('<?xml version="1.0" encoding="UTF-16"?>' +
        '<Benchmark xmlns="http://checklists.nist.gov/xccdf/1.1" id="U16_STIG"><title>Caf' + $eacute + ' STIG</title></Benchmark>')
    Assert-Equal ('Caf' + $eacute + ' STIG') @(ConvertFrom-BenchmarkXml ([byte[]]$utf16) 'u16.xml')[0].Title 'UTF-16 with BOM is read'

    # --- 2d. SCM probe: ids validated, single-quoted literal ----------------
    $tick = [string][char]0x60
    $rsquo = [string][char]0x2019
    Assert-Equal "'it''s'" (ConvertTo-PsSingleQuoted "it's") 'single quote doubled'
    Assert-Equal ("'a" + $tick + 'b $(c) "d"' + "'") (ConvertTo-PsSingleQuoted ('a' + $tick + 'b $(c) "d"')) 'backtick, $( ) and " stay literal'
    Assert-Equal ("'x" + $rsquo + $rsquo + "y'") (ConvertTo-PsSingleQuoted ('x' + $rsquo + 'y')) 'typographic quote doubled'
    Assert-Equal 'V-123' (Get-ScmProbeId 'xccdf_mil.disa.stig_group_V-123' 'xccdf_mil.disa.stig_rule_SV-123r2_rule') 'SCAP prefixes are accepted'
    $nasty = 'V-77$(Remove-Item C:\x)' + $tick + '"' + "'" + $rsquo
    $probeBench = @{ BenchmarkId = 'Probe_STIG'; Title = 'Probe'; Version = '1'; Release = 'R'; StatusDate = ''; Source = 's.xml'; Edition = 'manual'
        Rules = @(@{ VulnId = 'V-1'; RuleId = 'SV-1r1_rule'; StigId = 'X-1'; Severity = 'medium'; Title = 't'; Discussion = ''; CheckContent = ''; OvalRef = ''; FixText = ''; Ccis = @() },
                  @{ VulnId = $nasty; RuleId = 'SV-2$(x)'; StigId = 'X-2'; Severity = 'low'; Title = 't'; Discussion = ''; CheckContent = ''; OvalRef = ''; FixText = ''; Ccis = @() }) }
    $probeYaml = ConvertTo-ScmPolicyYaml $probeBench
    $scripts = @($probeYaml -split "`n" | Where-Object { $_.StartsWith('      script: ') })
    Assert-Equal "      script: `"Write-Host 'V-1 reviewed: False'`"" $scripts[0] 'valid id probe is a single-quoted literal'
    Assert-Equal "      script: `"Write-Host 'V-77_Remove-Item_C_x_ reviewed: False'`"" $scripts[1] 'hostile id is sanitized'
    Assert-True (@($scripts | Where-Object { $_.Contains('$(') -or $_.Contains($tick) }).Count -eq 0) 'no $( or backtick reaches probe source'

    # --- 2e. file names: one sanitizer, 200-character cap -------------------
    Assert-Equal '_.._x.ncm-report.xml' (Get-SafeFileName '../../x' '.ncm-report.xml') '../../x cannot climb out'
    $longName = Get-SafeFileName ('T' * 300) '.scm-policy.yaml'
    Assert-Equal 200 $longName.Length 'a 300-character title is capped at 200'
    Assert-True ($longName.EndsWith('.scm-policy.yaml')) 'the suffix survives the cap'
    Assert-Equal '_CON.ncm-report.xml' (Get-SafeFileName 'CON' '.ncm-report.xml') 'reserved device names are prefixed'
    $outDir = Join-Path $scratch 'out'
    [void](New-Item -ItemType Directory -Path $outDir)
    foreach ($reportName in @('../../evil', ('N' * 250))) {
        $rep = (New-NcmReports @($probeBench) $reportName "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $true)[0]
        $written = Write-ConsoleReportFile $rep $outDir
        Assert-Equal $outDir (Split-Path -Parent $written) "console file for '$($reportName.Substring(0, 5))...' stays in its folder"
        Assert-True (Test-Path -LiteralPath $written) "console file for '$($reportName.Substring(0, 5))...' is written"
    }
    $script:LogState.Path = $null   # later sections do not need the log

    # --- 3. seeds match the Python scheme (benchmark id, else title) --------
    $withId = @{ BenchmarkId = 'Cisco_IOS_Router_NDM_STIG'; Title = 'Cisco IOS Router NDM' }
    $noId = @{ BenchmarkId = ''; Title = 'Untitled Benchmark' }
    Assert-Equal (Get-DeterministicGuid 'stig2ncm-policy:Cisco_IOS_Router_NDM_STIG') (Get-NcmPolicyId $withId) 'NCM PolicyId seeds on the benchmark id'
    Assert-Equal (Get-DeterministicGuid 'stig2ncm-policy:Untitled Benchmark') (Get-NcmPolicyId $noId) 'NCM PolicyId falls back to the title'
    Assert-Equal (Get-DeterministicGuid 'stig2ncm-scm:Cisco_IOS_Router_NDM_STIG') (Get-ScmPolicyUniqueId $withId) 'SCM uniqueId seeds on the benchmark id'
    Assert-Equal (Get-DeterministicGuid 'stig2ncm-scm:Untitled Benchmark') (Get-ScmPolicyUniqueId $noId) 'SCM uniqueId falls back to the title'
    Assert-True ((Get-NcmPolicyId $withId) -ne (Get-DeterministicGuid 'stig2ncm-policy:Cisco_IOS_Router_NDM_STIGCisco IOS Router NDM')) 'old id+title seed is no longer used'

    # --- 4. uniqueId / name preflight survives CRLF -------------------------
    $lf = "!policy`nname: 'IIS Test Policy'`nuniqueId: 81d7a7f2-d976-486d-a6b9-39f2298c2348`npluginName: SCM`nrules:`n- displayId: V-1`n"
    $crlf = $lf -replace "`n", "`r`n"
    foreach ($case in @(@('LF', $lf), @('CRLF', $crlf))) {
        $info = Get-ScmPolicyInfo $case[1]
        Assert-Equal '81d7a7f2-d976-486d-a6b9-39f2298c2348' $info.UniqueId "uniqueId found ($($case[0]))"
        Assert-Equal 'IIS Test Policy' $info.Name "name found ($($case[0]))"
        Assert-True $info.IsPolicy "recognized as a policy ($($case[0]))"
    }
    $oldRegex = [regex]::Match($crlf, '(?m)^uniqueId:\s*(\S+)$')
    Assert-True (-not $oldRegex.Success) 'the pre-fix regex really does miss CRLF (guards the test itself)'

    # --- 5. SCM file routing: .scm-policy.yaml, legacy .scm-profile, JSON profile
    $policyNew = Join-Path $scratch 'x.scm-policy.yaml'
    [System.IO.File]::WriteAllText($policyNew, $lf, $utf8)
    Assert-Equal $lf (Read-ScmPolicyFile $policyNew $captureLog) 'reads .scm-policy.yaml'
    Assert-Equal 'SCM' (Get-FileModule $policyNew) '.scm-policy.yaml routes to SCM'

    $legacy = Join-Path $scratch 'legacy.scm-profile'
    [System.IO.File]::WriteAllText($legacy, $crlf, $utf8)
    $noteLog.Clear()
    Assert-Equal $crlf (Read-ScmPolicyFile $legacy $captureLog) 'legacy .scm-profile policy YAML is accepted'
    Assert-True ((@($noteLog) -join ' ') -match 'older build') 'legacy .scm-profile prints a deprecation note'

    $utf16Policy = Join-Path $scratch 'exported.yaml'
    [System.IO.File]::WriteAllText($utf16Policy, $lf, [System.Text.Encoding]::Unicode)   # UTF-16LE + BOM
    Assert-Equal $lf (Read-ScmPolicyFile $utf16Policy $null) 'UTF-16LE policy YAML with BOM decodes'

    $profileJson = '{"name":"Scheduled Task Profile","uniqueId":"ce741ac1-d041-49cb-bb86-613ef130b6bf","profileElements":[{"type":"powershell","settings":"{\"path\":\"Get-ScheduledTask\"}"}]}'
    $profile = Join-Path $scratch 'Scheduled_Task_Profile.scm-profile'
    [System.IO.File]::WriteAllText($profile, $profileJson, [System.Text.Encoding]::Unicode)
    Assert-Throws { Read-ScmPolicyFile $profile $null } 'collection profile' 'JSON .scm-profile is refused as a collection profile'
    Assert-Throws { Get-FileModule $profile } 'collection profile' 'Get-FileModule refuses a JSON .scm-profile'

    # --- 6. Import-ScmPolicyYaml validates !policy before any SWIS call -----
    $script:Calls = New-Object System.Collections.ArrayList
    function Invoke-SwisVerbCall($Conn, [string]$Entity, [string]$SwisVerb, [array]$Arguments) {
        [void]$script:Calls.Add("$SwisVerb"); return $null
    }
    function Invoke-SwisQuery($Conn, [string]$Swql, $Parameters) { [void]$script:Calls.Add('query'); return @() }
    Assert-Throws { Import-ScmPolicyYaml @{} 'name: not a policy' $captureLog } 'not an SCM compliance policy' 'Import-ScmPolicyYaml rejects text without !policy'
    Assert-Equal 0 $script:Calls.Count 'no SWIS call made for rejected text'

    # --- 7. report naming and truncation match Python ----------------------
    $bench = @{ BenchmarkId = 'B1'; Title = 'T' * 300; Version = '1'; Release = 'Release: 1'; StatusDate = '';
                Source = 's.xml'; Edition = 'manual'; Rules = @(@{ VulnId = 'V-1'; RuleId = 'SV-1r1_rule'; StigId = 'X-1';
                Severity = 'high'; Title = 'rule'; Discussion = ''; CheckContent = ''; OvalRef = ''; FixText = ''; Ccis = @() }) }
    Assert-Equal '' (Get-ReportBaseName 'C:\x\U_Foo-xccdf.xml' '') '.xml input has no base name'
    Assert-Equal 'U_Foo_STIG' (Get-ReportBaseName 'C:\x\U_Foo_STIG.zip' '') '.zip input uses its file name'
    Assert-Equal 'Mine' (Get-ReportBaseName 'C:\x\U_Foo_STIG.zip' 'Mine') '-Name wins'
    # New-NcmReports returns its array with a unary comma, so assign it rather
    # than wrapping the call in @() (which would nest the array one level).
    $built = New-NcmReports @($bench) '' "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $true 'Running'; $r = $built[0]
    Assert-Equal 250 $r.Name.Length 'report named after a long title is cut to 250'
    Assert-Equal 250 $r.AssignedPolicies[0].PolicyName.Length 'policy name is cut to 250'
    Assert-Equal 'Running' $r.AssignedPolicies[0].ConfigTypes '-ConfigType reaches the policy'
    $built = New-NcmReports @($bench) 'Base' "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $false; $r = $built[0]
    Assert-Equal 'Base - B1' $r.Name 'base name plus benchmark id'
    Assert-Equal 'Disabled' $r.ReportStatus 'Enabled=$false gives ReportStatus Disabled'
    $bench.BenchmarkId = ''
    $built = New-NcmReports @($bench) 'Base' "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $true; $r = $built[0]
    Assert-Equal 'Base' $r.Name 'base name alone when the benchmark has no id'

    # --- 8. YAML scalar quoting matches json.dumps for \b and \f -----------
    Assert-Equal '"a\bb\fc\u0001"' (Y ("a" + [char]8 + "b" + [char]12 + "c" + [char]1)) 'Y escapes like json.dumps'

    # --- 9. stubbed SWIS: removal plan keeps shared policies and rules ------
    # Report rA: policies p1 (rules r1, r2) and p2 (rule r3). Report rB shares
    # p2 and has p3 (rules r2, r4). Removing rA must delete p1 and r1 only.
    $script:Model = @{
        Reports  = [ordered]@{ 'rA' = @('p1', 'p2'); 'rB' = @('p2', 'p3') }
        Policies = [ordered]@{ 'p1' = @('r1', 'r2'); 'p2' = @('r3'); 'p3' = @('r2', 'r4') }
        Rules    = @('r1', 'r2', 'r3', 'r4')
    }
    $script:Calls = New-Object System.Collections.ArrayList
    function Invoke-SwisQuery($Conn, [string]$Swql, $Parameters) {
        [void]$script:Calls.Add("query: $Swql")
        $ids = @(); if ($Parameters -and $Parameters.ContainsKey('ids')) { $ids = @($Parameters.ids) }
        $rows = New-Object System.Collections.ArrayList
        $m = $script:Model
        if ($Swql -match 'FROM Cirrus\.PolicyAssignment WHERE PolicyReportID IN') {
            foreach ($rep in $ids) { if ($m.Reports.Contains($rep)) { foreach ($p in $m.Reports[$rep]) { [void]$rows.Add([pscustomobject]@{ PolicyID = $p }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyAssignment WHERE PolicyID IN') {
            foreach ($rep in $m.Reports.Keys) { foreach ($p in $m.Reports[$rep]) { if ($ids -contains $p) { [void]$rows.Add([pscustomobject]@{ PolicyReportID = $rep; PolicyID = $p }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRuleAssignment WHERE PolicyID IN') {
            foreach ($p in $ids) { if ($m.Policies.Contains($p)) { foreach ($x in $m.Policies[$p]) { [void]$rows.Add([pscustomobject]@{ PolicyRuleID = $x }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRuleAssignment WHERE PolicyRuleID IN') {
            foreach ($p in $m.Policies.Keys) { foreach ($x in $m.Policies[$p]) { if ($ids -contains $x) { [void]$rows.Add([pscustomobject]@{ PolicyID = $p; PolicyRuleID = $x }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyReports WHERE PolicyReportID IN') {
            foreach ($rep in $ids) { if ($m.Reports.Contains($rep)) { [void]$rows.Add([pscustomobject]@{ PolicyReportID = $rep; Name = $rep; ReportStatus = $false }) } }
        } elseif ($Swql -match 'FROM Cirrus\.Policies WHERE PolicyID IN') {
            foreach ($p in $ids) { if ($m.Policies.Contains($p)) { [void]$rows.Add([pscustomobject]@{ PolicyID = $p }) } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRules WHERE PolicyRuleID IN') {
            foreach ($x in $ids) { if ($m.Rules -contains $x) { [void]$rows.Add([pscustomobject]@{ PolicyRuleID = $x }) } }
        }
        return @($rows)
    }
    function Invoke-SwisVerbCall($Conn, [string]$Entity, [string]$SwisVerb, [array]$Arguments) {
        [void]$script:Calls.Add("verb: $SwisVerb " + (ConvertTo-Json $Arguments -Compress -Depth 5))
        $m = $script:Model
        switch ($SwisVerb) {
            'GetPolicyReport' {
                # The export tree carries names but (like console files) no PolicyId,
                # so membership must come from the SWQL link tables.
                $rep = $Arguments[0]
                $pols = @($m.Reports[$rep] | ForEach-Object {
                    $pid2 = $_
                    [pscustomobject]@{ PolicyName = "Policy $pid2"
                        AssignedPolicyRules = @($m.Policies[$pid2] | ForEach-Object { [pscustomobject]@{ RuleId = $_; RuleName = "Rule $_" } }) }
                })
                return [pscustomobject]@{ Name = $rep; AssignedPolicies = $pols }
            }
            'DeletePolicyReports' { foreach ($x in @($Arguments[0])) { $m.Reports.Remove($x) }; return 1 }
            'DeletePolicies' { foreach ($x in @($Arguments[0])) { $m.Policies.Remove($x) }; return 1 }
            'DeletePolicyRules' { $m.Rules = @($m.Rules | Where-Object { @($Arguments[0]) -notcontains $_ }); return 1 }
            'UpdateReportStatus' { return $null }
            'StartCaching' { return $null }
        }
        return $null
    }
    $plan = Get-NcmRemovalPlan @{} @('rA') $captureLog
    Assert-Equal 'p1' (@($plan.DeletePolicies) -join ',') 'removal deletes only the unshared policy'
    Assert-Equal 'p2' (@($plan.KeepPolicies.Keys) -join ',') 'removal keeps the policy report rB shares'
    Assert-Equal 'r1' (@($plan.DeleteRules) -join ',') 'removal deletes only the unshared rule'
    Assert-Equal 'r2,r3' ((@($plan.KeepRules.Keys) | Sort-Object) -join ',') 'removal keeps rules other policies use'
    $script:Calls.Clear()
    $left = Remove-NcmReports @{} $plan $captureLog
    $verbs = @($script:Calls | Where-Object { $_ -like 'verb:*' })
    Assert-Equal 'verb: DeletePolicyReports [["rA"],false]' $verbs[0] 'report row deleted first, deleteChildren false'
    Assert-Equal 'verb: DeletePolicies [["p1"],false]' $verbs[1] 'then the policies, deleteChildren false'
    Assert-Equal 'verb: DeletePolicyRules [["r1"]]' $verbs[2] 'then the rules'
    Assert-Equal 0 ($left.reports.Count + $left.policies.Count + $left.rules.Count) 'read-back finds nothing left'
    Assert-True ($script:Model.Policies.Contains('p2') -and ($script:Model.Rules -contains 'r2')) 'shared objects survive'

    # --- 10. rollback skips ids that existed before the run ----------------
    $script:Calls.Clear()
    $pre = @{ Rules = @{ 'aaaa-1' = $true }; Policies = @{} }
    $noteLog.Clear()
    Undo-NcmImport @{} @('AAAA-1', 'bbbb-2') @('pol-new') 'rep-new' $captureLog $pre
    $verbs = @($script:Calls | Where-Object { $_ -like 'verb:*' })
    Assert-Equal 'verb: DeletePolicyRules [["bbbb-2"]]' $verbs[2] 'rollback deletes only rules this run created'
    Assert-True ((@($noteLog) -join ' ') -match 'skipped rule AAAA-1') 'rollback says which rule it skipped'

    # --- 11. multi-report: earlier imports are kept and finished -----------
    $realImport = ${function:Import-NcmReport}
    function Import-NcmReport($Conn, $Report, [scriptblock]$Log, [bool]$Rollback = $true) {
        if ($Report.Name -eq 'second') {
            $e = New-Object System.Exception 'no wire format accepted'; $e.Data['WireFailure'] = $true; throw $e
        }
        return @{ ReportId = 'id-' + $Report.Name; Policies = 1; Rules = 3 }
    }
    $reports = @([ordered]@{ Name = 'first'; AssignedPolicies = @(@{ AssignedPolicyRules = @(1, 2, 3) }) },
                 [ordered]@{ Name = 'second'; AssignedPolicies = @(@{ AssignedPolicyRules = @(1) }) },
                 [ordered]@{ Name = 'third'; AssignedPolicies = @(@{ AssignedPolicyRules = @(1) }) })
    $run = Import-NcmReports @{} $reports $captureLog $true
    Set-Item -Path function:Import-NcmReport -Value $realImport
    Assert-Equal 'first' (@($run.Imported | ForEach-Object { $_.Report.Name }) -join ',') 'the report before the failure counts as imported'
    Assert-Equal 'second,third' (@($run.Remaining | ForEach-Object { $_.Name }) -join ',') 'only unimported reports remain for console files'
    Assert-True ([bool]$run.Failure.Data['WireFailure']) 'the wire failure is reported'
    $script:Model.Reports['id-first'] = @()
    $script:Calls.Clear()
    Assert-True (Complete-NcmImport @{} @('id-first') $true $false $captureLog) 'disabled state confirmed by read-back'
    Assert-True ($script:Calls[0] -like 'verb: UpdateReportStatus*') 'UpdateReportStatus called'
    Assert-True ($script:Calls[1] -like 'query: SELECT Name, ReportStatus FROM Cirrus.PolicyReports*') 'ReportStatus read back'
    $script:Calls.Clear()
    [void](Complete-NcmImport @{} @('id-first') $false $false $captureLog)
    Assert-Equal 'verb: StartCaching [["id-first"]]' $script:Calls[0] 'caching started for exactly the imported id'
    $script:Calls.Clear()
    [void](Complete-NcmImport @{} @('id-first') $false $true $captureLog)
    Assert-Equal 0 $script:Calls.Count '-NoCache makes no call'

    # --- 12. import reliability (a stateful stub of Cirrus.PolicyReports) ----
    $relLog = Join-Path $scratch 'reliability.log'
    [void](Initialize-ToolLog $relLog 'info')
    $wireCases = @(
        @("SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nValue cannot be null. Parameter name: input", $true),
        @("SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicy`nVerb Cirrus.PolicyReports.AddPolicy cannot unpackage parameter 0", $true),
        @("SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nRule name must not be empty.", $false),
        @("SWIS HTTP 400 from Invoke/X`nValue cannot be null. (Parameter 'input')", $false),
        @("SWIS HTTP 403 from Invoke/X`nAccess is denied.", $false),
        @("SWIS HTTP 500 from Invoke/X`ncannot unpackage parameter 0", $false),
        @('SWIS transport error calling Query: WebException: The operation has timed out', $false))
    foreach ($case in $wireCases) {
        Assert-Equal $case[1] (Test-WireRejection $case[0]) ('wire rejection: ' + @($case[0] -split "`n")[-1])
    }

    $treeP = [pscustomobject]@{ Policy = 'P'; Rules = [string[]]@('a', 'b', 'c') }
    $treeQ = [pscustomobject]@{ Policy = 'Q'; Rules = [string[]]@('d') }
    $exp = @{ Policies = @($treeP, $treeQ) }
    Assert-Equal 0 @(Compare-NcmReportTree $exp $exp).Count 'identical trees compare equal'
    $short = @{ Policies = @([pscustomobject]@{ Policy = 'P'; Rules = [string[]]@('a', 'b') }) }
    Assert-Equal ('policies: expected 2, stored 1|rules: expected 4, stored 2|policy "P": expected 3 rules, stored 2 (missing "c")|policy "Q" missing') `
        (@(Compare-NcmReportTree $exp $short) -join '|') 'tree differences match the Python text'
    Assert-True ($null -eq (Get-ReadBackTree '<PolicyReport />')) 'a string read-back cannot be compared'
    Assert-True ($null -eq (Get-ReadBackTree ([pscustomobject]@{ AssignedPoliciesList = @('x') }))) 'a tree without its policies cannot be compared'
    Assert-Equal 0 (Get-ReadBackTree ([pscustomobject]@{ Name = 'r' })).Policies.Count 'a report object with no policies is an empty tree'

    function Reset-Fake {
        $script:F = @{
            Reports = [ordered]@{}; Policies = [ordered]@{}; Rules = [ordered]@{}
            Fail = @{}; Results = @{}; RejectItems = $false; Nested = $null; InIdsBroken = $false; DropRule = $false
            Calls = New-Object System.Collections.ArrayList
        }
    }
    function Invoke-FakeFail([string]$Key) {
        if (-not $script:F.Fail.ContainsKey($Key)) { return }
        $spec = $script:F.Fail[$Key]
        if ($spec -is [System.Collections.ArrayList]) {
            if ($spec.Count -eq 0) { return }
            $next = $spec[0]; $spec.RemoveAt(0)
            if ($null -ne $next) { throw $next }
            return
        }
        throw $spec
    }
    function Invoke-SwisQuery($Conn, [string]$Swql, $Parameters) {
        [void]$script:F.Calls.Add("query: $Swql")
        Invoke-FakeFail 'query'
        $ids = @(); if ($Parameters -and $Parameters.ContainsKey('ids')) { $ids = @($Parameters.ids | ForEach-Object { Get-NormId $_ }) }
        $rows = New-Object System.Collections.ArrayList
        if ($Swql -match 'IN @ids' -and $script:F.InIdsBroken) { return @() }
        if ($Swql -eq 'SELECT TOP 1 PolicyRuleID FROM Cirrus.PolicyRules') {
            foreach ($k in @($script:F.Rules.Keys) | Select-Object -First 1) { [void]$rows.Add([pscustomobject]@{ PolicyRuleID = $k }) }
        } elseif ($Swql -eq 'SELECT TOP 1 PolicyID FROM Cirrus.Policies') {
            foreach ($k in @($script:F.Policies.Keys) | Select-Object -First 1) { [void]$rows.Add([pscustomobject]@{ PolicyID = $k }) }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyReports WHERE Name = @n') {
            foreach ($k in @($script:F.Reports.Keys)) { if ($script:F.Reports[$k].Name -eq $Parameters.n) { [void]$rows.Add([pscustomobject]@{ PolicyReportID = $k; Name = $script:F.Reports[$k].Name }) } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyReports WHERE PolicyReportID IN') {
            foreach ($k in @($script:F.Reports.Keys)) { if ($ids -contains (Get-NormId $k)) { [void]$rows.Add([pscustomobject]@{ PolicyReportID = $k; Name = $script:F.Reports[$k].Name; ReportStatus = $script:F.Reports[$k].Enabled }) } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRules WHERE PolicyRuleID IN') {
            foreach ($k in @($script:F.Rules.Keys)) { if ($ids -contains (Get-NormId $k)) { [void]$rows.Add([pscustomobject]@{ PolicyRuleID = $k }) } }
        } elseif ($Swql -match 'FROM Cirrus\.Policies WHERE PolicyID IN') {
            foreach ($k in @($script:F.Policies.Keys)) { if ($ids -contains (Get-NormId $k)) { [void]$rows.Add([pscustomobject]@{ PolicyID = $k }) } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyAssignment WHERE PolicyReportID IN') {
            foreach ($k in @($script:F.Reports.Keys)) { if ($ids -contains (Get-NormId $k)) { foreach ($p in $script:F.Reports[$k].Policies) { [void]$rows.Add([pscustomobject]@{ PolicyID = $p }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyAssignment WHERE PolicyID IN') {
            foreach ($k in @($script:F.Reports.Keys)) { foreach ($p in $script:F.Reports[$k].Policies) { if ($ids -contains (Get-NormId $p)) { [void]$rows.Add([pscustomobject]@{ PolicyReportID = $k; PolicyID = $p }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRuleAssignment WHERE PolicyID IN') {
            foreach ($k in @($script:F.Policies.Keys)) { if ($ids -contains (Get-NormId $k)) { foreach ($x in $script:F.Policies[$k].Rules) { [void]$rows.Add([pscustomobject]@{ PolicyRuleID = $x }) } } }
        } elseif ($Swql -match 'FROM Cirrus\.PolicyRuleAssignment WHERE PolicyRuleID IN') {
            foreach ($k in @($script:F.Policies.Keys)) { foreach ($x in $script:F.Policies[$k].Rules) { if ($ids -contains (Get-NormId $x)) { [void]$rows.Add([pscustomobject]@{ PolicyID = $k; PolicyRuleID = $x }) } } }
        } else { throw "fake has no answer for: $Swql" }
        return @($rows)
    }
    function Invoke-SwisVerbCall($Conn, [string]$Entity, [string]$SwisVerb, [array]$Arguments) {
        [void]$script:F.Calls.Add("verb: $SwisVerb")
        Invoke-FakeFail $SwisVerb
        $result = $null
        switch ($SwisVerb) {
            'AddPolicyRule' {
                $rule = $Arguments[0]
                if ($script:F.RejectItems -or $rule -is [string]) { throw "SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nValue cannot be null. Parameter name: input" }
                $script:F.Rules[$rule.RuleId] = $rule.RuleName
                $result = '"' + $rule.RuleId + '"'
            }
            'AddPolicy' {
                $pid2 = [guid]::NewGuid().ToString()
                $script:F.Policies[$pid2] = @{ Name = $Arguments[0].PolicyName; Rules = @($Arguments[0].AssignedRulesList) }
                $result = $pid2
            }
            'AddPolicyReport' {
                $rep = $Arguments[0]
                $rid = [guid]::NewGuid().ToString()
                if ($rep -is [string]) {
                    if (-not $script:F.Nested) { throw "SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyReport`ncannot unpackage parameter 0" }
                    $x = [xml]$rep
                    $script:F.Reports[$rid] = @{ Name = $x.PolicyReport.Name; Policies = @(); Enabled = $true }
                } else {
                    $script:F.Reports[$rid] = @{ Name = $rep.Name; Policies = @($rep.AssignedPoliciesList); Enabled = $true }
                }
                $result = $rid
            }
            'GetPolicyReport' {
                $rid = [string]$Arguments[0]
                if ($script:F.Reports.Contains($rid)) {
                    $pols = @(foreach ($p in $script:F.Reports[$rid].Policies) {
                        $ruleIds = @($script:F.Policies[$p].Rules)
                        if ($script:F.DropRule -and $ruleIds.Count -gt 0) { $ruleIds = @($ruleIds | Select-Object -First ($ruleIds.Count - 1)) }
                        [pscustomobject]@{ PolicyName = $script:F.Policies[$p].Name; PolicyId = $p
                            AssignedPolicyRules = @($ruleIds | ForEach-Object { [pscustomobject]@{ RuleId = $_; RuleName = $script:F.Rules[$_] } }) }
                    })
                    $result = [pscustomobject]@{ Name = $script:F.Reports[$rid].Name; AssignedPolicies = $pols }
                }
            }
            'DeletePolicyReports' { foreach ($x in @($Arguments[0])) { $script:F.Reports.Remove($x) }; $result = 1 }
            'DeletePolicies' { foreach ($x in @($Arguments[0])) { $script:F.Policies.Remove($x) }; $result = 1 }
            'DeletePolicyRules' { foreach ($x in @($Arguments[0])) { $script:F.Rules.Remove($x) }; $result = 1 }
            'StartCaching' { $result = $true }
            'UpdateReportStatus' { foreach ($x in @($Arguments[1])) { if ($script:F.Reports.Contains($x)) { $script:F.Reports[$x].Enabled = ($Arguments[0] -ne 'Disabled') } } }
        }
        if ($script:F.Results.ContainsKey($SwisVerb)) { return $script:F.Results[$SwisVerb] }
        return $result
    }
    function Get-FakeVerbCount([string]$Verb) { return @($script:F.Calls | Where-Object { $_ -eq "verb: $Verb" }).Count }
    $relRules = @(1, 2, 3 | ForEach-Object { @{ VulnId = "V-$_"; RuleId = "SV-$($_)r1_rule"; StigId = "X-$_"; Severity = 'medium'; Title = "Rule $_"; Discussion = ''; CheckContent = ''; OvalRef = ''; FixText = ''; Ccis = @() } })
    $relBench = @{ BenchmarkId = 'Rel_STIG'; Title = 'Reliability'; Version = '1'; Release = 'R1'; StatusDate = ''; Source = 'r.xml'; Edition = 'manual'; Rules = $relRules }
    $relReports = New-NcmReports @($relBench) 'Rel' "(Vendor = 'Cisco')" 'manual' 'DISA STIG' $true
    $relReport = $relReports[0]
    $relRuleIds = @($relReport.AssignedPolicies[0].AssignedPolicyRules | ForEach-Object { $_.RuleId })

    Reset-Fake
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-Equal 1 $res.Imported.Count 'a clean import is verified by name and count'
    Assert-Equal 3 $res.Imported[0].Rules 'verified rule count comes from the read-back'

    # Only a documented 400 moves on; anything else stops the report.
    foreach ($message in @("SWIS HTTP 400 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nRule name must not be empty.",
                           "SWIS HTTP 403 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nAccess is denied.",
                           "SWIS HTTP 500 from Invoke/Cirrus.PolicyReports/AddPolicyRule`nObject reference not set")) {
        Reset-Fake
        $script:F.Fail['AddPolicyRule'] = $message
        $res = Import-NcmReports @{} @($relReport) $captureLog $true
        $label = @($message -split "`n")[0]
        Assert-True ($null -ne $res.Failure -and -not $res.Failure.Data['WireFailure']) "$label stops the report without console files"
        Assert-Equal 1 (Get-FakeVerbCount 'AddPolicyRule') "$label tries no other wire format"
        Assert-Equal 0 (Get-FakeVerbCount 'AddPolicyReport') "$label does not fall back to the nested call"
    }

    # A transport error mid-import is rolled back and recorded.
    Reset-Fake
    $script:F.Fail['AddPolicy'] = 'SWIS transport error calling Invoke/Cirrus.PolicyReports/AddPolicy: WebException: The operation has timed out'
    $noteLog.Clear()
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ($res.Failure.Message -match 'timed out') 'the transport failure is recorded'
    Assert-Equal 0 $script:F.Rules.Count 'the rules created before the timeout are rolled back'
    Assert-True ((@($noteLog) -join ' ') -match 'outcome of the failed call is unknown') 'an unknown outcome is called out'

    # A rollback carries on past a failing delete.
    Reset-Fake
    $script:F.Fail['AddPolicyReport'] = "SWIS HTTP 500 from Invoke/Cirrus.PolicyReports/AddPolicyReport`nsimulated"
    $script:F.Fail['DeletePolicies'] = 'SWIS transport error calling Invoke/Cirrus.PolicyReports/DeletePolicies: WebException: timed out'
    $noteLog.Clear()
    [void](Import-NcmReports @{} @($relReport) $captureLog $true)
    Assert-Equal 0 $script:F.Rules.Count 'rules are deleted even after the policy delete failed'
    Assert-True ((@($noteLog) -join ' ') -match 'DeletePolicies failed, clean up by hand') 'the failed delete is reported'

    # Read-back: a string, or a partial tree, is a failed import that is rolled back.
    Reset-Fake
    $script:F.Results['GetPolicyReport'] = '<PolicyReport />'
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ($res.Failure.Message -match 'instead of a readable report object') 'a string read-back fails verification'
    Assert-Equal 0 ($script:F.Reports.Count + $script:F.Policies.Count + $script:F.Rules.Count) 'and everything it created is rolled back'
    Reset-Fake
    $script:F.DropRule = $true
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ($res.Failure.Message -match 'rules: expected 3, stored 2') 'a partial tree fails verification'
    Assert-True ($res.Failure.Message -match 'WebDownloader' -and $res.Failure.Message -notmatch 'WebUploader or higher') 'the role named is the right one'
    Assert-Equal 0 $script:F.Rules.Count 'a partial import is rolled back'

    # Nested fallback: a report row alone is deleted, then console files are due.
    Reset-Fake
    $script:F.RejectItems = $true; $script:F.Nested = 'report-only'
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ([bool]$res.Failure.Data['WireFailure']) 'nested report-only falls through to console files'
    Assert-Equal 0 $script:F.Reports.Count 'the bare nested report row is deleted'
    Assert-Equal 1 (Get-FakeVerbCount 'DeletePolicyReports') 'one report delete for the nested rollback'
    Reset-Fake
    $script:F.RejectItems = $true
    $script:F.Fail['AddPolicyReport'] = 'SWIS transport error calling Invoke/Cirrus.PolicyReports/AddPolicyReport: WebException: timed out'
    $noteLog.Clear()
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ($null -ne $res.Failure -and -not $res.Failure.Data['WireFailure']) 'a nested timeout stops the report without console files'
    Assert-True ((@($noteLog) -join ' ') -match 'outcome of the failed AddPolicyReport is unknown') 'the nested timeout is called out as an unknown outcome'
    Reset-Fake
    $script:F.RejectItems = $true; $script:F.Nested = 'report-only'; $script:F.InIdsBroken = $true
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ([bool]$res.Failure.Data['InIdsProbe'] -and -not $res.Failure.Data['WireFailure']) 'a broken IN @ids stops the nested rollback'
    Assert-Equal 1 $script:F.Reports.Count 'nothing is deleted on an unverified basis'
    Assert-Equal 0 (Get-FakeVerbCount 'DeletePolicyReports') 'no delete call was made'

    # IN @ids probe before the existing-id snapshot.
    Reset-Fake
    $script:F.Rules['old-r'] = 'old'; $script:F.InIdsBroken = $true
    $res = Import-NcmReports @{} @($relReport) $captureLog $true
    Assert-True ([bool]$res.Failure.Data['InIdsProbe']) 'a broken IN @ids stops the import before anything is created'
    Assert-Equal 0 (Get-FakeVerbCount 'AddPolicyRule') 'no rule was created'
    Reset-Fake
    $script:F.Reports['rA'] = @{ Name = 'Report A'; Policies = @(); Enabled = $true }
    $script:F.InIdsBroken = $true
    Assert-Throws { Get-NcmRemovalPlan @{} @('rA') $captureLog } 'IN @ids sanity probe failed' 'removal planning stops when IN @ids misses the report'

    # Permission preflight.
    Reset-Fake
    Assert-Equal 'ok' (Invoke-NcmPreflight @{} $captureLog) 'preflight ok when GetPolicyReport answers'
    $script:F.Fail['GetPolicyReport'] = "SWIS HTTP 403 from Invoke/Cirrus.PolicyReports/GetPolicyReport`nAccess is denied."
    Assert-Throws { Invoke-NcmPreflight @{} $captureLog } 'WebDownloader NCM role' 'preflight refuses a 403 and names the role'
    $script:F.Fail['GetPolicyReport'] = "SWIS HTTP 500 from Invoke/Cirrus.PolicyReports/GetPolicyReport`nnot found"
    Assert-Equal 'inconclusive' (Invoke-NcmPreflight @{} $captureLog) 'preflight is inconclusive on other errors'

    # StartCaching / UpdateReportStatus refused: logged, not thrown, $false returned.
    Reset-Fake
    $script:F.Reports['id-1'] = @{ Name = 'one'; Policies = @(); Enabled = $true }
    Assert-True (Complete-NcmImport @{} @('id-1') $false $false $captureLog) 'StartCaching true is confirmed'
    $script:F.Fail['StartCaching'] = "SWIS HTTP 403 from Invoke/Cirrus.PolicyReports/StartCaching`nAccess is denied."
    $noteLog.Clear()
    Assert-Equal $false (Complete-NcmImport @{} @('id-1') $false $false $captureLog) 'a refused StartCaching returns false'
    Assert-True ((@($noteLog) -join ' ') -match '(?s)StartCaching failed .*WebUploader') 'the refusal names WebUploader'
    $script:F.Fail.Remove('StartCaching'); $script:F.Results['StartCaching'] = $false
    Assert-Equal $false (Complete-NcmImport @{} @('id-1') $false $false $captureLog) 'StartCaching false is not confirmed'
    $script:F.Fail['UpdateReportStatus'] = "SWIS HTTP 403 from Invoke/Cirrus.PolicyReports/UpdateReportStatus`nAccess is denied."
    Assert-Equal $false (Complete-NcmImport @{} @('id-1') $true $false $captureLog) 'a refused UpdateReportStatus returns false'
    $relText = [System.IO.File]::ReadAllText($relLog)
    Assert-True ($relText.Contains('StartCaching returned true') -and $relText.Contains('StartCaching returned false')) "StartCaching's result is logged"
    Assert-True ($relText.Contains('NCM role needed (2026.2 verb descriptions): WebUploader or higher for StartCaching, UpdateReportStatus')) 'the role table is logged'
    Assert-True ($relText.Contains('IN @ids sanity probe ok before')) 'a passing probe is logged'
    Assert-True (@($relText -split "`n" | Where-Object { $_ -and $_ -cnotmatch $lineRe }).Count -eq 0) 'reliability log lines match the contract'
    $script:LogState.Path = $null

    # --- 13. transport: UTF-8 body, fail-closed pin, scoped callback ---------
    $bodyText = 'Caf' + [char]0xE9 + ' ' + [char]0x2014 + ' ' + [char]0x2713
    $req = New-SwisRequestBody @([ordered]@{ RuleName = $bodyText })
    Assert-Equal 'application/json; charset=utf-8' $req.ContentType 'the body says charset=utf-8'
    Assert-Equal ([System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($req.Text))) ([System.Convert]::ToBase64String($req.Bytes)) 'the body is the UTF-8 bytes of the JSON'
    Assert-True ($req.Text.Contains($bodyText)) 'non-Latin-1 text survives into the body'
    Assert-True ($null -eq (New-SwisRequestBody $null)) 'no body for a call without one'

    $pinnedConn = New-SwisConnection '127.0.0.1' 1 'admin' 'PsSecret-Pin-3307' $false $true ('AB' * 32)
    $plainConn = New-SwisConnection '127.0.0.1' 1 'admin' 'PsSecret-Pin-3307' $false $false $null
    $insecureConn = New-SwisConnection '127.0.0.1' 1 'admin' 'PsSecret-Pin-3307' $false $true $null
    $p7 = Get-SwisTransportPlan $pinnedConn $true
    Assert-True ($p7.Path -eq 'HttpClient' -and -not $p7.SkipCertificateCheck) 'PS 7 pinned: HttpClient, never SkipCertificateCheck (even with -Insecure)'
    $p5 = Get-SwisTransportPlan $pinnedConn $false
    Assert-True ($p5.Path -eq 'RestMethod' -and $p5.ScopedCallback -and -not $p5.SkipCertificateCheck) 'PS 5.1 pinned: Invoke-RestMethod with a scoped callback'
    $i7 = Get-SwisTransportPlan $insecureConn $true
    Assert-True ($i7.Path -eq 'RestMethod' -and $i7.SkipCertificateCheck) 'PS 7 -Insecure without a pin: SkipCertificateCheck'
    $i5 = Get-SwisTransportPlan $insecureConn $false
    Assert-True ($i5.ScopedCallback -and -not $i5.SkipCertificateCheck) 'PS 5.1 -Insecure: scoped accept-all callback'
    $n7 = Get-SwisTransportPlan $plainConn $true
    Assert-True ($n7.Path -eq 'RestMethod' -and -not $n7.SkipCertificateCheck -and -not $n7.ScopedCallback) 'no pin, no -Insecure: the system trust store'

    $sentinel = [System.Net.Security.RemoteCertificateValidationCallback] { param($a, $b, $c, $d) $false }
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $sentinel
    Assert-Throws { Invoke-SwisRest $pinnedConn 'Post' 'Query' @{ query = 'x' } } 'SWIS transport error' 'an unreachable pinned server is a transport error'
    Assert-True ([object]::ReferenceEquals([System.Net.ServicePointManager]::ServerCertificateValidationCallback, $sentinel)) 'the previous ServicePointManager callback is restored after the call'
    $script:ForceHttpClient = $true
    $forcedConn = New-SwisConnection '127.0.0.1' 1 'admin' 'PsSecret-Pin-3307' $false $false ('AB' * 32)
    Assert-Throws { Invoke-SwisRest $forcedConn 'Post' 'Query' @{ query = 'x' } } 'SWIS transport error' 'the HttpClient path reports a transport error too'
    Assert-True ($null -ne $forcedConn.HttpClient -and $null -ne $forcedConn.PinCheck) 'the HttpClient path installs the pin check'
    Assert-True ([object]::ReferenceEquals([System.Net.ServicePointManager]::ServerCertificateValidationCallback, $sentinel)) 'the HttpClient path leaves ServicePointManager alone'
    $script:ForceHttpClient = $false
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null

    if ('System.Security.Cryptography.X509Certificates.CertificateRequest' -as [type]) {
        $rsa = [System.Security.Cryptography.RSA]::Create(2048)
        $csr = New-Object System.Security.Cryptography.X509Certificates.CertificateRequest('CN=SolarWinds-Orion', $rsa,
            [System.Security.Cryptography.HashAlgorithmName]::SHA256, [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
        $cert = $csr.CreateSelfSigned([DateTimeOffset]::UtcNow.AddDays(-1), [DateTimeOffset]::UtcNow.AddDays(1))
        $thumb = [BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash($cert.RawData)) -replace '-', ''
        Assert-True ((New-PinCheck $thumb).Matches($cert)) 'the pin check accepts the pinned certificate'
        Assert-True ((New-PinCheck ('0' * 64)).Matches($cert) -eq $false) 'the pin check refuses any other certificate (fails closed)'
        Assert-True ((New-PinCheck '').Matches($cert) -eq $false) 'an empty pin refuses everything'
        Assert-True ((New-PinCheck ($thumb -replace '(..)(?!$)', '$1:')).Matches($cert)) 'colon-separated fingerprints are accepted'
    }
}
finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output ("{0} passed, {1} failed" -f $script:Passes, $script:Failures.Count)
if ($script:Failures.Count -gt 0) { exit 1 }
exit 0
