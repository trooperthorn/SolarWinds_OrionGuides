# Credentials

Discovery and polling need credentials, and the platform keeps them in one shared store so
that a community string or a service account is defined once and referenced by everything
that needs it. This page covers the entities that hold them, the verbs that create and update
them, how nodes and discovery profiles reference them, and the security posture that follows
from the way the store is designed.

The short version of that posture: **credentials go in, they do not come back out.** The
entity you query exposes a name, a type and an owner, and nothing else. That is a feature, and
it is the reason automating credentials is safe to do while automating them badly is not.

Grounded in SolarWinds'
[Credential Management](https://solarwinds.github.io/OrionSDK/docs/credential-management/)
page and in the extracted 2026.2 schema.

## `Orion.Credential`

```bash
python3 tools/schema_query.py show Orion.Credential
```

```text
Orion.Credential   [2026.2]
  Entity represents Orion Credential objects that are used in discovery and polling processes
  inherits: System.Entity -> Orion.Credential
  operations: create, delete, invoke, read, update
    read                                   requires everyone
    create,read,update,delete,invoke       requires manageNodes
    create,read,update,delete,invoke       requires manageReports
    create,read,update,delete,invoke       requires manageAlerts
    create,read,update,delete,invoke       requires admin
    create,read,update,delete,invoke       requires system

  properties (5)
    ID                                         System.Int32
    Name                                       System.String
    Description                                System.String
    CredentialType                             System.String
    CredentialOwner                            System.String
```

Five properties. That is the whole queryable surface of a credential, and the absence is the
point: there is no `Password`, no `Community`, no `SecretKey`. The secret material lives
behind the store and is never a column you can select.

| Property | Holds |
| --- | --- |
| `ID` | The integer every other entity references a credential by |
| `Name` | The display name, unique within a given type and owner |
| `Description` | Free text |
| `CredentialType` | The fully qualified .NET type of the credential, which decides its shape |
| `CredentialOwner` | Which subsystem owns it: `Orion`, `APM`, `CLI`, `CLM`, `ApiPoller` |

`CredentialOwner` is not decoration. SolarWinds' own documentation notes that the type and
owner of a credential set **cannot be changed after creation**, and that uniqueness is
enforced on the combination of name, type and owner. Two credentials called `windows-svc` can
coexist if one is owned by `Orion` and the other by `APM`, which is a real source of confusion
when a script looks a credential up by name alone.

Note the access control. Reading credential metadata requires only `everyone`, so any
authenticated account can see that a credential named `core-rw` exists. Creating, updating and
deleting requires one of `manageNodes`, `manageReports`, `manageAlerts`, `admin` or `system`,
which is broader than people expect: an account granted report management can create
credentials.

## `Orion.CredentialRelation`

A credential on its own does nothing. The relation entity is what attaches it to something.

```bash
python3 tools/schema_query.py show Orion.CredentialRelation
```

```text
Orion.CredentialRelation   [2026.2]
  Relation to Orion.Credential. Serve for reuse same credentials for different Entity type.
  inherits: System.Entity -> Orion.CredentialRelation
  operations: create, delete, invoke, read, update
    read                                   requires everyone
    create,read,update,delete,invoke       requires manageNodes

  properties (7)
    CredentialRelationID                       System.Int64
    EntityType                                 System.String
    EntityID                                   System.Int64
    EntityUri                                  System.String
    CredentialID                               System.Int32
    Use                                        System.String
    ConnectionProfile                          System.String
```

The schema's own summary says it exists to "reuse same credentials for different Entity type",
which is exactly how to read the shape. `EntityType` plus `EntityID` identifies the thing the
credential is attached to, `EntityUri` carries the same target in URI form, and `CredentialID`
points at `Orion.Credential.ID`. `Use` distinguishes several credentials attached to the same
object for different purposes.

There is a navigation property from the relation to the credential, so a query can dot-walk
one hop:

```sql
SELECT TOP 20
    r.EntityType,
    r.EntityID,
    r.Use,
    r.Credential.Name,
    r.Credential.CredentialType
FROM Orion.CredentialRelation r
ORDER BY r.CredentialRelationID
```

There is no navigation from the relation to the target object, because the target can be any
entity type. Joining to `Orion.Nodes` means an explicit join on `r.EntityID = n.NodeID`
together with a filter on `r.EntityType`, which the [worked queries](#worked-queries) below
show.

## Credential types

`CredentialType` is a fully qualified .NET type name. The table below is
[SolarWinds' published list](https://solarwinds.github.io/OrionSDK/docs/credential-management/),
which is the authority for it: these strings are not entity names in the SWIS schema and this
repository cannot verify them against the extracted data.

| `CredentialType` | Used for | Default `CredentialOwner` | Since |
| --- | --- | --- | --- |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.UsernamePasswordCredential` | Username and password, used throughout the product including discovery and alert or report actions | `Orion` | 2022.4 |
| `SolarWinds.APM.Common.Credentials.ApmUsernamePasswordCredential` | The SAM module's own username and password, for application discovery | `APM` | 2022.4 |
| `SolarWinds.Orion.Core.Models.Credentials.SnmpCredentialsV2` | SNMP v1 and v2c community strings, for discovery | `Orion` | 2022.4 |
| `SolarWinds.Orion.Core.Models.Credentials.SnmpCredentialsV3` | Node SNMPv3 credentials | `Orion` | 2022.4 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.CliCredential` | Node credentials for CLI polling, including an enable password | `CLI` | 2022.4 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.ApiKeyCredential` | Token authentication for the "Send GET/POST Request" alert action, and API pollers | `Orion` | 2022.4 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.SmtpServerCredential` | Basic authentication to an SMTP server, for alert and report delivery | `Orion` | 2022.4 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.BearerTokenCredential` | API poller bearer tokens | `Orion` | 2023.2 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.OAuth2Credential` | OAuth 2.0 for SMTP servers and API pollers | `Orion` | 2023.2 |
| `SolarWinds.Orion.Core.SharedCredentials.Credentials.UsernameWithOauth2Credentials` | OAuth 2.0 with the password grant type | `Orion` | 2024.2 |
| `SolarWinds.CloudMonitoring.Contract.Credentials.AwsCredentials` | AWS cloud account access key and secret | `CLM` | 2023.4 |
| `SolarWinds.CloudMonitoring.Contract.Credentials.AzureCredentials` | Azure subscription, tenant, client id and secret | `CLM` | 2023.4 |
| `SolarWinds.CloudMonitoring.Contract.Credentials.GcpCredential` | GCP service account key material | `CLM` | 2025.2 |

Note what is and is not in that list. There is no distinct "Windows" credential type: a
Windows or Active Directory service account used for WMI polling is a
`UsernamePasswordCredential`, created by `CreateUsernamePasswordCredentials`, with the
username in `domain\user` form. There is no distinct "SSH" type either: SSH and telnet device
logins are `CliCredential`, which is why that type carries an `EnablePassword` key alongside
username and password.

The authoritative list for **your** server is your server:

```sql
SELECT
    c.CredentialType,
    c.CredentialOwner,
    COUNT(c.ID) AS Credentials
FROM Orion.Credential c
GROUP BY c.CredentialType, c.CredentialOwner
ORDER BY COUNT(c.ID) DESC
```

Run that before writing anything that hard-codes a type string.

## The verbs

`Orion.Credential` exposes ten verbs. Every one requires `manageNodes`. They fall into two
generations.

### Type-specific verbs

These are the older set, one pair per credential shape. They are still the least ceremonious
way to create the common cases.

| Verb | Parameters, in order | Returns |
| --- | --- | --- |
| `CreateSNMPCredentials` | `name`, `community`, `owner` *(optional)* | `number` |
| `UpdateSNMPCredentials` | `credentialId`, `name`, `community` | `System.Void` |
| `CreateSNMPv3Credentials` | `name`, `username`, `context`, `authenticationMethodValue`, `authenticationPassword`, `authenticationKeyIsPassword`, `privacyMethodValue`, `privacyPassword`, `privacyKeyIsPassword`, `owner` *(optional)* | `number` |
| `UpdateSNMPv3Credentials` | `credentialId`, `name`, `username`, `context`, `authenticationMethodValue`, `authenticationPassword`, `authenticationKeyIsPassword`, `privacyMethodValue`, `privacyPassword`, `privacyKeyIsPassword` | `System.Void` |
| `CreateUsernamePasswordCredentials` | `name`, `username`, `password`, `owner` *(optional)* | `number` |
| `UpdateUsernamePasswordCredentials` | `credentialId`, `name`, `username`, `password` | `System.Void` |
| `CreateUsernamePasswordWithContentCredentials` | `name`, `username`, `password`, `content`, `owner` *(optional)* | `number` |
| `UpdateUsernamePasswordWithContentCredentials` | `credentialId`, `name`, `username`, `password`, `content` | `System.Void` |

The create verbs return the new credential's `ID`, which is what you feed into a discovery
plugin configuration or a `Orion.CredentialRelation` row. The update verbs return
`System.Void`, so confirm the change with a query rather than with the response.

Credential names must be unique for a given type, and SolarWinds' documentation states that
an attempt to create a duplicate throws. That makes create-then-ignore-the-error a poor
pattern; check first, or catch and resolve to the existing id.

```bash
python3 tools/schema_query.py verb Orion.Credential CreateSNMPv3Credentials
```

```text
Orion.Credential.CreateSNMPv3Credentials
  Creates SNMP v3 credentials
  returns: number
  REST:    POST /Invoke/Orion.Credential/CreateSNMPv3Credentials
  requires: manageNodes
  parameters (10):
    name: string (required)
        Required. Credentials name.
    username: string (required)
        Required. Username.
    context: string (required)
        Required. Context.
    authenticationMethodValue: string (required)
    authenticationPassword: string (required)
        Required. Authentication password. Value can be empty.
    authenticationKeyIsPassword: boolean (required)
        Required. Is authentication key password (True, False).
    privacyMethodValue: string (required)
    privacyPassword: string (required)
        Required. Privacy password. Value can be empty.
    privacyKeyIsPassword: boolean (required)
        Required. Is privacy key password (True, False).
    owner: string (optional)
        Optional. Credential owner. Default value = Orion
```

Two naming details. SolarWinds' prose calls the fourth parameter `authenticationMethod` and
the seventh `privacyMethod`, while the extracted contract names them
`authenticationMethodValue` and `privacyMethodValue`. Since **arguments are positional and
names never travel on the wire**, a positional caller is unaffected; a generated client that
binds by name is not. The same page also lists the boolean parameters as
`isAuthenticationPasswordKey` in the signature and `authenticationKeyIsPassword` in the
parameter notes. The contract says `authenticationKeyIsPassword`.

The accepted values for the method arguments are not recorded in the published schema and are
unverified here. SolarWinds' credential-management page names `None`, `MD5` and `SHA1` for
authentication and `None`, `DES56`, `AES128`, `AES192` and `AES256` for privacy in the verb
documentation, while the shared-credential property table for `SnmpCredentialsV3` also lists
`SHA256` and `SHA512` for authentication. Treat the shorter list as the safe one for the
type-specific verb unless you have confirmed otherwise on your release.

```powershell
$credentialId = Invoke-SwisVerb $swis 'Orion.Credential' 'CreateSNMPv3Credentials' @(
    'core-snmpv3',        # name
    $env:SNMP_USER,       # username
    '',                   # context
    'SHA1',               # authenticationMethodValue
    $env:SNMP_AUTH_PASS,  # authenticationPassword
    $true,                # authenticationKeyIsPassword
    'AES128',             # privacyMethodValue
    $env:SNMP_PRIV_PASS,  # privacyPassword
    $true,                # privacyKeyIsPassword
    'Orion'               # owner
)
```

The comments are doing real work there. Ten positional arguments of which six are strings that
would all coerce successfully in the wrong order is exactly the shape of call that fails
silently, and a credential that authenticates against nothing looks identical to a device that
is down.

### Shared credential verbs

From SolarWinds Platform 2022.4 there are two general verbs that handle most types through a
property dictionary instead of a fixed argument list.

```bash
python3 tools/schema_query.py verb Orion.Credential CreateCredentials
```

```text
Orion.Credential.CreateCredentials
  Creates credential with provided list of properties
  returns: number
  REST:    POST /Invoke/Orion.Credential/CreateCredentials
  requires: manageNodes
  parameters (3):
    type: string (required)
        Required. The credentials type.
    properties: array<System.Collections.Generic.KeyValuePair~System.String_System.String~> (required)
        Required. Credentials properties.
    owner: string (optional)
        Required. The credentials owner.
```

`UpdateCredentials` takes `id` and `properties`, and cannot change type or owner.

The `properties` dictionary always carries `Name` and `Description`, which belong to the
credential set itself rather than to the secret, plus the keys the type requires. For a
`UsernamePasswordCredential` those are `Username` and `Password`; for `SnmpCredentialsV2`,
`Community`; for `CliCredential`, `Username`, `Password` and `EnablePassword`; for
`BearerTokenCredential`, `Token`. SolarWinds' page carries the full key list per type.

```powershell
$props = @{
    Name        = 'wmi-monitoring'
    Description = 'Read-only WMI service account'
    Username    = $env:WMI_USER
    Password    = $env:WMI_PASSWORD
}

$credentialId = Invoke-SwisVerb $swis 'Orion.Credential' 'CreateCredentials' @(
    'SolarWinds.Orion.Core.SharedCredentials.Credentials.UsernamePasswordCredential',
    $props,
    'Orion'
)
```

Prefer this pair when you need a type the older verbs do not cover, such as bearer tokens,
OAuth 2.0 or cloud provider keys. Prefer the type-specific verbs when the type is SNMP or
username and password, because a fixed signature is validated by the contract and a dictionary
key typo is not.

Note the `owner` contradiction in the extracted contract: the parameter is marked optional
while its own description says "Required. The credentials owner." Pass it explicitly. The
default owner per type is in the table above, and getting it wrong produces a credential the
subsystem that needs it will not look at.

## How credentials are referenced

There are three distinct mechanisms, and conflating them is the usual reason a script sets a
credential and polling does not change.

### By the shared relation, for most things

`Orion.CredentialRelation` is the general mechanism. A row attaches credential `CredentialID`
to the object named by `EntityType` and `EntityID`, for the purpose named in `Use`. It is
created, read, updated and deleted through [CRUD](../swis/crud.md) with `manageNodes`, since
the entity declares no verbs.

`ConnectionProfile` on the same row is how NCM expresses a named bundle of device login
settings rather than a single credential. The NCM side of that lives on `Cirrus.Nodes`, which
exposes `GetAllConnectionProfiles`, `GetConnectionProfile`, `AddConnectionProfile`,
`UpdateConnectionProfile` and `DeleteConnectionProfile`. See [../modules/ncm.md](../modules/ncm.md).

### By per-node SNMPv3 settings, which are not shared credentials

`Orion.Nodes` has a navigation property to `Orion.SNMPv3Credentials`, a
`System.ExtensionEntity` keyed by `NodeID`:

```bash
python3 tools/schema_query.py path Orion.Nodes Orion.SNMPv3Credentials
```

```text
1 path(s) from Orion.Nodes to Orion.SNMPv3Credentials, shortest first

  Orion.Nodes.SNMPv3Credentials
    Orion.Nodes --SNMPv3Credentials--> Orion.SNMPv3Credentials
```

This is the node's **own** SNMPv3 configuration, not a pointer into the shared store. It
carries `Username`, `Context`, `AuthenticationMethod`, `PrivacyMethod`, the corresponding
`AuthenticationKey` and `PrivacyKey`, the two `KeyIsPassword` flags, and a parallel `RW*` set
for read-write access. It allows `read` and `update` with `manageNodes`.

So a node can be polled using credentials that exist nowhere in `Orion.Credential`. A report
that lists "which nodes use which credential" from the shared store alone will show nothing
for those nodes, which reads as a gap in the data and is not one. Query both.

`Orion.Nodes` itself declares **no** `CredentialID` property. If you were expecting one,
that expectation is the bug:

```bash
python3 tools/schema_query.py props Orion.Nodes --grep cred
```

```text
Orion.Nodes properties (0 shown, including inherited)
```

### By id, in a discovery plugin configuration

Discovery does not use the relation entity. It takes credential ids directly, in the XML
configuration passed to `Orion.Discovery.CreateCorePluginConfiguration`, ordered by the
sequence in which they should be tried. SolarWinds' own
[`DiscoverSnmpV3Node.ps1`](https://github.com/solarwinds/OrionSDK/blob/master/Samples/PowerShell/DiscoverSnmpV3Node.ps1)
sample resolves the ids by name first, which is the pattern to copy:

```powershell
$credentialId = Get-SwisData $swis 'SELECT ID FROM Orion.Credential WHERE Name = @name' `
    @{ name = 'core-snmpv3' }
```

```xml
<Credentials>
    <SharedCredentialInfo>
        <CredentialID>1</CredentialID>
        <Order>1</Order>
    </SharedCredentialInfo>
    <SharedCredentialInfo>
        <CredentialID>2</CredentialID>
        <Order>2</Order>
    </SharedCredentialInfo>
</Credentials>
```

`Order` matters: discovery tries them in sequence, so putting a rarely correct credential first
costs a timeout per device. Full discovery flow in [discovery.md](discovery.md).

`Orion.DiscoveredNodes.CredentialID` records which credential actually worked for each
discovered node, which is the feedback loop for tuning that order.

### Testing a credential before you rely on it

`Orion.Discovery.ValidateCredentials` checks a credential against a real endpoint and returns
a boolean:

```bash
python3 tools/schema_query.py verb Orion.Discovery ValidateCredentials
```

```text
Orion.Discovery.ValidateCredentials
  Check if provided credential is valid for given SNMP or WMI endpoint
  returns: boolean
  REST:    POST /Invoke/Orion.Discovery/ValidateCredentials
  parameters (6):
    ipAddress: string (required)
    port: number (required)
    credentialsType: string (required)
    credentialsProperties: array<System.Collections.Generic.KeyValuePair~System.String_System.String~> (required)
    engineId: number (required)
    preferredSnmpVersion: SolarWinds.Orion.Core.Models.Credentials.SNMPVersion (optional)
        one of: None, SNMP1, SNMP2c, SNMP3
```

Note that it takes the credential's **properties**, not its id, so it validates material you
are holding rather than something already stored. That makes it the right call to make between
"the operator gave me a password" and "I created a credential from it", and it is the cheapest
way to avoid filling the store with credentials that never worked.

## Security posture

### Credentials cannot be read back

`Orion.Credential` declares `ID`, `Name`, `Description`, `CredentialType` and
`CredentialOwner`. No verb on the entity returns secret material either: the create verbs
return an id, the update verbs return `System.Void`. There is no supported way to recover a
stored password, community string or key through SWIS.

Design around it rather than against it. In particular:

- **A migration script cannot copy credentials between servers.** It can enumerate names,
  types and owners on the source, and it must be given the secrets again for the target.
- **A backup of the SWIS-visible data is not a backup of the credentials.**
- **Rotation is set, not read-modify-write.** You supply the new secret; there is nothing to
  compare it against.

`Orion.SNMPv3Credentials` does declare `AuthenticationKey`, `PrivacyKey` and their read-write
counterparts as `System.String` columns. What a query against them actually returns is
runtime behaviour and is **not verified here**. Do not select them into a report, a log line
or an exception message on the assumption that they are masked. If you need to know what your
server returns, test it once, deliberately, on a node whose credentials you are about to
rotate anyway.

### Never hard-code a secret into a script

This is the rule that gets broken because the alternative feels like more work at the moment
the script is written, and it is the one that turns a repository into a credential leak.

- **Read secrets from the environment or from a secret manager at run time.** The PowerShell
  examples above use `$env:` variables for exactly this reason.
- **Prompt when running interactively.** `Get-Credential` in PowerShell,
  `getpass.getpass()` in Python. This repository's own
  [`swis_client.py`](../../scripts/python/swis_client.py) reads its password from
  `SWIS_PASSWORD` or prompts, and never accepts one as a command-line argument, because
  arguments land in shell history and in the process table where any local user can read them.
- **Do not log the arguments of a credential verb.** A generic "invoking {verb} with {args}"
  debug line will write the password to disk on the first failure, which is the moment
  somebody turns debug logging on.
- **Do not pass a secret as a query parameter.** `Orion.Credential` gives you no reason to,
  and a bound parameter still travels in the request body and may be logged by an intermediary.
- **Scope the account that runs the script.** Credential writes need `manageNodes`, not
  `admin`. See [accounts-and-permissions.md](accounts-and-permissions.md).
- **Rotate through `Update*` rather than delete-and-recreate.** Updating keeps the same `ID`,
  so every relation, discovery profile and node reference keeps working. Deleting and
  recreating gives you a new id and silently orphans everything that pointed at the old one.

If a secret has already been committed somewhere, treat rotating it as the fix. Removing the
commit is not.

## Worked queries

### The credential inventory

The starting point for any credential audit, and safe to run as any account, since the store
exposes no secret material.

```sql
SELECT
    c.ID,
    c.Name,
    c.Description,
    c.CredentialType,
    c.CredentialOwner
FROM Orion.Credential c
ORDER BY c.CredentialOwner, c.Name
```

Sorting by owner first groups the store the way the platform thinks about it, which makes the
duplicate-name-across-owners case visible instead of confusing.

### Which nodes use a given credential

The question this page exists to answer. Note the two-part filter: `EntityType` restricts the
relation rows to nodes, and only then does joining `EntityID` to `NodeID` mean anything.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.IPAddress,
    r.Use,
    r.ConnectionProfile,
    c.Name AS CredentialName,
    c.CredentialType
FROM Orion.CredentialRelation r
JOIN Orion.Credential c ON r.CredentialID = c.ID
JOIN Orion.Nodes n ON r.EntityID = n.NodeID
WHERE r.EntityType = 'Orion.Nodes'
  AND c.Name = @credentialName
ORDER BY n.Caption
```

Run this **before** rotating a credential, not after. It is the blast radius of the change: if
the new secret is wrong, this is the exact list of nodes that will start failing to poll, and
having it in front of you turns a mystery outage into a one-line rollback.

`EntityID` is a `System.Int64` and `NodeID` is a `System.Int32`, which the server widens for
the comparison. Without the `EntityType` filter the join would happily match a volume id
against a node id and produce rows that are pure coincidence.

### Where credentials are used at all

The same relation table, aggregated, which tells you which subsystems on this server actually
use the shared store.

```sql
SELECT
    r.EntityType,
    r.Use,
    COUNT(r.CredentialRelationID) AS Relations
FROM Orion.CredentialRelation r
GROUP BY r.EntityType, r.Use
ORDER BY COUNT(r.CredentialRelationID) DESC
```

The `Use` values are installation data rather than schema, so this doubles as the way to
discover what the `Use` column can contain on your server.

### Credentials nothing references

Cleanup candidates, and also the list of credentials whose secrets you are still storing and
still have to rotate for no benefit.

```sql
SELECT
    c.ID,
    c.Name,
    c.CredentialType,
    c.CredentialOwner
FROM Orion.Credential c
WHERE c.ID NOT IN (SELECT r.CredentialID FROM Orion.CredentialRelation r)
ORDER BY c.Name
```

Read the result carefully before deleting anything. A credential can be referenced from places
this query does not look: a discovery profile configuration, an alert action, an API poller, a
cloud account. `NOT IN` against the relation table means "no shared relation", not "unused".
Cross-check against the discovery query below, and against
`Orion.Cloud.Accounts.CredentialId` and `Orion.SMTPServers.CredentialID` if those modules are
installed.

### Nodes polled with per-node SNMPv3 settings

The other half of "which nodes use which credential", covering the nodes the shared store
knows nothing about.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.SNMPVersion,
    n.SNMPv3Credentials.Username,
    n.SNMPv3Credentials.Context,
    n.SNMPv3Credentials.AuthenticationMethod,
    n.SNMPv3Credentials.PrivacyMethod
FROM Orion.Nodes n
WHERE n.SNMPVersion = 3
ORDER BY n.Caption
```

Deliberately no key columns. The username, context and algorithm names are what you need for
an inventory, and the keys are not.

A run of nodes sharing a username with `AuthenticationMethod = 'MD5'` is the finding worth
acting on: it is a per-node configuration that should probably be a shared SNMPv3 credential,
and an algorithm that should probably be SHA.

### Which credential succeeded during discovery

The feedback loop for ordering credentials in a discovery profile.

```sql
SELECT
    p.ProfileID,
    p.Name AS ProfileName,
    p.LastRun,
    c.ID AS CredentialID,
    c.Name AS CredentialName,
    c.CredentialType,
    COUNT(d.NodeID) AS DiscoveredNodes
FROM Orion.DiscoveredNodes d
JOIN Orion.DiscoveryProfiles p ON d.ProfileID = p.ProfileID
JOIN Orion.Credential c ON d.CredentialID = c.ID
GROUP BY p.ProfileID, p.Name, p.LastRun, c.ID, c.Name, c.CredentialType
ORDER BY p.Name
```

A credential that discovered zero nodes across several runs is one to move to the end of the
order or remove from the profile. Every device the profile scans pays a timeout for it.

### Who has been changing credentials

```sql
SELECT
    e.TimeLoggedUtc,
    e.AccountID,
    t.ActionTypeDisplayName,
    e.AuditEventMessage
FROM Orion.AuditingEvents e
JOIN Orion.AuditingActionTypes t ON e.ActionTypeID = t.ActionTypeID
WHERE e.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
  AND t.ActionType LIKE '%Credential%'
ORDER BY e.TimeLoggedUtc DESC
```

`TimeLoggedUtc` is UTC, hence `ToUtc` around the bound; see
[../swql/date-and-time.md](../swql/date-and-time.md). Which `ActionType` values a given
release emits for credential operations is installation data, so if this returns nothing,
widen the filter and look at what the audit trail actually calls them. The technique is in
[events-and-auditing.md](events-and-auditing.md).

## Gotchas

**Name uniqueness is per type and owner, not global.** Looking a credential up by name alone
can return the wrong one. Filter on `CredentialType` or `CredentialOwner` too when it matters.

**Type and owner are immutable.** If either is wrong you create a new credential and repoint
everything, which is exactly the delete-and-recreate problem the rotation advice above warns
about. Get the owner right the first time.

**`Orion.Nodes` has no `CredentialID`.** Node credential references live in
`Orion.CredentialRelation` or in the per-node `Orion.SNMPv3Credentials` extension.

**Creating a duplicate throws.** SolarWinds documents this for the type-specific verbs and
says `CreateCredentials` "does not allow you to create duplicates". Query first.

**A credential is not a node property, so changing it does not repoll.** After rotating,
trigger a poll if you want to find out immediately whether the new secret works:
`Orion.Nodes.PollNow` with a NetObject id such as `N:42`. See
[node-management.md](node-management.md).

**Deleting a credential does not tell you what broke.** The relation rows and discovery
profiles that referenced it are the only record, and after deletion that record is gone. Run
the blast-radius query first and keep the output.

**Credential writes need `manageNodes`, but so do several other rights.** The entity grants
create and update to `manageReports` and `manageAlerts` as well, so an account provisioned for
reporting can also change polling credentials. That is worth knowing during an access review.

## See also

- [discovery.md](discovery.md) for the discovery flow credentials feed into
- [node-management.md](node-management.md) for creating nodes and repolling them
- [accounts-and-permissions.md](accounts-and-permissions.md) for the rights these verbs need
- [events-and-auditing.md](events-and-auditing.md) for tracking credential changes
- [../swis/crud.md](../swis/crud.md) for creating and deleting `Orion.CredentialRelation` rows
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for positional argument encoding
- SolarWinds'
  [Credential Management](https://solarwinds.github.io/OrionSDK/docs/credential-management/)
  page, which carries the full property key list for every shared credential type
