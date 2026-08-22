# NCM config change templates

A **config change template** — a CCT, and `Cirrus.ConfigSnippets` in the API — is a small
script that the NCM console turns into a form. A user picks devices, answers a few questions,
and the template assembles and sends the CLI commands. The point is that the person running it
does not have to know the commands, and the person who wrote it did not have to know the
devices.

Three things combine in one:

1. **Data NCM already holds.** Node inventory, interfaces, VLANs, IP addresses and custom
   properties are all reachable from inside the script, so a template can decide what to send
   based on what the device actually is.
2. **The template's own scripting.** Conditionals, loops and string manipulation, so one
   template can cover a family of devices rather than one model.
3. **Questions put to the user.** Free text, a device selection, a dropdown. Whatever the
   script declares as a parameter becomes a field on the form.

This page covers what a template is made of and how to manage one through the API.
[ncm-change-template-language.md](ncm-change-template-language.md) is the language reference:
operators, functions, variables and control flow.

## Cirrus, NCM, and which name appears where

Network Configuration Manager was called **Cirrus**, and both names survive in the schema as
two separate namespaces. Which one holds what is not a detail you can guess:

| Namespace | Holds |
| --- | --- |
| `Cirrus.` | The NCM data model proper — nodes, the config archive, compliance, jobs, and **config change templates** |
| `NCM.` | Device inventory — interfaces, VLANs, IP addresses, ARP and route tables |

So a change template is stored in `Cirrus.ConfigSnippets`, and the things it reads at run time
are `NCM.` entities. Both appear in the same template, which is the usual reason people assume
one of the two names is wrong.

See [../modules/ncm.md](../modules/ncm.md) for the full module.

## Anatomy

A template has three parts, in order: an optional comment block, a directive block, and the
script itself.

```text
// A free comment. Anything on a line after // is ignored.

/*
.CHANGE_TEMPLATE_DESCRIPTION
    Upgrade Cisco IOS from an FTP server.

.CHANGE_TEMPLATE_TAGS
    IOS, upgrade, cisco

.PLATFORM_DESCRIPTION
Cisco IOS

.PARAMETER_LABEL @ContextNode
    Devices to upgrade
.PARAMETER_DESCRIPTION @ContextNode
    Select the routers this image applies to.
*/

script UpgradeIOS (
    NCM.Nodes @ContextNode,
    string @FTPServerIP
)
{
    // body
}
```

The directive block is a `/* ... */` comment. NCM parses it anyway — that is the trick, and it
is why the directives are invisible to anything that only understands comments.

## The directives

| Directive | Takes | Effect |
| --- | --- | --- |
| `.CHANGE_TEMPLATE_DESCRIPTION` | Text on the following lines | The description shown in the console when the template is imported |
| `.CHANGE_TEMPLATE_TAGS` | Comma-separated list | Tags applied on import; these become `Cirrus.Tags` rows |
| `.PLATFORM_DESCRIPTION` | A device platform, e.g. `Cisco IOS` | Declares which NCM device type the template is written for |
| `.PARAMETER_LABEL @Var` | Text | The label shown to the left of that parameter's field |
| `.PARAMETER_DESCRIPTION @Var` | Text | Help text shown under that parameter's field |
| `.PARAMETER_DISPLAY_TYPE @Var` | `Listbox:1=A\|2=B\|3=C` | Renders that parameter as a dropdown instead of a text field |

`.PARAMETER_DISPLAY_TYPE` is the one worth dwelling on. The value is a `Listbox:` prefix
followed by `value=label` pairs separated by pipe characters:

```text
.PARAMETER_DISPLAY_TYPE @Speed
    Listbox:10=10 Mbit|100=100 Mbit|1000=1 Gbit
```

The user picks a label and the script receives the value on the left of the `=`. Whether any
display type other than `Listbox` is supported is **not documented by SolarWinds and is
unverified here**.

The parameter directives are keyed by variable name, so each one names the parameter it
decorates. A directive naming a variable that is not in the signature has nothing to attach to.

## The signature decides what the user sees

```text
script ConfigureVLANmembershipCiscoIOS (
    NCM.Nodes @ContextNode,
    NCM.Interfaces[] @TargetPorts,
    NCM.VLANs[] @VlansToRemove,
    NCM.VLANs[] @VlanToAssign
)
```

Four rules govern this line, and between them they explain most templates that "do not work":

**Every template must take a node parameter.** `NCM.Nodes @ContextNode` is the device
selection, and it is required. Everything else is optional.

**A parameter is the only way to ask the user for something.** A variable used in the body but
absent from the signature is not a question — it is an undefined variable. If you want the
user to supply an FTP server address, `string @FTPServerIP` has to be in the signature.

**`[]` makes a parameter a collection**, and the console renders it as a multi-select.
`NCM.Interfaces[] @TargetPorts` asks the user to pick interfaces, plural, and the body
iterates them.

**The script name is not addressable.** `script UpgradeIOS (...)` names the script, but the
console identifies the template by its `Name` in `Cirrus.ConfigSnippets`, not by this
identifier. Keep them consistent for the reader's sake; nothing enforces it.

## The parameter types are SWIS entities

This is the part that makes templates worth writing, and it is barely mentioned in SolarWinds'
material: `NCM.Nodes`, `NCM.Interfaces` and `NCM.VLANs` in a template signature are **the same
entities the API exposes**. What you can navigate from a template parameter is what the schema
says you can navigate.

So the schema tools in this repository answer questions about template authoring directly:

```bash
python3 tools/schema_query.py show NCM.Nodes
```

That lists 48 properties and 22 navigation properties on `NCM.Nodes`, and every one of them is
reachable from `@ContextNode`. The ones templates use most:

| From | Reaches | As |
| --- | --- | --- |
| `@ContextNode.Vendor` | `NCM.Nodes.Vendor` | `System.String`, mirroring `Orion.Nodes.Vendor` |
| `@ContextNode.MachineType` | `NCM.Nodes.MachineType` | `System.String` |
| `@ContextNode.SysName` | `NCM.Nodes.SysName` | `System.String` |
| `@ContextNode.AgentIP` | `NCM.Nodes.AgentIP` | `System.String`, the polling IP |
| `@ContextNode.Interfaces` | `NCM.Interfaces` | A collection, `System.Hosting` |
| `@ContextNode.VLANs` | `NCM.VLANs` | A collection, `System.Hosting` |

and one hop further:

| From | Reaches | As |
| --- | --- | --- |
| `@interfaceItem.InterfaceDescription` | `NCM.Interfaces.InterfaceDescription` | `System.String` |
| `@interfaceItem.InterfaceName` | `NCM.Interfaces.InterfaceName` | `System.String` |
| `@interfaceItem.IpAddresses` | `NCM.IpAddresses` | A collection, `System.Hosting` |
| `@ip.IPAddress` | `NCM.IpAddresses.IPAddress` | `System.String` |

Note the casing on that last one. The navigation property is `IpAddresses` with a lowercase
`p`, and the property on the entity it reaches is `IPAddress` with a capital `P`. They are one
hop apart and spelled differently, which is exactly the sort of thing to copy from the schema
rather than from memory.

Whether the template engine accepts a navigation the schema declares but SolarWinds' own
examples never use is **unverified here**. The mapping holds for every documented example, and
the schema is the best available guide to the rest.

## Managing templates through the API

Templates are `Cirrus.ConfigSnippets` rows. The entity declares **no operations at all**, so
there is no CRUD path to them — the eleven verbs are the entire interface.

```sql
SELECT
    s.ID,
    s.Name,
    s.Description,
    s.Created,
    s.LastModified,
    s.PreserveWhiteSpace
FROM Cirrus.ConfigSnippets s
ORDER BY s.Name
```

`AdvancedScript` is the template body itself, so this is how you export every template you
have as text:

```sql
SELECT
    s.ID,
    s.Name,
    s.AdvancedScript
FROM Cirrus.ConfigSnippets s
ORDER BY s.Name
```

Worth doing before an upgrade. The console has no bulk export, and a template is source code
that nothing version-controls for you.

### The entity and the contract disagree about two names

The verbs take and return a
`SolarWinds.NCM.Contracts.InformationService.ConfigSnippet`, and that type is not shaped quite
like the entity:

| Entity property | Contract member | Note |
| --- | --- | --- |
| `ID` | `Id` | Different casing |
| `AdvancedScript` | `Script` | **Different name** |
| `Name` | `Name` | |
| `Description` | `Description` | |
| `Created` | `Created` | `System.DateTime` on the entity, `string` in the contract |
| `LastModified` | `LastModified` | Same |
| `PreserveWhiteSpace` | `PreserveWhiteSpace` | |
| — | `Tags` | `array<string>`, with no property on the entity |

So a script read from a query comes back in `AdvancedScript` and the same script handed to
`AddSnippet` goes in `Script`. And tags are on the contract type but not the entity: to read
them from a query you join `Cirrus.Tags` on `SnippetID`, and to read them through a verb you
call `GetTagsListForSnippets`.

### The eleven verbs

| Verb | Arguments | Returns |
| --- | --- | --- |
| `AddSnippet` | `snippet` (a `ConfigSnippet`) | number |
| `GetSnippet` | `snippetId` | `ConfigSnippet` |
| `UpdateSnippet` | `snippet` | number |
| `SaveSnippetAsCopy` | `snippet` | number |
| `CopySnippets` | `snippetIds` (array of number) | void |
| `DeleteSnippets` | `snippetIds` | number |
| `ImportSnippets` | `snippets` (array of `ConfigSnippet`) | void |
| `GetTagsList` | none | array |
| `GetTagsListForSnippets` | `snippetIds` | array |
| `AddTags` | `snippetIds`, `tags` | number |
| `DeleteTags` | `snippetIds`, `tags` | number |

```bash
python3 tools/schema_query.py verb Cirrus.ConfigSnippets AddSnippet
```

`AddSnippet` and `ImportSnippets` are not the same operation at different scales: `AddSnippet`
returns the new id and `ImportSnippets` returns `System.Void`, so a bulk import gives you
nothing to correlate against what you sent. Import, then query by name to find out what
happened.

All eleven require at least the **WebUploader NCM role**, which is separate from the Orion
rights the rest of this repository documents. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

**`Cirrus.SnippetArchive` is a different entity.** It archives snippet *configs* keyed by a
`ConfigID` GUID and has its own `AddSnippet`, `UpdateSnippet` and `DeleteSnippet` requiring the
Administrator NCM role. The verb names overlap and the entities do not. Do not reach for it
when you meant `Cirrus.ConfigSnippets`.

## What this repository can and cannot check

Every entity, property, navigation and verb named on this page is checked against the 2026.2
schema, and the SWQL queries are validated like any other query here.

The template language is not in the schema. Directive names, the `Listbox:` syntax, the
signature grammar and everything in
[ncm-change-template-language.md](ncm-change-template-language.md) come from SolarWinds'
documentation and from THWACK, and **cannot be verified here**. They are marked where they
appear and collected in [../reference/unverified.md](../reference/unverified.md).

## See also

- [ncm-change-template-language.md](ncm-change-template-language.md) — operators, string
  functions, macros, control flow and CLI blocks
- [../modules/ncm.md](../modules/ncm.md) — the NCM module, the config archive, compliance,
  jobs, and `Cirrus.Nodes.ParseMacros` for previewing macro expansion
- [README.md](README.md) — the rest of this section
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) — the Invoke contract and array arguments
- [../automation/custom-properties.md](../automation/custom-properties.md) — the custom
  properties a template can read
