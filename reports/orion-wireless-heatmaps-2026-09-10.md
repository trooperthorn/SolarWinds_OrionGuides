# SolarWinds Orion — Wireless Heat Maps: Data Model, Collection, and Injection

**Compiled:** 2026-09-10
**Platform version:** 2026.2 (SolarWinds Observability Self-Hosted, formerly Orion)
**Schema source:** `~/repos/SolarWinds_OrionGuides/data/schema/2026.2/`
**Query validation:** every SWQL block below passes `tools/validate_swql.py` against the 2026.2 schema

---

## 1. What the OrionGuides repo already covers

The **data model is fully present**. The **collection mechanism and the write path are not**.

| Present | Location |
|---|---|
| All 11 `Orion.WirelessHeatMap.*` entities, with properties and relationships | `data/schema/2026.2/entities/Orion.json` |
| 20 heat-map verbs with typed, **ordered** parameters | `data/schema/2026.2/verbs.json` |
| NetObject mapping: `Orion.WirelessHeatMap.Map` to prefix `WLHM`, key `MapID`, module NPM | `data/reference/netobject-types.json` |
| A ~9-line "Heat maps" subsection | `docs/modules/npm.md:299` |
| Verb / access-control table | `docs/modules/npm.md:503-504` |
| Family count (`Orion.WirelessHeatMap.` = 11 entities) | `docs/modules/npm.md:26` |

**Gap:** nothing states how the numbers get into those tables, and there is no worked create/inject
sequence. Sections 3-5 of this document fill that gap.

Lookup commands (no network, no server required):

```bash
cd ~/repos/SolarWinds_OrionGuides
python3 tools/schema_query.py find Orion.WirelessHeatMap
python3 tools/schema_query.py show Orion.WirelessHeatMap.Map
python3 tools/schema_query.py verbs --entity Orion.WirelessHeatMap.Map
python3 tools/schema_query.py verb Orion.WirelessHeatMap.MapPoint InsertMapPoint
```

---

## 2. The data model

```
Orion.MapStudioFiles                    floor-plan image blob
  FileId (Guid), FileName, FileData (Binary), FileType, Owner, Timestamp,
  LockUser, LockDate, ComputerName, IsDeleted, UpdateUser
        |
        | referenced by MapStudioFileID
        v
Orion.WirelessHeatMap.Map               canCreate: TRUE   base: Orion.Map
  MapID (Int32, key)      ProjectID (String)      DisplayName (String)
  Scale (Double)          ScaleUnit (Byte)        MapStudioFileID (Guid)
  Width, Height (Double - inherited from Orion.Map)
  PercentProgress (Byte)  ProcessingEngine (String)  GenerateStarted (Boolean)
  LastGenerationStarted / LastGenerationFinished (DateTime)
  ErrorCode (Byte)        DetailsUrl (String)
        |
        +--> Orion.WirelessHeatMap.MapPoint          base: Orion.Map.Point
        |      PointID, MapID, X, Y  (inherited from Orion.Map.Point)
        |      EntityType (String)   InstanceId (Int32)     <- polymorphic pointer
        |         |
        |         +--> Orion.WirelessHeatMap.SignalIdentification    (per antenna)
        |         |      SignalIdentificationID, PointID, AntennaSlot (Byte),
        |         |      AntennaMACAddress (String),
        |         |      TransmittedSignalStrength (Int16),
        |         |      NegativeTransmittedSignalStrength (Int16)
        |         |         |
        |         |         +--> Orion.WirelessHeatMap.Measurement   (per RSSI sample)
        |         |                MeasurementID (Int64), PointID, SignalIdentificationID,
        |         |                ReceivedSignalStrength (Int16),
        |         |                NegativeReceivedSignalStrength (Int16)
        |
        +--> Orion.WirelessHeatMap.ClientLocation    <- COMPUTED, not polled
               Id, MapId, ClientMACAddress, NodeID, X, Y, LastCalculationTime

Orion.WirelessHeatMap.AccessPoints      base: System.ManagedEntity
  ID (Int64), NodeID, Index (Int64), ControllerID (Int64), Description, IPAddress,
  Clients, WirelessType, Status, StatusDescription, StatusLED, Image, TypeDescription,
  Available, AvailablePercent, FirstUpdate, LastUpdate,
  InBps, OutBps, InPps, OutPps, DetailsUrl, ModernIcon
    nav: Node    -> Orion.Nodes   (Orion.NodeHostsWirelessHeatMap.AccessPoints)
    nav: WebUri  -> Orion.WirelessHeatMap.AccessPoints.WebUri  (ID, WebUri)

Orion.WirelessHeatMap.PollingStatus     <- ingest health
  NodeID, IsAPRSSIPolling (Boolean), LastPollStarted, LastPollFinished,
  CompleteStatus (Boolean), LastPollMessage (String)

Orion.WirelessHeatMap.ErrorCode                 Code (Byte)  - lookup table
Orion.WirelessHeatMap.ResourceLimitation        ResourceId, MapId, ResourceLimitationCount,
                                                APMACAddress, APLimitationCount
Orion.WirelessHeatMap.ResourceClientLimitation  ResourceId, MapId, ClientMACAddress
```

### Three structural facts that matter

1. **`MapPoint` is polymorphic.** `EntityType` + `InstanceId` is what makes a point an access point
   rather than a manual reference point. For an AP, `EntityType` is
   `'Orion.WirelessHeatMap.AccessPoints'` and `InstanceId` is that entity's `ID`.

2. **Only `Map` is directly creatable.** `Orion.WirelessHeatMap.Map` has `canCreate: true`.
   Every other entity in the family is `canCreate: false` — verb-driven or engine-written only.

3. **Access control is `manageMaps`, not `manageNodes`.** These are the only entities in the NPM
   families with that requirement. `Orion.WirelessHeatMap.Map` requires it for create, update,
   delete and invoke; `Orion.WirelessHeatMap.MapPoint` requires it for invoke. Web-console
   equivalent: `AllowMapManagement`. (See `docs/automation/accounts-and-permissions.md:380`.)

---

## 3. How the data is actually gathered

Three distinct sources feed a heat map.

### 3.1 AP transmit power — SNMP from the Cisco WLC

Polled from the wireless LAN controller, AIRESPACE-WIRELESS-MIB:

| OID | Object | Purpose |
|---|---|---|
| `1.3.6.1.4.1.14179.2.2.2.1.22` | `bsnAPIfAbsolutePowerList` | Absolute TX power levels the radio supports |
| `1.3.6.1.4.1.14179.2.2.2.1.6` | `bsnAPIfPhyTxPowerLevel` | Current PHY TX power level |

Every AP placed on the map must respond to both. Result lands in
`Orion.WirelessHeatMap.SignalIdentification`, one row per antenna slot
(`AntennaSlot`, `AntennaMACAddress`, `TransmittedSignalStrength`).

### 3.2 Client RSSI — SNMP from the Cisco WLC

| OID | Object | Purpose |
|---|---|---|
| `1.3.6.1.4.1.14179.2.1.11` | `bsnMobileStationRssiDataTable` | Per-client, per-AP-antenna received signal strength |

This is the core table. Each associated client MAC has an RSSI value **per AP interface/antenna**,
held on the controller. Client association data refreshes on a **5-minute** cycle. Result lands in
`Orion.WirelessHeatMap.Measurement` (`ReceivedSignalStrength`, keyed to a `SignalIdentificationID`).

### 3.3 Manual signal samples — Network Atlas, operator-driven

"Take Signal Sample" in Network Atlas. The operator walks a real, associated client device to a
physical spot, clicks the corresponding point on the floor plan, and Orion reads that client's RSSI
across all APs at that instant. A multi-device variant captures several placed clients at once.

Stored as a `MapPoint` plus its `Measurement` rows, and used to **calibrate the propagation model** —
it corrects for walls, floors and obstructions that a pure free-space model gets wrong. Samples
persist in the map indefinitely until deleted, or until APs are relocated.

### 3.4 What is computed rather than collected

`Orion.WirelessHeatMap.ClientLocation.X/Y` is **derived**, not polled. The generation job
trilaterates each client MAC from the AP-reported RSSI values against the placed AP coordinates and
the map `Scale`/`ScaleUnit`. `LastCalculationTime` timestamps that computation.

Documented minimum for clients to render: **4 access points**, or **3 access points plus at least
one signal sample**.

### 3.5 Ingest triggers (the poll verbs)

| Verb | Signature | What it does |
|---|---|---|
| `PollAPSignalStrengthNow` | `(heatmapId)` -> `DataTable` | Forces an AP TX-power / signal poll for the map |
| `PollRPSignalStrengthNow` | `(heatmapId, clientIdVsMapPointIdMap)` -> `DataTable` | Reference-point poll, tying client IDs to map points |
| `StartClientSignalPoll` | `(heatmapId, clientIdVsMapPointIdMap)` -> `array` | Kicks off the async client RSSI poll |

### 3.6 Platform constraint

Heat maps support **Cisco controllers only** — the 2500 / 5500 / 7500 class that expose the CleanAir
OIDs. The controller must itself be a node managed in NPM. Aruba, Meraki, Ubiquiti and other vendors
are monitored by `Orion.Packages.Wireless.*` but have **no heat-map ingest path**.

---

## 4. Reading the data — validated SWQL

All five queries below pass `python3 tools/validate_swql.py` against the 2026.2 schema.

### 4.1 Maps and generation health

```sql
SELECT m.MapID, m.DisplayName, m.Scale, m.ScaleUnit, m.PercentProgress,
       m.LastGenerationStarted, m.LastGenerationFinished, m.ErrorCode,
       m.MapStudioFileID, m.Width, m.Height, m.DetailsUrl
FROM Orion.WirelessHeatMap.Map m
ORDER BY m.DisplayName
```

### 4.2 The raw signal data behind one map

```sql
SELECT p.PointID, p.MapID, p.EntityType, p.InstanceId, p.X, p.Y,
       s.SignalIdentificationID, s.AntennaSlot, s.AntennaMACAddress,
       s.TransmittedSignalStrength, s.NegativeTransmittedSignalStrength,
       me.MeasurementID, me.ReceivedSignalStrength, me.NegativeReceivedSignalStrength
FROM Orion.WirelessHeatMap.MapPoint p
LEFT JOIN Orion.WirelessHeatMap.SignalIdentification s ON s.PointID = p.PointID
LEFT JOIN Orion.WirelessHeatMap.Measurement me ON me.SignalIdentificationID = s.SignalIdentificationID
WHERE p.MapID = 1
```

Use `LEFT JOIN` deliberately: an AP point that has never been polled has a `MapPoint` row and no
`SignalIdentification` children. An inner join hides exactly the rows you are troubleshooting.

### 4.3 Computed client positions

```sql
SELECT cl.Id, cl.MapId, cl.ClientMACAddress, cl.NodeID, cl.X, cl.Y, cl.LastCalculationTime,
       cl.Map.DisplayName AS MapName
FROM Orion.WirelessHeatMap.ClientLocation cl
WHERE cl.LastCalculationTime > ADDMINUTE(-60, GETUTCDATE())
```

### 4.4 Is RSSI polling actually running?

```sql
SELECT ps.NodeID, ps.IsAPRSSIPolling, ps.LastPollStarted, ps.LastPollFinished,
       ps.CompleteStatus, ps.LastPollMessage
FROM Orion.WirelessHeatMap.PollingStatus ps
ORDER BY ps.LastPollFinished DESC
```

**`LastPollMessage` is the first place to look** when a map generates but shows no clients. A
`CompleteStatus` of false with a populated message usually means the controller did not answer the
RSSI table — SNMP credentials, ACL, or an unsupported controller model.

### 4.5 Heat-map APs joined back to their nodes

```sql
SELECT ap.ID, ap.NodeID, ap.Index, ap.ControllerID, ap.Description, ap.IPAddress,
       ap.Clients, ap.Status, ap.StatusDescription, ap.LastUpdate,
       ap.Node.Caption AS NodeCaption, ap.WebUri.WebUri AS WebUri
FROM Orion.WirelessHeatMap.AccessPoints ap
```

---

## 5. Injecting data

### 5.1 Correction to the premise: SWQL cannot write

SWQL is **SELECT-only**. There is no INSERT, UPDATE or DELETE statement. The write path into Orion
is the SWIS layer: REST/SOAP **CRUD** operations for entities with `canCreate: true`, and **Invoke**
for verbs. For heat maps it is almost entirely Invoke, because only `Map` is creatable.

See `docs/swis/crud.md` and `docs/swis/invoke-verbs.md` in the repo.

### 5.2 The complete verb surface

| Entity | Verb | Parameters (positional, in order) | Returns |
|---|---|---|---|
| `Orion.MapStudioFiles` | `InsertFile` | `path, imageFile, owner, fileType, timeStamp` | `System.Object` |
| `Orion.MapStudioFiles` | `UpdateFile` | `fileId, path, imageFile, updater, timeStamp, computerName` | `System.Object` |
| `Orion.MapStudioFiles` | `DeleteFile` | `fileId, user, computerName` | `System.Object` |
| `Orion.MapStudioFiles` | `LockFile` | `fileId, user, lockDate, computerName, locked` | `System.Object` |
| `Orion.MapStudioFiles` | `LockFileTable` | `fileId, user, lockDate, computerName, locked` | `DataTable` |
| `Orion.MapStudioFiles` | `UnlockAllFiles` | `user, computerName` | `System.Object` |
| `Orion.MapStudioFiles` | `GetMapStyle` | `FileId` | `System.Object` |
| `Orion.WirelessHeatMap.Map` | `InsertMap` | `name, scale, scaleUnit, width, height, mapStudioFileGuid` | `number` |
| `Orion.WirelessHeatMap.Map` | `InsertWirelessHeatMap` | `projectId, name, scale, scaleUnit, width, height` | `number` |
| `Orion.WirelessHeatMap.Map` | `UpdateWirelessHeatMap` | `mapId, projectId, name, scale, scaleUnit, width, height` | `number` |
| `Orion.WirelessHeatMap.Map` | `DeleteWirelessHeatMap` | `mapId` | `void` |
| `Orion.WirelessHeatMap.Map` | `DeleteMap` | `mapStudioFileGuid` | `void` |
| `Orion.WirelessHeatMap.Map` | `CloneWirelessHeatMapFromNAMap` | `naMapId, projectId, name, scale, scaleUnit, lastGenerationStarted, lastGenerationFinished, width, height, points` | `number` |
| `Orion.WirelessHeatMap.Map` | `PollAPSignalStrengthNow` | `heatmapId` | `DataTable` |
| `Orion.WirelessHeatMap.Map` | `PollRPSignalStrengthNow` | `heatmapId, clientIdVsMapPointIdMap` | `DataTable` |
| `Orion.WirelessHeatMap.Map` | `StartClientSignalPoll` | `heatmapId, clientIdVsMapPointIdMap` | `array` |
| `Orion.WirelessHeatMap.Map` | `UpdateMapGenerationProgress` | `mapId, progress, errorCode` | `void` |
| `Orion.WirelessHeatMap.Map` | `GetProgress` | `keysByEngines` | `DataTable` |
| `Orion.WirelessHeatMap.Map` | `FireMapGenerationIndication` | `mapId` | `void` |
| `Orion.WirelessHeatMap.Map` | `SetMapError` | `mapId, started, errorCode` | `void` |
| `Orion.WirelessHeatMap.Map` | `DeleteReferencePoints` | `mapPointIds` | `boolean` |
| `Orion.WirelessHeatMap.MapPoint` | `InsertMapPoint` | `mapId, entityType, instanceId, x, y` | `number` |
| `Orion.WirelessHeatMap.MapPoint` | `DeleteMapPoint` | `mapId, entityType, instanceId` | `void` |
| `Orion.WirelessHeatMap.MapPoint` | `DeleteMapPoints` | `wlhmId` | `void` |
| `Orion.WirelessHeatMap.MapPoint` | `SyncMapPoints` | `mapId, naMapPoints, isAP` | `void` |
| `Orion.WirelessHeatMap.ResourceLimitation` | `InsertResourceLimitation` | `resourceId, mapGuid, mapLimitationCount, apMACAddress, apLimitationCount, clientMACAddress, mapId?` | `void` |

> **Arguments are positional.** A reordered call fails silently rather than erroring. Always confirm
> against `data/schema/2026.2/verbs.json` — do not recall a signature from memory.

REST invoke path shape: `/Invoke/<Entity>/<Verb>`, e.g.
`/Invoke/Orion.WirelessHeatMap.MapPoint/InsertMapPoint`.

### 5.3 Worked sequence (PowerShell / SwisPowerShell)

```powershell
$swis = Connect-Swis -Hostname orion.example.local -Trusted

# --- 1. Floor plan image into the map file store -----------------------------
$imageBytes = [System.IO.File]::ReadAllBytes('C:\plans\Building3-L2.png')
$timeStamp  = (Get-Date).ToString('o')
$fileType   = 0          # installation-specific; confirm on your server (see section 6)

$guid = Invoke-SwisVerb $swis Orion.MapStudioFiles InsertFile @(
    'FloorPlans\Building3-L2.png',
    $imageBytes,
    'admin',
    $fileType,
    $timeStamp
)

# --- 2. The map row -----------------------------------------------------------
# Classic Network Atlas style map, bound to the image GUID:
$mapId = Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map InsertMap @(
    'Building 3 Level 2',   # name
    0.05,                   # scale
    0,                      # scaleUnit  (see section 6 - enumeration not in schema)
    1200,                   # width  (px)
    800,                    # height (px)
    $guid                   # mapStudioFileGuid
)

# Intelligent Maps variant instead - takes a ProjectID, no file GUID:
# $mapId = Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map InsertWirelessHeatMap @(
#     $projectId, 'Building 3 Level 2', 0.05, 0, 1200, 800)

# --- 3. Place each access point ----------------------------------------------
# Find the heat-map AP IDs first:
$aps = Get-SwisData $swis @"
SELECT ap.ID, ap.Description, ap.IPAddress, ap.Node.Caption AS NodeCaption
FROM Orion.WirelessHeatMap.AccessPoints ap
WHERE ap.ControllerID = @cid
"@ @{ cid = $controllerId }

foreach ($p in $placements) {
    Invoke-SwisVerb $swis Orion.WirelessHeatMap.MapPoint InsertMapPoint @(
        $mapId,
        'Orion.WirelessHeatMap.AccessPoints',   # entityType
        $p.ApId,                                # instanceId
        $p.X,
        $p.Y
    )
}

# --- 4. Trigger collection ----------------------------------------------------
Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map PollAPSignalStrengthNow @($mapId)
Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map StartClientSignalPoll  @($mapId, $clientIdVsMapPointIdMap)

# --- 5. Watch it build --------------------------------------------------------
Invoke-SwisVerb $swis Orion.WirelessHeatMap.Map GetProgress @($keysByEngines)

Get-SwisData $swis @"
SELECT m.MapID, m.DisplayName, m.PercentProgress, m.GenerateStarted,
       m.LastGenerationStarted, m.LastGenerationFinished, m.ErrorCode
FROM Orion.WirelessHeatMap.Map m
WHERE m.MapID = @id
"@ @{ id = $mapId }
```

### 5.4 The hard limit on injection

`Orion.WirelessHeatMap.SignalIdentification` and `Orion.WirelessHeatMap.Measurement` are both
`canCreate: false` and expose **no Insert verb**.

Consequence: you can script the map, the image, the scale, and every AP placement — but you
**cannot hand-feed RSSI values**. Measurements only arrive via the poll verbs, which read the Cisco
WLC over SNMP. There is no supported entry point for:

- synthetic or modelled signal data
- a third-party site-survey export (Ekahau, AirMagnet, NetSpot)
- RSSI harvested from a non-Cisco controller (Aruba, Meraki, Ubiquiti)

If the goal is to visualise externally-surveyed coverage in Orion, the heat-map engine is the wrong
target. Practical alternatives:

1. **Network Atlas custom map** with a static survey image as background — no live data, but it
   renders in the console alongside real status.
2. **Custom SWQL / Modern Dashboard resource** driving your own SVG or canvas overlay from a custom
   table or an `Orion.APIPoller` feed. Loses the generation engine, keeps live data.
3. **Direct database writes** to the underlying heat-map tables. Unsupported, breaks on upgrade, and
   voids support. Noted for completeness only — not recommended.

---

## 6. Unverified — confirm on your own server

Following the OrionGuides convention of not asserting what the schema does not record:

| Item | Status | How to settle it |
|---|---|---|
| `ScaleUnit` byte enumeration (feet/metres/...) | Not in published schema | `SELECT DISTINCT ScaleUnit FROM Orion.WirelessHeatMap.Map` against maps of known units |
| `ErrorCode` byte values and meanings | `Orion.WirelessHeatMap.ErrorCode` carries only `Code` — no description column | `SELECT Code FROM Orion.WirelessHeatMap.ErrorCode`; cross-reference maps in a failed state |
| `Orion.MapStudioFiles.FileType` values | Not in schema | Inspect existing rows before inserting |
| `GetProgress(keysByEngines)` array shape | Type not documented in the extracted contract | `SELECT * FROM Metadata.VerbArgument WHERE VerbName='GetProgress'` |
| `clientIdVsMapPointIdMap` array shape | Same | Same approach |
| Default map regeneration interval (reported as once/day) | From a search snippet only — the THWACK SDK thread 404s on all three URL forms | Observe `LastGenerationStarted` deltas on a live map |
| Claim that `InsertMapPoint` is "public API but not for end users" and inserts inconsistently | Attributed to SolarWinds staff in a search snippet; source thread not retrievable | Test in a lab before relying on it; prefer Network Atlas for production placement |
| Whether `Orion.NPM.WL.*` / `Orion.Wireless.*` are deprecated | Not marked obsolete in schema | `SELECT FullName, IsObsolete, ObsolescenceReason FROM Metadata.Entity WHERE FullName LIKE 'Orion.Wireless.%' OR FullName LIKE 'Orion.NPM.WL.%'` |

---

## 7. Troubleshooting decision path

```
Map exists but shows no coverage
  |- Check Orion.WirelessHeatMap.Map.ErrorCode and PercentProgress          (4.1)
       |- ErrorCode non-zero      -> generation failed; see ErrorCode table (6)
       |- PercentProgress stuck   -> check ProcessingEngine is polling
       |- Clean but empty         -> no Measurement rows; go to next branch

No Measurement / SignalIdentification rows
  |- Check Orion.WirelessHeatMap.PollingStatus                              (4.4)
       |- IsAPRSSIPolling = false -> RSSI polling not enabled for that node
       |- CompleteStatus = false  -> read LastPollMessage
       |- Never polled at all     -> verify controller is a managed NPM node
                                     and answers 1.3.6.1.4.1.14179.2.1.11

APs render but clients do not
  |- Fewer than 4 APs placed, and no signal sample                          (3.4)
  |- Controller not a supported Cisco model (2500/5500/7500, CleanAir OIDs) (3.6)
  |- APs missing bsnAPIfAbsolutePowerList / bsnAPIfPhyTxPowerLevel          (3.1)
  |- ClientLocation.LastCalculationTime stale -> generation not re-running  (4.3)
```

---

## 8. Related entities outside the heat-map family

Heat maps sit on top of the general wireless model. For live wireless data that is **not**
position-aware, prefer `Orion.Packages.Wireless.*` — it is the family the rest of the schema is
wired into:

| Entity | Role |
|---|---|
| `Orion.Packages.Wireless.Controllers` | The WLC, keyed by `NodeID`; `ThinAPsCount`, `RogueAPsCount` |
| `Orion.Packages.Wireless.AccessPoints` | The AP; `ControllerID`, `SSID`, `Clients`, throughput, `LastReported` |
| `Orion.Packages.Wireless.Interfaces` | The radio; `Channel`, `RadioType`, error counters |
| `Orion.Packages.Wireless.Clients` | The associated station; `MAC`, `IPAddress`, `SignalStrength` |
| `Orion.Packages.Wireless.Rogues` | Rogue APs seen by the controller |
| `Orion.Packages.Wireless.ClientsSessionHistory` | Completed sessions, `APName`, SSID |

Three older families (`Orion.Wireless.*`, `Orion.NPM.WL.*`, `Orion.NPM.Wireless.*`) coexist in
2026.2 with overlapping names and thinner shapes. See `docs/modules/npm.md:241` for how to tell them
apart, and section 6 above for the deprecation query.

---

## 9. Sources

**Repo (authoritative for schema facts):**

- `~/repos/SolarWinds_OrionGuides/data/schema/2026.2/entities/Orion.json`
- `~/repos/SolarWinds_OrionGuides/data/schema/2026.2/verbs.json`
- `~/repos/SolarWinds_OrionGuides/data/reference/netobject-types.json`
- `~/repos/SolarWinds_OrionGuides/docs/modules/npm.md`

**SolarWinds documentation (authoritative for behaviour):**

- [Wireless heat map support in NPM](https://support.solarwinds.com/SuccessCenter/s/article/Wireless-heat-map-support) — the OIDs and the Cisco-only constraint
- [Create wireless heat maps](https://documentation.solarwinds.com/en/success_center/npm/content/core-creating-wireless-heat-maps-sw3557.htm)
- [Create wireless heat maps with Intelligent Maps](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-orion-maps-wireles-heatmaps.htm)
- [Improve accuracy by taking signal samples](https://documentation.solarwinds.com/en/success_center/npm/content/core-taking-signal-samples-sw3569.htm)
- [Add wireless access points for NPM wireless heat maps](https://documentation.solarwinds.com/en/success_center/npm/content/core-adding-wireless-access-points-sw3344.htm)
- [Display wireless heat maps in the Web Console](https://documentation.solarwinds.com/en/success_center/npm/content/core-displaying-wireless-heat-maps-in-the-orion-web-console-sw341.htm)
- [View wireless data](https://documentation.solarwinds.com/en/success_center/npm/content/npm-viewing-wireless-data-sw1481.htm)
- [Clients do not show in Wireless Heatmaps but all APs are present](https://support.solarwinds.com/SuccessCenter/s/article/Clients-do-not-show-in-Wireless-Heatmaps-but-all-APs-are-present)

**Community (lower confidence — thread not directly retrievable, 404 on all URL forms):**

- THWACK, "create new accesspoints on wireless heat map", Orion SDK forum, thread 23371

---

## 10. Multi-vendor ingest and mobile survey — feasibility

Added 2026-09-10. Assesses two related proposals: supporting Ubiquiti/UniFi hardware, and
driving the survey workflow from an Android application.

### 10.1 These are two separable problems

The two ideas are routinely conflated, and they have very different difficulty:

| Problem | Blocked by | Difficulty |
|---|---|---|
| **Survey / position capture** — walk the floor, establish position, trigger a sample | Nothing in Orion. Android platform limits only. | Moderate |
| **Ubiquiti RSSI ingest** — get UniFi signal data into the heat-map tables | `canCreate: false`, no Insert verb, Cisco-only SNMP collector (§3.6, §5.4) | Hard |

An Android app solves the first entirely. It contributes nothing to the second. Scope them
as separate deliverables.

### 10.2 The supported remote-sample path

Two verbs compose into a legitimate remote implementation of the Network Atlas
"Take Signal Sample" workflow:

```
InsertMapPoint(mapId, entityType, instanceId, x, y)          -> PointID
PollRPSignalStrengthNow(heatmapId, clientIdVsMapPointIdMap)  -> DataTable
```

`RP` is Reference Point. The pattern is: assert *"client X is physically standing at map
point Y"*, then let Orion poll the controller for that client's RSSI and write the
`SignalIdentification` and `Measurement` rows itself. No direct table writes, no
unsupported calls, and it uses the same engine path the desktop tool uses.

This means an Android client **can** drive the supported sample workflow over SWIS REST,
replacing a Windows-only desktop dependency. That capability exists today, against Cisco
controllers, with no platform modification.

The constraint that matters: `PollRPSignalStrengthNow` polls *the controller*. The phone
asserts position; the WLC supplies signal. On UniFi there is no controller Orion knows how
to poll, so the verb has nothing to read. The mobile app does not remove the vendor
constraint — it removes the desktop constraint.

### 10.3 Three architectures for Ubiquiti

**A — Native engine, direct injection. Not viable.** `Orion.WirelessHeatMap.SignalIdentification`
and `Orion.WirelessHeatMap.Measurement` are `canCreate: false` with no Insert verb (§5.4).
Only the poll verbs write them, and those are bound to the Airespace SNMP collector.

**B — SNMP shim presenting UniFi as a Cisco WLC.** A service that polls the UniFi
controller API and exposes an SNMP agent implementing the `1.3.6.1.4.1.14179` subtree.
Orion discovers it as a controller, polls it normally, and everything downstream —
`Orion.Packages.Wireless.*`, `Orion.WirelessHeatMap.AccessPoints`, `PollRPSignalStrengthNow` —
works unmodified. The only route into the real generation engine that does not touch the
database.

The cost is larger than the OID list in §3 suggests. Implementing
`bsnMobileStationRssiDataTable` alone is not enough: Orion's wireless discovery must first
*classify* the device, which means a plausible sysObjectID under the Airespace enterprise
tree plus enough of the AP, radio-interface and mobile-station tables for discovery to
complete. Index stability across polls matters, or `Orion.WirelessHeatMap.AccessPoints.Index`
churns and map points detach from their APs. Which specific OIDs Orion's discovery requires
before it will classify a device as a supported controller is **not recorded in the published
schema** and is unverified here; it would have to be established empirically against a real
WLC or by inspecting the shipped discovery definitions. The approach is also fragile across
platform upgrades, with no support recourse.

**C — Bypass the generation engine.** Hold survey data in a custom table or an
`Orion.APIPoller.ApiPoller` feed, and render coverage yourself in a Modern Dashboard
resource (SVG or canvas). You forfeit the generation engine and write your own
interpolation, and you gain vendor independence permanently. See
[../docs/webui/modern-dashboard-authoring.md](../docs/webui/modern-dashboard-authoring.md).

### 10.4 Android platform limitations

These are the constraints that actually determine whether a phone-based survey works,
independent of Orion:

**Scan throttling.** Since Android 9, `WifiManager.startScan()` is rate-limited to roughly
four scans per two-minute window for a foreground application; background applications are
limited far more aggressively on Android 10 and later. A developer-options toggle can
disable throttling on a test device, but a deployed application cannot depend on it. The
practical effect is a ceiling on walking speed — on the order of one usable sample every
thirty seconds, turning a forty-point floor survey into a twenty-minute walk at minimum.

This constraint largely disappears on the §10.2 path, because the *controller* performs the
measurement and the phone only asserts position. That asymmetry is a strong argument for
the reference-point architecture over a client-side survey.

**MAC randomization.** Android 10 randomizes MAC address per SSID by default, and later
releases extended this. `Orion.WirelessHeatMap.ClientLocation` is keyed on
`ClientMACAddress`, and the reference-point client map is keyed the same way. A randomizing
survey handset silently decorrelates from the client Orion sees, producing samples attached
to a MAC that will not exist in the next session. The survey SSID must be pinned to a stable
MAC, and that setting verified rather than assumed.

**Permissions.** Wi-Fi scan results require location permission and location services
actually enabled. Later Android releases added a nearby-devices permission that improves the
privacy posture but does not remove the location dependency for BSSID and RSSI access. On
managed handsets this is an MDM policy question, not a code change, and is worth settling
before development rather than after.

**Positioning has no platform answer.** Android provides nothing usable for indoor position.
The realistic options, in descending order of reliability: tap-on-floorplan (reliable,
tedious, and what commercial survey tools do); ARCore visual-inertial odometry (good over
short runs, drifts over long walks, needs textured surfaces and adequate light — useful for
interpolating *between* taps rather than replacing them); raw inertial dead reckoning
(drifts to metres within a minute — not viable). Start with tap-on-floorplan.

**Per-device RSSI variance.** Two handsets at the same location routinely differ by several
dB owing to chipset, antenna placement and RF front-end differences, with hand grip and body
orientation adding more. Any client-side survey needs per-device calibration against a known
reference, and device model should be recorded with every sample.

### 10.5 RF and measurement limitations

**Direction mismatch.** The heat-map model is *uplink*: what the AP heard from the client
(§3.2). A phone survey measures *downlink*: what the phone heard from the AP. Path loss is
reciprocal but transmit powers are not — an AP transmitting at a substantially higher level
than a handset, with better antennas and receive sensitivity. Downlink measurements cannot
be fed into an uplink-shaped schema without a per-AP offset, and that offset varies with the
AP's current power level, which is precisely why the engine polls `bsnAPIfPhyTxPowerLevel`
(§3.1).

**BSSID resolution.** `Orion.WirelessHeatMap.SignalIdentification` keys on
`AntennaMACAddress` and `AntennaSlot`. UniFi access points emit a distinct BSSID per SSID
per radio, so a scanned BSSID does not map to an AP-plus-radio-slot without cross-referencing
the controller's device inventory. Resolvable through the UniFi API, but it is a join to
build and keep current.

**UniFi field semantics.** In the UniFi station statistics API, the `signal` and `rssi`
fields do not carry the same units — one is dBm and the other a shifted positive value.
Which is which, and the exact offset, could not be verified for this document and should be
confirmed against a live controller before either is used as a signal value. The failure
mode is quiet: both look plausible, and a wrong choice produces a heat map that is
internally consistent and uniformly wrong.

### 10.6 Recommended sequencing

1. **Settle the blocker in §10.7 first.** It can invalidate the whole plan.
2. **Build the Android application against the Cisco path** (§10.2). Fully supported, a real
   improvement over desktop-tethered surveying, and it exercises the positioning UX — the
   component most likely to disappoint.
3. **Then choose an ingest architecture** with the survey workflow already proven.

On B versus C: the SNMP shim is the more interesting engineering, but it means maintaining a
synthetic Cisco controller across platform upgrades indefinitely, and its failure mode is
Orion quietly declassifying the device after a patch. The custom-renderer path costs the
generation engine and buys every vendor, permanently. For an estate that is not
Cisco-first, C is the better trade.

### 10.7 Settle this before writing code

Whether `clientIdVsMapPointIdMap` can be constructed by an external caller at all. Its
array shape is **not recorded in the published schema** and is unverified here. If the
structure turns out to be opaque or engine-internal, the entire supported-path plan in §10.2
needs rethinking, and that is worth knowing before any application code exists.

`Metadata.VerbArgument` carries `XmlTemplate` and `XmlSchemas`, which is exactly what
settles this — they give the serialized shape a complex argument expects, rather than just
its declared type:

```sql
SELECT va.EntityName, va.VerbName, va.Position, va.Name, va.Type,
       va.IsOptional, va.XmlTemplate, va.Summary
FROM Metadata.VerbArgument va
WHERE va.VerbName IN ('PollRPSignalStrengthNow', 'StartClientSignalPoll', 'GetProgress',
                      'SyncMapPoints', 'CloneWirelessHeatMapFromNAMap')
ORDER BY va.VerbName, va.Position
```

If `XmlTemplate` comes back populated for `clientIdVsMapPointIdMap`, the supported path is
open and the template tells you what to send. If it is empty, treat that as the signal to
fall back to architecture C in §10.3 before investing in the mobile client.

---

## 11. Additional research — is there any supported ingest or client-reporting path?

Added 2026-09-10 (second pass). Question: does Orion / Observability Self-Hosted offer *any*
way to get heat-map data, or even per-client wireless reporting, in for hardware outside the
Cisco path — by design, by a documented workaround, or by a community-proven pattern.

Short answer: **no supported ingest path exists for heat maps, and no create path exists for
any wireless entity at all.** The details below tighten the picture from §10 in five ways,
two of which change the recommendation.

### 11.1 The heat-map data path is a discrete, OID-gated poller

The collector is a named poller — "wireless heat map poller" — visible under
**Settings → Manage Pollers → Wireless Controller**, disabled by default, and switched on for
a controller by Network Atlas or Intelligent Maps when that controller's APs are placed on a
map. Two facts from that:

- **Assignment is an OID match, not a vendor list.** A 2015 THWACK report on Colubris MSM 760
  controllers: the Manage Pollers page refused the heat-map poller because "the OIDs don't
  match". SolarWinds staff in the same thread: *"Currently only Cisco WLC supporting cleanair
  MIB are supported. We are certainly looking to expand our device support for heat-maps, but
  are dependent on the dataset available from the WLC."* Staff also listed tested controllers
  as 2500, 4400, 7500, 8500; 2100-series excluded for lacking CleanAir.
- **It is fragile in practice.** Community reports (2017, 2020) of the poller switching itself
  off over hours to days, and of the "Wireless Heat Map poller is not enabled" summary widget
  disagreeing with the poller's actual state. The service log is
  `WLHM.BusinessLayer.log` under `ProgramData\SolarWinds\Logs\Orion`.

The OID-gate matters for architecture B in §10.3: it confirms that what a shim has to satisfy
is a poller test plus the standard wireless discovery — not a hidden vendor whitelist.

### 11.2 The engine's inputs are two tables, and only one is Cisco-specific

A SolarWinds KB on clients missing from heat maps names the storage directly:

- `Wireless_Interfaces` — every AP antenna/interface MAC, linked to its AP by `ParentID`.
  Populated by the **standard** wireless poller, which is multi-vendor.
- `WirelessHeatMap_ClientMeasurement` — RSSI per client MAC **per AP interface**. Populated
  only by the heat-map poller.

The KB's stated cause when clients fail to appear: the WLC "will not report back all the
Interface MACaddresses correctly", and the engine needs **3–4 AP interfaces' readings per
client** before it will place that client. Its resolution is to "contact the WLC vendor".

This is the precise shape of the vendor gate: *a per-client, per-antenna RSSI matrix across
every AP that can hear the client*. Everything else in the pipeline is generic.

### 11.3 Intelligent Maps (2024.1+) is a new UI over the same engine

Heat maps moved into Intelligent Maps in 2024.1; Network Atlas has been deprecated since
2020.2 and 2024.2 added import of NA maps (that is what `CloneWirelessHeatMapFromNAMap` and
`InsertWirelessHeatMap(projectId, …)` serve — `ProjectID` is the Intelligent Maps project).
Requirements are stated identically: Cisco controllers only, heat-map poller enabled on the
WLC, APs dragged from the Entity Library "must already be monitored". Sampling is the same
reference-point mechanism, now called "Sitting Edition" (multiple clients placed at once) and
"Walking Edition" (one client walked between points), with an optional "Track history".

Nothing in the newer surface loosens the data requirement. It does confirm that the §10.2
verbs are the current, not legacy, path.

### 11.4 No wireless entity of any family can be created through SWIS

Checked every entity in `Orion.Packages.Wireless.*`, `Orion.Wireless.*`, `Orion.NPM.WL.*`,
`Orion.NPM.Wireless.*`, `Orion.UDT.AllWirelessEndpoints` and `Orion.Orchestrators.*`
against the 2026.2 schema: **all `canCreate: false`, and none carries a verb** except
`Orion.Orchestrators.Info`. There is no `Orion.DeviceStudio` technology for wireless either —
the shipped technologies are CPU & Memory, Multi CPU & Memory, and Node Details.

Consequence, stronger than §5.4: it is not only heat-map *measurements* that cannot be
injected. **A wireless client, AP, radio or controller row cannot be created by any public
call.** "Reporting of the client" inside the wireless model is available only through a
vendor poller SolarWinds ships.

### 11.5 The vendor paths that do exist — and where Ubiquiti falls

| Path | Mechanism | Ubiquiti? |
|---|---|---|
| SNMP controllers | Cisco WLC, Aruba Mobility, HP MSM 760/765, Extreme WiNG, Ruckus ZoneDirector, FortiGate | No |
| API orchestrators | `Orion.Orchestrators.Info.Add{Meraki,ArubaCentral,JuniperMist,RuckusOne,RuckusSmartZone,ExtremeCloudIQ,AristaWM,FortiEdgeCloud}Node` — a closed set; no generic add verb | No |
| "Any 802.11-compliant autonomous AP" | IEEE802dot11-MIB over SNMP | Partly — see below |
| Heat maps | Cisco WLC + CleanAir OIDs only | No |

The API-orchestrator path is worth knowing because it *does* land per-client signal: the Aruba
Central integration records "Client name, SSID, IP Address, IPv6 address, MAC, Signal
Strength, Connected" into `Orion.Packages.Wireless.Clients`. That is the only vendor-neutral
"client reporting" shape the platform has — one RSSI per client from its associated AP — and
it is reachable only via a shipped orchestrator.
`CreateOrchestratorPluginConfiguration(orchestratorId, productTypes)` configures product
types on an *existing* orchestrator; it is not a hook for a new vendor.

Query the orchestrator surface on a live server:

```sql
SELECT o.NodeID, o.Caption, o.Type, o.OrganizationName, o.EnableMetricsPolling, o.ApiKeyExpired,
       n.DeviceID, n.ProductType, n.ProductCategory, n.IsApiOnly, n.Caption AS DeviceCaption
FROM Orion.Orchestrators.Info o
LEFT JOIN Orion.Orchestrators.Nodes n ON n.OrchestratorNodeID = o.NodeID
ORDER BY o.Caption, n.Caption
```

And the per-client signal the wireless model already holds, for any vendor that populates it:

```sql
SELECT c.MAC, c.Name, c.IPAddress, c.SSID, c.SignalStrength, c.LastUpdate,
       c.WirelessInterface.AccessPoint.Name AS AccessPoint,
       c.WirelessInterface.AccessPoint.ControllerName AS Controller
FROM Orion.Packages.Wireless.Clients c
WHERE c.SignalStrength IS NOT NULL
ORDER BY c.SignalStrength
```

**Ubiquiti over SNMP.** UniFi APs do answer parts of IEEE802dot11-MIB (third-party SNMP
libraries read `dot11manufacturerProductName`/`ProductVersion` from them), so an AP may be
discoverable as an autonomous AP with SSID and channel. But IEEE802dot11-MIB has no station
table, and **UBNT-UniFi-MIB has no per-station object at all** — `unifiVapTable` exposes
`unifiVapBssId`, `unifiVapEssId`, `unifiVapChannel`, `unifiVapTxPower`, `unifiVapCcq` and a
`unifiVapNumStations` *count*, nothing per client. Two further practical obstacles: UniFi
devices report sysObjectID under enterprise 100002 (Frogfoot Networks) rather than Ubiquiti's
41112, which mis-vendors them in discovery (SolarWinds KB; workaround is a Device Studio
Node Details poller), and Ubiquiti's own guidance is that its MIB "may not include all OIDs".
Net: SNMP can give AP inventory, not clients, not RSSI.

**Ubiquiti over its own API.** The Network application's `stat/sta` returns, per client:
`rssi`, `signal`, `noise`, `ap_mac`, `bssid`, `radio`, `radio_proto`, `channel`, `essid`,
`tx_power`, `ccq`, `satisfaction`, `is_wired`, `last_seen`, `uptime` (field list confirmed
from the unpoller Go client). The units of `rssi` versus `signal` are still **not documented
in that source** and remain unverified here. More important than units: this is **one RSSI
per client, from the AP it is associated with**. The heat-map engine needs the reading from
*every* AP that can hear the client (§11.2). UniFi does not expose neighbour-heard RSSI
through its standard API, and Ubiquiti's own Design Center heat maps are predictive, not
measured. So even a flawless SNMP shim would reproduce exactly the KB failure mode — APs
present, clients absent — unless it fabricated the missing readings.

**The SolarWinds-endorsed Ubiquiti pattern** (a SolarWinds product manager on THWACK, 2022):
a PowerShell script that reads the UniFi API and imports each site and device as an
ICMP-only node at `127.0.0.1` with custom properties, plus a SAM application template that
polls the UniFi API per site for health. It deliberately does not touch the wireless model.

### 11.6 What this changes in the recommendation

1. **Architecture B (SNMP shim) is now off the table for heat maps**, not merely expensive.
   The gate is a per-client-per-antenna matrix that UniFi cannot supply, so the shim cannot
   satisfy the engine without inventing data.
2. **"Client reporting" is a separate, achievable goal — outside the wireless model.** The
   endorsed pattern is SAM API Poller / custom table fed from `stat/sta`, rendered in a Modern
   Dashboard or custom widget. That gives per-client RSSI, AP, SSID and satisfaction with no
   schema fight. Extending it to a coverage overlay is architecture C in §10.3.
3. **The Android survey app is unaffected** for supported hardware (§10.2), and for Ubiquiti it
   becomes the *only* source of multi-point signal data — which is precisely the argument for
   C: the app's client-side downlink survey plus the API's uplink association data, rendered
   by you, is more than Orion could ever produce for this hardware natively.

### 11.7 Sources for this section

- THWACK, *Official List of Supported Devices for Heat Maps* (2015) — staff statements on CleanAir dependency and tested WLC models
- THWACK, *Wireless Heat map requirements?* (2017–2018); *How to get wireless clients to display in Heat Maps?* (2018); *All Wireless Heat Maps – poller is not enabled* (2017–2020); *Wireless Heat-map Issue in Network Atlas* (2022)
- THWACK, *Ubiquiti API Monitoring – A different approach to polling* (SolarWinds PM, 2022)
- SolarWinds KB, *Clients do not show in Wireless Heatmaps but all APs are present* — `Wireless_Interfaces`, `WirelessHeatMap_ClientMeasurement`
- SolarWinds KB, *Ubiquiti Networks devices show up as Frogfoot Networks devices*
- SolarWinds docs: *Create wireless heat maps with Intelligent Maps*; *Disable the wireless heat map poller*; *Add wireless access points for NPM wireless heat maps*; *Monitor wireless infrastructure*; *HPE Aruba Networking Central*; *Cisco Meraki*; *Choose the polling method*; *Device Studio technologies*; *NPM 2024.1 release notes*
- Ubiquiti Help Center, *SNMP Monitoring in UniFi Network*; Observium MIB browser, UBNT-UniFi-MIB; SNMP::Info::Layer2::Ubiquiti; unpoller/unifi `clients.go`
- Repo: `data/schema/2026.2/` canCreate/verb audit across all wireless families and `Orion.Orchestrators.*`
