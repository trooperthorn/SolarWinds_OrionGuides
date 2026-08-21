<#
.SYNOPSIS
    Put nodes into a maintenance window (unmanage) or bring them back (remanage).

.DESCRIPTION
    Wraps the Orion.Nodes Unmanage and Remanage verbs. Unmanaged nodes stop being
    polled and stop alerting, which is what you want around a planned change.

    Verb signatures, verified against the 2026.2 schema:

        Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative,
                             allowOverlapping)   requires the allowUnmanage right
        Orion.Nodes.Remanage(netObjectId)        requires the allowUnmanage right

    Arguments are POSITIONAL. Invoke-SwisVerb sends an ordered array, so the order
    above is the contract; the parameter names exist only for documentation.

    netObjectId is a NetObject string, not a bare id: node 42 is "N:42". The prefix
    comes from the NetObjectType table in docs/schema/netobject-types.md.

    Times are sent as DateTime values and handled in UTC. This script converts to UTC
    explicitly rather than relying on the caller's locale, because passing local time
    is the single most common cause of a window that opens at the wrong hour.

.PARAMETER Hostname
    Name or IP of the primary Orion server.

.PARAMETER NodeId
    One or more NodeID values. Accepts pipeline input.

.PARAMETER Hours
    Length of the maintenance window, starting now.

.PARAMETER Until
    Explicit end time instead of -Hours. Interpreted in local time and converted to UTC.

.PARAMETER Remanage
    Bring the nodes back under management immediately.

.EXAMPLE
    # Suppress node 42 for the next four hours
    .\Set-NodeMaintenanceWindow.ps1 -Hostname orion.example.com -NodeId 42 -Hours 4

.EXAMPLE
    # Unmanage every node in a group ahead of a datacentre move
    $swis = Connect-Swis -Hostname orion.example.com -Trusted
    $ids = Get-SwisData $swis @"
        SELECT cm.MemberPrimaryID
        FROM Orion.ContainerMembers cm
        WHERE cm.Container.Name = 'DC2 Migration'
          AND cm.MemberEntityType = 'Orion.Nodes'
"@
    $ids | .\Set-NodeMaintenanceWindow.ps1 -Hostname orion.example.com -Hours 8

.EXAMPLE
    # End the window early
    .\Set-NodeMaintenanceWindow.ps1 -Hostname orion.example.com -NodeId 42 -Remanage

.NOTES
    See docs/automation/maintenance-mode.md.
#>
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High', DefaultParameterSetName = 'Duration')]
param(
    [Parameter(Mandatory)]
    [string]$Hostname,

    [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName)]
    [int[]]$NodeId,

    [System.Management.Automation.PSCredential]$Credential,

    [switch]$Trusted,

    [Parameter(ParameterSetName = 'Duration')]
    [ValidateRange(1, 8760)]
    [int]$Hours = 1,

    [Parameter(ParameterSetName = 'Until')]
    [datetime]$Until,

    [Parameter(ParameterSetName = 'Remanage')]
    [switch]$Remanage,

    # Allow a new window even when one is already open for the node.
    [switch]$AllowOverlapping
)

begin {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
    Import-Module SwisPowerShell

    $swis = if ($Trusted) {
        Connect-Swis -Hostname $Hostname -Trusted
    } else {
        if (-not $Credential) { $Credential = Get-Credential -Message "Orion account for $Hostname" }
        Connect-Swis -Hostname $Hostname -Credential $Credential
    }

    $startUtc = [datetime]::UtcNow
    $endUtc = if ($PSCmdlet.ParameterSetName -eq 'Until') { $Until.ToUniversalTime() } else { $startUtc.AddHours($Hours) }
    $processed = 0
}

process {
    foreach ($id in $NodeId) {
        $netObjectId = "N:$id"

        # Resolve the caption first so the confirmation prompt and the log name the node
        # rather than a bare number. This also fails early on a bad id.
        $caption = Get-SwisData -SwisConnection $swis `
            -Query 'SELECT Caption FROM Orion.Nodes WHERE NodeID = @id' `
            -Parameters @{ id = $id }

        if (-not $caption) {
            Write-Warning "No node with NodeID $id; skipping."
            continue
        }

        if ($Remanage) {
            if ($PSCmdlet.ShouldProcess("$caption ($netObjectId)", 'Remanage')) {
                Invoke-SwisVerb $swis 'Orion.Nodes' 'Remanage' @($netObjectId) | Out-Null
                Write-Information "Remanaged $caption" -InformationAction Continue
                $processed++
            }
        }
        else {
            $target = "$caption ($netObjectId)"
            $action = "Unmanage until $($endUtc.ToString('u'))"
            if ($PSCmdlet.ShouldProcess($target, $action)) {
                # isRelative = $false means the two times are absolute, which is why they
                # are converted to UTC above.
                Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
                    $netObjectId,
                    $startUtc,
                    $endUtc,
                    $false,
                    [bool]$AllowOverlapping
                ) | Out-Null
                Write-Information "Unmanaged $caption until $($endUtc.ToString('u')) UTC" -InformationAction Continue
                $processed++
            }
        }
    }
}

end {
    Write-Information "$processed node(s) processed." -InformationAction Continue

    # Confirm the result rather than trusting the verb call silently succeeded.
    Get-SwisData -SwisConnection $swis -Query @'
SELECT Caption, UnManaged, UnManageFrom, UnManageUntil
FROM Orion.Nodes
WHERE NodeID IN @ids
'@ -Parameters @{ ids = $NodeId }
}
