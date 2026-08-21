# Technology polling

Technology polling is the newest of the five systems and the least visible. Where
`Orion.Pollers` assigns a named poller to a NetObject, this assigns a *technology* — a whole
declarative description of how to talk to a class of device or service — and then tracks which
instances it is switched on for.

It is also the only one of the five whose entities carry no schema summaries at all. Every
property below is named and typed by the contract and described by nothing, so this page says
what the contract says and marks the rest as unverified rather than guessing.

## The four entities

| Entity | Holds | Size |
| --- | --- | --- |
| `Orion.Technology` | A technology and the entity type it targets | 2 properties |
| `Orion.TechnologyPolling` | One polling definition for a technology | 3 properties |
| `Orion.TechnologyPollingAssignments` | Which instances it is enabled for | 4 properties, 4 verbs |
| `Orion.Declarative.PollerTemplates` | The declarative templates behind it | 3 properties, 2 verbs |

The first three are a hosting chain: `Orion.Technology` navigates down through
`TechnologyPollings`, `Orion.TechnologyPolling` navigates down through `Assignments` and back
up through `Technology`, and the assignment navigates back through `TechnologyPolling`.
`Orion.Declarative.PollerTemplates` sits apart, with no relationship to the other three.

### Read the operations and the verbs separately

`Orion.Technology`, `Orion.TechnologyPolling` and `Orion.TechnologyPollingAssignments` all
declare **no operations at all** — not even read. Yet the assignment entity publishes four
verbs, every one of which requires **`admin`**:

```bash
python3 tools/schema_query.py verb Orion.TechnologyPollingAssignments EnableAssignments
```

So the state is queryable, the rows are not writable through CRUD, and the only supported way
to change anything is the verbs. That is the reverse of most of this repository, where CRUD is
the general mechanism and verbs are the exception. Here the verbs are the entire write surface.

`Orion.Declarative.PollerTemplates` is the exception to the exception: it declares `read` and
`invoke`, both gated on `manageNodes`.

## What technologies exist

```sql
SELECT
    t.TechnologyID,
    t.TargetEntity
FROM Orion.Technology t
ORDER BY t.TechnologyID
```

Two columns and both are worth explaining. `TechnologyID` is a `System.String` here — see the
warning below — and `TargetEntity` is a `System.Type`, which is the schema's way of saying the
column holds an entity name rather than an id. That is what scopes a technology: one that
targets `Orion.Nodes` is assigned to nodes, one that targets `Orion.Volumes` to volumes.

```sql
SELECT
    tp.TechnologyID,
    tp.TechnologyPollingID,
    tp.Priority,
    tp.Technology.TargetEntity
FROM Orion.TechnologyPolling tp
ORDER BY tp.TechnologyID, tp.Priority
```

`Priority` orders competing definitions for one technology. What happens when two share a
priority is **not recorded in the published schema** and is unverified here.

## What it is assigned to

```sql
SELECT
    a.InstanceID,
    a.TechnologyPollingID,
    a.TargetEntity,
    a.Enabled
FROM Orion.TechnologyPollingAssignments a
ORDER BY a.TechnologyPollingID, a.InstanceID
```

`InstanceID` is the id of the object within whatever `TargetEntity` names, so it is a node id
when `TargetEntity` is `Orion.Nodes` and a volume id when it is `Orion.Volumes`. The entity
declares navigation properties for exactly those two, which is the readable way to write it:

```sql
SELECT
    a.TechnologyPollingID,
    a.Enabled,
    a.Node.Caption,
    a.Node.IPAddress
FROM Orion.TechnologyPollingAssignments a
WHERE a.TargetEntity = 'Orion.Nodes'
ORDER BY a.Node.Caption
```

Whether `TargetEntity` on the assignment always matches `TargetEntity` on the technology above
it, and whether a third target beyond nodes and volumes can appear, are **not recorded in the
schema** and are unverified here. Only `Node` and `Volume` navigations are declared, so those
two are the ones the schema supports reaching.

Assignments that exist and are switched off, which is the same silent state as everywhere else
in this section:

```sql
SELECT
    a.TechnologyPollingID,
    a.TargetEntity,
    COUNT(a.InstanceID) AS Instances
FROM Orion.TechnologyPollingAssignments a
WHERE a.Enabled = FALSE
GROUP BY a.TechnologyPollingID, a.TargetEntity
ORDER BY COUNT(a.InstanceID) DESC
```

## The four verbs

All four require `admin`, all four take `technologyPollingID` as a **string** first, and all
four return an array.

| Verb | Arguments | Scope |
| --- | --- | --- |
| `EnableAssignments` | `technologyPollingID` | Every assignment for that definition |
| `DisableAssignments` | `technologyPollingID` | Every assignment for that definition |
| `EnableAssignmentsOnNetObjects` | `technologyPollingID`, `netObjectIDs` | Only the ids given |
| `DisableAssignmentsOnNetObjects` | `technologyPollingID`, `netObjectIDs` | Only the ids given |

The pairing is the thing to read carefully. `EnableAssignments` and `DisableAssignments` take
**one argument and act on everything** under that `TechnologyPollingID`; the `OnNetObjects`
forms take a second argument and act on a list. Calling the one-argument form when you meant
the two-argument one is not an error, produces no warning, and changes every instance in the
estate for that technology.

```powershell
$swis = Connect-Swis -Hostname orion.example.com -Trusted

# Scope first, as a query you have read. See ../automation/README.md.
$nodeIds = Get-SwisData $swis @'
SELECT a.InstanceID
FROM Orion.TechnologyPollingAssignments a
WHERE a.TechnologyPollingID = @tp
  AND a.TargetEntity = 'Orion.Nodes'
  AND a.Enabled = TRUE
'@ @{ tp = $technologyPollingId }

Invoke-SwisVerb $swis 'Orion.TechnologyPollingAssignments' 'DisableAssignmentsOnNetObjects' @(
    $technologyPollingId,   # technologyPollingID, a string
    ,[int[]]$nodeIds        # netObjectIDs, an array of number
)
```

`netObjectIDs` is declared `array<number>`, so these are bare integers rather than `N:42`
NetObject strings despite the argument's name. The leading comma keeps PowerShell from
splatting the array into separate positional arguments; see
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

What the returned array contains is **not recorded in the published schema** and is unverified
here. Verify the outcome with the assignment query above rather than by reading the result.

## The declarative templates

`Orion.Declarative.PollerTemplates` is the template library the declarative polling engine
works from:

```sql
SELECT
    pt.Name,
    pt.Version,
    pt.VendorModelId
FROM Orion.Declarative.PollerTemplates pt
ORDER BY pt.Name, pt.Version
```

`Version` is a `System.String` rather than a number, so ordering by it is lexicographic and
`10` sorts before `9`. `VendorModelId` identifies the device model a template was written for.

Its two verbs both run a template rather than manage one, and they differ in exactly one
argument:

| Verb | Arguments |
| --- | --- |
| `Execute` | `pollerPrefix`, `clientSettings`, `credential`, `engineId` |
| `ExecuteWithCreds` | `pollerPrefix`, `clientSettings`, `credentialId`, `engineId` |

`Execute` takes `credential` as a `SolarWinds.Orion.Core.SharedCredentials.Credential` — the
credential itself — while `ExecuteWithCreds` takes `credentialId` as a **number**, a row in
the credential store. The names read backwards from what they do: the one called
"WithCreds" is the one that does *not* carry the credential inline. Prefer it, because it
keeps the secret out of the call. See [../automation/credentials.md](../automation/credentials.md).

Both return a `DeclarativeJobResult`:

```bash
python3 tools/schema_query.py verb Orion.Declarative.PollerTemplates ExecuteWithCreds
```

```text
  return shape (4 member(s)):
    IsSuccess                                    boolean
    ErrorMessage                                 string
    ErrorCode                                    number
    Entities                                     array<array>
```

**Read `IsSuccess`.** The verb reports failure in the result rather than by throwing, so a
call that completed and a call that worked are different things. `ErrorMessage` and
`ErrorCode` carry the reason.

### `clientSettings` is the whole configuration

`clientSettings` is an array of `DeclarativeClientSettings`, and that type has nineteen
members — it is the HTTP client configuration, the polling schedule and the caching policy in
one object:

| Member | Type |
| --- | --- |
| `BaseEndpoint` | string |
| `VerifySslCertificate` | boolean |
| `CertificateThumbprint` | string |
| `UseProxy` | boolean |
| `PageSize` | number |
| `PollingInterval` | `System.TimeSpan` |
| `CredentialID` | number |
| `RequestsLimitationPeriod` | `System.TimeSpan` |
| `RequestsLimit` | number |
| `RequestRetries` | number |
| `RequestMaxWait` | `System.TimeSpan` |
| `PollingRequestsCacheTimeToLive` | `System.TimeSpan` |
| `CacheTimeToLiveToleranceAdjustment` | number |
| `ClientSessionCacheTimeToLive` | `System.TimeSpan` |
| `SettingsAsMacros` | array of `MacroValue` |
| `EnableEntityTypeCheck` | boolean |
| `LogSensitiveDetails` | `LogSensitiveDetailsSettings` |
| `HttpTimeout` | `System.TimeSpan` |
| `SessionManagerCacheStorageScope` | `CacheStorageScope` |

Three things to notice. `RequestsLimit` with `RequestsLimitationPeriod` is a rate limit, which
matters when the target is an API with quotas. The `System.TimeSpan` members are not plain
numbers, so a value serialised as an integer is unlikely to be read as you intend. And
`CredentialID` appears here as well as in the verb's own argument list, with nothing in the
schema saying which wins — that is unverified here, so set one deliberately rather than both.

**`LogSensitiveDetails` does what its name says.** It is a
`LogSensitiveDetailsSettings` with eight booleans — `LogRequestParameters`, `LogRequestBody`,
`LogResponseUri`, `LogResponseStatus`, `LogResponseHeaders`, `LogResponseContent`,
`LogResponseRequestParameters` and `LogFailureResponseDetails`. Turning on the body, header or
parameter flags writes authentication material into logs that are not treated as secret. It
exists for diagnosing a template that will not authenticate; leave it off otherwise, and turn
it off again afterwards.

`CacheStorageScope` and the fields of `MacroValue` beyond `Key`, `Value`, `Values` and
`IsExpandable` are **not described in the published schema** and are unverified here.

## Gotchas

**`TechnologyID` is a string here and a GUID in Device Studio.**
`Orion.Technology.TechnologyID` and `Orion.TechnologyPolling.TechnologyID` are
`System.String`; `Orion.DeviceStudio.Technologies.TechnologyID` and
`Orion.DeviceStudio.Pollers.TechnologyID` are `System.Guid`. Joining across the two returns
nothing rather than erroring. `TechnologyPollingID`, a `System.String` on both sides, is the
column that actually bridges them. See [device-studio.md](device-studio.md).

**The one-argument verbs act on the whole estate.** `EnableAssignments` and
`DisableAssignments` are not scoped versions of the `OnNetObjects` forms with a default; they
have no scope at all beyond the technology.

**`netObjectIDs` wants bare integers.** The argument is `array<number>` despite the name, so
`N:42` is wrong here. This is the same trap the guides document for other verbs whose
`netObjectId` argument is declared as a number rather than a string; see
[../swis/invoke-verbs.md](../swis/invoke-verbs.md).

**Nothing here is writable through CRUD.** Three of the four entities declare no operations,
so there is no URI to `POST` to. The verbs are the write surface.

**No property in these entities carries a schema summary.** Everything above is read from
names and types. Confirm behaviour on your own server before automating against it, and see
[../reference/unverified.md](../reference/unverified.md) for the collected list of what this
repository does not know.

## Related pages

- [README.md](README.md) for the other four polling systems and how to tell them apart
- [device-studio.md](device-studio.md) for the system `TechnologyPollingID` joins to
- [api-pollers.md](api-pollers.md) for the other HTTP-based collector, which is documented
  far more thoroughly by the schema
- [../automation/credentials.md](../automation/credentials.md) for the credential store
  `credentialId` points at
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the Invoke contract and array arguments
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for confirming any of
  this against a live server
