# Credential storage across modules

The platform has a shared credential store, and not every module uses it. That is the whole
subject of this page: which modules reference `Orion.Credential`, which keep credential
material of their own, which do both, and what can be done about it through SWIS.

[credentials.md](credentials.md) covers the store itself — the credential types, the verbs,
and why you cannot read a secret back. This page is about the seams between it and the
modules.

## Two architectures, side by side

**Reference the store.** The entity carries an integer pointing at `Orion.Credential.ID` and
holds no secret of its own. `Orion.Cloud.Accounts`, `Orion.VIM.VCenters`,
`Orion.SRM.Providers`, `Orion.HardwareHealth.BMC.Controllers`, `Orion.SMTPServers` and the
three VNQM connection-info entities all work this way.

**Keep the material inline.** The entity has its own `Password`, `Community` or
`EnablePassword` columns. `Cirrus.Nodes` and `NCM.Nodes` do this, and so does
`Orion.SEUM.Agents`, `Orion.Toolset.ConnectionProfiles` and `Orion.SSH.Session`. Even
`Orion.Nodes` holds `Community` and `RWCommunity` directly.

58 entities carry at least one credential-shaped column. Both patterns are in current use and
neither is being migrated toward the other.

## The reference is a convention, not a relationship

28 columns across the schema name a credential id. **Three of them navigate to
`Orion.Credential`.**

```bash
python3 tools/schema_query.py show Orion.Credential
```

The entity declares one source relationship and two target relationships, and that is the
whole of the declared graph:

| Entity | Navigation | Direction |
| --- | --- | --- |
| `Orion.Cloud.Accounts` | `Credential` | to the store |
| `Orion.ESI.IncidentService` | `Credentials` | to the store |
| `Orion.CredentialRelation` | `Credential` | to the store |

Every other credential id — VNQM's, IPAM's, VMAN's, SRM's, hardware health's, the SMTP
servers' — is a **bare integer with nothing enforcing it**. Nothing stops a row pointing at a
credential that was deleted, and no query will tell you it happened unless you go looking:

```sql
SELECT
    c.ID,
    c.Name,
    c.CredentialType,
    c.CredentialOwner
FROM Orion.Credential c
ORDER BY c.CredentialType, c.Name
```

Take that list and compare it against every referencing column. There is no join the schema
will write for you.

### Four spellings and two widths

The column name is not consistent either, which matters the moment you write anything generic
over it:

| Spelling | Where |
| --- | --- |
| `CredentialID` | The platform convention — VNQM, VMAN, SRM, hardware health, SMTP, EOC, SCM, discovery |
| `CredentialId` | IPAM's `DhcpServer` and `DnsServer`, and `Orion.Cloud.Accounts` |
| `CredentialsId` | API pollers, `Orion.Cman.ContainerAgent`, WPM recording authentications |
| `CredentialsID` | SAM's `TemplateGroupAssignment`, as `AgentWmiCredentialsID` and `SnmpIcmpCredentialsID` |

SWQL is forgiving about identifier case, so a query written against the wrong spelling usually
still runs; a client that maps result columns onto a case-sensitive structure is not. See
[../swql/language-reference.md](../swql/language-reference.md).

The width is the sharper problem. **`Orion.Credential.ID` is a `System.Int32`.** Three
families store the reference as `System.Int64`:

| Entity | Column | Type |
| --- | --- | --- |
| `Orion.VIM.Hosts` | `CredentialID` | `System.Int64` |
| `Orion.VIM.VCenters` | `CredentialID` | `System.Int64` |
| `Orion.VIM.VMwareNodes` | `CredentialID` | `System.Int64` |
| `Orion.APIPoller.RequestDetails` | `CredentialsId` | `System.Int64` |
| `Orion.Cman.ContainerAgent` | `CredentialsId` | `System.Int64` |

A 64-bit column holding a 32-bit key is harmless until something compares them in a
type-sensitive way. It is the same class of trap as `Cirrus.Nodes.NodeID` being a `System.Guid`
where `Orion.Nodes.NodeID` is an `Int32` — see [../swql/gotchas.md](../swql/gotchas.md).

## `Orion.CredentialRelation` is the mechanism nobody mentions

The schema describes it in one sentence, and the sentence is the answer to "how do I share a
credential across modules":

> Relation to Orion.Credential. Serve for reuse same credentials for different Entity type.

```bash
python3 tools/schema_query.py show Orion.CredentialRelation
```

It is a generic association table — **any entity type, any object, one credential**:

| Property | Type | What it is |
| --- | --- | --- |
| `CredentialRelationID` | `System.Int64` | The row's own key |
| `EntityType` | `System.String` | The entity name, as a string |
| `EntityID` | `System.Int64` | That entity's own key |
| `EntityUri` | `System.String` | The canonical reference |
| `CredentialID` | `System.Int32` | The credential, matching the store's width |
| `Use` | `System.String` | What the credential is used for |
| `ConnectionProfile` | `System.String` | The profile it belongs to |

It declares **create, read, update, delete and invoke on `manageNodes`, and no verbs at all** —
so it is pure CRUD, and writable. That makes it the one place you can bind a credential to an
object of any type without the module offering an API for it.

```sql
SELECT
    cr.CredentialRelationID,
    cr.EntityType,
    cr.EntityID,
    cr.Use,
    cr.ConnectionProfile,
    cr.Credential.Name,
    cr.Credential.CredentialType
FROM Orion.CredentialRelation cr
ORDER BY cr.EntityType, cr.Credential.Name
```

That query is the closest thing to a cross-module credential inventory the platform has, and
the `Credential` navigation on it is one of only three that exist.

**What values `EntityType` and `Use` take is not recorded in the schema and is unverified
here.** Read the existing rows on your own server before writing new ones — the table is
generic enough that a wrong `Use` string is accepted and does nothing.

## Module by module

### VNQM is the least integrated

`Orion.IpSla.AxlConnectionInfo`, `Orion.IpSla.CliConnectionInfo` and
`Orion.IpSla.FtpConnectionInfo` each carry `NodeID` and a `CredentialID`, and:

- **none declares any operation** — no create, read, update, delete or invoke
- **none navigates** to `Orion.Credential`
- **no `Orion.IpSla.*` entity declares a single credential verb**

```bash
python3 tools/schema_query.py show Orion.IpSla.CliConnectionInfo
```

So there is **no SWIS path to change which credential a VNQM connection uses.** You can read
the binding and you cannot write it. That is the inconsistency in its clearest form: the
module stores a reference into the shared store and offers nothing to maintain it.

Reading what is bound takes an explicit join in both directions, since neither end declares a
navigation:

```sql
SELECT
    n.Caption,
    n.IPAddress,
    cli.CredentialID,
    cli.Port,
    c.Name AS CredentialName,
    c.CredentialType
FROM Orion.IpSla.CliConnectionInfo cli
JOIN Orion.Nodes n ON n.NodeID = cli.NodeID
LEFT JOIN Orion.Credential c ON c.ID = cli.CredentialID
ORDER BY n.Caption
```

The `LEFT JOIN` is deliberate. A row where `CredentialName` comes back empty is a VNQM
connection pointing at a credential that no longer exists, and nothing else in the platform
will report it.

The same shape works for `AxlConnectionInfo` and `FtpConnectionInfo`.

### IPAM has its own creation path and its own spelling

`IPAM.DhcpServer` and `IPAM.DnsServer` carry `CredentialId` — lowercase `d` — with no
navigation and no declared operations. But unlike VNQM, IPAM does publish verbs, on
`IPAM.DhcpDnsManagement`:

| Verb | Arguments | Returns |
| --- | --- | --- |
| `CreateDhcpCredentials` | `dhcpServerType`, `credentials` | number |
| `CreateDnsCredentials` | `dnsServerType`, `credentials` | number |
| `StartDhcpCredentialsTest` | `nodeId`, `dhcpServerType`, `credentialId`, `credentials` | string |
| `StartDnsCredentialsTest` | `nodeId`, `dnsServerType`, `credentialId`, `credentials` | string |

**None of the four declares a right.** The entity declares no operations either, so nothing in
the contract says who may create an IPAM credential.

Two details make this a genuine seam rather than just a parallel path:

**The property bag is typed differently.** `Orion.Credential.CreateCredentials` takes
`array<KeyValuePair<String, String>>`; `IPAM.DhcpDnsManagement.CreateDhcpCredentials` takes
`array<KeyValuePair<String, Object>>`. Same idea, different value type, so a helper written for
one does not serialise correctly for the other.

**`AddDhcpServer` accepts both paths at once.** It takes 22 arguments, and among them are
`newCredentialName`, `newCredentialUserName`, `newCredentialPassword`,
`newCredentialEnablePassword`, `newCredentialProtocol` — *and* `credentialId`:

```bash
python3 tools/schema_query.py verb IPAM.DhcpDnsManagement AddDhcpServer
```

So you can hand it an existing credential id or have it mint one inline. **Which id space
`credentialId` belongs to — the shared store or an IPAM-local one — is not stated in the
schema and is unverified here.** The width matches `Orion.Credential.ID`, which is suggestive
and not proof. Settle it on your own server by creating one credential through
`Orion.Credential.CreateUsernamePasswordCredentials`, passing the returned id to
`AddDhcpServer`, and querying `IPAM.DhcpServer.CredentialId` to see what landed.

That experiment is the single most useful thing on this page for anyone standardising
credentials across modules, and this repository cannot run it.

### SRM has a complete parallel API

`Orion.SRM.BusinessLayer` publishes an entire second credential surface:

| Verb | Purpose |
| --- | --- |
| `AddCredential` | Create |
| `GetCredential` | Read one |
| `GetCredentialNames` | List by type |
| `GetCredentialType` | Type of one |
| `UpdateCredential` | Update |
| `DeleteCredentials` | Delete, by array of ids |
| `CheckIfCredentialNameExists` | Name collision check |
| `TestCredentials` | Validate a connection |

None of the eight declares a right. `Orion.SRM.StorageArrays.AddSmisCredentials` is a ninth,
taking `displayName`, `userName`, `password` and more directly.

The interesting part is that `AddCredential` takes a
`SolarWinds.Orion.Core.SharedCredentials.Credential` — **the platform's own shared credential
type**. So SRM is not using a different credential model; it is using the same model through a
different door. `DeleteCredentials` is one of the twelve array-in, void-out, destructive verbs
catalogued in
[../swis/invoke-at-scale.md](../swis/invoke-at-scale.md#the-four-dangerous-shapes).

### The contract type and the entity disagree

Worth knowing before writing anything against either:

| `Orion.Credential` entity | `SharedCredentials.Credential` type |
| --- | --- |
| `ID` | `ID` |
| `Name` | `Name` |
| `Description` | `Description` |
| `CredentialOwner` | `Owner` |
| `CredentialType` | — |
| — | `IsBroken` |

**`IsBroken` exists only on the contract type.** A credential the platform has decided no
longer works is flagged there and is not queryable from the entity, so an audit built on
`Orion.Credential` alone cannot see it. Reading it means a verb call per credential —
`Orion.SRM.BusinessLayer.GetCredential` is one path, though whether it reports the flag for
credentials SRM did not create is **unverified here**.

### NCM keeps the material itself

`Cirrus.Nodes` and `NCM.Nodes` carry `Password`, `EnablePassword`, `Community`,
`CommunityReadWrite` and a `UseUserDeviceCredential` flag directly on the node row. There is no
credential id at all. `Cirrus.NodeProperties` and `NCM.NodeProperties` repeat the same columns.

`Cirrus.Settings.CryptPasswords()` — no parameters, `System.Void`, `admin` — is the only verb
in this area, and what it does to existing rows is not documented. Treat it as one of the
no-parameter verbs from
[../swis/invoke-at-scale.md](../swis/invoke-at-scale.md#the-four-dangerous-shapes).

Connection profiles are the integration point NCM does offer; see
[../modules/ncm.md](../modules/ncm.md).

## Auditing what you have

**Every credential and what claims to use it**, as far as the declared graph goes:

```sql
SELECT
    c.ID,
    c.Name,
    c.CredentialType,
    c.CredentialOwner,
    COUNT(cr.CredentialRelationID) AS Bindings
FROM Orion.Credential c
LEFT JOIN Orion.CredentialRelation cr ON cr.CredentialID = c.ID
GROUP BY c.ID, c.Name, c.CredentialType, c.CredentialOwner
ORDER BY COUNT(cr.CredentialRelationID)
```

A credential with zero bindings is **not** unused — it may be referenced by any of the 25
columns that do not navigate. That query finds candidates for review, never candidates for
deletion.

**Dangling references**, per module. There is no generic form, because there is no generic
join; write one per referencing entity:

```sql
SELECT
    v.CredentialID,
    v.NodeID
FROM Orion.IpSla.FtpConnectionInfo v
LEFT JOIN Orion.Credential c ON c.ID = v.CredentialID
WHERE c.ID IS NULL
```

```sql
SELECT
    d.NodeId,
    d.CredentialId,
    d.ServerType
FROM IPAM.DhcpServer d
LEFT JOIN Orion.Credential c ON c.ID = d.CredentialId
WHERE c.ID IS NULL
```

**Nodes carrying SNMP community strings inline**, which the credential store never sees:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.SNMPVersion,
    n.Community,
    n.RWCommunity
FROM Orion.Nodes n
WHERE n.SNMPVersion > 0
ORDER BY n.Caption
```

Treat the output of that one as sensitive. `Community` and `RWCommunity` are the credential,
not a reference to it, and they are readable by anything that can query the node.

## What can actually be synced

| Goal | Path |
| --- | --- |
| Create a credential once, centrally | `Orion.Credential.CreateUsernamePasswordCredentials` or `CreateCredentials` |
| Bind it to an object of any entity type | Write an `Orion.CredentialRelation` row through CRUD |
| Point IPAM at an existing credential | `IPAM.DhcpDnsManagement.AddDhcpServer`, passing `credentialId` — id space unverified |
| Point SRM at one | `Orion.SRM.BusinessLayer.AddCredential`, which takes the shared type |
| Point VMAN at one | Set `CredentialID` on `Orion.VIM.VCenters` through CRUD, then `Orion.VIM.Discovery.ValidateExistingCredentials` to check it |
| Point VNQM at one | **No SWIS path exists** |
| Rotate a secret in place | `Orion.Credential.UpdateUsernamePasswordCredentials`, which keeps the id and so keeps every reference |

That last row is the one that makes central storage worth the effort. Updating a credential
by id leaves all 28 referencing columns pointing at the same row, so a rotation is one call
rather than a hunt. A module that keeps its material inline gets none of that, which is the
practical cost of the inconsistency.

## Gotchas

**A credential id is not a foreign key.** 25 of the 28 columns have nothing behind them.
Deleting a credential leaves them pointing at a row that is gone, silently.

**Four spellings.** `CredentialID`, `CredentialId`, `CredentialsId`, `CredentialsID`.

**Two widths.** The store's key is `System.Int32`; VMAN, API pollers and container agents
store `System.Int64`.

**VNQM is read-only for credentials through SWIS.** There is no verb and no declared
operation.

**IPAM and SRM credential verbs declare no rights at all**, at either level. See
[../swis/invoke-at-scale.md](../swis/invoke-at-scale.md#authorization-is-thinner-than-it-looks).

**`IsBroken` is invisible from the entity.** It exists on the contract type only.

**Inline credential columns are readable.** `Orion.Nodes.Community`, `RWCommunity`,
`Cirrus.Nodes.Password` and `EnablePassword` are queryable columns, and several are published
alert variables — see
[../webui/variables-reference.md](../webui/variables-reference.md#snmpv3-credential-variables).

## See also

- [credentials.md](credentials.md) — the credential store, its types, and its verbs
- [../swis/invoke-at-scale.md](../swis/invoke-at-scale.md) — the verbs here in the context of
  the whole Invoke risk surface
- [../modules/vnqm.md](../modules/vnqm.md), [../modules/ipam.md](../modules/ipam.md),
  [../modules/srm.md](../modules/srm.md), [../modules/vman.md](../modules/vman.md) — the
  modules themselves
- [../modules/ncm.md](../modules/ncm.md) — connection profiles, NCM's own answer
- [../swql/gotchas.md](../swql/gotchas.md) — id types that differ across entities
