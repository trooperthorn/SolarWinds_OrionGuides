# Variables SolarWinds does not publish

**Everything on this page is inference, not documentation.** SolarWinds publishes no table
containing these names. They are derived from the 2026.2 schema by a rule this repository
checked and then applied past the end of the published lists.

## The rule, and why it holds

Every one of the 60 node variables SolarWinds publishes is a declared property of
`Orion.Nodes`. Every one of the 23 volume variables is a member of `Orion.Volumes`. The three
dotted node variables resolve through real navigation properties, and all 32 members behind
them are declared on the entities those navigations reach:

| Published set | Members | In the schema |
| --- | --- | --- |
| Node variables | 60 | 60 |
| Volume variables | 23 | 23 |
| `SNMPv3Credentials.*` | 16 | 16 |
| `PCUs.*` | 16 | 16 |
| `Stats.MinResponseTime` | 1 | 1 |
| Node status root cause | 2 | 2 |

118 for 118. A published variable is a schema member, without exception in the material this
repository has seen.

**The inference is the converse: a schema member is probably an addressable variable.** That
does not follow logically, and the schema does not record which members the variable engine
exposes. It is a strong pattern, not a guarantee.

So treat every name below as a **candidate**. The test is one alert message and one trigger.

## Why this is worth having anyway

`Orion.Nodes` declares 102 properties. **59 of them are published as variables** — the 57 in
SolarWinds' node table plus the two root-cause macros described above. The remaining **43** are
listed here.

(SolarWinds' node table has 60 entries, but three of them — `UnManaged`, `UnManageFrom` and
`UnManageUntil` — are inherited from `System.ManagedEntity` rather than declared on
`Orion.Nodes`, so they do not come out of the 102. That is the arithmetic: 102 − 59 = 43.)

The 43 include the things a modern estate actually wants in an alert — cloud identifiers, load
averages, hardware UUIDs — and their absence from the published table is much more likely to be
an un-updated document than a deliberate exclusion. The two root-cause variables are the
evidence for that reading: they were candidates on this page until SolarWinds turned out to
document them elsewhere.

## `Orion.Nodes` — 43 declared, unpublished

```bash
python3 tools/schema_query.py props Orion.Nodes
```

| Candidate | Notes |
| --- | --- |
| `BiosUUID`, `MachineUUID` | Hardware identity |
| `Category`, `ObjectSubType`, `EntityType` | Classification |
| `ChildStatus`, `CustomStatus`, `PolledStatus`, `UiSeverity` | Status facets beyond `Status` and `StatusDescription` |
| `CloudAccountID`, `CloudInstanceID`, `CloudZoneID` | Cloud placement; nothing in the published list covers these |
| `CMTS` | Cable modem termination system flag |
| `CPUCount` | Published list has `CPULoad` but not the count |
| `Description`, `DisplayName`, `NodeName` | Naming, beside the published `Caption` and `NodeDescription` |
| `DetailsUrl`, `Icon`, `ModernIcon`, `StatusIcon` | Console presentation; `StatusIcon` is the modern counterpart of the published `StatusLED` |
| `External`, `IsOrionServer`, `IsServer` | Role flags |
| `IP`, `IPAddress`, `IPAddressGUID` | Beside the published `IP_Address`. Three spellings, and only one is published |
| `IsPollingError`, `SkippedPollingCycles`, `MinutesSinceLastSync` | Polling health |
| `LastSystemUpTimePollUtc` | A **UTC** timestamp, where most published time variables are not |
| `LoadAverage1`, `LoadAverage5`, `LoadAverage15` | Unix-style load, absent from the published list entirely |
| `MemoryAvailable`, `PercentMemoryAvailable` | The complements of the published `MemoryUsed` and `PercentMemoryUsed` |
| `MinResponseTime` | Published only as `Stats.MinResponseTime` |
| `NodeDependencies`, `NodeDependenciesWithLinks` | Dependency summary, plain and hyperlinked |
| `OrionIdColumn`, `OrionIdPrefix` | Internal addressing |
| `RWCommunity` | **Read/write SNMP community string.** See below |
| `WindowsConnectionUsed` | WMI connection state |

> **Two candidates from this page have since been confirmed as published.**
> `NodeStatusRootCause` and `NodeStatusRootCauseWithLinks` were listed here as promising
> inferences. SolarWinds documents both, as the macros that accompany enhanced node status
> calculation, so they have moved to
> [variables-reference.md](variables-reference.md#the-two-root-cause-variables). They are the
> first candidates from this page to be confirmed, and the confirmation came from a SolarWinds
> page this repository had not seen rather than from a test — which is the outcome the method
> here predicts but cannot produce on its own.

**`RWCommunity` is a credential.** The read-only `Community` is published as a node variable
and this is its read/write counterpart. Everything in
[variables-reference.md](variables-reference.md#snmpv3-credential-variables) about not putting
credentials in an alert email applies here with more force.

## `Orion.Volumes` — 30 declared, unpublished

| Candidate | Notes |
| --- | --- |
| `DiskQueueLength`, `DiskReads`, `DiskWrites`, `DiskTransfer`, `TotalDiskIOPS` | Performance counters; the published list is capacity only |
| `DiskSerialNumber`, `DeviceId`, `Index` | Identity |
| `SCSIControllerId`, `SCSILunId`, `SCSIPortId`, `SCSIPortOffset`, `SCSITargetId` | SCSI addressing |
| `VolumePercentAvailable`, `VolumeSpaceAvailableExp`, `Size` | Complements of the published capacity figures |
| `Responding` | Beside the published `VolumeResponding` |
| `StatusDescription`, `StatusIcon` | The published list has `Status` and `StatusLED` but no description |
| `DetailsUrl`, `DisplayName`, `Icon`, `ModernIcon` | Presentation |
| `InterfaceType`, `Type`, `VolumeTypeID` | Typing, beside the published `VolumeType` |
| `MinutesSinceLastSync`, `SkippedPollingCycles`, `OrionIdColumn`, `OrionIdPrefix` | Polling and addressing |

That the published volume list is capacity-only and the schema carries five I/O counters is
the clearest case on this page: an alert on a volume that is slow rather than full has nothing
to say in the published vocabulary.

## Inherited members, which are a different thing

Eight members reachable from `Orion.Nodes` and twelve from `Orion.Volumes` are inherited from
the platform base entities rather than declared, and most are lowercase where real properties
are not:

```text
ancestordetailsurls  ancestordisplaynames  entitylink  image
instancesiteid       instancetype          statusiconhint  uri
```

The casing marks them: these are SWIS-injected display members that the console uses to render
lists, not facts about a node. Some — `uri` above all — do have obvious uses in a
notification. But they are the members most likely to be internal, and
[`Metadata.Property`](../swis/metadata-introspection.md) carries `IsInjected` and `IsInternal`
flags that settle it on a live server, which the extracted schema does not:

```sql
SELECT
    p.Name,
    p.Type,
    p.IsInjected,
    p.IsInternal,
    p.IsNavigable
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes'
ORDER BY p.Name
```

That query is the right way to finish this page against your own server. Anything flagged
internal or injected is not a variable to build a notification on, whatever the schema says.

## Navigation is the larger unpublished surface

`Orion.Nodes` has **162 navigation properties** and SolarWinds publishes three of them —
`Stats`, `SNMPv3Credentials` and `PCUs`. If the dotted form works generally, and the three
published cases say it does, then the addressable surface is far larger than any table:

```bash
python3 tools/schema_query.py show Orion.Nodes
```

Whether the engine walks an arbitrary navigation, whether it walks more than one hop, and what
it renders for a to-many navigation that returns several rows, are all **undocumented and
unverified here**. The three published examples are all to-many navigations rendered as a
single value, which suggests some flattening rule exists, but the rule is not stated.

## Testing a candidate

1. Create an alert on the entity, or edit one you already have.
2. Put the candidate in the message beside a variable you know works, so a blank result is
   distinguishable from a broken alert.
3. Trigger it.

A variable that does not resolve renders as empty text or as the literal `${...}` — it does
not error. That is why the known-good variable beside it matters, and it is the same silent
failure the defunct-variables list exists for. See
[variables.md](variables.md).

## See also

- [variables.md](variables.md) — the syntax and how the member list is derived
- [variables-reference.md](variables-reference.md) — what SolarWinds does publish
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) — `Metadata.Property`
  and the `IsInjected` and `IsInternal` flags
- [../automation/credentials.md](../automation/credentials.md) — why `RWCommunity` and the
  SNMPv3 keys deserve care
