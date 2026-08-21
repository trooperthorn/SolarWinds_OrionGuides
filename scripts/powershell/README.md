# PowerShell examples

For the `SwisPowerShell` module, which is the richest client and the one SolarWinds' own
samples use. It speaks the SOAP endpoint on port 17777 and supports Orion local accounts,
Windows/Active Directory authentication, and client certificates.

```powershell
Install-Module -Name SwisPowerShell -Scope CurrentUser
```

| Script | Does |
| --- | --- |
| [Invoke-SwisQuery.ps1](Invoke-SwisQuery.ps1) | Connect and run a query, showing all three authentication modes |
| [Export-OrionInventory.ps1](Export-OrionInventory.ps1) | Export nodes, interfaces, volumes or applications to CSV, with paging |
| [Set-NodeMaintenanceWindow.ps1](Set-NodeMaintenanceWindow.ps1) | Unmanage and remanage nodes through the Invoke interface |

## The cmdlets these use

| Cmdlet | Interface |
| --- | --- |
| `Connect-Swis` | Opens the connection |
| `Get-SwisData` | Runs a SWQL query, returns rows |
| `Get-SwisObject` | Reads one entity by URI |
| `New-SwisObject` | Creates an entity, returns its URI |
| `Set-SwisObject` | Updates properties on an entity |
| `Remove-SwisObject` | Deletes an entity |
| `Invoke-SwisVerb` | Invokes a verb with a positional argument array |

`Invoke-SwisVerb` takes its arguments as an ordered array, because that is what travels on
the wire. The names in the documentation are for humans; position is the contract. Check a
signature before calling:

```bash
python3 ../../tools/schema_query.py verb Orion.Nodes Unmanage
```

## Conventions

`Set-NodeMaintenanceWindow.ps1` supports `-WhatIf` and `-Confirm` through
`SupportsShouldProcess`, because it changes production state. Any script here that writes
should do the same. None of them hard-code credentials; they prompt or accept a
`PSCredential`.

The official SolarWinds samples are worth reading alongside these:
<https://github.com/solarwinds/OrionSDK/tree/master/Samples/PowerShell>.
