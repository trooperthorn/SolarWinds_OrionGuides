<#
.SYNOPSIS
    Export a monitored-estate inventory to CSV.

.DESCRIPTION
    Produces the report people ask for most: what is monitored, where, on which polling
    engine, and in what state. It is also a worked example of the things that matter when
    querying SWIS for anything large.

    Three of those are worth calling out because they are not obvious:

    Paging. SWQL supports `WITH ROWS a TO b` together with `WITH TOTALROWS`, and this
    script uses them rather than pulling everything in one request. On a large estate a
    single unbounded query can hold a lot of memory on both ends and block for a long
    time. Paging keeps each request small and lets you show progress.

    Status by name. Status is an integer on every entity. Joining Orion.StatusInfo turns
    it into something a reader understands, and keeps the report correct if SolarWinds
    adds a status value later.

    Account limitations. Everything read through SWIS is filtered by the limitations on
    the account you connect as. If this report looks short, check the account before you
    debug the query.

.PARAMETER Hostname
    Name or IP of the primary Orion server.

.PARAMETER Path
    Output CSV path. Defaults to a timestamped file in the current directory.

.PARAMETER Scope
    Which inventory to export.

.PARAMETER PageSize
    Rows per request. Smaller is gentler on the database; larger is fewer round trips.

.EXAMPLE
    .\Export-OrionInventory.ps1 -Hostname orion.example.com -Trusted

.EXAMPLE
    .\Export-OrionInventory.ps1 -Hostname orion.example.com -Scope Volumes -Path disks.csv

.NOTES
    See docs/automation/reporting.md.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Hostname,

    [System.Management.Automation.PSCredential]$Credential,

    [switch]$Trusted,

    [ValidateSet('Nodes', 'Interfaces', 'Volumes', 'Applications')]
    [string]$Scope = 'Nodes',

    [string]$Path,

    [ValidateRange(50, 10000)]
    [int]$PageSize = 1000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module SwisPowerShell

# Each query selects only the columns the report needs. There is no SELECT * in SWQL, and
# naming columns keeps the payload small on a wide entity such as Orion.Nodes, which has
# over a hundred properties.
#
# ORDER BY is on the key column rather than on the caption. Paging without a stable,
# unique sort can repeat or skip rows between pages, and captions are neither.
$queries = @{
    Nodes = @'
SELECT n.NodeID, n.Caption, n.IPAddress, n.DNS, n.SysName, n.Vendor, n.MachineType,
       n.Location, n.Contact, n.ObjectSubType AS PollingMethod, n.SNMPVersion,
       n.Status, s.StatusName, n.UnManaged, n.LastBoot, n.MinutesSinceLastSync,
       n.Engine.ServerName AS PollingEngine
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY n.NodeID
'@
    Interfaces = @'
SELECT i.InterfaceID, i.NodeID, i.Node.Caption AS NodeName, i.Name, i.InterfaceAlias,
       i.InterfaceTypeName, i.InterfaceSpeed, i.AdminStatus, i.OperStatus,
       i.Status, s.StatusName, i.UnManaged, i.InPercentUtil, i.OutPercentUtil
FROM Orion.NPM.Interfaces i
JOIN Orion.StatusInfo s ON i.Status = s.StatusId
ORDER BY i.InterfaceID
'@
    Volumes = @'
SELECT v.VolumeID, v.NodeID, v.Node.Caption AS NodeName, v.Caption AS VolumeName,
       v.VolumeType, v.VolumeSize, v.VolumeSpaceUsed, v.VolumeSpaceAvailable,
       v.VolumePercentUsed, v.Status, s.StatusName, v.UnManaged
FROM Orion.Volumes v
JOIN Orion.StatusInfo s ON v.Status = s.StatusId
ORDER BY v.VolumeID
'@
    Applications = @'
SELECT a.ApplicationID, a.NodeID, a.Node.Caption AS NodeName, a.Name AS ApplicationName,
       a.ApplicationTemplateID, a.Status, s.StatusName, a.UnManaged,
       a.Created, a.LastModified
FROM Orion.APM.Application a
JOIN Orion.StatusInfo s ON a.Status = s.StatusId
ORDER BY a.ApplicationID
'@
}

$swis = if ($Trusted) {
    Connect-Swis -Hostname $Hostname -Trusted
} else {
    if (-not $Credential) { $Credential = Get-Credential -Message "Orion account for $Hostname" }
    Connect-Swis -Hostname $Hostname -Credential $Credential
}

if (-not $Path) {
    $Path = "orion-{0}-{1:yyyyMMdd-HHmmss}.csv" -f $Scope.ToLower(), (Get-Date)
}

$baseQuery = $queries[$Scope]
$rows = [System.Collections.Generic.List[object]]::new()
$start = 1
$total = $null

do {
    $end = $start + $PageSize - 1

    # WITH TOTALROWS makes the response carry the unpaged count, so the first page tells
    # us how many pages there are. It costs an extra count on the server, so ask for it
    # once rather than on every page.
    $paged = if ($null -eq $total) {
        "$baseQuery WITH ROWS $start TO $end WITH TOTALROWS"
    } else {
        "$baseQuery WITH ROWS $start TO $end"
    }

    $page = @(Get-SwisData -SwisConnection $swis -Query $paged)

    if ($null -eq $total) {
        # SwisPowerShell surfaces the row objects rather than the envelope, so the total
        # is not directly available here. Fall back to a count query, which is cheap
        # compared to the export itself and gives an accurate progress denominator.
        $countQuery = $baseQuery -replace '(?s)^SELECT.*?FROM', 'SELECT COUNT(1) FROM' -replace '(?s)ORDER BY.*$', ''
        $total = [int](Get-SwisData -SwisConnection $swis -Query $countQuery)
        Write-Information "$total $Scope row(s) to export" -InformationAction Continue
    }

    if ($page.Count -eq 0) { break }
    $rows.AddRange($page)

    $pct = if ($total -gt 0) { [Math]::Min(100, [int](($rows.Count / $total) * 100)) } else { 100 }
    Write-Progress -Activity "Exporting $Scope" -Status "$($rows.Count) of $total" -PercentComplete $pct

    $start = $end + 1
} while ($rows.Count -lt $total -and $page.Count -eq $PageSize)

Write-Progress -Activity "Exporting $Scope" -Completed

if ($rows.Count -eq 0) {
    Write-Warning @"
No rows returned. Before assuming the query is wrong, check:
  - the account's limitations, which silently filter every read through SWIS
  - whether the module for this scope is installed ($Scope needs NPM or SAM for
    interfaces and applications respectively)
"@
    return
}

$rows | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
Write-Information "Wrote $($rows.Count) row(s) to $Path" -InformationAction Continue

Get-Item $Path
