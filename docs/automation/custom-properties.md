# Custom properties

A custom property is an extra column you add to an Orion object type: `DataCentre` on nodes,
`Owner` on applications, `Bitlocker_Enabled` on volumes. Once defined, it behaves like any
other column. You can filter on it, group by it, drive alert scopes and group membership from
it, and put it in a report.

This page covers the whole lifecycle: defining a property, populating it, and querying it.

## The one structural fact to hold on to

**Custom properties have two halves, and each half uses a different SWIS interface.**

| Half | What it is | Interface | Entity |
|:---|:---|:---|:---|
| The **definition** | "Nodes have a column called `DataCentre`, a 128-character string, optionally restricted to a list of values" | Invoke, through verbs | `Orion.NodesCustomProperties` |
| The **value** | "Node 42's `DataCentre` is `London`" | CRUD update | The node's `/CustomProperties` URI |

Getting this backwards is the usual source of confusion. You cannot create a definition with
a CRUD create, and you cannot set a value with a verb.

There is a second consequence worth stating early: **custom property names are not schema
facts**. They are created per installation, they are not in the published schema, and so
this repository cannot verify them. `python3 tools/schema_query.py show Orion.NodesCustomProperties`
returns exactly one property, `NodeID`, because that is all SolarWinds ships. Anything else
on that entity was added by someone at your site. Queries in this page that use example
property names are shown as plain text rather than as checked SWQL for that reason.

## The entities

Twenty-five entities inherit from `System.CustomPropertiesEntity` in 2026.2, one per object
type that supports custom properties. Each is reached from its parent through a
`CustomProperties` navigation property.

| Object type | Custom properties entity | Navigation from |
|:---|:---|:---|
| Nodes | `Orion.NodesCustomProperties` | `Orion.Nodes.CustomProperties` |
| Interfaces | `Orion.NPM.InterfacesCustomProperties` | `Orion.NPM.Interfaces.CustomProperties` |
| Volumes | `Orion.VolumesCustomProperties` | `Orion.Volumes.CustomProperties` |
| Applications | `Orion.APM.ApplicationCustomProperties` | `Orion.APM.Application.CustomProperties` |
| Groups | `Orion.GroupCustomProperties` | |
| Alerts | `Orion.AlertConfigurationsCustomProperties` | |
| Reports | `Orion.ReportsCustomProperties` | |
| WPM recordings | `Orion.SEUM.RecordingCustomProperties` | |
| WPM transactions | `Orion.SEUM.TransactionCustomProperties` | |
| IPAM nodes | `IPAM.NodesCustomProperties` | |
| IPAM groups | `IPAM.GroupsCustomProperties` | |
| SRM file shares | `Orion.SRM.FileShareCustomProperties` | |
| SRM LUNs | `Orion.SRM.LUNCustomProperties` | |
| SRM pools | `Orion.SRM.PoolCustomProperties` | |
| SRM providers | `Orion.SRM.ProviderCustomProperties` | |
| SRM arrays | `Orion.SRM.StorageArrayCustomProperties` | |
| SRM controllers | `Orion.SRM.StorageControllerCustomProperties` | |
| SRM controller ports | `Orion.SRM.StorageControllerPortCustomProperties` | |
| SRM virtual servers | `Orion.SRM.VServersCustomProperties` | |
| SRM volumes | `Orion.SRM.VolumeCustomProperties` | |
| VIM clusters | `Orion.VIM.ClustersCustomProperties` | |
| VIM datacenters | `Orion.VIM.DataCentersCustomProperties` | |
| VIM datastores | `Orion.VIM.DatastoresCustomProperties` | |
| VIM hosts | `Orion.VIM.HostsCustomProperties` | |
| VIM virtual machines | `Orion.VIM.VirtualMachinesCustomProperties` | |

Get the current list on any version with:

```bash
python3 tools/schema_query.py children System.CustomPropertiesEntity
```

`IPAM.AttrDefine` is a twenty-sixth entity carrying custom property verbs, but it does not
inherit from `System.CustomPropertiesEntity` and uses a different verb set:
`AddCustomProperty(propertyName, description, maxStringLength, attributeType, linkTitle, addToIpAddress, addToGroups)`,
`UpdateCustomProperty(propertyName, description, maxStringLength, linkTitle, addToIpAddress, addToGroups)`
and `DeleteCustomProperty(propertyName)`. All three return `boolean`. See
[../modules/ipam.md](../modules/ipam.md).

Access control on `Orion.NodesCustomProperties` in 2026.2:

| Operations | Required right |
|:---|:---|
| `read` | `everyone` |
| `read`, `update` | `manageNodes` |
| `read`, `update`, `invoke` | `admin` |

So setting a *value* needs `manageNodes`, and creating or changing a *definition* needs
`admin`. There is no `create` or `delete` on the entity at all: the custom-properties row
exists because the node exists.

## Defining a property

### CreateCustomProperty

Sixteen parameters in 2026.2, the first ten required, and six of those ten documented as
unused. This is the verb that most rewards looking up the signature.

```bash
python3 tools/schema_query.py verb Orion.NodesCustomProperties CreateCustomProperty
```

```text
Orion.NodesCustomProperties.CreateCustomProperty(
    PropertyName, Description, ValueType, Size, ValidRange, Parser, Header,
    Alignment, Format, Units, Usages?, Mandatory?, Default?, SourceId?,
    SourceName?, DisplayName?) -> System.Void
```

| # | Name | Type | Required | What to pass |
|---:|:---|:---|:---|:---|
| 0 | `PropertyName` | string | yes | The column name. |
| 1 | `Description` | string | yes | Shown in the editing UI. |
| 2 | `ValueType` | string | yes | One of `string`, `integer`, `datetime`, `single`, `double`, `boolean`. |
| 3 | `Size` | number | yes | Maximum length in characters for `string`. Ignored for other types. |
| 4 | `ValidRange` | string | yes | Unused. Pass null. |
| 5 | `Parser` | string | yes | Unused. Pass null. |
| 6 | `Header` | string | yes | Unused. Pass null. |
| 7 | `Alignment` | string | yes | Unused. Pass null. |
| 8 | `Format` | string | yes | Unused. Pass null. |
| 9 | `Units` | string | yes | Unused. Pass null. |
| 10 | `Usages` | `array<KeyValuePair<string,bool>>` | no | Optional. The official documentation says you can pass null. |
| 11 | `Mandatory` | boolean | no | If true, the Add Node wizard requires a value at node creation time. |
| 12 | `Default` | string | no | Default value for new nodes. |
| 13 | `SourceId` | string | no | |
| 14 | `SourceName` | string | no | |
| 15 | `DisplayName` | string | no | |

The allowed `ValueType` strings and the "unused, pass null" descriptions for positions 4 to 9
come from SolarWinds'
[Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
page, which is the authority for them. They are not recorded in the schema data.

```powershell
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname 'orion.example.com' -Trusted

Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'CreateCustomProperty' @(
    'DataCentre',                            # PropertyName
    'Physical datacentre the node lives in', # Description
    'string',                                # ValueType
    128,                                     # Size
    $null, $null, $null, $null, $null, $null # ValidRange..Units, all unused
) | Out-Null
```

```python
swis.invoke(
    "Orion.NodesCustomProperties", "CreateCustomProperty",
    "DataCentre",
    "Physical datacentre the node lives in",
    "string",
    128,
    None, None, None, None, None, None,
)
```

```bash
curl -sS -X POST \
  -u 'admin:...' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '["DataCentre","Physical datacentre the node lives in","string",128,null,null,null,null,null,null]' \
  'https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.NodesCustomProperties/CreateCustomProperty'
```

The call stops after position 9 because everything from `Usages` on is optional. If you do
need `Mandatory` or `Default`, you must also supply `Usages` in position 10, because
arguments are positional and you cannot skip one. Passing `$null` for `Usages` is what the
official documentation recommends:

```powershell
Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'CreateCustomProperty' @(
    'DataCentre', 'Physical datacentre', 'string', 128,
    $null, $null, $null, $null, $null, $null,
    $null,          # Usages
    $true,          # Mandatory
    'Unassigned'    # Default
) | Out-Null
```

`Usages` is typed `array<KeyValuePair<string,bool>>`. The schema does not publish how that
serialises over REST and this repository has no live server to determine it, so the safe
value is null. If you need it, define the property once through the web console and then read
back what the platform stored, using the introspection queries below.

### CreateCustomPropertyWithValues

Same list with one extra parameter, **`Value`, inserted between `Units` and `Usages`**, which
shifts every optional parameter by one position. Note the singular name in the 2026.2
schema; older documentation calls it `Values`.

```text
Orion.NodesCustomProperties.CreateCustomPropertyWithValues(
    PropertyName, Description, ValueType, Size, ValidRange, Parser, Header,
    Alignment, Format, Units, Value, Usages?, Mandatory?, Default?, SourceId?,
    SourceName?, DisplayName?) -> System.Void
```

`Value` is `array<string>` and it is required. A property created this way is restricted to
the listed values, which is what turns a free-text column into something you can group and
report on reliably.

```powershell
$values = [string[]]@('London', 'Frankfurt', 'Singapore')

Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'CreateCustomPropertyWithValues' @(
    'DataCentre', 'Physical datacentre', 'string', 128,
    $null, $null, $null, $null, $null, $null,
    $values
) | Out-Null
```

```python
swis.invoke(
    "Orion.NodesCustomProperties", "CreateCustomPropertyWithValues",
    "DataCentre", "Physical datacentre", "string", 128,
    None, None, None, None, None, None,
    ["London", "Frankfurt", "Singapore"],
)
```

In PowerShell, cast the list to `[string[]]` explicitly. `Invoke-SwisVerb` takes an array of
arguments, and a bare PowerShell array in that position can be flattened into separate
arguments rather than sent as one array-typed argument. The cast is what keeps it as one.

### ValidateCustomProperty

A dry run. It returns a `CustomPropertyValidationResult` rather than changing anything, so it
is the right thing to call before creating a property in an automated pipeline.

```text
Orion.NodesCustomProperties.ValidateCustomProperty(
    PropertyName, Description, ValueType, Size, Value, Usages?, propertyDisplayName?)
    -> SolarWinds.Orion.Core.Common.Models.CustomPropertyValidationResult
```

Seven parameters, five required, and the list is *not* a prefix of `CreateCustomProperty`:
`ValidRange` through `Units` are absent and `Value` sits at position 4. Do not reuse the
create argument array.

```powershell
$result = Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'ValidateCustomProperty' @(
    'DataCentre', 'Physical datacentre', 'string', 128, [string[]]@('London', 'Frankfurt')
)
```

Only 14 of the 25 entities declare this verb. `Orion.NodesCustomProperties`,
`Orion.VolumesCustomProperties`, `Orion.GroupCustomProperties`,
`Orion.ReportsCustomProperties`, `Orion.AlertConfigurationsCustomProperties` and the nine
`Orion.SRM.*` ones have it; the `Orion.VIM.*`, `Orion.NPM.InterfacesCustomProperties`,
`Orion.APM.ApplicationCustomProperties`, `Orion.SEUM.*` and `IPAM.*` ones do not. Check
before relying on it:

```bash
python3 tools/schema_query.py verbs --grep ValidateCustomProperty
```

The shape of `CustomPropertyValidationResult` is not published in the schema data. Inspect
what your server returns rather than assuming field names.

### ModifyCustomProperty

```text
Orion.NodesCustomProperties.ModifyCustomProperty(
    PropertyName, Description, Size, Values, Usages?, Mandatory?, Default?,
    SourceId?, SourceName?, propertyDisplayName?) -> System.Void
```

| # | Name | Type | Required |
|---:|:---|:---|:---|
| 0 | `PropertyName` | string | yes |
| 1 | `Description` | string | yes |
| 2 | `Size` | number | yes |
| 3 | `Values` | `array<string>` | yes |
| 4 | `Usages` | `array<KeyValuePair<string,bool>>` | no |
| 5 | `Mandatory` | boolean | no |
| 6 | `Default` | string | no |
| 7 | `SourceId` | string | no |
| 8 | `SourceName` | string | no |
| 9 | `propertyDisplayName` | string | no |

Two things to notice. `ValueType` is absent, so you cannot change a property's data type this
way. And **`Values` replaces the list, it does not add to it.** An empty or null list has the
effect of allowing any value, which is how you remove a restriction.

Adding one allowed value therefore means read, append, write back. This is SolarWinds' own
recipe from the Managing Custom Properties page, adapted:

```powershell
$propertyName = 'DataCentre'

$existing = Get-SwisData $swis @'
SELECT Description, MaxLength
FROM Orion.CustomProperty
WHERE Table = 'NodesCustomProperties' AND Field = @property
'@ @{ property = $propertyName }

[array]$values = Get-SwisData $swis @'
SELECT Value
FROM Orion.CustomPropertyValues
WHERE Table = 'NodesCustomProperties' AND Field = @property
'@ @{ property = $propertyName }

$values += 'Dublin'

Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'ModifyCustomProperty' @(
    $propertyName,
    $existing.Description,
    $existing.MaxLength,
    [string[]]$values
) | Out-Null
```

Skipping the read is the classic way to wipe an allowed-value list. If you pass
`@('Dublin')`, `Dublin` becomes the only permitted value.

### DeleteCustomProperty

```text
Orion.NodesCustomProperties.DeleteCustomProperty(PropertyName) -> System.Void
```

One argument on every `System.CustomPropertiesEntity` descendant. This drops the column and
every value in it across every node. It is not reversible and there is no per-object
confirmation, so find out what you are about to lose first:

```text
SELECT COUNT(n.NodeID) AS NodesWithValue
FROM Orion.Nodes n
WHERE n.CustomProperties.DataCentre IS NOT NULL
```

```powershell
Invoke-SwisVerb $swis 'Orion.NodesCustomProperties' 'DeleteCustomProperty' @('DataCentre') | Out-Null
```

Check nothing depends on it before you delete: alert definitions, group definitions, reports
and account limitations can all be scoped by a custom property, and none of them will tell
you in advance.

`Orion.APM.ApplicationCustomProperties.DeleteCustomProperty` takes three arguments,
`(propertyName, sourceId, sourceName)`, not one. Do not assume the signature carries across
entities.

### The signatures are not identical across entities

The `Orion.*` and `IPAM.*` families use `PropertyName`, `Description`, `Usages`, `Default`
and add `DisplayName`. `Orion.APM.ApplicationCustomProperties` is different in several ways
at once: lower-camel parameter names, `usageFlags` instead of `Usages`, `defaultValue`
instead of `Default`, 15 parameters instead of 16, no `DisplayName`, and `usageFlags`,
`mandatory` and `defaultValue` marked required rather than optional.

```text
Orion.APM.ApplicationCustomProperties.CreateCustomProperty(
    propertyName, description, valueType, size, validRange, parser, header,
    alignment, format, units, usageFlags, mandatory, defaultValue, sourceId,
    sourceName) -> System.Void
```

Check each entity you target:

```bash
python3 tools/schema_query.py verb Orion.APM.ApplicationCustomProperties CreateCustomProperty
python3 tools/schema_query.py verb Orion.VolumesCustomProperties CreateCustomProperty
```

## Discovering what is defined

Three entities describe the definitions themselves, and all three are readable through plain
SWQL. This is how you find out what exists on a server you did not build.

`Orion.CustomProperty` is the catalogue:

```sql
SELECT
    cp.Table,
    cp.Field,
    cp.DataType,
    cp.MaxLength,
    cp.Description,
    cp.Mandatory,
    cp.Default,
    cp.TargetEntity,
    cp.DisplayName
FROM Orion.CustomProperty cp
ORDER BY cp.Table, cp.Field
```

`Table` is the storage table name, which is the custom properties entity name without its
namespace: `NodesCustomProperties`, `InterfacesCustomProperties`, `VolumesCustomProperties`.
`TargetEntity` names the entity the property applies to. Filter to one object type:

```sql
SELECT cp.Field, cp.DataType, cp.MaxLength, cp.Description, cp.Mandatory, cp.Default
FROM Orion.CustomProperty cp
WHERE cp.Table = 'NodesCustomProperties'
ORDER BY cp.Field
```

`Orion.CustomPropertyValues` holds the allowed-value lists:

```sql
SELECT v.Table, v.Field, v.Value
FROM Orion.CustomPropertyValues v
WHERE v.Table = 'NodesCustomProperties'
  AND v.Field = @property
ORDER BY v.Value
```

Every restricted property on the system, with its list:

```sql
SELECT v.Table, v.Field, COUNT(v.Value) AS AllowedValues
FROM Orion.CustomPropertyValues v
GROUP BY v.Table, v.Field
ORDER BY v.Table, v.Field
```

`Orion.CustomPropertySources` records where a property came from, carrying `Table`, `Field`,
`Id` and `FriendlyName`:

```sql
SELECT s.Table, s.Field, s.Id, s.FriendlyName
FROM Orion.CustomPropertySources s
ORDER BY s.Table, s.Field
```

`Orion.CustomProperty` also navigates to `Orion.CustomPropertyUsage` through a `Usage`
reference and to `Orion.CustomPropertySources` through `Source`. `Orion.CustomPropertyUsage`
declares no properties of its own in 2026.2, so there is nothing useful to select from it
here.

Confirming a definition landed after creating it is the same query:

```sql
SELECT cp.Field, cp.DataType, cp.MaxLength, cp.Mandatory, cp.Default
FROM Orion.CustomProperty cp
WHERE cp.Table = 'NodesCustomProperties'
  AND cp.Field = @property
```

## Setting values

A value is a CRUD update against the object's `CustomProperties` URI. The URI is the object's
own URI with `/CustomProperties` appended, which works because `CustomProperties` is a real
`System.Hosting` navigation property, not a naming convention.

Get the URI from a query. Do not build it by string formatting: the system identifier
component is fixed per installation.

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

```powershell
$nodeUri = Get-SwisData $swis `
    'SELECT Uri FROM Orion.Nodes WHERE NodeID = @nodeId' @{ nodeId = 42 }

Set-SwisObject $swis -Uri "$nodeUri/CustomProperties" -Properties @{
    DataCentre = 'London'
    Owner      = 'Network Engineering'
}
```

```python
node_uri = swis.query(
    "SELECT Uri FROM Orion.Nodes WHERE NodeID = @id", id=42
)["results"][0]["Uri"]

swis.update(node_uri + "/CustomProperties", DataCentre="London", Owner="Network Engineering")
```

```bash
curl -sS -X POST \
  -u 'svc-automation:...' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '{"DataCentre":"London"}' \
  'https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/swis%3A%2F%2Fabcdef%2FOrion%2FOrion.Nodes%2FNodeID%3D42%2FCustomProperties'
```

The update is partial: properties you do not name are left alone, so setting one custom
property does not clear the others.

SolarWinds' own
[`CRUD.SettingCustomProperty.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/CRUD.SettingCustomProperty.ps1)
sample does the same thing for a node and for an interface. The interface case shows the
pattern nesting, because an interface URI is itself built from a node URI:

```text
swis://abcdef/Orion/Orion.Nodes/NodeID=8/CustomProperties
swis://abcdef/Orion/Orion.Nodes/NodeID=8/Interfaces/InterfaceID=58/CustomProperties
```

Both take the same `Set-SwisObject` call. See [../swis/uris.md](../swis/uris.md).

### Many objects at once

`BulkUpdate` takes a list of URIs and one property bag, so the URIs to send are the object
URIs with `/CustomProperties` appended:

```python
rows = swis.query("""
    SELECT NodeID, Caption, Uri
    FROM Orion.Nodes
    WHERE Location = @loc
    ORDER BY Caption
""", loc="London DC")["results"]

print(f"about to tag {len(rows)} nodes")     # read this number before continuing

cp_uris = [r["Uri"] + "/CustomProperties" for r in rows]
for i in range(0, len(cp_uris), 200):
    swis.bulkupdate(cp_uris[i:i + 200], DataCentre="London")
```

```powershell
$nodes = Get-SwisData $swis @'
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.Location = @loc
'@ @{ loc = 'London DC' }

$nodes | Format-Table NodeID, Caption
Write-Warning "About to tag $($nodes.Count) node(s)."

foreach ($n in $nodes) {
    Set-SwisObject $swis -Uri "$($n.Uri)/CustomProperties" -Properties @{ DataCentre = 'London' }
}
```

`BulkUpdate` returns an empty body and no per-item result, so read back afterwards. Because
the column name is site-specific, that read-back query is shown as plain text:

```text
SELECT n.NodeID, n.Caption, n.CustomProperties.DataCentre
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

See [../swis/bulk-operations.md](../swis/bulk-operations.md).

### The idempotent form

SolarWinds'
[`SetVolumeCustomProperty.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/SetVolumeCustomProperty.ps1)
sample reads the current value and skips objects that already have it. That makes a rerun
after a partial failure free rather than another full pass of writes:

```powershell
# The SELECT here uses a site-specific custom property name, so substitute your own.
$volumes = Get-SwisData $swis @'
SELECT TOP 100
    v.VolumeID,
    v.Uri AS VolumeUri,
    v.Caption AS VolumeName,
    vcp.Bitlocker_Enabled
FROM Orion.Volumes v
JOIN Orion.VolumesCustomProperties vcp ON v.VolumeID = vcp.VolumeID
ORDER BY v.VolumeID
'@

foreach ($v in $volumes) {
    if ($v.Bitlocker_Enabled -eq 'true') { continue }
    Write-Host "Setting [$($v.VolumeName)] Bitlocker_Enabled to true"
    Set-SwisObject $swis -Uri ('{0}/CustomProperties' -f $v.VolumeUri) -Properties @{ Bitlocker_Enabled = 'true' }
}
```

## Querying and filtering on custom properties

Two spellings, and they mean the same thing.

**Navigation form.** Shorter, and the one you will see most often. `CustomProperties` is a
navigation property on the object, so the custom column hangs off it:

```text
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    n.CustomProperties.DataCentre,
    n.CustomProperties.Owner
FROM Orion.Nodes n
WHERE n.CustomProperties.DataCentre = @dc
ORDER BY n.Caption
```

**Explicit join form.** More verbose, but it lets you alias the side table, use it in
aggregates cleanly, and select the custom-properties row's own `Uri` so you can write to it
in the same pass:

```text
SELECT
    n.NodeID,
    n.Caption,
    ncp.DataCentre,
    ncp.Uri AS CustomPropertiesUri
FROM Orion.Nodes n
JOIN Orion.NodesCustomProperties ncp ON ncp.NodeID = n.NodeID
WHERE ncp.DataCentre = @dc
ORDER BY n.Caption
```

The join key is the object's key property, which is `NodeID` for nodes, `InterfaceID` for
interfaces, `VolumeID` for volumes, `ApplicationID` for applications. This join key part *is*
verifiable, so the shape without the custom column checks out as real SWQL:

```sql
SELECT n.NodeID, n.Caption, ncp.Uri AS CustomPropertiesUri
FROM Orion.Nodes n
JOIN Orion.NodesCustomProperties ncp ON ncp.NodeID = n.NodeID
ORDER BY n.Caption
```

Useful shapes, all shown as plain text because they name a site-specific column:

```text
-- Coverage: which nodes are missing a value that they ought to have
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.CustomProperties.DataCentre IS NULL
ORDER BY n.Caption
```

```text
-- Inventory rollup by tag
SELECT n.CustomProperties.DataCentre AS DataCentre, COUNT(n.NodeID) AS Nodes
FROM Orion.Nodes n
GROUP BY n.CustomProperties.DataCentre
ORDER BY COUNT(n.NodeID) DESC
```

```text
-- Tag combined with a real column, which is the everyday case
SELECT n.Caption, n.Status, si.StatusName, n.CustomProperties.Owner
FROM Orion.Nodes n
JOIN Orion.StatusInfo si ON n.Status = si.StatusId
WHERE n.CustomProperties.DataCentre = @dc
  AND n.Status <> 1
ORDER BY si.Ranking, n.Caption
```

```text
-- Walking from a child object up to the node's tag
SELECT i.InterfaceID, i.Caption, i.Node.Caption AS NodeCaption, i.Node.CustomProperties.DataCentre
FROM Orion.NPM.Interfaces i
WHERE i.Node.CustomProperties.DataCentre = @dc
ORDER BY i.Node.Caption, i.Caption
```

Because these cannot be validated against the published schema, check them on your own server
before putting them in an alert or a report. The one command that tells you what is actually
there:

```sql
SELECT cp.Field, cp.DataType, cp.MaxLength
FROM Orion.CustomProperty cp
WHERE cp.Table = 'NodesCustomProperties'
ORDER BY cp.Field
```

## Things that go wrong

- **Trying to create a definition with CRUD.** `Orion.NodesCustomProperties` declares no
  `create` operation at all. Definitions come from `CreateCustomProperty`.
- **Trying to set a value with a verb.** Values are a CRUD update on the `/CustomProperties`
  URI.
- **Forgetting `/CustomProperties` on the URI.** Updating the node URI with a custom property
  name in the bag fails, because the property is not on `Orion.Nodes`.
- **`ModifyCustomProperty` wiping the allowed-value list.** It replaces. Read, append, write.
- **Reusing the create argument array for `ValidateCustomProperty`.** Different list,
  different order.
- **Assuming one signature fits all entities.**
  `Orion.APM.ApplicationCustomProperties.CreateCustomProperty` has 15 parameters with
  different names, and its `DeleteCustomProperty` takes three arguments rather than one.
- **A `403` on the create.** Invoke on `Orion.NodesCustomProperties` requires `admin`, while
  setting a value only requires `manageNodes`. A service account that populates tags cannot
  necessarily define them.
- **A string value longer than `Size`.** Check `MaxLength` in `Orion.CustomProperty` before
  bulk-loading values from another system.
- **Expecting this repository to know your property names.** It cannot. They are per
  installation, which is the whole point of the feature.

## Related pages

- [README.md](README.md) for the query-first method
- [node-management.md](node-management.md) for the node URIs these updates target
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional argument mechanics
- [../swis/crud.md](../swis/crud.md) for the update semantics
- [../swis/uris.md](../swis/uris.md) for how `/CustomProperties` composes onto a URI
- [../swis/bulk-operations.md](../swis/bulk-operations.md) for tagging many objects at once
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for navigation versus explicit joins
- Official: [Managing Custom Properties](https://solarwinds.github.io/OrionSDK/docs/managing-custom-properties/)
