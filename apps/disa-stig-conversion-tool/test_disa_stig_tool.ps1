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
}
finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output ("{0} passed, {1} failed" -f $script:Passes, $script:Failures.Count)
if ($script:Failures.Count -gt 0) { exit 1 }
exit 0
