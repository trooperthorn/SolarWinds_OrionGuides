# IPAM: IP Address Manager

IP Address Manager is the module that replaces the spreadsheet. It holds a hierarchy of
supernets, subnets and groups, keeps one row per individual IP address inside each subnet,
scans those addresses over ICMP, SNMP, DNS and ARP to work out which are really in use,
and reconciles what it finds against the DHCP servers that hand addresses out and the DNS
servers that name them. When two devices claim the same address, or a DHCP scope overlaps
another, or forward and reverse DNS disagree, IPAM records it as a conflict rather than
leaving you to notice.

That reconciliation is the point. Every other module in the platform tells you about
things it is monitoring. IPAM tells you about address space you own whether anything is
plugged into it or not, which is why it is the module people use to answer "can I have an
address" and "who took this one".

## Namespaces and how many entities

IPAM contributes **77 entities**, all under a bare `IPAM.` prefix with no `Orion.` in front
of it. At 77 it is the largest namespace outside `Orion.` in the whole schema, and IPAM is
the only licensed module whose entire surface lives under a single bare top-level prefix.
The other two modules outside `Orion.` are NCM, which splits across `Cirrus.` and `NCM.`,
and DPA, which splits across `DPA.` and `Orion.DPA.`. See
[../platform/modules.md](../platform/modules.md) for the whole map and
[ncm.md](ncm.md) for the split.

```bash
python3 tools/schema_query.py find "IPAM."
python3 tools/schema_query.py show IPAM.Subnet
python3 tools/schema_query.py verbs --entity IPAM.SubnetManagement
```

The 77 divide into eight families:

| Family | Entities | What is in it |
|---|---|---|
| Hierarchy and addresses | 25 | `IPAM.GroupNode`, `IPAM.Subnet`, `IPAM.IPNode`, `IPAM.IPInfo`, `IPAM.IPHistory`, the report and grid views, custom property carriers |
| DHCP | 18 | `IPAM.DhcpServer`, `IPAM.DhcpScope`, `IPAM.DhcpLease`, `IPAM.DhcpRange`, `IPAM.DhcpExclusions`, `IPAM.DHCPFailover`, `IPAM.DHCPView` |
| DNS | 12 | `IPAM.DnsServer`, `IPAM.DnsZone`, `IPAM.DnsRecord`, `IPAM.DnsView`, plus `IPAM.CloudDnsZones` and `IPAM.CloudDnsRecords` for Route 53 style hosted zones |
| Conflicts | 5 | `IPAM.Conflict`, `IPAM.ConflictDetail`, `IPAM.IPConflict`, `IPAM.DHCPScopeOverlapping`, `IPAM.DNSMismatch` |
| Verb facades | 5 | `IPAM.SubnetManagement`, `IPAM.IPAddressManagement`, `IPAM.DhcpDnsManagement`, `IPAM.GroupManagement`, `IPAM.SupernetManagement` |
| Operations | 5 | `IPAM.ScanInstance`, `IPAM.UIJob`, `IPAM.Setting`, `IPAM.AttrDefine`, `IPAM.EventType` |
| Address requests | 4 | `IPAM.IPRequests`, `IPAM.IPRequestAddresses`, `IPAM.RequesterDetailsFieldsMetadata`, `IPAM.RequesterDetailsFieldsValues` |
| Role model | 3 | `IPAM.AccountRoles`, `IPAM.GroupRole`, `IPAM.GroupRoleNode` |

The verb facades are the unusual family. All five carry **zero properties** and exist only to
hang verbs on: you cannot `SELECT` from `IPAM.SubnetManagement`, only `Invoke` against it.
All 67 of IPAM's verbs live on those five plus `IPAM.AttrDefine`,
`IPAM.GroupsCustomProperties` and `IPAM.NodesCustomProperties`.

They are not quite the only property-less entities in the namespace. `IPAM.ImportStarted`
has none either, but it is a `System.Indication` rather than a facade: an event SWIS
publishes, with no verbs and no operations at all. Six IPAM entities have no properties;
five of them are facades.

## The API changed shape across versions, and SolarWinds documents it that way

This matters more for IPAM than for any other module. SolarWinds does not publish one IPAM
API page. It publishes [seven of them](https://solarwinds.github.io/OrionSDK/docs/ip-address-manager/ipam-api/),
one per generation: 4.5.x, 4.6, 4.7, 4.9, 2019.4 and higher, Observability 2022.2, and
vNext. They are not revisions of a single document. Each describes the verb surface as it
stood, and verbs were added, renamed and given extra parameters between them.

Three concrete examples of what changed, all checkable against the pages:

- The **2019.4** page has no group, supernet, or DHCP and DNS server management at all. Its
  whole surface is subnet creation, reservations, DNS records and custom properties.
- The **Observability 2022.2** page adds `CreateGroup`, `GetGroupsByName`, `CreateSupernet`,
  `GetSupernetsByName`, `AddDhcpServer`, `AddDnsServer`, `DeleteDhcpServer`,
  `DeleteDnsServer` and `AddDhcpScope`.
- The **vNext** page adds the 2026.2 range verbs (`AddIpRange`, `AddIpv6Range`,
  `RemoveIpRange`), IPv6 DHCP reservations, `RemoveGroup`, `EditSupernet` and
  `GetAllGroupNodesByName`.

Neither of the two newest pages is a superset of the other, and both run ahead of 2026.2.
The Observability 2022.2 page documents `EditDhcpScope`, `DeleteDhcpScope` and
`DeleteDhcpScopes` as "available since 2026.4", and none of those three is in the 2026.2
schema. The vNext page documents `CreateIpv6Reservation` and the range verbs, which are in
2026.2, but omits `StartScanDhcpServer`, `UpdateDhcpServer`, `CreateDhcpCredentials` and
`StartDhcpCredentialsTest`, which are also in 2026.2 and are documented nowhere.

The working rule: **treat the extracted schema as the arbiter for 2026.2 and the published
pages as the explanation of what each verb means**. When the two disagree, ask your own
server:

```sql
SELECT Name
FROM Metadata.Verb
WHERE Entity.FullName = 'IPAM.SubnetManagement'
ORDER BY Name
```

`Metadata.Verb` names the verb in `Name` and reaches its owner through the `Entity`
navigation. It has no flat `EntityName` or `VerbName` column. `Metadata.VerbArgument` does
carry both, which is the asymmetry to remember when moving between the two.

See [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for the rest of
that pattern.

## The hierarchy: groups, supernets, subnets

Everything in IPAM's tree is a row in **`IPAM.GroupNode`**, and `GroupType` says which kind
of thing it is. The tree is self-referential: `ParentId` points at another `GroupId`, and
the `Parent` navigation property follows it. `Children` walks the other way.

The `GroupType` values are documented on the vNext page with the `GetAllGroupNodesByName`
verb, and they are a bit field rather than a sequence:

| Value | Node type |
|---|---|
| 1 | Hierarchy Group |
| 2 | Group |
| 4 | Supernet |
| 8 | Subnet |
| 128 | Global Prefix |
| 256 | IPv6 Site |
| 512 | IPv6 Subnet |

A **hierarchy group** is a root: the vNext page notes that a group whose `ParentId` is `-1`
is a hierarchy group. A **group** is an ordinary folder. A **supernet** is a summarised
block you can carve subnets out of. A **subnet** is the thing that actually contains
addresses.

`IPAM.GroupNode` is wide (63 properties) because it carries the union of everything a node
in that tree might be. On a subnet row the interesting columns are `Address`, `CIDR`,
`FriendlyName`, `VLAN`, `Location`, `ScanInterval`, `DisableAutoScanning`, `LastDiscovery`
and the five counters (`TotalCount`, `UsedCount`, `AvailableCount`, `ReservedCount`,
`TransientCount`) plus `PercentUsed`. On a DHCP server row the same entity carries
`ServerType`, `PrimaryServer`, `SecondaryServer`, `FailoverServerType` and the failover
state columns. Selecting a DHCP column from a subnet row is legal and returns null.

`IPAM.GroupNode` declares eleven navigation properties, which is how you get from a tree node
to whatever it actually is. `Parent` and `Children` are the two ends of one self-relationship,
`IPAM.GroupNodeHostsGroupNode`, which is why the table below has ten rows for eleven
navigations:

| From `IPAM.GroupNode` | Leads to |
|---|---|
| `Parent`, `Children` | `IPAM.GroupNode` |
| `Server` | `IPAM.DhcpServer` |
| `Scope` | `IPAM.DhcpScope` |
| `DnsServer` | `IPAM.DnsServer` |
| `DnsZone` | `IPAM.DnsZone` |
| `ScanInstance` | `IPAM.ScanInstance` |
| `PrefixAggregate` | `IPAM.PrefixAggregate` |
| `Engines` | `Orion.Engines` |
| `Custom`, `CustomProperties` | `IPAM.GroupNodeAttr`, `IPAM.GroupsCustomProperties` |

**`IPAM.Subnet` is the narrowed, writable view of the subnet rows.** It has 33 properties,
`SubnetId` as its key, and unlike `IPAM.GroupNode` it declares full CRUD (`create`, `read`,
`update`, `delete`, `invoke`), all of it requiring the `admin` right except plain `read`.
It navigates to `IPAM.IPNode` through `IPNode`.

Note the id confusion here and get it right before you write anything: `IPAM.Subnet` keys on
`SubnetId`, `IPAM.GroupNode` and `IPAM.GroupReport` key on `GroupId`, and the verbs that
take a subnet take **`GroupId`**, not `SubnetId`. `AddIpRange(subnetGroupId, ...)`,
`CreateSubnetForGivenParentNode(..., parentGroupId)` and
`ChangeDisableAutoScanning(groupId, ...)` all want the group id.

**`IPAM.GroupReport`** is the display-layer twin of `IPAM.GroupNode`: 50 properties, the
same `GroupId` key, plus `DetailsUrl`, `GroupStatus`, `PercentageUsed` and `IPsAllocated`,
and a `Node` navigation property to `Orion.Nodes`. It is also the entity that carries
IPAM's NetObject prefix, `IPAMG`, so a group id appears as `IPAMG:412` where the platform
needs a NetObject string. See
[../reference/netobject-types.md](../reference/netobject-types.md).

## IP nodes and their status

**`IPAM.IPNode` is one row per address**, not one row per device. A `/24` that IPAM manages
has 256 rows in `IPAM.IPNode` whether anything answers on them or not. That is the single
most important thing to understand about the entity, because it inverts how you write
queries: an address being free is a `Status` value, not a missing row.

| Property | Type | Notes |
|---|---|---|
| `IpNodeId` | `System.Int64` | Primary key |
| `SubnetId` | `System.Int32` | Owning subnet. Not editable after create |
| `IPAddress` | `System.String` | Not editable after create |
| `IPOrdinal` | `System.Int32` | Position within the subnet. `ORDER BY IPOrdinal` gives numeric address order, which `ORDER BY IPAddress` does not |
| `Status` | `System.Byte` | Used, Available, Reserved, Transient or Blocked. See below |
| `AllocPolicy` | `System.Byte` | Static or Dynamic |
| `MAC`, `DUID`, `IAID` | `System.String` | Layer 2 identity. `DUID` and `IAID` are the DHCPv6 equivalents of a MAC |
| `DnsBackward` | `System.String` | The PTR record IPAM last resolved |
| `DhcpClientName` | `System.String` | The client name the DHCP server reported |
| `Alias`, `Comments` | `System.String` | Free text you own |
| `SysName`, `Description`, `Contact`, `Location`, `SysObjectID`, `Vendor`, `MachineType` | | Learned over SNMP when the address answers |
| `ResponseTime`, `LastBoot`, `LastSync` | | Last scan result. `LastSync` is when IPAM last had a conversation with this address |
| `LeaseExpires` | `System.DateTime` | Populated from DHCP |
| `SkipScan` | `System.Boolean` | Exclude this address from scanning |
| `DnsBy`, `MacBy`, `StatusBy`, `SystemDataBy` | `System.Int16` | Provenance: which scan method set each of those four facts |

`IPAM.IPNode` supports full CRUD under `admin` and navigates to `IPAM.Subnet` (`Subnet`),
`IPAM.IPHistory` (`History`), `IPAM.IPNodeAttr` (`Custom`) and
`IPAM.NodesCustomProperties` (`CustomProperties`).

### The status values, and how to find out what the numbers are

IPAM's five statuses are **Used, Available, Reserved, Transient and Blocked**. SolarWinds
documents them as those strings, because that is what the API takes on the way in:
`IPAM.SubnetManagement.ChangeIpStatus(ipAddress, status, subnetId)` wants the word, and so
does a CRUD write to `IPAM.IPNode.Status`.

On the way out, `IPAM.IPNode.Status` is a `System.Byte`, and **the 2026.2 schema does not
declare the number-to-name mapping**. Neither `IPAM.IPNode` nor any other IPAM entity
carries a property summary. Rather than hard-code a constant, derive it once on your own
server: `IPAM.IPInfo` carries the byte and the text side by side.

```sql
SELECT DISTINCT
    i.IPStatus,
    i.IPStatusText
FROM IPAM.IPInfo i
ORDER BY i.IPStatus
```

`IPAM.IPNodeReport.IPStatus` is a `System.String` for the same reason, so it is another way
to read a status without knowing the integer.

This repository's own sample file
[`../../scripts/swql/13-hardware-wireless-ipam.swql`](../../scripts/swql/13-hardware-wireless-ipam.swql)
treats `Status = 2` as available. That is consistent across the file but it is **not
verified against 2026.2 schema documentation**; run the query above before you rely on it.

`Transient` is worth calling out because it is IPAM-specific and confuses people. An
address that stops responding does not go straight from Used to Available. It becomes
Transient for `IPAM.GroupNode.TransientPeriod`, and only then is reclaimed. That is why
`TransientCount` is one of the five counters on every subnet row.

## Conflicts

Conflict detection is the reason people buy IPAM rather than keeping the spreadsheet, and
there are five separate conflict entities covering three different kinds of conflict: three
views of an address-level conflict, one for overlapping DHCP scopes, one for DNS that
disagrees with itself.

**`IPAM.Conflict`** is the address-level conflict: two MACs claiming one IP. It carries
`ConflictType` with a matching `ConflictTypeText`, `ConflictTimeUTC`, `ConflictStatus`, and
then two symmetrical halves. The **assigned** side (`AssignedMac`, `AssignedRawMac`,
`AssignedSourceType`, `AssignedSourceText`) is what IPAM believes should be there. The
**conflicting** side (`ConflictingMac`, `ConflictingRawMac`, `ConflictingSourceType`,
`ConflictingSourceText`) is what it found. The `SourceText` columns are the readable form
of how each side was learned, which is usually the fastest way to see whether the argument
is between DHCP and a statically configured host.

**`IPAM.ConflictDetail`** is 33 columns: 25 of `IPAM.Conflict`'s 27, dropping only
`AccountID` and `Role`, plus eight more that name the DHCP scope and server on each side —
`AssignedScopeName`, `AssignedDhcpServerName`, `ConflictScopeName`,
`ConflictDhcpServerName` and their four icons. Use `IPAM.ConflictDetail` when the conflict
involves DHCP, which is most of the time.

**`IPAM.IPConflict`** is the rolled-up form used by the web console: one row per address
with `ActiveConflicts`, a pre-rendered `IPConflictMsg`, `FirstSeenUTC`, `LastSeenUTC` and
`DetailsUrl`. It carries the `IPAMN` NetObject prefix. Reach for this one when you want a
count and a link, and `IPAM.ConflictDetail` when you want the evidence.

**`IPAM.DHCPScopeOverlapping`** is a different kind of conflict entirely: two DHCP scopes
covering overlapping address ranges, which means two servers can hand out the same address.
It is small (`ScopeId`, `FriendlyName`, `ActiveConflicts`, `DHCPConflictMsg`, `NodeId`,
`SubnetId`, `DetailsUrl`, `Status`) and it navigates straight to the DHCP server's platform
node through `DHCPScopeOvrLapp`. `Orion.Nodes` navigates back through `ScopeOverLapping`.
Its NetObject prefix is `IPAM-DSO`.

**`IPAM.DNSMismatch`** catches the third kind: forward and reverse DNS disagreeing. It
gives `DNSServer`, `DNSZone`, `ClientHostName`, `ForwardZoneIPAddress` and
`ReverseZoneIPAddress`, plus the two `IPNodeID` columns so you can join back to the
addresses on both sides.

## DHCP integration

IPAM does not just record what your DHCP servers do. It logs into them, reads their scopes
and leases, and can write reservations and scopes back. The entity set mirrors a DHCP
server's own structure.

| Entity | Contents |
|---|---|
| `IPAM.DhcpServer` | One managed server. `NodeId` links to `Orion.Nodes`, `GroupId` to the tree, `ServerType`, `CredentialId`, `AddNewScopes`, `AutoScanNewSubnets`, `LastPollHadError`, plus 16 protocol counters: seven IPv4 (`StatDiscovers`, `StatOffers`, `StatRequests`, `StatAcks`, `StatNaks`, `StatDeclines`, `StatReleases`) and nine DHCPv6 `V6Stat...` equivalents |
| `IPAM.DhcpScope` | One scope. `ScopeId`, `SubnetId`, `GroupId`, `Address`, `FoundAddress`, `FoundCIDR`, `DisabledAtServer`, `LastPollHadError`, `StatAddressesInUse`, `StatAddressesFree`, `StatPendingOffers`, `ScopeType`, `KeaSubnetId` |
| `IPAM.DhcpLease` | One lease. `ClientIpAddress`, `ClientMAC`, `ClientIAID`, `ClientDUID`, `ClientName`, `ClientLeaseExpires`, `ClientPreferredLeaseExpires`, `LeaseType`, `ReservationType` |
| `IPAM.DhcpRange` | The allocatable ranges inside a scope: `StartAddress`, `EndAddress`, `RangeType`, `PoolId` |
| `IPAM.DhcpPool` | ISC and Kea `pool {}` blocks: `PoolId`, `PoolStartAddress`, `PoolEndAddress` |
| `IPAM.DhcpExclusions` | Ranges carved out of a scope |
| `IPAM.DhcpOptions`, `IPAM.DhcpOptionsValue`, `IPAM.DhcpOptionServerMeta`, `IPAM.DhcpOptionWebMeta` | DHCP option definitions and their values |
| `IPAM.DhcpSharedNetwork`, `IPAM.DhcpGroup` | ISC and Kea shared networks and groups |
| `IPAM.DHCPFailover`, `IPAM.FailoverMode` | Failover relationships: `PrimaryServer`, `SecondaryServer`, `Mode`, `State`, `PrevState`, `MaxClientLeadTimeInSeconds`, `SafePeriodInSeconds`, `Percentage` |
| `IPAM.DHCPView`, `IPAM.TopUtilDHCPScopes` | Denormalised views behind the DHCP dashboards |

`IPAM.DhcpScope` navigates to `IPAM.DhcpLease` (`Leases`), `IPAM.DhcpRange` (`Ranges`),
`IPAM.DhcpExclusions` (`Exclusion`) and `IPAM.GroupNode` (`GroupNode`), which is the
practical route from a scope to its name and its place in the tree.

The server types IPAM can manage are named in the `AddDhcpServer` verb documentation:
Unknown `0`, Windows `1`, CISCO `2`, ASA `3`, ISC `4`, Infoblox `5`, Kea `6`. Kea support
arrived in 2026.2.

## DNS integration

The DNS side is smaller and reads the same way.

| Entity | Contents |
|---|---|
| `IPAM.DnsServer` | `NodeId`, `GroupId`, `ServerType`, `CredentialId`, `ConfigPath`, `IncrementalZoneTransfer`, `LastFileUpdate` |
| `IPAM.DnsZone` | `DnsZoneId`, `Name`, `ZoneType`, `LookUpType`, `DynamicUpdate`, `DsIntegrated`, `MasterDnsServers`, `DnsViewId` |
| `IPAM.DnsRecord` | `DnsRecordId`, `DnsZoneId`, `Name`, `Type`, `Data`, `IPAddressN`. Five properties and one blob of data, because a record really is that simple |
| `IPAM.DnsView`, `IPAM.DnsMasterServerView` | BIND views |
| `IPAM.DnsRecordType`, `IPAM.DnsZoneType`, `IPAM.DnsServerType` | The lookup tables for the integer type columns. Join these rather than hard-coding numbers |
| `IPAM.CloudDnsZones`, `IPAM.CloudDnsRecords`, `IPAM.CloudAccountSettings` | Hosted cloud DNS. `IPAM.CloudDnsRecords` carries the provider-specific fields: `AliasHostedZoneId`, `Failover`, `GeolocationCountryCode`, `HealthCheckId`, `Weight`, `TrafficPolicyInstanceId` |

`IPAM.DnsZone` navigates to `IPAM.DnsRecord` (`DnsRecord`) and to `IPAM.GroupNode`
(`GroupNode`); `IPAM.DnsRecord` navigates back through `DnsZone`.

The DNS server types are named in the `AddDnsServer` documentation: Unknown `0`,
Windows `1`, Bind `2`, Infoblox `3`.

## Scanning

IPAM finds out what is really on an address by scanning it, and the scan queue is visible.

**`IPAM.ScanInstance`** is one row per queued or running scan: `SubnetId`,
`ScanInstanceType`, `Status`, `QueueTimeStamp`, `ScanStartTimeStamp`, `JobId` and
`StartedBy`. It navigates to `IPAM.GroupNode` through `Subnet`, and `IPAM.GroupNode`
navigates to it through `ScanInstance`. Note that its `SubnetId` matches
`IPAM.GroupNode.GroupId`, not `IPAM.Subnet.SubnetId`.

Scanning is controlled per node in the tree: `IPAM.GroupNode.ScanInterval` (minutes),
`DisableAutoScanning`, `DisableNeighborScanning`, `NeighborScanAddress` and
`NeighborScanInterval`. `IPAM.IPNode.SkipScan` excludes a single address.

There is no "scan this subnet now" verb in 2026.2. The only scan verbs are
`IPAM.DhcpDnsManagement.StartScanDhcpServer(dhcpServerId)` and
`StartScanDnsServer(dnsServerId)`, both taking the server's `GroupId`. Subnet scanning is
driven by the interval, and the switch you have is
`IPAM.SubnetManagement.ChangeDisableAutoScanning(groupId, disableAutoScanning)`.

**`IPAM.UIJob`** tracks the long-running jobs the console starts (imports and bulk
operations) with `WebId`, `StatusText`, `ProgressMin`, `ProgressMax` and
`CompletionState`. `IPAM.ImportStarted` and `IPAM.SubnetStructureChanged` are
`System.Indication` entities rather than tables: they are events you can subscribe to, not
rows you can select.

## The address request workflow

IPAM has a built-in request queue so that people who need an address ask for one instead of
picking one. Two entities carry it, and both allow `create` for **everyone**, which is the
whole point: an ordinary user must be able to raise a request.

**`IPAM.IPRequests`** is the ticket: `IPRequestId`, `RequestAccountId`, `RequestDate`,
`RequestAddressCount`, `ResolutionAccountId`, `ResolutionDate`, `State`, the requester's
`FirstName`, `LastName`, `Phone` and `Email`, a `Comment` from the requester and an
`AdminComment` from whoever resolved it, plus `Subnet`, `GroupId`, `DisplayName` and
`IsLegacy`.

**`IPAM.IPRequestAddresses`** is one row per address in the request: `Address`,
`AddressType`, `HostName`, `MacAddress`, `IAID`, `DUID`, `State`, `IsScanDisabled` and
`IPNodeId` once the address is actually allocated.

`IPAM.RequesterDetailsFieldsMetadata` and `IPAM.RequesterDetailsFieldsValues` hold the
extra fields an administrator adds to the request form.

Access control is worth reading carefully here. Both entities declare
`create,read` for `everyone` and the full `create,read,update,delete,invoke` set for
`admin`. So anyone can raise a request and read it; only an administrator can approve one
by updating it. `ResolutionDate IS NULL` is the "still waiting" filter.

## Custom properties

IPAM has **two** custom property mechanisms, from two different eras, and both are live in
2026.2. Getting them mixed up is the most common IPAM scripting mistake after the
`GroupId` versus `SubnetId` one.

**The older one is `IPAM.AttrDefine`.** It is IPAM's own field definition table:
`TargetTable` and `Name`, with three verbs.

| Verb | Parameters, in order |
|---|---|
| `AddCustomProperty` | `propertyName`, `description`, `maxStringLength`, `attributeType` (optional), `linkTitle` (optional), `addToIpAddress` (optional), `addToGroups` (optional) |
| `UpdateCustomProperty` | `propertyName`, `description`, `maxStringLength`, `linkTitle`, `addToIpAddress`, `addToGroups` |
| `DeleteCustomProperty` | `propertyName` |

`attributeType` accepts `String`, `Integer`, `Datetime`, `Float` or `Boolean`.
`addToIpAddress` puts the field on addresses, `addToGroups` puts it on groups, supernets,
subnets, DHCP servers, scopes, DNS servers and zones. Values then appear as columns on
`IPAM.IPNodeAttr` and `IPAM.GroupNodeAttr`, both of which declare nothing but their key
(`IPNodeId` and `GroupId`) until you create one.

**The newer one is the platform's own custom property system**, reached through
`IPAM.NodesCustomProperties` (for addresses, keyed on `IPNodeId`) and
`IPAM.GroupsCustomProperties` (for tree nodes, keyed on `GroupId`). Both inherit from
`System.CustomPropertiesEntity` and carry the standard four verbs, `CreateCustomProperty`,
`CreateCustomPropertyWithValues`, `ModifyCustomProperty` and `DeleteCustomProperty`, with
the same 16 and 17 argument signatures every other module's custom property entity uses.
See [../swis/verb-catalog.md](../swis/verb-catalog.md) for that shared shape.

SolarWinds' own note on the split is on the vNext page and is worth quoting in effect:
IPAM 4.8 and newer does not use its own custom fields for groups any more, so create and
remove on `IPAM.GroupNodeAttr` are no longer valid, and group custom property values are
written through `IPAM.GroupNodeDisplayCustomProperties`. Address custom properties still
work both ways.

To see which fields exist on a server:

```sql
SELECT
    a.TargetTable,
    a.Name
FROM IPAM.AttrDefine a
ORDER BY a.TargetTable, a.Name
```

## Verbs

IPAM declares **67 verbs**, an unusually rich surface for a module of 77 entities, and they
are concentrated on eight entities:

| Entity | Verbs | Theme |
|---|---|---|
| `IPAM.SubnetManagement` | 21 | Subnets, IP ranges, address status, reservations, scanning switch |
| `IPAM.DhcpDnsManagement` | 18 | DHCP and DNS server lifecycle, scopes, DHCP reservations, credentials, scans |
| `IPAM.IPAddressManagement` | 10 | DNS A, AAAA and PTR records for an address |
| `IPAM.GroupManagement` | 4 | Groups and hierarchy groups |
| `IPAM.GroupsCustomProperties` | 4 | Platform custom properties on tree nodes |
| `IPAM.NodesCustomProperties` | 4 | Platform custom properties on addresses |
| `IPAM.AttrDefine` | 3 | IPAM's own custom fields |
| `IPAM.SupernetManagement` | 3 | Supernets |

Arguments are positional. Names appear in the schema and the Swagger contract but never on
the wire, so the order is the whole contract. Check before calling:

```bash
python3 tools/schema_query.py verbs --entity IPAM.SubnetManagement
python3 tools/schema_query.py verb IPAM.SubnetManagement StartIpReservation
```

None of IPAM's 67 verbs declares an access control right in the extracted schema, unlike
NPM or NCM verbs. That does not mean they are unguarded: `IPAM.AccountRoles`,
`IPAM.GroupRole` and `IPAM.GroupRoleNode` model a per-group role of Admin, PowerUser,
Operator, ReadOnly or NoAccess, and IPAM enforces it. A permission failure from an IPAM
verb is usually a missing IPAM role on that part of the tree rather than a missing platform
right. This is **not stated in the extracted schema**; confirm on your own server by
reading `IPAM.AccountRoles` for the account in question.

### Claiming an address: the reservation handshake

This is the sequence that matters most, because it is how you allocate an address without
racing another script for it. It is three verbs on `IPAM.SubnetManagement`.

| Verb | Parameters, in order | Returns |
|---|---|---|
| `StartIpReservation` | `subnetAddress`, `subnetCidr`, `reservationTimeInMinutes` (optional), `addressToStart` (optional) | The reserved IP address, as a string |
| `FinishIpReservation` | `ipAddress`, `finalIpStatus` | void |
| `CancelIpReservation` | `reservedIpAddress` | void |

`StartIpReservation` picks the first free address in the subnet, marks it held, and returns
it. The hold is temporary: SolarWinds documents the default as 10 minutes and states that
**when the reservation time expires the address returns to Available**. So the handshake is
start, provision the device, then `FinishIpReservation` with the status you actually want
(`"Used"`, `"Reserved"`, `"Available"`, `"Transient"` or `"Blocked"`), or
`CancelIpReservation` if the provisioning failed. Forgetting to finish is not catastrophic,
which is the point of the timeout, but it does mean the address quietly frees itself.

`subnetCidr` is a **string**, not a number, in both `GetFirstAvailableIp` and
`StartIpReservation`. That is what the Swagger contract types it as, and passing an integer
where a string is expected is the sort of thing that fails on some clients and not others.

Each of the three has a `ForGroup` variant taking an extra hierarchy group name, for
installations where the same address space exists in more than one hierarchy:
`StartIpReservationForGroup(subnetAddress, subnetCidr, hierarchyGroup,
reservationTimeInMinutes, addressToStart)`,
`FinishIpReservationForGroup(ipAddress, finalIpStatus, hierarchyGroup)` and
`CancelIpReservationForGroup(reservedIpAddress, hierarchyGroup)`. Note that
`hierarchyGroup` is the **third** argument on `StartIpReservationForGroup`, ahead of the
two optional ones, so the positions are not a simple append.

```powershell
# Allocate one address from 10.20.30.0/24, hold it for 15 minutes, then commit it.
Import-Module SwisPowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$ip = Invoke-SwisVerb $swis 'IPAM.SubnetManagement' 'StartIpReservation' `
        @('10.20.30.0', '24', 15, '') |
      Select-Object -ExpandProperty '#text'

Write-Host "Reserved $ip"

try {
    # ... build the machine, configure the interface, whatever takes the time ...

    Invoke-SwisVerb $swis 'IPAM.SubnetManagement' 'FinishIpReservation' @($ip, 'Used') | Out-Null

    # Record who it is for. Status must not be Available for these columns to be accepted.
    $uri = Get-SwisData $swis `
        "SELECT TOP 1 Uri FROM IPAM.IPNode WHERE IPAddress = @ip" @{ ip = $ip }
    Set-SwisObject $swis -Uri $uri -Properties @{
        Alias    = 'app-07'
        Comments = 'Provisioned by build pipeline'
    }
}
catch {
    Invoke-SwisVerb $swis 'IPAM.SubnetManagement' 'CancelIpReservation' @($ip) | Out-Null
    throw
}
```

`Invoke-SwisVerb` returns an XML element, which is why the result is unwrapped with
`Select-Object -ExpandProperty '#text'`. See
[../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the serialisation rules.

The CRUD write at the end is doing something the verbs cannot: SolarWinds' documented
constraint on `IPAM.IPNode` is that `IPMapped`, `Alias`, `MAC`, `DnsBackward`,
`DhcpClientName` and `Comments` **must be undefined when `Status` is Available**. Set the
status first, then the metadata.

### Just looking, not claiming

Three verbs find a free address without changing anything, which the vNext page states
explicitly ("It doesn't change status of the returned node"):

| Verb | Parameters, in order |
|---|---|
| `GetFirstAvailableIp` | `subnetAddress`, `subnetCidr` |
| `GetFirstAvailableIpForGroup` | `subnetAddress`, `subnetCidr`, `hierarchyGroup` |
| `GetFirstAvailableIpViaFriendlyName` | `friendlyName` |

There is also a `GetFirstAvailableIpv6` on `IPAM.SubnetManagement`. It appears in the
rendered schema pages with **no parameters and an unknown return type**, and it is absent
from the 2026.2 Swagger contract entirely, so its signature is **unverified here**. Confirm
it on your own server before calling it:

```sql
SELECT Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = 'IPAM.SubnetManagement' AND VerbName = 'GetFirstAvailableIpv6'
ORDER BY Position
```

### Changing an address status directly

| Verb | Parameters, in order |
|---|---|
| `ChangeIpStatus` | `ipAddress`, `status`, `subnetId` (optional) |
| `ChangeIpStatusForGroup` | `ipAddress`, `status`, `hierarchyGroup` |

The optional `subnetId` on `ChangeIpStatus` is new in 2026.2 and solves a real ambiguity:
without it the address is looked up **globally by address**, so if the same private range
exists in two subnets the verb picks one for you. Pass the subnet's `GroupId` when you know
it.

### Adding a subnet

| Verb | Parameters, in order | Where the subnet lands |
|---|---|---|
| `CreateSubnet` | `subnetAddress`, `rawCidr` | Root of the IPAM group tree |
| `CreateSubnetForGroup` | `subnetAddress`, `rawCidr`, `hierarchyGroup` | Root of that hierarchy group |
| `CreateSubnetForGivenParentNode` | `subnetAddress`, `rawCidr`, `parentGroupId` | Under any group, supernet or hierarchy group |
| `CreateIPv6Subnet` | `prefix`, `prefixName`, `isNewPrefix`, `subnetAddress`, `rawCidr` | Root, under a global IPv6 prefix |
| `CreateIPv6SubnetForGroup` | `prefix`, `prefixName`, `isNewPrefix`, `subnetAddress`, `rawCidr`, `hierarchyGroup` | That hierarchy group |

`rawCidr` is a **string** in all five. All of them return void and all of them can fail
with an overlap error, which SolarWinds names as the expected failure mode: a new subnet
that overlaps an existing one is rejected.

`CreateSubnetForGivenParentNode` is the one to reach for in automation, because it is the
only one that puts a subnet somewhere specific by id rather than by name.

Creating a subnet through CRUD works too and is sometimes easier, since it lets you set the
friendly name and VLAN in the same call:

```powershell
New-SwisObject $swis -EntityType 'IPAM.Subnet' -Properties @{
    Address      = '10.20.31.0'
    CIDR         = 24
    FriendlyName = 'Lab VLAN 31'
    VLAN         = '31'
    Location     = 'Building A'
    ScanInterval = 240
}
```

SolarWinds documents `Address` and `CIDR` as the only required properties, `CIDR` and
`AddressMask` as non-editable after creation, and for IPv4 **`CIDR` must be greater than 21
and no more than 32**. A `/16` cannot be created as an `IPAM.Subnet`; that is what supernets
are for.

### Populating addresses inside a large subnet

New in 2026.2, and the fix for a real limitation. SolarWinds' note on `AddIpRange` says
that **for subnets with a CIDR larger than /20, IP addresses are not created automatically**
and must be added through the verb.

| Verb | Parameters, in order |
|---|---|
| `AddIpRange` | `subnetGroupId`, `startIp`, `endIp` |
| `AddIpv6Range` | `subnetGroupId`, `startIp`, `endIp` |
| `RemoveIpRange` | `subnetGroupId`, `startIp`, `endIp` |

`RemoveIpRange` handles both families and only removes addresses that IPAM currently
manages. All three take the subnet's `GroupId`.

### Groups and supernets

| Verb | Parameters, in order | Notes |
|---|---|---|
| `IPAM.GroupManagement.CreateGroup` | `groupName`, `comments`, `parentGroupId` | Pass null for `parentGroupId` to create a hierarchy group, `0` for a group at the root |
| `IPAM.GroupManagement.GetGroupsByName` | `groupName` | Returns groups and hierarchy groups; a `ParentId` of `-1` marks a hierarchy group |
| `IPAM.GroupManagement.GetAllGroupNodesByName` | `groupName` | Returns any node type, with `GroupType` from the table above |
| `IPAM.GroupManagement.RemoveGroup` | `groupId` | **Removes children too.** There is no dry run |
| `IPAM.SupernetManagement.CreateSupernet` | `supernetName`, `address`, `cidr`, `description`, `parentGroupId` | `cidr` is a number here, unlike the subnet verbs |
| `IPAM.SupernetManagement.EditSupernet` | `id`, `name`, `cidr`, `description` | |
| `IPAM.SupernetManagement.GetSupernetsByName` | `supernetName` | |

The three `Get...ByName` verbs all return objects carrying `GroupId` and `ParentId`, and
since 2025.4 also `Address`, `CIDR`, `Description`, `VLAN` and `Location`. They are how you
turn a name from a change ticket into the id every other verb wants.

### DHCP and DNS server management

| Verb | Parameters, in order |
|---|---|
| `AddDhcpServer` | 22 arguments beginning `nodeId`, `newHierarchyGroupName`, `newCredentialName`, `newCredentialUserName`, `newCredentialPassword`, `newCredentialEnablePassword`, and ending with six Kea-only credential arguments |
| `AddDnsServer` | `nodeId`, `newCredentialName`, `newCredentialUserName`, `newCredentialPassword`, `newCredentialProtocol`, `newCredentialClientPort`, `credentialId`, `enableScanning`, `incrementalZoneTransfer`, `scanInterval`, `serverType` |
| `DeleteDhcpServer` | `groupId`, `removeCorrespondingSubnets`, `removeScopesFromServer` |
| `DeleteDnsServer` | `groupId`, `removeZonesFromServer` |
| `UpdateDhcpServer` | `dhcpServerId`, `propertiesToUpdate` (an array of key/value pairs) |
| `UpdateDnsServer` | `dnsServerId`, `propertiesToUpdate` (an array of key/value pairs) |
| `StartScanDhcpServer` | `dhcpServerId` |
| `StartScanDnsServer` | `dnsServerId` |
| `CreateDhcpCredentials` | `dhcpServerType`, `credentials` (an array of key/value pairs) |
| `CreateDnsCredentials` | `dnsServerType`, `credentials` |
| `StartDhcpCredentialsTest` | `nodeId`, `dhcpServerType`, `credentialId`, `credentials` |
| `StartDnsCredentialsTest` | `nodeId`, `dnsServerType`, `credentialId`, `credentials` |
| `AddDhcpScope` | 23 arguments; see the table on the [vNext page](https://solarwinds.github.io/OrionSDK/docs/ipam-vnext-api/) |
| `CreateIpReservation` | `ipAddressToReserve`, `dhcpServerIpAddress`, `reservationName`, `reservationMAC`, `reservationType` |
| `CreateIpv6Reservation` | `ipAddressToReserve`, `dhcpServerIpAddress`, `reservationName`, `duid`, `iaid` |
| `RemoveIpReservation` | `ipRemoveReservation`, `dhcpServerIpAddress` |
| `RemoveIpv6Reservation` | `ipRemoveReservation`, `dhcpServerIpAddress` |
| `GetAandPTRrecordsForDnsZone` | `zoneName`, `dnsServerIp` |

Note the naming collision that catches everyone: **`CreateIpReservation` on
`IPAM.DhcpDnsManagement` is a DHCP reservation on the DHCP server**, permanently binding an
address to a MAC. **`StartIpReservation` on `IPAM.SubnetManagement` is a temporary hold
inside IPAM's own database** and never touches a DHCP server. They are unrelated
operations with almost the same name. The DHCP one requires `reservationMAC` in
`00:00:00:00:00:00` form and takes a `reservationType` of `DhcpOnly`, `BootpOnly` or
`Both`.

Eight of those verbs exist in the 2026.2 schema and are **not documented on any published
SolarWinds IPAM page**: `CreateDhcpCredentials`, `CreateDnsCredentials`,
`StartDhcpCredentialsTest`, `StartDnsCredentialsTest`, `StartScanDhcpServer`,
`StartScanDnsServer`, `UpdateDhcpServer` and `UpdateDnsServer`. Their parameter names and
types above come from the Swagger contract, which is authoritative for the shape but says
nothing about semantics. Treat the `credentials` and `propertiesToUpdate` key/value arrays
as unverified in content and inspect `Metadata.VerbArgument.XmlTemplate` on your own server
for the keys they expect.

### DNS records for an address

Ten verbs on `IPAM.IPAddressManagement`, and they are the most regular set in the module.
Every one of them takes `dnsIpAddress` (the DNS **server** address) and `dnsZoneName`, and
in seven of the ten those two are the last arguments. The three exceptions append one more:
`ChangeDnsARecord` and `ChangeDnsAaaaRecord` put the replacement address after the zone
name, and `RemovePtrRecord` puts its retry flag there.

| Verb | Parameters, in order |
|---|---|
| `AddDnsARecord` | `recordName`, `nodeIPv4Address`, `dnsIpAddress`, `dnsZoneName` |
| `AddDnsARecordWithPtr` | `recordName`, `nodeIPv4Address`, `dnsIpAddress`, `dnsZoneName` |
| `ChangeDnsARecord` | `recordName`, `nodeIPv4Address`, `dnsIpAddress`, `dnsZoneName`, `nodeIPv4AddressNew` |
| `RemoveDnsARecord` | `recordName`, `nodeIPv4Address`, `dnsIpAddress`, `dnsZoneName` |
| `AddDnsAaaaRecord` | `recordName`, `nodeIPv6Address`, `dnsIpAddress`, `dnsZoneName` |
| `ChangeDnsAaaaRecord` | `recordName`, `nodeIpV6Address`, `dnsIpAddress`, `dnsZoneName`, `newNodeIpV6Address` |
| `RemoveDnsAaaaRecord` | `recordName`, `nodeIpV6Address`, `dnsIpAddress`, `dnsZoneName` |
| `AddPtrRecord` | `recordName`, `recordData`, `dnsIpAddress`, `dnsZoneName` |
| `AddPtrToDnsARecord` | `recordName`, `nodeIPv4Address`, `dnsIpAddress`, `dnsZoneName` |
| `RemovePtrRecord` | `recordName`, `dnsIpAddress`, `dnsZoneName`, `isRetryingDnsZoneSearch` |

`RemovePtrRecord` is the odd one: it has **no address argument**, because the record name
of a PTR already encodes the address (`1.10.10.10.in-addr.arpa.`). Its
`isRetryingDnsZoneSearch` flag widens the search up the reverse zone tree, so a record
actually held in `10.10.in-addr.arpa` is still found when you named `10.10.10.in-addr.arpa`.

SolarWinds notes that these execute against the DNS server immediately, taking around 30
seconds, after which the result is visible in `IPAM.DnsZone`, `IPAM.DnsServer` and
`IPAM.DnsRecord`.

## Worked queries

Every query below was validated against the 2026.2 schema with
`python3 tools/validate_swql.py`. Time bounds arrive as bound parameters rather than being
computed in SWQL, for the reason under [Gotchas](#gotchas).
[`../../scripts/swql/13-hardware-wireless-ipam.swql`](../../scripts/swql/13-hardware-wireless-ipam.swql)
has the basic utilization and address-lookup queries; these go further.

### 1. Free addresses in a subnet

The direct answer, and the one that does not require knowing what the `Status` byte means.
`IPAM.IpAddressesForReservation` is IPAM's own pick list: the addresses in each subnet that
are currently available to hand out.

```sql
SELECT TOP 100
    a.FriendlyName AS SubnetName,
    a.SubnetAddress,
    a.CIDR,
    a.AvailableCount,
    a.IpNodeAddress,
    a.DnsBackward,
    a.MAC,
    a.SkipScan
FROM IPAM.IpAddressesForReservation a
WHERE a.FriendlyName = @subnetName
ORDER BY a.IpNodeAddress
```

`DnsBackward` and `MAC` being populated on a free address is the interesting signal: it
means the address used to be in use and IPAM has not yet forgotten who had it. Those are
the safest ones to reuse if you need the address to have been idle for a while, and the
riskiest if something is still quietly using it without answering scans.

If you want the same answer straight from `IPAM.IPNode`, run the `IPAM.IPInfo` query from
[The status values](#the-status-values-and-how-to-find-out-what-the-numbers-are) first to
learn which byte value means Available on your server, then filter on it and
`ORDER BY IPOrdinal` rather than by address text.

### 2. Subnets running out of space

```sql
SELECT TOP 100
    sn.FriendlyName,
    sn.Address,
    sn.CIDR,
    sn.VLAN,
    sn.Location,
    sn.TotalCount,
    sn.UsedCount,
    sn.AvailableCount,
    sn.ReservedCount,
    sn.TransientCount,
    sn.PercentUsed,
    sn.LastDiscovery
FROM IPAM.Subnet sn
WHERE sn.PercentUsed > 85
ORDER BY sn.PercentUsed DESC
```

Select `TransientCount` alongside `AvailableCount`, because a subnet with a large transient
count is not as full as `PercentUsed` suggests: those addresses are on their way back to
available. `LastDiscovery` tells you whether the numbers are worth believing at all.

### 3. The subnet tree, one level of parent at a time

```sql
SELECT TOP 100
    g.GroupId,
    g.GroupTypeText,
    g.FriendlyName,
    g.Address,
    g.CIDR,
    g.Parent.FriendlyName AS ParentName,
    g.Parent.GroupTypeText AS ParentType,
    g.PercentUsed,
    g.AvailableCount,
    g.DisableAutoScanning
FROM IPAM.GroupNode g
WHERE g.GroupType = 8
ORDER BY g.Parent.FriendlyName, g.Address
```

`GroupType = 8` restricts to subnets. Change it to `4` for supernets or `1` for hierarchy
groups. `Parent` is a self-referencing navigation property, so this reads one level up
without a join; `IPAM.GroupAncestors` holds the full ancestry if you need more than one
level. `GroupTypeText` saves you translating the bit values by hand.

### 4. IP address conflicts, with both sides of the argument

```sql
SELECT TOP 100
    c.IPAddress,
    c.SubnetAddress,
    c.ConflictTypeText,
    c.ConflictTimeUTC,
    c.AssignedMac,
    c.AssignedSourceText,
    c.ConflictingMac,
    c.ConflictingSourceText,
    c.ConflictStatus
FROM IPAM.Conflict c
WHERE c.ConflictTimeUTC >= @startUtc
ORDER BY c.ConflictTimeUTC DESC
```

Selecting both `SourceText` columns is what makes this actionable. A conflict between a
DHCP-sourced MAC and an ARP-sourced MAC is a machine with a static address inside a DHCP
range, which you fix on the machine. A conflict between two DHCP sources is a scope
problem, which you fix on the servers, and query 5 will already have told you about it.

For conflicts involving DHCP, `IPAM.ConflictDetail` adds the scope and server names:

```sql
SELECT TOP 50
    d.IPAddress,
    d.ConflictTypeText,
    d.ConflictTimeUTC,
    d.AssignedMac,
    d.AssignedDhcpServerName,
    d.AssignedScopeName,
    d.ConflictingMac,
    d.ConflictDhcpServerName,
    d.ConflictScopeName
FROM IPAM.ConflictDetail d
WHERE d.ConflictTimeUTC >= @startUtc
ORDER BY d.ConflictTimeUTC DESC
```

### 5. Overlapping DHCP scopes, named by the server they live on

```sql
SELECT
    o.ScopeId,
    o.FriendlyName,
    o.ActiveConflicts,
    o.DHCPConflictMsg,
    o.SubnetId,
    o.DHCPScopeOvrLapp.Caption AS DhcpServerNode,
    o.DHCPScopeOvrLapp.IPAddress AS DhcpServerIP
FROM IPAM.DHCPScopeOverlapping o
WHERE o.ActiveConflicts > 0
ORDER BY o.ActiveConflicts DESC
```

`DHCPScopeOvrLapp` is the navigation property to `Orion.Nodes`, and the spelling is exactly
that, abbreviated and without the second `e` in "Overlapping". It is the kind of name you
have to look up rather than guess:

```bash
python3 tools/schema_query.py show IPAM.DHCPScopeOverlapping
```

Overlapping scopes are the cause of a whole class of intermittent duplicate-address
complaints, and this is a very cheap query to put on a schedule.

### 6. DHCP scopes near exhaustion

```sql
SELECT TOP 100
    s.Address AS ScopeAddress,
    s.GroupNode.FriendlyName AS ScopeName,
    s.StatAddressesInUse,
    s.StatAddressesFree,
    s.PercentUsed,
    s.DisabledAtServer,
    s.LastPollHadError,
    s.LastDiscovery
FROM IPAM.DhcpScope s
WHERE s.PercentUsed > 80
ORDER BY s.PercentUsed DESC
```

`StatAddressesInUse` and `StatAddressesFree` come from the DHCP server itself, while
`PercentUsed` is IPAM's own figure over the subnet. When those disagree, `LastPollHadError`
usually explains why. `DisabledAtServer` matters because a disabled scope at 100 percent is
not an emergency.

### 7. Forward and reverse DNS disagreeing

```sql
SELECT TOP 100
    m.DNSServer,
    m.DNSZone,
    m.ClientHostName,
    m.ForwardZoneIPAddress,
    m.ReverseZoneIPAddress
FROM IPAM.DNSMismatch m
ORDER BY m.DNSZone, m.ClientHostName
```

Every row is a name whose A record and PTR record point at different addresses. This is the
entity behind IPAM's DNS mismatch report, and it is cheap enough to run in full.

### 8. Address requests still waiting for someone

```sql
SELECT TOP 50
    r.IPRequestId,
    r.RequestDate,
    r.FirstName,
    r.LastName,
    r.Email,
    r.Subnet,
    r.RequestAddressCount,
    r.State,
    r.Comment,
    a.Address,
    a.HostName,
    a.MacAddress,
    a.State AS AddressState
FROM IPAM.IPRequests r
LEFT JOIN IPAM.IPRequestAddresses a ON a.IPRequestId = r.IPRequestId
WHERE r.ResolutionDate IS NULL
ORDER BY r.RequestDate
```

`ResolutionDate IS NULL` is a more reliable "unresolved" test than any particular `State`
value, since `State` is an undocumented integer on both entities. The `LEFT JOIN` is
deliberate: a request that has not been allocated yet has no address rows, and an `INNER
JOIN` would hide exactly the requests you are looking for.

### 9. The audit trail for one address

```sql
SELECT TOP 100
    h.Timestamp,
    h.IPAddress,
    h.HistoryType,
    h.FromValue,
    h.IntoValue,
    h.Source,
    h.UserName,
    h.ICMP,
    h.SNMP,
    h.DNS,
    h.DHCP,
    h.ARP
FROM IPAM.IPHistory h
WHERE h.IPAddress = @ipAddress
  AND h.Timestamp >= @startUtc
ORDER BY h.Timestamp DESC
```

This answers "who took this address and when" better than anything else in the module.
`HistoryType` and `Source` are the readable forms of the `HistoryTypeN` and `SourceN`
bytes, so select the text ones. The five booleans record which scan methods saw the address
at that moment, which is how you tell an address that genuinely went quiet from one that a
firewall started blocking ICMP for.

Always time-bound this. `IPAM.IPHistory` grows with every scan of every address, and it is
one of the largest tables IPAM has.

### 10. Subnets whose scan is stalled

```sql
SELECT TOP 100
    g.FriendlyName,
    g.Address,
    g.CIDR,
    g.LastDiscovery,
    g.ScanInterval,
    g.DisableAutoScanning,
    si.ScanInstanceType,
    si.Status AS ScanStatus,
    si.QueueTimeStamp,
    si.ScanStartTimeStamp,
    si.StartedBy
FROM IPAM.GroupNode g
LEFT JOIN IPAM.ScanInstance si ON si.SubnetId = g.GroupId
WHERE g.GroupType = 8
ORDER BY g.LastDiscovery
```

The join condition is the whole point of this query: `IPAM.ScanInstance.SubnetId` matches
`IPAM.GroupNode.GroupId`, despite the name. A row with a `QueueTimeStamp` and no
`ScanStartTimeStamp` has been queued and never started, which is the signature of a stuck
scan engine. A subnet with an old `LastDiscovery` and `DisableAutoScanning = TRUE` is not
stuck, it is switched off, and those two need separating before anyone opens a ticket.

### 11. What is in a DNS zone for one address

```sql
SELECT TOP 100
    z.Name AS ZoneName,
    z.ZoneType,
    z.DnsViewId,
    r.Name AS RecordName,
    r.Type AS RecordType,
    r.Data
FROM IPAM.DnsRecord r
JOIN IPAM.DnsZone z ON r.DnsZoneId = z.DnsZoneId
WHERE r.Data = @ipAddress
ORDER BY z.Name, r.Name
```

`IPAM.DnsRecord.Data` holds the record's payload, which for an A record is the address. Two
records with different names and the same `Data` is a legitimate alias; the same name in two
zones with different `Data` is usually the bug you were looking for. Join
`IPAM.DnsRecordType` on `r.Type` if you want the record type as a word.

## Gotchas

**`GroupId` and `SubnetId` are different ids, and the verbs want `GroupId`.**
`IPAM.Subnet.SubnetId` and `IPAM.GroupNode.GroupId` are both `System.Int32` and both look
like a subnet id, so passing the wrong one produces an error about a subnet that does not
exist rather than a type failure. `AddIpRange`, `RemoveIpRange`,
`CreateSubnetForGivenParentNode`, `ChangeDisableAutoScanning`, `ChangeIpStatus`,
`RemoveGroup`, `DeleteDhcpServer`, `DeleteDnsServer`, `StartScanDhcpServer` and
`StartScanDnsServer` all take a `GroupId`. `IPAM.ScanInstance.SubnetId` is also a `GroupId`
in spite of its name.

**`StartIpReservation` and `CreateIpReservation` are unrelated.** The first holds an
address inside IPAM for a few minutes. The second writes a permanent MAC binding into a
DHCP server. They live on different entities and do different things to different systems.

**A reservation that is never finished expires silently.** SolarWinds states that when the
reservation time runs out the address status is set back to Available. If your provisioning
step takes longer than `reservationTimeInMinutes`, something else can take the address you
thought you had. Set the timeout to match the work, and always call `FinishIpReservation`
or `CancelIpReservation`.

**`subnetCidr` and `rawCidr` are strings, `cidr` on a supernet is a number.**
`GetFirstAvailableIp(subnetAddress, subnetCidr)`, `StartIpReservation` and all five
`CreateSubnet` variants type the CIDR as a string in the Swagger contract.
`IPAM.SupernetManagement.CreateSupernet(supernetName, address, cidr, description,
parentGroupId)` and `EditSupernet(id, name, cidr, description)` type it as a number. There
is no consistency to learn, only a signature to check.

**An IPv4 `IPAM.Subnet` must be between /22 and /32.** SolarWinds documents `CIDR` as
required, non-editable, and "greater than 21 and less than or equal to 32". Larger blocks
are supernets.

**Above /20, addresses are not created for you.** The `AddIpRange` documentation states
that for subnets with a CIDR larger than /20 the individual addresses are not populated
automatically. A large subnet whose `TotalCount` looks wrong is usually this, not a scan
failure.

**`IPAM.IPNode` metadata columns are rejected while the status is Available.** SolarWinds
documents `IPMapped`, `Alias`, `MAC`, `DnsBackward`, `DhcpClientName` and `Comments` as
having to be undefined when `Status` is Available. Set the status first.

**The status byte is not documented in 2026.2.** No IPAM entity carries a property summary
in the extracted schema, so the mapping from `IPAM.IPNode.Status` to Used, Available,
Reserved, Transient and Blocked is not stated anywhere in `data/`. Derive it with the
`IPAM.IPInfo` query above, or read `IPAM.IPNodeReport.IPStatus`, which is already a string.

**Two custom property systems coexist.** `IPAM.AttrDefine` with `IPAM.IPNodeAttr` and
`IPAM.GroupNodeAttr` is IPAM's own; `IPAM.NodesCustomProperties` and
`IPAM.GroupsCustomProperties` are the platform's. Since IPAM 4.8, group custom fields are
no longer IPAM's own, so create and remove on `IPAM.GroupNodeAttr` no longer apply and
values are written through `IPAM.GroupNodeDisplayCustomProperties`.

**Five entities have no properties at all.** `IPAM.SubnetManagement`,
`IPAM.IPAddressManagement`, `IPAM.DhcpDnsManagement`, `IPAM.GroupManagement` and
`IPAM.SupernetManagement` are verb facades. `SELECT` against any of them fails. If a
generated client offers them as queryable tables, it is wrong.

**`RemoveGroup` deletes children.** One integer argument, no confirmation, no dry run. Read
[`IPAM.GroupNode`](#the-hierarchy-groups-supernets-subnets) with a `Children` walk before
calling it, and consider whether `RemoveIpRange` on a specific range is what you actually
wanted.

**`IPAM.DHCPScopeOverlapping`'s navigation property is `DHCPScopeOvrLapp`.** Abbreviated,
inconsistently cased against the entity name, and impossible to guess. Look it up.

**The published API pages run ahead of and behind 2026.2 at the same time.** The
Observability 2022.2 page documents scope editing and deletion verbs marked "available since
2026.4" that do not exist in 2026.2; the vNext page omits eight verbs that do. Neither is
wrong, they are just written against different builds. Confirm with `Metadata.Verb`.

**Eight verbs are in the schema and in no published document.** `CreateDhcpCredentials`,
`CreateDnsCredentials`, `StartDhcpCredentialsTest`, `StartDnsCredentialsTest`,
`StartScanDhcpServer`, `StartScanDnsServer`, `UpdateDhcpServer` and `UpdateDnsServer` come
from the Swagger contract alone; none of the seven published IPAM pages mentions any of
them. Their argument names and types are verified, their semantics are not.
`Metadata.VerbArgument.XmlTemplate` on your own server is the next best source. A ninth,
`GetFirstAvailableIpv6`, is undocumented **and** absent from the Swagger contract, so even
its arguments are unknown.

**IPAM has its own per-group role model.** `IPAM.AccountRoles` and `IPAM.GroupRole` record
Admin, PowerUser, Operator, ReadOnly and NoAccess per account per group. None of the 67
verbs declares a platform right in the schema, so a permission failure is usually an IPAM
role on that branch of the tree. On top of that, ordinary platform account limitations
still filter query results silently, so two accounts running the same IPAM query
legitimately see different subnets.

**Do not build time windows with `GetUtcDate()` plus the `AddX` functions.** They compile
to T-SQL `DATEADD`, which is timezone blind, so the combination is wrong by your server's
UTC offset. Compute bounds in the client and bind them, which is what the queries above do.
See [../swql/date-and-time.md](../swql/date-and-time.md).

## Related pages

- [README.md](README.md) for the module index and how to check what is installed.
- [udt.md](udt.md) for the other half of the address question: IPAM says who owns an
  address, UDT says which switch port it is plugged into.
- [../platform/modules.md](../platform/modules.md) for the whole-schema namespace map.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional arguments and
  serialisation.
- [../swis/crud.md](../swis/crud.md) and [../swis/uris.md](../swis/uris.md) for creating
  subnets and addresses without a verb.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking a live
  server which IPAM verbs it actually has.
- [../swql/joins-and-navigation.md](../swql/joins-and-navigation.md) for the navigation
  property syntax the tree queries use.
- [../swql/date-and-time.md](../swql/date-and-time.md) for time-bounding `IPAM.IPHistory`.
- [../reference/netobject-types.md](../reference/netobject-types.md) for the `IPAMG`,
  `IPAMN` and `IPAM-DSO` prefixes.
- [../reference/verb-index.md](../reference/verb-index.md) for all 67 IPAM verbs with their
  ordered parameters.
- [../../scripts/swql/13-hardware-wireless-ipam.swql](../../scripts/swql/13-hardware-wireless-ipam.swql)
  for the utilization and address-lookup queries this page builds on.

## Official SolarWinds documentation

- [IPAM API index](https://solarwinds.github.io/OrionSDK/docs/ip-address-manager/ipam-api/),
  which links all seven per-version pages
- [IPAM vNext API](https://solarwinds.github.io/OrionSDK/docs/ipam-vnext-api/), the closest
  match to 2026.2 for the range, group and IPv6 reservation verbs
- [IPAM Observability 2022.2 API](https://solarwinds.github.io/OrionSDK/docs/ipam-observability-2022-2/),
  which carries the fullest `AddDhcpScope` documentation and the newer scope editing verbs
- [IPAM 2019.4 and higher API](https://solarwinds.github.io/OrionSDK/docs/ipam-2019-4-and-higher-versions-api/),
  useful when you are working against an older server
- [Orion SDK documentation index](https://solarwinds.github.io/OrionSDK/)
