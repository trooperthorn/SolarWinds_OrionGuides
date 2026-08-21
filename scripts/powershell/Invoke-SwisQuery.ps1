<#
.SYNOPSIS
    Connect to SWIS and run a SWQL query, with the three authentication modes.

.DESCRIPTION
    The smallest useful end-to-end example. Use it to confirm connectivity and
    credentials before debugging anything more complicated.

    Requires the SwisPowerShell module:
        Install-Module -Name SwisPowerShell -Scope CurrentUser

.PARAMETER Hostname
    Name or IP of the primary Orion server. Do not include a port.

.PARAMETER Query
    The SWQL to run. Bind values with @name and pass them in -Parameters rather
    than concatenating strings into the query.

.EXAMPLE
    .\Invoke-SwisQuery.ps1 -Hostname orion.example.com -Credential (Get-Credential)

.EXAMPLE
    .\Invoke-SwisQuery.ps1 -Hostname orion.example.com -Trusted `
        -Query 'SELECT TOP 5 Caption, IPAddress FROM Orion.Nodes WHERE Status = @s' `
        -Parameters @{ s = 2 }

.NOTES
    Documented against SolarWinds Platform 2026.2. See docs/swis/connecting.md.
#>
[CmdletBinding(DefaultParameterSetName = 'Credential')]
param(
    [Parameter(Mandatory)]
    [string]$Hostname,

    [Parameter(ParameterSetName = 'Credential')]
    [System.Management.Automation.PSCredential]$Credential,

    # Use the current Windows identity (Kerberos). Not supported for a local
    # connection on the Orion server itself; connect remotely or use -Certificate.
    [Parameter(ParameterSetName = 'Trusted')]
    [switch]$Trusted,

    # Use the SolarWinds-Orion client certificate. Generally only available when
    # running on the Orion server, elevated, so the private key can be read.
    [Parameter(ParameterSetName = 'Certificate')]
    [switch]$Certificate,

    [string]$Query = 'SELECT TOP 10 NodeID, Caption, IPAddress, Status FROM Orion.Nodes ORDER BY Caption',

    [hashtable]$Parameters = @{}
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name SwisPowerShell)) {
    throw "The SwisPowerShell module is not installed. Run: Install-Module -Name SwisPowerShell -Scope CurrentUser"
}
Import-Module SwisPowerShell

$swis = switch ($PSCmdlet.ParameterSetName) {
    'Trusted'     { Connect-Swis -Hostname $Hostname -Trusted }
    'Certificate' { Connect-Swis -Hostname $Hostname -Certificate }
    default {
        if (-not $Credential) { $Credential = Get-Credential -Message "Orion account for $Hostname" }
        Connect-Swis -Hostname $Hostname -Credential $Credential
    }
}

Write-Verbose "Connected to $Hostname"

# Get-SwisData returns rows as objects. Passing -Parameters keeps values out of the
# query text, which lets SQL Server reuse the plan and removes an injection class.
$rows = if ($Parameters.Count -gt 0) {
    Get-SwisData -SwisConnection $swis -Query $Query -Parameters $Parameters
} else {
    Get-SwisData -SwisConnection $swis -Query $Query
}

$rows
Write-Verbose ("{0} row(s) returned" -f @($rows).Count)
