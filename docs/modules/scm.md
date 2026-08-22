# SCM: Server Configuration Monitor

Server Configuration Monitor watches the configuration of servers the way NCM watches the
configuration of network devices: it collects files, registry keys, script output and
query results from monitored nodes on a schedule, keeps every detected change as a
versioned record, and compares the current state against a baseline you set. The question
it answers is "what changed on this server, when, and who did it" — which is the question
behind most "it worked yesterday" incidents.

The vocabulary maps cleanly onto the entity model. A **profile** is a named bundle of
things to watch. An **element** is one of those things — one file path, one registry key,
one script. Assigning a profile to a node makes SCM discover the **polled elements** that
match each element's settings on that machine, and every subsequent change to one of them
lands as a row of **element metadata**, optionally with the content itself. A **baseline**
pins one moment per node as the comparison point.

## Namespace and size

SCM contributes **23 entities**, all under `Orion.SCM.`, and 10 verbs across three of
them.

| Group | Entities | What is in it |
|---|---|---|
| The monitored node | 1 | `Orion.SCM.ServerConfiguration` |
| Profiles and elements | 4 | `Orion.SCM.Profiles`, `Orion.SCM.ProfileElements`, `Orion.SCM.NodesProfiles`, `Orion.SCM.ProfileElementPolicyDataSources` |
| Assignment history | 2 | `Orion.SCM.NodesProfilesHistory`, `Orion.SCM.NodesProfilesArchive` |
| Poll results | 8 | The seven `Orion.SCM.Results.*` entities plus `Orion.SCM.PollEntries` |
| Baseline | 1 | `Orion.SCM.Baseline` |
| Indications | 3 | `Orion.SCM.ServerConfigurationChange`, `Orion.SCM.ServerConfigurationDiffersFromBaseline`, `Orion.SCM.OneTimePollFinished` |
| SAM bridges | 2 | `Orion.SCM.ApplicationTemplateToProfileMapping`, `Orion.SCM.ProfileToApplicationTemplateMapping` |
| Switches and dismissals | 2 | `Orion.SCM.FimDisabledNodes`, `Orion.SCM.DismissedCandidates` |

Check the grouping yourself:

```bash
python3 tools/schema_query.py find Orion.SCM
python3 tools/schema_query.py show Orion.SCM.ServerConfiguration
python3 tools/schema_query.py verbs --entity Orion.SCM.Profiles
```

The module has to be installed for any of it to exist. Confirm before concluding anything:

```sql
SELECT COUNT(FullName) AS EntityCount
FROM Metadata.Entity
WHERE FullName LIKE 'Orion.SCM.%'
```

## The model, from profile to change record

```
Orion.SCM.Profiles                    what to watch — a named bundle of elements
  └── Orion.SCM.ProfileElements      one thing to collect: a file, a registry key, a script
Orion.SCM.NodesProfiles              which profile is assigned to which node (M:N)
Orion.SCM.ServerConfiguration        the node as SCM sees it, hosted by Orion.Nodes
  └── Orion.SCM.Results.PolledElements        discovered items matching an element's settings
        └── Orion.SCM.Results.ElementMetadata   one row per detected change, versioned
              └── Orion.SCM.Results.ElementContents   the content itself — admin-only
Orion.SCM.Baseline                   the pinned comparison point, one or more per node
```

### `Orion.SCM.ServerConfiguration` — the node as SCM sees it

One row per node SCM monitors, keyed by `NodeID` and hosted by `Orion.Nodes` — from the
platform side the navigation is `Orion.Nodes.SCMNode`, from this side it is `Node`. The
entity inherits `System.ManagedEntity`, so the platform status and unmanage columns are
present without being declared here.

The columns that carry the operational story: `Enabled`, `PollingInterval` (minutes — the
schema qualifies it "Apply only for SWIS element"), `LastPoll`, `LastChangeDetected`,
`LastAgentPluginHealthCheck` ("indicating that change detection is working properly"),
`ErrorCount`, and `BaselineStatus`, an integer the schema enumerates inline: `0` no
baseline set, `1` is baseline, `2` matches baseline, `3` differs from baseline.
`AssignedProfileList` is a denormalised comma-delimited string of profile names — handy in
a report column, but join `Orion.SCM.NodesProfiles` when you need real rows.

Navigations run everywhere the chain goes: `Profiles`, `NodesProfiles`, `PolledElements`,
`ElementMetadata`, `Baselines` and `PollEntries`.

### Profiles

`Orion.SCM.Profiles` is the unit of configuration monitoring policy, with full CRUD plus
`invoke` under `manageNodes`. Key `ProfileID`. The identity columns are worth reading
carefully, because they are what the export/import round trip stands on:

| Column | Meaning |
|---|---|
| `Name`, `DisplayName` | The name, and the display form that "may differ from Name, e.g. if the Profile is managed by other module" |
| `BuiltIn` | Read-only; true only for profiles deployed with the SCM installation, which cannot be modified |
| `UniqueId` | A GUID the schema calls "valuable for import/export to identify identical profiles across different environments" |
| `ProfileOrigin` | `0` New, `1` Copied, `2` Imported, `3` ImportedFromThwack |
| `OriginalProfileUniqueID` | The parent profile's GUID when this one is a copy |
| `Modified` | Last modification time |
| `Version` | Version of the out-of-the-box profile definition |
| `PolicyID` | "Identifier of Policy which caused creation of this entity" — the `Orion.PolicyEngine.` link |
| `ManagedExternally` | True when another module, e.g. PolicyEngine, owns the profile |

Note what this entity has that `Orion.APM.ApplicationTemplate` famously lacks: a built-in
indicator. `WHERE p.BuiltIn = FALSE` is a reliable server-side filter for user-authored
profiles. `TemplateMappingRules` is internal discovery configuration, and `AutoImport`
carries no description in the published schema — **unverified**, treat it as opaque.

### Profile elements

`Orion.SCM.ProfileElements` is one thing to collect, keyed `ElementID`, parent
`ProfileID`. `Type` is the element kind, enumerated inline by the schema with gaps as
shipped: `0` Unknown, `1` File, `2` Registry, `4` ParsedFile, `5` SwisQuery,
`6` PowerShell, `8` Script — there is no `3` or `7` in the published list. `Settings`
holds "all related settings specific for given type" as JSON, `CredentialID` points into
the platform credential store (the `CredentialID` convention covered in
[../automation/credential-integration.md](../automation/credential-integration.md)), and
`UniqueId` identifies an out-of-the-box element "even if its name changes".

`Orion.SCM.ProfileElementPolicyDataSources` maps an `ElementID` to a `DataSourceID` in the
PolicyEngine namespace — the plumbing behind `ImportPolicyProfile` and
`ManagedExternally`.

### Poll results

`Orion.SCM.Results.PolledElements` is a discovered item on a specific node that matched an
element's settings: `PolledElementID` (an `Int64`, unlike the element's `Int32`),
`NodeID`, `ElementID`, its own `Settings` JSON, and a `BaselineStatus` with the same
four-value enumeration as the node's. `Orion.SCM.Results.PolledElementDetails` hangs off
it through a hosting relationship (`Details` from the parent side) and pre-splits the
display name into path and name parts for the console.

`Orion.SCM.Results.ElementMetadata` is the change record, and it is the entity an audit
query lives on. `VersionID` counts changes per polled element from 1. `ChangeType` is `1`
Add, `2` Update, `3` Remove. `LastModified` is when the thing itself changed ("for File
type it is typically LastWriteTime of the file"), `LastModifiedBy` names the account, and
a family of file facts rides along: `FileSize`, `FileAttributes`, `Owner`, `UserGroup`,
`UnixFileMode`, `UnixPermissionBits`.

Two timestamps and two flags deserve care:

- `TimeStamp` is "when the change was spotted", but the schema warns it "can change with
  maintenance" — detail rows are aggregated over time. `OriginalTimeStamp` "holds original
  value of TimeStamp and does not changes". Audit on `OriginalTimeStamp`.
- `AggregationFlag` says what a row now is: `0` initial poll, `1` detail record, `2`
  aggregated to hourly, `3` aggregated to daily, `4` archived. `ChangesCount` counts the
  changes an aggregated row absorbed, and `IsInitialPoll` separates first sight from real
  change.

`Orion.SCM.Results.ElementContents` holds the content behind a metadata row when
collection is enabled: `Content` as binary (`System.Byte[]`), a SHA1 `Hash`, and a
`StructureType` (`0` Unknown, `1` None, `2` Text, `3` Json, `4` Xml). It is the one SCM
entity readable **only by `admin`**, in the schema's own words "for security reason …
content can contain sensitive data". `ContentCollectionState` on the metadata row says
whether content exists to fetch: `0` not present, `1` present, `2` collection disabled,
`3` size limit exceeded.

The error entities split by scope. `Orion.SCM.Results.NodesPollingErrors` is
node-level plumbing state, current only ("does not keep records of previous ones"), typed
`0` Agent not required through `7` Asset inventory missing.
`Orion.SCM.Results.ElementErrors` and `Orion.SCM.Results.PolledElementErrors` are per
element and per polled element, with types like access denied, parsing failed and script
execution timeout. `Orion.SCM.PollEntries` records each poll per node and element with a
`PollTime`.

### Baselines

`Orion.SCM.Baseline` is deliberately small: `BaselineID`, `NodeID`, `TimeStamp` — "all
elements in the base line contain state at this moment". The row is created or moved by
the `SetBaseline` verb rather than CRUD, and its point is durability: the verb's summary
says it snapshots "all related data so that they are not touched by maintenance
processes", which is the same maintenance that rewrites `ElementMetadata.TimeStamp`.

### Assignment history

`Orion.SCM.NodesProfiles` is the live M:N assignment (`NodeID`, `ProfileID`, `Assigned`),
with `SCMNode` and `Profile` navigations. `Orion.SCM.NodesProfilesHistory` keeps every
assignment with its `Assigned` and `Unassigned` times; `Orion.SCM.NodesProfilesArchive`,
in the schema's own words, "contains only the most recent record of a Profile unassigned
from a given Node". History for the full story, archive for "when did this stop".

### Indications

Three entities inherit `System.Indication` and declare no operations: they are events you
can subscribe to, not rows you can select. `Orion.SCM.ServerConfigurationChange` fires per
detected change, carrying `ChangeDetectedOn` ("not when it happened on the monitored
system"), `ChangeType`, `WhoMadeTheChange`, and ready-made `CompareUrl` and
`ContentDiffUrl` links. `Orion.SCM.ServerConfigurationDiffersFromBaseline` fires when a
node drifts, with a `BaselineVsCurrentConfigurationUrl`. `Orion.SCM.OneTimePollFinished`
is the completion signal for `PollNowWithNotification` below — its `State` column
"contains the same value as passed to the job when created (for callback purposes)".

### The SAM bridges

`Orion.SCM.ApplicationTemplateToProfileMapping` and
`Orion.SCM.ProfileToApplicationTemplateMapping` are near-identical read-only mapping
tables running in opposite directions: the first recommends SCM profiles from the SAM
application templates already assigned to a node, the second recommends SAM applications
from the SCM profiles already assigned. Both carry the template and profile ids, GUIDs and
names; the template-to-profile direction adds `AgentLess`, "whether the profile doesn't
require agent". See [sam.md](sam.md) for the template side.

`Orion.SCM.DismissedCandidates` records the recommendations a user told the "Candidates
for monitoring" widget to stop showing (`Type`: `0` Agent, `1` Profile), and
`Orion.SCM.FimDisabledNodes` is the "explicit list of nodes where FIM is forcibly
disabled" — one `NodeID` column, written by the FIM verbs below, reachable from the
platform side as `Orion.Nodes.SCMFimDisabledNode`.

## Verbs

SCM publishes 10 verbs across three entities: five on `Orion.SCM.Profiles`, four on
`Orion.SCM.ServerConfiguration`, one on `Orion.SCM.Baseline`. No verb declares a right of
its own; the entity level covers them — all three declare `invoke` for `manageNodes`.
Arguments are positional, and the names below never travel on the wire (see
[../swis/invoke-verbs.md](../swis/invoke-verbs.md)).

| Verb | Positional parameters | Returns |
|---|---|---|
| `Orion.SCM.Profiles.ExportProfile` | `profileId` (number) | the profile document, a string |
| `Orion.SCM.Profiles.ImportProfile` | `profileJson` (string) | number |
| `Orion.SCM.Profiles.ImportPolicyProfile` | `policyId` (number), `profileJson` (string) | number |
| `Orion.SCM.Profiles.AssignToNode` | `profileId` (number), `nodeId` (number), `data` (string) | void |
| `Orion.SCM.Profiles.UnassignFromNode` | `profileId` (number), `nodeId` (number), `keepHistory` (boolean) | void |
| `Orion.SCM.ServerConfiguration.PollNow` | `nodeIds` (array of number) | void |
| `Orion.SCM.ServerConfiguration.PollNowWithNotification` | `nodeId` (number), `elementIds` (array of number), `timeout` (`System.TimeSpan`), `state` (string) | void |
| `Orion.SCM.ServerConfiguration.EnableFimDriverWatching` | `nodeId` (number) | void |
| `Orion.SCM.ServerConfiguration.DisableFimDriverWatching` | `nodeId` (number) | void |
| `Orion.SCM.Baseline.SetBaseline` | `nodeId` (number), `timestamp` (string) | number |

### The profile round trip

`ExportProfile(profileId)` returns the profile as a document — "Exports profile to JSON"
in the contract's own summary — and `ImportProfile(profileJson)` takes one and returns a
number. The contract does not say what the number identifies; resolve the landing yourself
by querying `Orion.SCM.Profiles` for the imported `Name` afterwards, and use `UniqueId` to
recognise the same profile across servers — that is what the schema says the column is
for. An imported profile shows `ProfileOrigin = 2`, and profiles fetched from Thwack show
`3`, so the origin of every definition on a server is auditable.

`ImportPolicyProfile(policyId, profileJson)` is the PolicyEngine variant, creating a
profile tied to an `Orion.PolicyEngine.` policy — these are the rows that come back with
`PolicyID` set and, when the engine owns them, `ManagedExternally = TRUE`. One
contradiction to flag: the parameter is named `profileJson` while the verb's summary reads
"Imports policy profile from YAML". Which format the verb actually expects is
**unverified** here; export from your own server and look before hand-writing one.

**Unverified:** the internal structure of the exported profile document is not documented
in this repository — no real console export was available to parse, so this page cannot
give it the field-by-field treatment [sam-templates.md](sam-templates.md) and
[ncm-device-templates.md](ncm-device-templates.md) give their formats. The reliable path
is `ExportProfile` against a profile on your own server; round-trip it through
`ImportProfile` on a test server before editing anything inside.

### Assignment and polling

`AssignToNode(profileId, nodeId, data)` writes the assignment that `NodesProfiles` then
shows. The third argument's content is not described in the contract — **unverified**;
observe what the console sends on your own server before composing one.
`UnassignFromNode(profileId, nodeId, keepHistory)` removes it, and `keepHistory` is the
switch that decides whether the trail survives into `NodesProfilesHistory` rather than
just the archive row.

`PollNow(nodeIds)` "refreshes … watchers, polls the current results of file, registry and
script elements and executes jobs for polling SWIS and database elements", per its
summary. `PollNowWithNotification(nodeId, elementIds, timeout, state)` does the same for
one node and then raises the `Orion.SCM.OneTimePollFinished` indication once results are
collected, echoing your `state` string back in the indication — which is how a script
knows its poll, not someone else's, has finished. The `timeout` parameter is typed
`System.TimeSpan`; its wire format is not stated in the contract, so confirm on your own
server before depending on a particular string shape.

`EnableFimDriverWatching(nodeId)` and `DisableFimDriverWatching(nodeId)` toggle polling
through the FIM driver per node — disable writes the `Orion.SCM.FimDisabledNodes` row,
and enable, per its summary, only undoes a previous disable.

### Baselines

`SetBaseline(nodeId, timestamp)` creates or updates the node's baseline at the given
moment and snapshots the related data out of maintenance's reach. The `timestamp`
parameter is a **string** in the contract, not a `DateTime`. After it runs,
`BaselineStatus` on the node and on each polled element says how the present compares:
`2` matches, `3` differs — and drift also fires the
`ServerConfigurationDiffersFromBaseline` indication.

## Worked queries

Every query below has been validated against the 2026.2 schema with
`tools/validate_swql.py`. Time bounds follow
[../swql/date-and-time.md](../swql/date-and-time.md): the SCM timestamp columns state no
zone, so the platform's assume-UTC rule applies.

### The estate at a glance

```sql
SELECT
    sc.Node.Caption AS NodeName,
    sc.Enabled,
    sc.AssignedProfileList,
    sc.BaselineStatus,
    sc.LastChangeDetected,
    sc.ErrorCount,
    MinuteDiff(sc.LastPoll, GetUtcDate()) AS MinutesSinceLastPoll
FROM Orion.SCM.ServerConfiguration sc
ORDER BY sc.LastChangeDetected DESC
```

`BaselineStatus = 3` rows are the drifted servers. A `MinutesSinceLastPoll` that keeps
growing while `Enabled` is true is a polling problem, and the error queries below say
which kind.

### What changed in the last week

```sql
SELECT TOP 100
    em.SCMNode.Node.Caption AS NodeName,
    em.PolledElement.DisplayAlias AS Element,
    em.ChangeType,
    em.OriginalTimeStamp,
    em.LastModified,
    em.LastModifiedBy,
    em.VersionID,
    em.ChangesCount
FROM Orion.SCM.Results.ElementMetadata em
WHERE em.OriginalTimeStamp >= ToUtc(AddDay(-7, GetDate()))
  AND em.IsInitialPoll = FALSE
ORDER BY em.OriginalTimeStamp DESC
```

`OriginalTimeStamp` rather than `TimeStamp`, because maintenance rewrites the latter when
it aggregates detail rows; `IsInitialPoll = FALSE` keeps first-sight rows out of a change
report. `ChangeType` reads `1` add, `2` update, `3` remove.

### Which profiles are assigned where

```sql
SELECT
    np.Profile.Name AS ProfileName,
    np.Profile.BuiltIn,
    np.SCMNode.Node.Caption AS NodeName,
    np.Assigned
FROM Orion.SCM.NodesProfiles np
ORDER BY np.Profile.Name, np.SCMNode.Node.Caption
```

### The profiles worth exporting

Out-of-the-box profiles reinstall with the module; user-authored ones are what a migration
must carry. `BuiltIn` makes the split server-side.

```sql
SELECT
    p.ProfileID,
    p.Name,
    p.UniqueId,
    p.ProfileOrigin,
    p.Modified,
    p.ManagedExternally
FROM Orion.SCM.Profiles p
WHERE p.BuiltIn = FALSE
ORDER BY p.Modified DESC
```

### Why polling is failing

```sql
SELECT
    n.Caption AS NodeName,
    npe.Type,
    npe.Message
FROM Orion.SCM.Results.NodesPollingErrors npe
INNER JOIN Orion.Nodes n ON n.NodeID = npe.NodeID
ORDER BY n.Caption
```

Node-level plumbing first — `Type` runs from `2` agent missing to `5` SCM plugin not
responding — then the per-element errors:

```sql
SELECT TOP 50
    ee.NodeID,
    ee.ElementID,
    ee.TimeStamp,
    ee.Type,
    ee.Message
FROM Orion.SCM.Results.ElementErrors ee
WHERE ee.TimeStamp >= ToUtc(AddDay(-1, GetDate()))
ORDER BY ee.TimeStamp DESC
```

## Gotchas

**Content is admin-only and binary.** `Orion.SCM.Results.ElementContents` declares `read`
for `admin` and nothing for anyone else, so every other account sees the metadata but an
empty result for content — a permissions effect that looks like missing data. `Content`
is `System.Byte[]`, not a string; decode it according to `StructureType`.

**`TimeStamp` moves; `OriginalTimeStamp` does not.** Maintenance aggregates
`ElementMetadata` detail rows to hourly and daily records (`AggregationFlag` 2 and 3) and
can rewrite `TimeStamp` in the process. An audit that must stand up later should quote
`OriginalTimeStamp` and note `ChangesCount` on aggregated rows.

**The element `Type` enum has holes.** The published list is 0, 1, 2, 4, 5, 6, 8 — no 3,
no 7. Do not iterate the range; enumerate the documented values.

**The indications are not tables.** `ServerConfigurationChange`,
`ServerConfigurationDiffersFromBaseline` and `OneTimePollFinished` inherit
`System.Indication` and declare no operations: subscribe to them, do not `SELECT` from
them.

**`AssignedProfileList` is a display string.** It is a comma-delimited denormalisation on
the node row. Join `Orion.SCM.NodesProfiles` for anything beyond a report column.

**Unmanage columns exist, an unmanage verb does not.** `Orion.SCM.ServerConfiguration`
inherits `System.ManagedEntity`, so `UnManaged` and its window columns are filterable,
but no `Orion.SCM.*` verb sets them.

**`Orion.SCM.AssignedElementSettingOverride` has no schema page.** Three entities declare
relationships to it (`Profiles`, `ProfileElements` and `ServerConfiguration`, as
`AssignedElementSettingOverrides`), but no entity record for it exists in the extracted
schema. Whether the navigation resolves on a live server is **unverified** here.

**The two SAM mapping entities look identical and are not.**
`ApplicationTemplateToProfileMapping` recommends profiles from templates;
`ProfileToApplicationTemplateMapping` recommends templates from profiles. Only the first
carries `AgentLess`.

## Related pages

- [README.md](README.md) for the index of every module page.
- [sam.md](sam.md) for the application templates the two mapping entities bridge to.
- [../platform/modules.md](../platform/modules.md) for the whole namespace map.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional argument handling.
- [../swis/verb-catalog.md](../swis/verb-catalog.md) for `PollNow` among the platform's
  poll-now shapes.
- [../swql/date-and-time.md](../swql/date-and-time.md) for the UTC discipline the worked
  queries follow.
- [../automation/credential-integration.md](../automation/credential-integration.md) for
  the `CredentialID` convention `ProfileElements` uses.
- [../reference/verb-index.md](../reference/verb-index.md) for every verb with its ordered
  parameters.
- [../reference/glossary.md](../reference/glossary.md#scm) for the one-paragraph version
  of this module.
