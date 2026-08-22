# Variables and macros

A **variable** — SolarWinds also calls these macros — is a placeholder the platform substitutes
at run time. They appear in alert messages and notifications, in report titles, in NCM command
scripts and change templates, and in a few other places the console lets you type free text.

Two syntaxes exist and both are current:

| Form | Example | Meaning |
| --- | --- | --- |
| `${Value}` | `${NodeName}` | A named variable. The previous-generation form |
| `${N=context;M=macro;F=format}` | `${N=SwisEntity;M=Status;F=Status}` | The current form: three attributes, of which `N` and `M` are required |
| `${SQL:query}` | `${SQL:Select Count(*) From Nodes}` | A SQL query evaluated against the database |

The second form arrived in **Orion Platform 2015.1** and is built on SWIS, which is why it is
the interesting one for this repository: the `M=` half resolves against the SWIS schema, and
that is something the checked-in data can answer exactly.

Both still work. The console's variable picker inserts the new form by default; a
previous-generation variable such as `${NodeName}` has to be typed by hand.

## The three attributes

| Attribute | Required | What it does |
| --- | --- | --- |
| `N` | Yes | The **context**: which source the value comes from |
| `M` | Yes | The **macro**: the variable or member name within that context |
| `F` | No | The **format**: converts the value to a friendly form |

`F` has to correlate with the data. SolarWinds' own guidance is that `DateTime` belongs with
`AcknowledgedTime` and not with `ObjectType`. `${N=SwisEntity;M=Status;F=Status}` and
`${N=Generic;M=Today;F=Date}` are the published shapes. The complete set of format names is
**not published in the material this repository has** and is unverified here; the variable
picker in the console offers them, which is the practical way to find out what your version
accepts.

Everything is available from the picker. Nothing here needs to be typed by hand except a
previous-generation variable, which the picker will not insert.

### The four contexts

| `N=` | Supplies |
| --- | --- |
| `Alerting` | Variables specific to the alert itself — its name, severity, acknowledgement state |
| `SwisEntity` | Variables for the object being monitored, in the context of the alert |
| `OrionGroup` | Variables specific to groups |
| `Generic` | General environmental properties — the installation, and the clock |

The full tables are in [variables-reference.md](variables-reference.md).

`N=SwisEntity` is the one that matters most. It resolves against **the entity the alert
triggered on**, and `M` is a property of that entity. So `${N=SwisEntity;M=Caption}` on a
node alert is `Orion.Nodes.Caption`, and on an interface alert the same variable is
`Orion.NPM.Interfaces.Caption`. The variable does not name the entity; the alert does.

```text
Node ${N=SwisEntity;M=Caption} is currently down.
```

Which entity that is comes from the alert definition:

```sql
SELECT
    ac.AlertID,
    ac.Name,
    ac.ObjectType,
    ac.Severity,
    ac.Enabled
FROM Orion.AlertConfigurations ac
ORDER BY ac.ObjectType, ac.Name
```

`ObjectType` is the entity name as a string. At run time the same fact is on
`Orion.AlertObjects`, which ties a triggered alert to the object that triggered it:

```sql
SELECT
    ao.AlertObjectID,
    ao.EntityType,
    ao.EntityCaption,
    ao.EntityNetObjectId,
    ao.RelatedNodeCaption,
    ao.TriggeredCount
FROM Orion.AlertObjects ao
ORDER BY ao.EntityType
```

Read `Orion.AlertObjects` alongside the variable list. Its own columns — `EntityCaption`,
`EntityDetailsUrl`, `EntityNetObjectId`, `RelatedNodeUri`, `RelatedNodeCaption` — are the
shape of what the alerting layer knows about a triggered object regardless of what that object
is, and that is the same job several of the general alert variables do.

## The member list is the property list

`M=` on the `SwisEntity` context is a member of the trigger entity, and this repository has
checked that against SolarWinds' own published tables:

| Published set | Members | Found in the 2026.2 schema |
| --- | --- | --- |
| Node variables | 60 | **60** on `Orion.Nodes` |
| Volume variables | 23 | **23** on `Orion.Volumes` |
| `SNMPv3Credentials.*` | 16 | **16** on `Orion.SNMPv3Credentials` |
| `PCUs.*` | 16 | **16** on `Cortex.Orion.PowerControlUnit` |

116 of 116. That correspondence is what makes the context enumerable, and it also settles a
question the schema alone could not: **a dotted `M=` walks a navigation property.** `Stats`,
`SNMPv3Credentials` and `PCUs` are all real navigation properties of `Orion.Nodes`, and
SolarWinds publishes variables that go through them.

One published name does not fit. `${N=SwisEntity;M=Node.Allow64BitCounters}` carries a `Node.`
prefix, but `Allow64BitCounters` is a directly declared property of `Orion.Nodes` and `Node` is
not one of its navigation properties, so there is nothing for the prefix to resolve through.
Treat it as a discrepancy in the published table rather than a rule.

So the property list is the variable list:

```bash
python3 tools/schema_query.py props Orion.Nodes
```

Every name that prints is addressable as `${N=SwisEntity;M=<name>}` on an alert whose
`ObjectType` is `Orion.Nodes`. The same works for any entity:

```bash
python3 tools/schema_query.py props Orion.NPM.Interfaces --grep status
```

One qualification remains, marked **unverified here** because the schema does not record it:
whether *every* member is exposed to the variable engine, or only a subset. The published
tables cover 60 of the 102 properties `Orion.Nodes` declares, and nothing says what the other
42 do. [variables-undocumented.md](variables-undocumented.md) works through them and says
plainly that it is inference.

Navigation depth is the other open question. The three published examples each walk exactly
one hop; whether two hops work, and what a to-many navigation renders when it matches several
rows, are **not documented and unverified here**.

On a live server, `Metadata.Property` answers the same question authoritatively for that
server:

```sql
SELECT
    p.Name,
    p.Type,
    p.IsNavigable
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Nodes'
ORDER BY p.Name
```

Note the filter. `Metadata.Property` has no `EntityName` column and reaches its owner through
the `Entity` navigation property; see
[../swis/metadata-introspection.md](../swis/metadata-introspection.md).

## `${SQL:…}` runs a query

Any value the database can produce can be a variable:

```text
${SQL:Select Count(*) From Nodes}
```

Note what that is and is not. The query is **T-SQL against the database**, not SWQL against
SWIS — `Nodes` there is the table, not `Orion.Nodes` the entity. So none of
[../swql/README.md](../swql/README.md) applies to it, and neither do account limitations,
which are a SWIS concept. A `${SQL:…}` variable in an alert message reads the database
directly with whatever rights the platform runs as.

That makes it powerful and worth treating carefully:

- It runs **every time the message renders**. An expensive query behind a frequently
  triggering alert is a load problem that will not look like one.
- It bypasses the account limitations that scope everything else a user sees. Two people
  reading the same alert email see the same number, whatever their limitations would allow
  them to see in the console.
- Whether the query text is escaped or validated in any way is **not documented and is
  unverified here**. Treat an alert message that accepts user input and interpolates it into
  a `${SQL:…}` as you would any other dynamic SQL.

Prefer a `SwisEntity` member when one exists. Reach for `${SQL:…}` for aggregate values that
have no entity behind them, which is what SolarWinds' own example does.

## Custom properties are variables too

A custom property is a column on the custom-property entity for its target, so it is reachable
the same way as any other member. What exists is enumerable:

```sql
SELECT
    cp.Field,
    cp.TargetEntity,
    cp.DataType,
    cp.MaxLength,
    cp.Description
FROM Orion.CustomProperty cp
ORDER BY cp.TargetEntity, cp.Field
```

`Field` is the column name — the name a variable would use — and `TargetEntity` says which
kind of object it hangs off. `DisplayName` is the console label and need not match `Field`.
See [../automation/custom-properties.md](../automation/custom-properties.md).

## What is in use on your own server

Alert messages are stored, so the variables actually being used are queryable. This is the
fastest way to see the real conventions on an installation you have inherited:

```sql
SELECT
    ac.Name,
    ac.ObjectType,
    ac.AlertMessage,
    ac.SuppressMessage
FROM Orion.AlertConfigurations ac
WHERE ac.AlertMessage LIKE '%${%'
ORDER BY ac.ObjectType, ac.Name
```

`Orion.ActionsProperties` holds the bodies of notification actions, which is where most
variables actually live — the alert message is often short and the email is not.

## Variables by module

Which variables exist for a module is determined by which entities that module contributes,
because those are the entities an alert can trigger on. The entity families are:

| Module | Namespaces | Enumerate with |
| --- | --- | --- |
| NPM | `Orion.NPM.`, `Orion.Routing.`, `Orion.Packages.Wireless.`, `Orion.WirelessHeatMap.`, `Orion.NetPath.` | `python3 tools/schema_query.py find Orion.NPM.` |
| SAM | `Orion.APM.` | `python3 tools/schema_query.py find Orion.APM.` |
| NCM | `Cirrus.`, `NCM.` | `python3 tools/schema_query.py find Cirrus.` |
| NTA | `Orion.Netflow.` | `python3 tools/schema_query.py find Orion.Netflow.` |
| IPAM | `IPAM.` | `python3 tools/schema_query.py find IPAM.` |
| UDT | `Orion.UDT.` | `python3 tools/schema_query.py find Orion.UDT.` |
| SRM | `Orion.SRM.` | `python3 tools/schema_query.py find Orion.SRM.` |
| VMAN | `Orion.VIM.` | `python3 tools/schema_query.py find Orion.VIM.` |
| VNQM | `Orion.IpSla.` | `python3 tools/schema_query.py find Orion.IpSla.` |
| WPM | `Orion.SEUM.` | `python3 tools/schema_query.py find Orion.SEUM.` |
| DPA | `Orion.DPA.`, `DPA.` | `python3 tools/schema_query.py find Orion.DPA.` |
| Log Analyzer | `Orion.OLM.` | `python3 tools/schema_query.py find Orion.OLM.` |
| Hardware Health | `Orion.HardwareHealth.` | `python3 tools/schema_query.py find Orion.HardwareHealth.` |
| QoE | `Orion.DPI.` | `python3 tools/schema_query.py find Orion.DPI.` |
| Cloud | `Orion.Cloud.` | `python3 tools/schema_query.py find Orion.Cloud.` |
| Agents | `Orion.AgentManagement.` | `python3 tools/schema_query.py find Orion.AgentManagement.` |

Each module page carries the entity detail: [../modules/README.md](../modules/README.md).

### NCM is the exception

NCM has a **second, unrelated macro system** that is not alert variables and does not use the
`N=`/`M=` form. `${StorageAddress}`, `${SCPStorageAddress}`, `${SCPServerUserName}`,
`${SCPServerPassword}` and `${CRLF}` are NCM settings substituted into command scripts and
config change templates. They share the `${...}` spelling with alert variables and have
nothing else in common.

`Cirrus.Nodes.ParseMacros(nodeId, macro)` expands one against a real node, which is the way to
find out what a macro produces. See
[ncm-change-template-language.md](ncm-change-template-language.md#two-kinds-of-variable-and-they-are-not-interchangeable)
and [../modules/ncm.md](../modules/ncm.md).

## What is published, and what still is not

The tables SolarWinds publishes are in [variables-reference.md](variables-reference.md):
the `Alerting`, `Generic` and `OrionGroup` contexts, the node and volume lists, the UPS
variables, and the previous-generation syslog and trap lists.

Still missing from this repository, and named so the gap is explicit rather than silent:

| Not here | Where it lives |
| --- | --- |
| Module-specific variable tables beyond nodes, volumes and UPS | Each module's own documentation, e.g. [SAM alert variables](https://documentation.solarwinds.com/en/success_center/sam/content/sam-alerts-variables.htm) |
| The complete `F=` format list | The variable picker in your console |
| Defunct variables — those that no longer resolve | [Defunct alert variables](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-defunct-alert-variables-sw1433.htm) |
| Interface, application and component variable tables | The NPM and SAM documentation |

The defunct list is worth singling out. A variable that no longer resolves does not error — it
renders as empty text or as the literal `${...}`, so an alert email quietly loses a field.
That is the same silent-failure shape as an unmatched `_LinkFor_` column in
[custom-query-widget.md](custom-query-widget.md), and the reason to put a known-good variable
beside any new one while testing.

For members that exist in the schema and appear in no published table at all, see
[variables-undocumented.md](variables-undocumented.md).

## See also

- [README.md](README.md) — the rest of this section, and why the schema cannot verify console
  behaviour
- [../automation/alerts.md](../automation/alerts.md) — alert definitions, actions and
  suppression through the API
- [../automation/custom-properties.md](../automation/custom-properties.md) — creating the
  properties that become variables
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) — asking a live server
  what members an entity has
- [ncm-change-template-language.md](ncm-change-template-language.md) — NCM's separate macro
  system
