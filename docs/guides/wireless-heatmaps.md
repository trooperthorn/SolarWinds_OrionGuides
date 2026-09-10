# Wireless heat maps

A heat map is the one part of the wireless model that is not simply polled and displayed.
It is computed: a floor plan, a set of access points placed on it at known coordinates, a
scale, and a body of signal measurements, run through a generation job that produces
coverage and infers where each client is standing.

That makes it the part people most often try to script, and the part where the schema is
most likely to say no. This page covers where the numbers come from, how to read them, what
can and cannot be written back, and what that means for hardware the feature was not built
for.

The entity family is `Orion.WirelessHeatMap.`, eleven entities, contributed by NPM. For the
rest of the wireless model — controllers, access points, radios, clients, rogues — see
[../modules/npm.md](../modules/npm.md#wireless), which also explains which of the four
overlapping wireless families to use. Worked queries for everything below are in
[../../scripts/swql/17-wireless-heatmaps.swql](../../scripts/swql/17-wireless-heatmaps.swql).

## Where the data comes from

Three sources feed a map, and they are not equivalent.

**Access point transmit power** is polled over SNMP from the wireless controller. The
generation job needs to know how hard each radio is transmitting before it can infer
anything from how loudly a client was heard. This lands in
`Orion.WirelessHeatMap.SignalIdentification`, one row per antenna slot, carrying
`AntennaSlot`, `AntennaMACAddress` and `TransmittedSignalStrength`.

**Client received signal strength** is polled the same way, from the controller's table of
per-client, per-antenna RSSI. This is the substance of the map. It lands in
`Orion.WirelessHeatMap.Measurement`, keyed back to the antenna through
`SignalIdentificationID`.

**Signal samples** are taken by hand. An operator walks an associated client device to a
known physical spot, marks that spot on the floor plan, and the platform records what the
controller heard from that client at that moment. Samples calibrate the propagation model
against the building — walls, floors, and everything else a free-space calculation gets
wrong. They persist until deleted or until the access points move.

SolarWinds' own documentation names the OIDs involved and states that heat maps support
Cisco controllers only, of the 2500, 5500 and 7500 class exposing the CleanAir OIDs, with
each access point additionally answering the absolute-power and PHY-transmit-power objects.
Those OID values are vendor MIB facts rather than schema facts, so they are not in `data/`
and are not asserted here; the [support article][hmsupport] is the citation. What the
platform does with them is visible in the schema, and that is what this page documents.

### What is computed rather than collected

`Orion.WirelessHeatMap.ClientLocation` carries `X`, `Y` and `LastCalculationTime` per client
MAC address per map. These are **derived**, not polled: the generation job trilaterates each
client from the AP-reported RSSI values against the placed AP coordinates and the map scale.
A stale `LastCalculationTime` means generation has not run, not that the client has not
moved.

The documented minimum before clients render at all is four access points, or three plus a
signal sample.

## The shape of the data

```
Orion.MapStudioFiles                      the floor plan image itself
  └─ Orion.WirelessHeatMap.Map            the map: scale, dimensions, generation state
       ├─ Orion.WirelessHeatMap.MapPoint  a placed thing, at X/Y
       │    ├─ …SignalIdentification      per antenna: which radio, how hard it transmits
       │    │    └─ …Measurement          per sample: how loudly it was heard
       │    └─ (a point is an AP or a reference point — see below)
       └─ …ClientLocation                 computed client positions
```

Four things about this structure are worth knowing before writing any code against it.

**`MapPoint` is polymorphic.** It inherits `PointID`, `MapID`, `X` and `Y` from `Orion.Map.Point`
and adds `EntityType` and `InstanceId`. Those two columns are what make a point an access
point rather than a manually placed reference point. For an access point, `EntityType` holds
`'Orion.WirelessHeatMap.AccessPoints'` and `InstanceId` holds that entity's `ID`. Joins to
the AP entity therefore go through `InstanceId`, not through a declared navigation property.

**`Map` inherits its dimensions.** `Width` and `Height` come from `Orion.Map`, alongside
`MapStudioFileID`. `Orion.WirelessHeatMap.Map` itself adds `ProjectID`, `DisplayName`,
`Scale`, `ScaleUnit`, `PercentProgress`, `ProcessingEngine`, `GenerateStarted`,
`LastGenerationStarted`, `LastGenerationFinished` and `ErrorCode`.

**Only the map is creatable.** `Orion.WirelessHeatMap.Map` declares `canCreate: true`. Every
other entity in the family declares `canCreate: false` and is written by a verb or by the
generation job. This is the single most consequential fact on the page; see
[what cannot be written](#what-cannot-be-written).

**The access-control right is `manageMaps`.** These are the only entities in the NPM
families gated by it rather than by `manageNodes` — `Orion.WirelessHeatMap.Map` for create,
update, delete and invoke, and `Orion.WirelessHeatMap.MapPoint` for invoke. An account that
can do everything else on the platform may see nothing here. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

The remaining entities are supporting cast. `Orion.WirelessHeatMap.AccessPoints` is the
heat-map view of an AP, navigating to `Orion.Nodes` and to a `WebUri` child.
`Orion.WirelessHeatMap.PollingStatus` records whether RSSI collection ran for a node.
`Orion.WirelessHeatMap.ErrorCode` is a lookup table carrying a single `Code` column.
`Orion.WirelessHeatMap.ResourceLimitation` and
`Orion.WirelessHeatMap.ResourceClientLimitation` scope a console resource to particular
access points or clients.

## Reading it

The queries are in
[../../scripts/swql/17-wireless-heatmaps.swql](../../scripts/swql/17-wireless-heatmaps.swql).
Two of them are worth calling out because of how they are written.

Joining a map point to its signal data needs `LEFT JOIN`, not `JOIN`:

```sql
SELECT p.PointID, p.EntityType, p.InstanceId, p.X, p.Y,
       s.AntennaSlot, s.AntennaMACAddress, s.TransmittedSignalStrength,
       me.MeasurementID, me.ReceivedSignalStrength
FROM Orion.WirelessHeatMap.MapPoint p
LEFT JOIN Orion.WirelessHeatMap.SignalIdentification s ON s.PointID = p.PointID
LEFT JOIN Orion.WirelessHeatMap.Measurement me ON me.SignalIdentificationID = s.SignalIdentificationID
WHERE p.MapID = 1
```

A point that has never been polled has no `SignalIdentification` children at all. An inner
join silently drops exactly the rows you opened the query to find.

And collection health lives in one small entity that is easy to overlook:

```sql
SELECT ps.NodeID, ps.IsAPRSSIPolling, ps.LastPollStarted, ps.LastPollFinished,
       ps.CompleteStatus, ps.LastPollMessage
FROM Orion.WirelessHeatMap.PollingStatus ps
ORDER BY ps.LastPollFinished DESC
```

`LastPollMessage` is the first thing to read when a map generates cleanly and shows no
clients. A false `CompleteStatus` with a populated message usually means the controller did
not answer the RSSI table — credentials, an ACL, or a controller model the feature does not
support.

## Writing it

SWQL cannot write. There is no INSERT, UPDATE or DELETE statement in the language; the write
path is SWIS CRUD for entities that allow creation and Invoke for verbs. See
[../swis/crud.md](../swis/crud.md) and [../swis/invoke-verbs.md](../swis/invoke-verbs.md).
For heat maps it is almost entirely Invoke, because only the map allows creation.

The family declares 26 verbs across four entities. The full signatures, with parameters in
order, are in [../reference/verb-index.md](../reference/verb-index.md); the ones that carry
the workflow are:

| Verb | Parameters |
|---|---|
| `Orion.MapStudioFiles.InsertFile` | `path, imageFile, owner, fileType, timeStamp` |
| `Orion.WirelessHeatMap.Map.InsertMap` | `name, scale, scaleUnit, width, height, mapStudioFileGuid` |
| `Orion.WirelessHeatMap.Map.InsertWirelessHeatMap` | `projectId, name, scale, scaleUnit, width, height` |
| `Orion.WirelessHeatMap.MapPoint.InsertMapPoint` | `mapId, entityType, instanceId, x, y` |
| `Orion.WirelessHeatMap.Map.PollAPSignalStrengthNow` | `heatmapId` |
| `Orion.WirelessHeatMap.Map.PollRPSignalStrengthNow` | `heatmapId, clientIdVsMapPointIdMap` |
| `Orion.WirelessHeatMap.Map.StartClientSignalPoll` | `heatmapId, clientIdVsMapPointIdMap` |
| `Orion.WirelessHeatMap.Map.GetProgress` | `keysByEngines` |

Arguments are positional. A reordered call does not raise an error, it does the wrong thing,
which is why the repository checks verb signatures written into prose against the extracted
data on every build.

Note the two creation verbs. `InsertMap` binds a map to an image already in the map file
store and is the classic Network Atlas shape. `InsertWirelessHeatMap` takes a `ProjectID`
instead and no file GUID, and is the Intelligent Maps shape. Which one your installation
expects depends on which map system you are targeting.

A build sequence looks like this:

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

$guid = Invoke-SwisVerb $swis Orion.MapStudioFiles InsertFile @(
    'FloorPlans\Building3-L2.png', $imageBytes, 'admin', $fileType, $timeStamp)

$mapId = Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map InsertMap @(
    'Building 3 Level 2', 0.05, 0, 1200, 800, $guid)

foreach ($p in $placements) {
    Invoke-SwisVerb $swis Orion.WirelessHeatMap.MapPoint InsertMapPoint @(
        $mapId, 'Orion.WirelessHeatMap.AccessPoints', $p.ApId, $p.X, $p.Y)
}

Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map PollAPSignalStrengthNow @($mapId)
```

`fileType` for `InsertFile`, and the `ScaleUnit` byte enumeration, are installation data
rather than schema and are **not recorded in the published schema**; both are unverified
here. Read existing rows before writing new ones.

A community report describes `InsertMapPoint` as part of the public API but not intended for
end users, and as inserting inconsistently, recommending Network Atlas instead. The source
thread could not be retrieved to confirm the attribution, so treat that as a caution to test
in a lab rather than as an established limitation.

### What cannot be written

`Orion.WirelessHeatMap.SignalIdentification` and `Orion.WirelessHeatMap.Measurement` both
declare `canCreate: false` and expose no Insert verb. Nothing in the public API writes a
signal measurement.

The consequence is worth stating plainly, because it is the thing people discover after
building most of an integration: you can script the map, the floor plan image, the scale and
every access point placement, and you cannot supply a single RSSI value. Measurements arrive
only through the poll verbs, and those read the controller over SNMP. There is no entry point
for synthetic data, for a third-party site-survey export, or for signal harvested from a
controller the platform does not recognise.

### The one supported way to inject a sample

Two verbs compose into a remote equivalent of the Network Atlas signal-sample workflow:

```
InsertMapPoint(mapId, entityType, instanceId, x, y)          -> PointID
PollRPSignalStrengthNow(heatmapId, clientIdVsMapPointIdMap)  -> DataTable
```

`RP` is reference point. The pattern is to assert that a given client is physically standing
at a given map point, and let the platform poll the controller for that client's RSSI and
write the `SignalIdentification` and `Measurement` rows itself. No direct table writes and
no unsupported calls — it is the same engine path the desktop tool uses, reachable over
SWIS.

This is the seam worth knowing about. It means the survey workflow can be driven from
something other than a Windows desktop, which is otherwise the only way to take a sample.

It does not lift the vendor constraint. `PollRPSignalStrengthNow` polls *the controller*: the
caller asserts position, the controller supplies signal. Against hardware the platform cannot
poll, the verb has nothing to read.

Whether `clientIdVsMapPointIdMap` can be constructed by an external caller at all is **not
recorded in the published schema** and is unverified here. `Metadata.VerbArgument` carries
`XmlTemplate` and `XmlSchemas`, which is what settles it on a live server:

```sql
SELECT va.EntityName, va.VerbName, va.Position, va.Name, va.Type,
       va.IsOptional, va.XmlTemplate, va.Summary
FROM Metadata.VerbArgument va
WHERE va.EntityName LIKE 'Orion.WirelessHeatMap.%'
ORDER BY va.EntityName, va.VerbName, va.Position
```

If `XmlTemplate` comes back populated for that parameter, the shape is discoverable and the
path is open. If it is empty, treat that as the answer.

## Hardware the feature was not built for

Wanting heat maps for non-Cisco wireless is a reasonable thing to want, and it comes up
often enough to be worth setting out honestly. Three approaches exist and only two are real.

**Injecting into the native engine** is not viable, for the reason in
[what cannot be written](#what-cannot-be-written). No amount of API work gets a measurement
into the tables.

**Presenting other hardware as a supported controller** — a service that polls a vendor API
and exposes an SNMP agent implementing the controller MIB the platform expects — is the only
route into the real generation engine that does not touch the database. Everything
downstream then works unmodified, including the reference-point path above.

The cost is larger than the OID list suggests. Implementing the client RSSI table alone is
not enough: wireless discovery must first *classify* the device, which means a plausible
sysObjectID and enough of the access point, radio-interface and mobile-station tables for
discovery to complete. Index stability across polls matters, or
`Orion.WirelessHeatMap.AccessPoints.Index` churns and placed points detach from their access
points. Exactly which objects discovery requires before it will classify a device as a
supported controller is **not recorded in the published schema** and is unverified here; it
would have to be established against real hardware or from the shipped discovery
definitions. The approach is also fragile across platform upgrades, and nothing about it is
supportable.

**Bypassing the generation engine** — holding survey data in a custom table or an
`Orion.APIPoller.ApiPoller` feed and rendering coverage in a custom widget — forfeits the
generation engine and buys vendor independence permanently. See
[../webui/modern-dashboard-authoring.md](../webui/modern-dashboard-authoring.md) and
[../webui/custom-query-widget.md](../webui/custom-query-widget.md).

For an estate that is not Cisco-first, the third option is usually the better trade. The
second is more interesting engineering and means maintaining a synthetic controller
indefinitely, with a failure mode of the platform quietly declassifying the device after a
patch.

### If the survey is the goal

Note that the vendor problem and the *surveying* problem are separable, and only the first
is a platform constraint. A mobile survey client that drives `InsertMapPoint` and
`PollRPSignalStrengthNow` is buildable today against supported hardware, and replaces a
desktop-only dependency.

Two things dominate whether that works, and neither is an Orion question. Client-side Wi-Fi
scanning on modern mobile platforms is rate-limited hard enough to bound how fast a survey
can be walked — though that constraint largely disappears on the reference-point path, where
the controller performs the measurement and the client only asserts position. And per-device
MAC randomization, on by default, decorrelates the survey handset from the client the
platform sees; since `ClientLocation` and the reference-point map are both keyed on
`ClientMACAddress`, the address must be pinned for the survey network and the pinning
verified rather than assumed.

One measurement caveat is worth recording because it is easy to get backwards. The schema is
*uplink*: `Measurement.ReceivedSignalStrength` is what the antenna heard from the client. A
handset survey measures *downlink*, what the handset heard from the antenna. Path loss is
reciprocal but transmit powers are not, which is why the engine polls transmit power
separately. Downlink readings do not drop into an uplink-shaped schema without a per-antenna
offset that varies with the radio's current power level.

## What the platform will and will not ingest

The question behind most heat-map scripting is whether there is any way in — for signal
data, or failing that for wireless clients — that does not go through a controller
SolarWinds already polls. Checked against the schema and the vendor documentation, the answer
is no on both counts, and the shape of the no is worth recording.

### The collector is a discrete, gated poller

The data path is a named poller, listed under Settings → Manage Pollers → Wireless
Controller, disabled by default, and enabled on a controller when Network Atlas or
Intelligent Maps places that controller's access points on a map. Assignment is a poller
test against the device rather than a vendor list: community reports describe Manage Pollers
refusing to apply it to a non-Cisco controller because the OIDs did not match, and SolarWinds
staff have stated that support is "dependent on the dataset available from the WLC". Its log
is `WLHM.BusinessLayer.log` under the platform log directory.

### The engine reads two stores, and only one is Cisco-specific

SolarWinds' knowledge base on clients missing from heat maps names the storage the
generation job reads: a wireless-interfaces table holding every access point antenna MAC,
populated by the ordinary wireless poller, which is multi-vendor; and a client-measurement
table holding RSSI **per client, per access point interface**, populated only by the heat-map
poller. The job needs readings from three or four interfaces per client before it will place
one, and the documented failure when a controller does not report every antenna MAC is
exactly the symptom people see: access points render, clients do not.

That is the precise vendor gate — a per-client, per-antenna signal matrix across every access
point that can hear the client. Everything else in the pipeline is generic.

### Nothing wireless is creatable

Every entity in `Orion.Packages.Wireless.`, `Orion.Wireless.`, `Orion.NPM.WL.`,
`Orion.NPM.Wireless.`, `Orion.UDT.AllWirelessEndpoints` and `Orion.Orchestrators.` declares
`canCreate: false`, and none carries a verb except `Orion.Orchestrators.Info`. Device Studio
does not help either: its technologies are CPU and memory, multi-CPU and memory, and node
details, none of which produce a wireless entity. So it is not only measurements that cannot
be injected. A wireless client, access point, radio or controller row cannot be created by
any public call; the wireless model is populated by shipped pollers or not at all.

### The paths that exist

Two families of vendor support populate the wireless model. SNMP-polled controllers — Cisco
WLC, Aruba Mobility, HP MSM, Extreme WiNG, Ruckus ZoneDirector, FortiGate — and API-polled
orchestrators added through `Orion.Orchestrators.Info`, whose creation verbs are a closed set
(`AddMerakiNode`, `AddArubaCentralNode`, `AddJuniperMistNode`, `AddRuckusOneNode`,
`AddRuckusSmartZoneNode`, `AddExtremeCloudIQNode`, `AddAristaWMNode`,
`AddFortiEdgeCloudNode`) with no generic equivalent. `CreateOrchestratorPluginConfiguration`
configures product types on an orchestrator that already exists; it is not a hook for a new
vendor.

The orchestrator path is worth knowing because it does record per-client signal: the Aruba
Central integration writes client name, SSID, addresses, MAC and signal strength into
`Orion.Packages.Wireless.Clients`. That single value — one RSSI per client, from the access
point it is associated with — is the only vendor-neutral client-reporting shape the platform
has, and it is reachable only through a shipped orchestrator. Heat maps remain Cisco-only in
both families.

```sql
SELECT c.MAC, c.Name, c.IPAddress, c.SSID, c.SignalStrength, c.LastUpdate,
       c.WirelessInterface.AccessPoint.Name AS AccessPoint,
       c.WirelessInterface.AccessPoint.ControllerName AS Controller
FROM Orion.Packages.Wireless.Clients c
WHERE c.SignalStrength IS NOT NULL
ORDER BY c.SignalStrength
```

### What that means for a vendor outside both lists

Take Ubiquiti UniFi as the worked case, since it is the one most often asked about. Over
SNMP, UniFi access points answer parts of the IEEE 802.11 MIB, so an access point may be
discovered as an autonomous AP with an SSID and channel; but that MIB has no station table,
and Ubiquiti's own MIB exposes per-radio BSSID, channel, transmit power and a *count* of
stations, with no per-client object at all. Over the controller's APIs it depends which one:
the versioned Integration API (Network 10.4.57) describes a client as an id, name, MAC, IP,
connection time, type and uplink device, with no signal field of any kind; the older
unversioned controller API does return RSSI, signal, noise, the associated access point and
radio per client — but one reading, from that one access point, and only for clients
currently connected. The neighbour-heard readings the engine needs are not exposed by
either, nor by the access point's own station list read over SSH.

So a service presenting UniFi as a Cisco controller over SNMP, which is otherwise the only
route into the generation engine, cannot satisfy it without inventing the missing readings.
It would reproduce the documented failure exactly. The SolarWinds-endorsed pattern for
Ubiquiti, described by a SolarWinds product manager on THWACK, deliberately stays outside the
wireless model: import sites and devices as ICMP-only nodes with custom properties, and poll
the UniFi API from a SAM application template. Client reporting and coverage rendering for
such hardware belong in that pattern — a custom table and a custom widget — not in
`Orion.WirelessHeatMap.`.

## When a map is wrong

Work down, not across. Each step names the query in
[17-wireless-heatmaps.swql](../../scripts/swql/17-wireless-heatmaps.swql).

**The map generates but shows no coverage.** Read `ErrorCode` and `PercentProgress` on
`Orion.WirelessHeatMap.Map`. A non-zero `ErrorCode` is a failed run — what the byte values
mean is not recorded in the published schema, so `Orion.WirelessHeatMap.ErrorCode` on your
own server is the lookup. `PercentProgress` stuck below 100 with `GenerateStarted` set
points at `ProcessingEngine` rather than at the data.

**Generation is clean but there is nothing to draw.** Look for map points with no
`SignalIdentification` children. If every point is bare, collection never ran, and
`Orion.WirelessHeatMap.PollingStatus` will say why: `IsAPRSSIPolling` false means it is not
enabled for that node, and a false `CompleteStatus` means it ran and failed, with
`LastPollMessage` carrying the detail.

**Access points render and clients do not.** Check the count of placed points first — below
four access points, with no signal sample, clients are not expected to appear. Then confirm
the controller is a model the feature supports and that the access points answer the
transmit-power objects, since without those the generation job cannot convert RSSI into
distance. Finally check `ClientLocation.LastCalculationTime`: positions that are hours stale
mean generation is not re-running, which is a scheduling problem rather than a collection
one.

**Nothing is visible at all, to one account.** Confirm the account holds `manageMaps`. It is
not implied by node management rights.

## Related pages

- [../modules/npm.md](../modules/npm.md#wireless) — the wireless model these sit on, and the
  four overlapping families
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) — calling verbs, and positional
  arguments
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) — asking a live
  server what it actually declares
- [../reference/verb-index.md](../reference/verb-index.md) — every verb signature
- [../reference/unverified.md](../reference/unverified.md) — what this repository declines to
  assert, including everything flagged above

[hmsupport]: https://support.solarwinds.com/SuccessCenter/s/article/Wireless-heat-map-support
