# Variables and macros

A **variable** — SolarWinds also calls these macros — is a placeholder the platform substitutes
at run time. They appear in alert messages and notifications, in report titles, in NCM command
scripts and change templates, and in a few other places the console lets you type free text.

Two syntaxes exist and both are current:

| Form | Example | Meaning |
| --- | --- | --- |
| `${Value}` | `${NodeName}` | A named variable. The previous-generation form |
| `${N=Namespace;M=Member}` | `${N=SwisEntity;M=Caption}` | The current form: `N` selects a namespace, `M` a member within it |

The second form arrived in **Orion Platform 2015.1** and is built on SWIS, which is why it is
the interesting one for this repository: the `M=` half resolves against the SWIS schema, and
that is something the checked-in data can answer exactly.

Both still work. The console's variable picker inserts the new form by default; a
previous-generation variable such as `${NodeName}` has to be typed by hand.

## What `N` and `M` select

`N` names a **namespace** — a source of values — and `M` names a **member** of it.

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

## Finding the valid `M=` values for yourself

This is the part no SolarWinds page can give you, because it depends on your version and your
installed modules. If `M=` is a property of the trigger entity, then the property list *is*
the variable list:

```bash
python3 tools/schema_query.py props Orion.Nodes
```

Every name that prints is addressable as `${N=SwisEntity;M=<name>}` on an alert whose
`ObjectType` is `Orion.Nodes`. The same works for any entity:

```bash
python3 tools/schema_query.py props Orion.NPM.Interfaces --grep status
```

Two qualifications, both marked **unverified here** because the schema does not record them.
Whether every property is exposed to the variable engine — or only a subset — is not
something the contract states. And whether a navigation property can be walked inside a
variable, so that `M=Node.Caption` resolves from an interface alert, is likewise not stated.
Test both on your own server before depending on them.

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

## The named-variable tables are not transcribed here

**This section is a gap, and this is what is missing and why.**

SolarWinds publishes the authoritative lists of *named* variables — the `N=` namespaces beyond
`SwisEntity`, the previous-generation `${NodeName}` family, the date and time variables, and
the module-specific tables — across a set of pages in the Success Center. This repository
could not reach them: `documentation.solarwinds.com` is blocked by the network egress policy of
the environment these pages were written in, for both direct fetches and the documentation
tooling.

Rather than reconstruct several hundred variable names from memory — which is exactly the
plausible-but-wrong failure the rest of this repository exists to prevent — the pages are named
here so the gap is explicit and fillable:

| Page | Holds |
| --- | --- |
| [Variables in the SolarWinds Platform](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-orion-variables-and-examples-sw1115.htm) | The syntax reference and the namespace list |
| [General alert variables](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-general-alert-variables-sw1121.htm) | The general alert variable table |
| [Syslog alert variables](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-syslog-alert-variables-sw2132.htm) | Syslog-specific variables |
| [Defunct alert variables](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-defunct-alert-variables-sw1433.htm) | Variables that no longer resolve, which is the table to check when a message renders blank |
| [Alert on custom properties](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-use-a-custom-property-in-alerts-sw1100.htm) | Custom properties in the `N=`/`M=` form |
| [Use properties, variables, and macros in SAM alerts](https://documentation.solarwinds.com/en/success_center/sam/content/sam-alerts-variables.htm) | The SAM module table |
| [NCM macros (variables)](https://documentation.solarwinds.com/en/success_center/ncm/content/ncm-understanding-ncm-macros.htm) | The NCM macro list, the second system described above |

What *is* on this page is verified: the `${N=SwisEntity;M=...}` mechanism, how the trigger
entity is determined, and how to enumerate the members for any entity from the checked-in
schema or from `Metadata.Property` on a live server. That covers the half of the system that
depends on your installation, which is also the half no published table can be current for.

The defunct-variables page is worth singling out. A variable that no longer resolves does not
error — it renders as empty text or as the literal `${...}`, so an alert email quietly loses a
field. That is the same silent-failure shape as an unmatched `_LinkFor_` column in
[custom-query-widget.md](custom-query-widget.md).

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
