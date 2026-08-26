# A Layer 2 switching Modern Dashboard for the whole platform

The companion to [soc2-dashboard-10k-nodes.md](soc2-dashboard-10k-nodes.md), scoped to the
access and distribution layer: switch ports, interfaces, duplex, VLANs, trunks, topology,
and the endpoints plugged into it all. Every query is validated against the extracted
2026.2 schema (`python3 tools/validate_swql.py --docs docs/guides/layer2-switching-dashboard.md`),
and the Modern Dashboard widget type is called out per query. The assembly rules — SWQL
written twice per widget, one query per KPI tile, columns feeding formatters — are in
[../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md).

Two modules carry this page:

- **NPM** gives you `Orion.NPM.Interfaces` — status, utilisation, errors, discards,
  duplex. Present on every installation.
- **UDT** gives you `Orion.UDT.Port` and its denormalised views — per-port endpoint
  tracking, VLAN membership, watch lists, rogue detection, unused ports. The rows marked
  *(requires UDT)* silently return nothing useful without it. The module's entity map is
  [../modules/udt.md](../modules/udt.md).

The scale rules from the SOC 2 page apply unchanged: aggregate server-side, `TOP`-bound
every table, scope tables to exceptions, and time-bound anything historical.

Value mappings used below, from [../modules/udt.md](../modules/udt.md) and the NPM
interface property prose: interface `Status` 0 Unknown / 1 Up / 2 Down / 3 Warning /
4 Shutdown / 9 Unmanaged; `AdminStatus` and UDT `AdministrativeStatus` 1 Up / 2 Down;
UDT `OperationalStatus` 1 Up / 2 Down; `Duplex` 0 Unknown / 1 Full / 2 Half / 3 Disagree /
4 AutoNegotiate; `TrunkMode` 0 Unknown / 1 Trunking / 2 NonTrunking; and
`Orion.NPM.Interfaces.DuplexMode = 2` is half duplex.

---

## Row 1 — Switching health scorecard (`kpi` widget, six tiles)

One query per tile, one row per query.

**Tile 1 — Monitored interfaces**

```sql
SELECT COUNT(i.InterfaceID) AS [Monitored Interfaces]
FROM Orion.NPM.Interfaces i
```

**Tile 2 — Interfaces down** (operationally down while administratively up — a shut port
is not a fault)

```sql
SELECT COUNT(i.InterfaceID) AS [Interfaces Down]
FROM Orion.NPM.Interfaces i
WHERE i.Status = 2 AND i.AdminStatus = 1
```

**Tile 3 — Half-duplex interfaces** (the classic "slow but not down" cause — the full
triage query is [cookbook.md #26](cookbook.md))

```sql
SELECT COUNT(i.InterfaceID) AS [Half Duplex]
FROM Orion.NPM.Interfaces i
WHERE i.DuplexMode = 2
```

**Tile 4 — Interfaces with errors today**

```sql
SELECT COUNT(i.InterfaceID) AS [Erroring Today]
FROM Orion.NPM.Interfaces i
WHERE i.InErrorsToday + i.OutErrorsToday > 0
```

**Tile 5 — UDT-monitored ports** *(requires UDT — `IsMonitored` is the licence-consuming
flag)*

```sql
SELECT COUNT(p.PortID) AS [Monitored Ports]
FROM Orion.UDT.Port p
WHERE p.IsMonitored = TRUE
```

**Tile 6 — Watch-list endpoints present right now** *(requires UDT)*

```sql
SELECT COUNT(wp.WatchID) AS [Watched Present]
FROM Orion.UDT.WatchListPresent wp
WHERE wp.Present = TRUE
```

## Row 2 — Interface faults (the actionable lists)

**Down-but-shouldn't-be interfaces** (`table` widget). `_URL`/`_Status` columns are parked
with `isActive: false` and wired into the `EntityLinkFormatterComponent` on the visible
columns, per [the authoring guide](../webui/modern-dashboard-authoring.md#columns-exist-to-feed-formatters).

```sql
SELECT TOP 50
    i.Node.Caption AS [Switch],
    i.Node.DetailsUrl AS [Switch_URL],
    i.Node.Status AS [Switch_Status],
    i.Caption AS [Interface],
    i.DetailsUrl AS [Interface_URL],
    i.Status AS [Interface_Status],
    i.StatusDescription AS [State],
    i.LastChange AS [Since]
FROM Orion.NPM.Interfaces i
WHERE i.Status = 2 AND i.AdminStatus = 1
ORDER BY i.LastChange DESC
```

**Error and discard offenders** (`table` widget). Today's counters live on the interface
row itself, so this touches no history table.

```sql
SELECT TOP 20
    i.Node.Caption AS [Switch],
    i.Caption AS [Interface],
    i.DetailsUrl AS [Interface_URL],
    i.Status AS [Interface_Status],
    i.InErrorsToday AS [In Errors],
    i.OutErrorsToday AS [Out Errors],
    i.InDiscardsToday AS [In Discards],
    i.OutDiscardsToday AS [Out Discards],
    i.CRCAlignErrorsToday AS [CRC Errors]
FROM Orion.NPM.Interfaces i
WHERE i.InErrorsToday + i.OutErrorsToday
    + i.InDiscardsToday + i.OutDiscardsToday > 0
ORDER BY i.InErrorsToday + i.OutErrorsToday DESC
```

**Duplex problems** (`table` widget). `DuplexMode = 2` is half duplex; a gigabit port
running half duplex is almost always a negotiation failure.

```sql
SELECT TOP 50
    i.Node.Caption AS [Switch],
    i.Caption AS [Interface],
    i.DetailsUrl AS [Interface_URL],
    i.Status AS [Interface_Status],
    i.DuplexMode AS [Duplex],
    i.InterfaceSpeed AS [Speed bps]
FROM Orion.NPM.Interfaces i
WHERE i.DuplexMode = 2 AND i.Status = 1
ORDER BY i.InterfaceSpeed DESC
```

**Hot uplinks** (`table` widget) — utilisation above 80 % on up interfaces, with live
throughput alongside so a reader can tell a burst from a sustained squeeze.

```sql
SELECT TOP 20
    i.Node.Caption AS [Switch],
    i.Caption AS [Interface],
    i.DetailsUrl AS [Interface_URL],
    i.Status AS [Interface_Status],
    i.InPercentUtil AS [In %],
    i.OutPercentUtil AS [Out %],
    i.Inbps AS [In bps],
    i.Outbps AS [Out bps]
FROM Orion.NPM.Interfaces i
WHERE (i.InPercentUtil > 80 OR i.OutPercentUtil > 80)
  AND i.Status = 1
ORDER BY i.PercentUtil DESC
```

Bind the percentage columns to a `ThresholdFormatterComponent` rather than hard-coding
colours.

## Row 3 — VLANs and trunks

**VLAN footprint** (`proportional` widget, bar) — how many switches carry each VLAN.
`Orion.NodeVlans` is core platform data (no UDT needed).

```sql
SELECT
    nv.VlanName AS [Label],
    COUNT(nv.NodeID) AS [Value]
FROM Orion.NodeVlans nv
GROUP BY nv.VlanName
ORDER BY COUNT(nv.NodeID) DESC
```

**VLAN inventory** (`table` widget) — one row per VLAN per switch, bounded because a large
campus can carry thousands of rows here.

```sql
SELECT TOP 100
    nv.Node.Caption AS [Switch],
    nv.Node.DetailsUrl AS [Switch_URL],
    nv.Node.Status AS [Switch_Status],
    nv.VlanId AS [VLAN],
    nv.VlanName AS [Name],
    nv.VlanStatus AS [VLAN Status]
FROM Orion.NodeVlans nv
ORDER BY nv.VlanId, nv.Node.Caption
```

**Trunk ports** *(requires UDT)* (`table` widget). `TrunkMode = 1` is trunking; the
per-port VLAN list comes through the verified `PortVLANs` navigation to `Orion.UDT.VLAN`
if you want to expand it.

```sql
SELECT TOP 100
    p.Node.Caption AS [Switch],
    p.Node.DetailsUrl AS [Switch_URL],
    p.Node.Status AS [Switch_Status],
    p.Name AS [Port],
    p.DetailsUrl AS [Port_URL],
    p.PortDescription AS [Description],
    p.OperationalStatus AS [Oper],
    p.Speed AS [Speed bps]
FROM Orion.UDT.Port p
WHERE p.TrunkMode = 1 AND p.IsMonitored = TRUE
ORDER BY p.Node.Caption, p.Name
```

**Layer 2 adjacencies** (`table` widget). `Orion.TopologyConnections` has no navigation
properties, so the captions come from explicit joins. `LayerType` is a string the schema
does not enumerate — run `SELECT DISTINCT LayerType FROM Orion.TopologyConnections` on
your own server and add `WHERE tc.LayerType = '...'` with the L2 value it returns.

```sql
SELECT TOP 100
    sn.Caption AS [Switch A],
    sn.DetailsUrl AS [SwitchA_URL],
    sn.Status AS [SwitchA_Status],
    dn.Caption AS [Switch B],
    dn.DetailsUrl AS [SwitchB_URL],
    dn.Status AS [SwitchB_Status],
    tc.LayerType AS [Layer],
    tc.LastUpdateUtc AS [Last Seen (UTC)]
FROM Orion.TopologyConnections tc
JOIN Orion.Nodes sn ON tc.SrcOrionNodeID = sn.NodeID
JOIN Orion.Nodes dn ON tc.DestOrionNodeID = dn.NodeID
ORDER BY sn.Caption, dn.Caption
```

## Row 4 — Port capacity (requires UDT)

**Fullest access switches** (`table` widget). `Orion.UDT.PortCapacity` is the percentage
view behind UDT's licence dashboards; it carries a `DateTime`, so take the recent window
and the worst offenders. The UTC-safe window shape is from
[../swql/date-and-time.md](../swql/date-and-time.md).

```sql
SELECT TOP 15
    pc.Caption AS [Switch],
    MAX(pc.PortPercentUsed) AS [Ports Used %]
FROM Orion.UDT.PortCapacity pc
WHERE pc.DateTime >= ToUtc(AddDay(-1, ToLocal(GetUtcDate())))
GROUP BY pc.Caption
ORDER BY MAX(pc.PortPercentUsed) DESC
```

**Busiest access ports by endpoint count** (`table` widget) — a port with dozens of MACs
behind it is an unmonitored downstream switch or hub.

```sql
SELECT TOP 20
    ep.Name AS [Port],
    ep.DetailsUrl AS [Port_URL],
    ep.EndpointCount AS [Endpoints]
FROM Orion.UDT.AccessPortEndpointCount ep
ORDER BY ep.EndpointCount DESC
```

**Reclaimable ports** (`table` widget). `Orion.UDT.UnusedPorts` is the report that pays
for the module. `DaysUnused` is a `System.String`, so it neither sorts nor compares
numerically — display it, order by something else.

```sql
SELECT TOP 50
    up.Caption AS [Switch],
    up.Name AS [Port],
    up.DetailsUrl AS [Port_URL],
    up.PortDescription AS [Description],
    up.DaysUnused AS [Days Unused]
FROM Orion.UDT.UnusedPorts up
ORDER BY up.Caption, up.Name
```

## Row 5 — Who is plugged in (requires UDT)

**Rogue endpoints** (`table` widget) — devices UDT has seen that match no watch/allow
rule.

```sql
SELECT TOP 50
    re.DisplayText AS [Endpoint],
    re.NetobjectType AS [Type],
    re.LastSeen AS [Last Seen (UTC)]
FROM Orion.UDT.RogueEndpoints re
ORDER BY re.LastSeen DESC
```

**Watch list, aggregated** (`table` widget) — everything on the watch list with where it
last appeared.

```sql
SELECT TOP 50
    wa.WatchName AS [Watch],
    wa.MACAddress AS [MAC],
    wa.DNSName AS [DNS],
    wa.UserName AS [User],
    wa.LastSeen AS [Last Seen (UTC)]
FROM Orion.UDT.WatchListAggregated wa
ORDER BY wa.LastSeen DESC
```

**Recently seen MACs on monitored ports** (`table` widget). `Orion.UDT.MACCurrentInformation`
is the denormalised current-state view — node, port and endpoint columns pre-joined, with
`PortUrl`/`MacUrl` ready for link formatters.

```sql
SELECT TOP 50
    mc.HostName AS [Host],
    mc.MACAddress AS [MAC],
    mc.MacUrl AS [MAC_URL],
    mc.MACVendor AS [NIC Vendor],
    mc.IPAddress AS [IP],
    mc.PortName AS [Port],
    mc.PortUrl AS [Port_URL],
    mc.LastSeen AS [Last Seen (UTC)]
FROM Orion.UDT.MACCurrentInformation mc
ORDER BY mc.LastSeen DESC
```

## Scoping the page to switches only

`Orion.NPM.Interfaces` and `Orion.UDT.Port` scope themselves — a port implies a switch.
The node-level rows do not, and the stock schema has no "is a switch" flag. Two working
approaches:

- **`MachineType` prefix** — `WHERE n.MachineType LIKE 'Cisco Catalyst%'` and similar.
  Fragile across vendors; enumerate yours first with
  `SELECT DISTINCT MachineType FROM Orion.Nodes`.
- **A custom property** (`Role = 'Access Switch'`), joined through
  `Orion.NodesCustomProperties` exactly as in the
  [SOC 2 page's slicing section](soc2-dashboard-10k-nodes.md#slicing-by-customer-or-site) —
  sturdier, and it doubles as the `?filters=` drill-down key.

## Assembling and verifying

Identical to the SOC 2 page: validate
(`python3 tools/validate_swql.py --docs docs/guides/layer2-switching-dashboard.md`), start
from [`scripts/dashboards/minimal-dashboard.json`](../../scripts/dashboards/minimal-dashboard.json)
regenerating every `unique_key`, write each query in both `dataSource` places, then
`python3 tools/check_dashboards.py your-dashboard.json`.

## See also

- [soc2-dashboard-10k-nodes.md](soc2-dashboard-10k-nodes.md) — the platform-wide companion and the scale rules
- [../modules/udt.md](../modules/udt.md) — the UDT entity map, value tables and licence mechanics
- [../modules/npm.md](../modules/npm.md) — the interface entity in full
- [../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md) — turning these queries into an importable file
