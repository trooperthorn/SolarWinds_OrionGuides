# NCM device templates: the `.ConfigMgmtCommands` format

A device template tells NCM **how to talk to one kind of device over Telnet or SSH**: which
command shows the running config, how to get into configuration mode, what the prompt looks
like when the session is privileged, and how to recognise that a page-break prompt needs a
keypress.

Everything NCM does that involves a CLI session — downloading a config, uploading one, running
a script — runs through the template for that device. Get it wrong and the symptom is not an
error but a session that hangs at a prompt nobody answered, or a config file containing a page
of `--More--`.

**Source.** Derived by parsing three real exports — a SolarWinds-shipped Cisco CatOS template,
a stock Cisco starting template, and a hand-built custom one — against the 2026.2 schema.
SolarWinds documents the console workflow but not the file.

[ncm.md](ncm.md) covers NCM's entities and its config-archive verbs. This page is the template
document and the CRUD around it.

## The file

```xml
<!--SolarWinds Network Management Tools-->
<!--Copyright 2007 SolarWinds.Net All rights reserved-->
<Configuration-Management Device="Cisco Catalyst CatOS6500"
                          SystemOID="1.3.6.1.4.1.9.5.50"
                          SystemDescriptionRegex=""
                          AutoDetectType="BySystemOid">
  <Commands>
    <Command Name="RESET" Value="set length 0" />
    <Command Name="DownloadConfig" Value="Show ${ConfigType}" />
    …
  </Commands>
</Configuration-Management>
```

No namespace, no schema declaration — this is the oldest and simplest of the platform's export
formats, and the 2007 copyright header on the shipped ones says so.

The console names the file `<Device><SystemOID>.ConfigMgmtCommands`, with spaces in the device
name replaced by underscores: `Cisco_Catalyst_CatOS6500` + `1.3.6.1.4.1.9.5.50` +
`.ConfigMgmtCommands`.

### The root attributes

| Attribute | Maps to `Cli.DeviceTemplates` | Meaning |
| --- | --- | --- |
| `Device` | `TemplateName` | Display name |
| `SystemOID` | `SystemOID` | The sysObjectID prefix this template matches |
| `SystemDescriptionRegex` | `SystemDescriptionRegex` | The alternative match, by system description |
| `AutoDetectType` | `AutoDetectType` | Which of the two is used |

**`AutoDetectType` is a string in the file and an integer in the entity.** The XML writes
`BySystemOid`; the schema documents `AutoDetectType` as `System.Int32` — *"0 uses the system
OID; 1 uses the system description."* So `BySystemOid` is `0`, and the string for `1` is
presumably `BySystemDescription`, which is **not attested by any of the three samples and is
unverified here**.

`SystemOID` is a **prefix**, not an exact value. `1.3.6.1.4.1.9` matches all of Cisco;
`1.3.6.1.4.1.9.5.50` matches the Catalyst 6500 specifically. The more specific template wins,
which is how a vendor-wide fallback and a model-specific override coexist. That the longest
match wins is the obvious reading of the two shipped samples and is **unverified here**.

`Comments`, `UseForAutoDetect`, `IsDefault` and `Author` are columns on the entity with **no
attribute in the file**. They are installation state rather than template content, which is why
the document travels.

## The commands

Every entry is `<Command Name="…" Value="…" />`. The `Name` is a fixed vocabulary NCM looks up;
the `Value` is what gets sent, or what gets matched.

### Session control

| `Name` | Purpose |
| --- | --- |
| `RESET` | Sent first, to stop the device paginating. `terminal width 0${CRLF}terminal length 0` on IOS, `set length 0` on CatOS |
| `Disconnect` | Ends the session cleanly — `exit` |
| `Reboot` | `reload${CRLF}y${CRLF}y` — the confirmations are part of the value |
| `Version` | `show version` |

**`RESET` is the one that decides whether anything else works.** A device left paginating
returns `--More--` in the middle of a config, and NCM has no way to tell that from config text.

### Configuration mode

| `Name` | Purpose |
| --- | --- |
| `EnterConfigMode` | `config terminal` on IOS; **empty** on CatOS, which has no config mode |
| `ExitConfigMode` | `end` on IOS; empty on CatOS |
| `VirtualPrompt` | What the prompt looks like once in config mode |

An empty `Value` is meaningful rather than missing: CatOS genuinely has no configuration mode,
so the template declares both commands empty and the upload command below degrades gracefully.

### Privilege detection

This is the part the console does not explain well, and it is why two of the three samples
carry it:

| `Name` | Purpose | Sample values |
| --- | --- | --- |
| `EnableIdentifier` | **The substring that says the session is privileged.** NCM matches the prompt against it | `(enable)` on CatOS, `$` on the custom template |
| `EnableCommand` | What to send to become privileged | `enable` |
| `CustomUserNamePrompt` | Overrides the expected username prompt | `username prompt` |
| `CustomPasswordPrompt` | Overrides the expected password prompt | `password prompt` |
| `More` | The pagination prompt to answer | `\| more` |
| `MenuBased` | `True` for a device that presents a menu rather than a prompt | `False` |

**`EnableIdentifier` is prompt matching, not a command.** NCM sends nothing for it — it reads
the device's prompt and looks for that substring to decide whether it is already elevated. A
wrong value here produces the classic NCM failure where every command runs unprivileged and
the config comes back empty or truncated.

`MenuBased` is a **boolean carried in a `Command` element**, which is the format's one real
irregularity: the container is called `Commands` but not everything in it is one.

### Config transfer

| `Name` | Purpose |
| --- | --- |
| `Startup` / `Running` | The device's own words for the two config types. `startup`/`running` on IOS, both `config` on CatOS |
| `DownloadConfig` | Read a config over the session — `Show ${ConfigType}` |
| `UploadConfig` | Write one over the session |
| `DownloadConfigIndirect` | Read via a transfer server — `copy ${ConfigType} ${TransferProtocol}://…` |
| `UploadConfigIndirect` | Write via a transfer server |
| `DownloadConfigIndirectSCP` / `UploadConfigIndirectSCP` | The SCP variants, which need a username and password inline |
| `EraseConfig` | `write erase${CRLF}Y` |
| `SaveConfig` | `write memory` |

**`Startup` and `Running` are translations, not commands.** `${ConfigType}` in
`DownloadConfig` is substituted with whichever of the two applies, which is how one command
serves both. On CatOS both are `config`, because the device has one.

**Direct versus indirect is a real operational choice.** Direct reads the config through the
CLI session itself; indirect tells the device to `copy` it to a TFTP/FTP/SCP server that NCM
then reads. Indirect is what you need for devices whose `show` output is unreliable or
enormous, and it introduces a second thing that can fail — the transfer server.

## The macros

Values are templates, and `${…}` substitutions come from three places.

**Session and payload:**

| Macro | Substituted with |
| --- | --- |
| `${CRLF}` | A line break — how one `Value` sends several lines |
| `${ConfigType}` | The `Startup` or `Running` value |
| `${ConfigText}` | The config being uploaded |

**Transfer:**

| Macro | Substituted with |
| --- | --- |
| `${TransferProtocol}` | `tftp`, `ftp`, `scp` |
| `${StorageAddress}` | The transfer server's address |
| `${StorageFilename}` | The file on it |
| `${SCPStorageAddress}`, `${SCPServerUserName}`, `${SCPServerPassword}` | The SCP-specific set |

**Other commands in the same template.** This is the part worth noticing:

```xml
<Command Name="UploadConfig"
         Value="${EnterConfigMode}${CRLF}${ConfigText}${CRLF}${ExitConfigMode}" />
```

`${EnterConfigMode}` and `${ExitConfigMode}` are **the other `Command` entries by name**. So
the template is self-referencing, and one command composes from others. That is why the CatOS
template can leave both config-mode commands empty and still ship the same `UploadConfig`
value as IOS: the macros expand to nothing and the upload becomes a bare config paste.

**Whether any `Command` name can be used as a macro, or only a fixed subset, is not documented
and unverified here.** The samples only ever compose the two config-mode commands.

`${CRLF}` also appears in NCM's change templates and command scripts — see
[../webui/ncm-change-template-language.md](../webui/ncm-change-template-language.md), where its
availability inside a change template as opposed to a command script is a separate open
question. These files confirm it is standard in a *device* template.

## The three execution modes

The console offers three levels when running a script against a device, and they map onto
different verbs and different NCM roles:

| Console option | Verb | Minimum NCM role |
| --- | --- | --- |
| Execute scripts only | `Cirrus.ConfigArchive.ExecuteScript` | WebUploader |
| Execute scripts, then download the config | `ExecuteScript`, then `DownloadConfig` | WebDownloader for the download |
| Execute scripts, download, then upload | the above, then `UploadConfig` | WebUploader |

The distinction matters because **downloading after a script is what makes the change
auditable**. A script that changes a device without a following download leaves the archive
holding the pre-change config, so the next comparison reports a drift that has already been
applied deliberately.

`Cirrus.ConfigArchive` carries both a per-node and an on-nodes form of each:

```text
ExecuteScript(nodeId[], script, Reboot?)                 -> array
ExecuteScriptOnNodes(nodes[], deviceTemplateXML, script) -> array
DownloadConfig(...)                                       -> array
DownloadConfigOnNodes(nodes[], deviceTemplateXML, configType) -> array
UploadConfig(nodeId[], configType, ConfigText, RebootDevice)  -> array
```

**The `OnNodes` forms take `deviceTemplateXML` directly** — the whole document as a string,
which is exactly `Cli.DeviceTemplates.TemplateXml`. So you can run a script against a device
using a template that is *not* the one assigned to it, without changing any assignment. That is
the right tool for testing a template edit against one node before saving it, and the wrong one
to reach for casually: nothing records that the run used a different template.

The plain forms use the node's assigned template and stored credentials instead.

## Import and export through SWIS

**There is no `ImportTemplate` or `ExportTemplate` verb here.** Unlike API poller templates,
SAM templates and Log Analyzer rules, `Cli.DeviceTemplates` is a **plain CRUD entity** — the
document lives in a column and you read and write it like any other row.

```sql
SELECT t.ID, t.TemplateName, t.SystemOID, t.AutoDetectType, t.IsDefault, t.TemplateXml
FROM Cli.DeviceTemplates t
WHERE t.IsDefault = 'False'
ORDER BY t.TemplateName
```

That is the export. `WHERE IsDefault = 'False'` is the set worth backing up — the built-ins come
back with the product.

Creating one is a CRUD insert:

```powershell
$xml = Get-Content -Raw '.\Custom_device_commands1.3.6.1.4.1.9999.ConfigMgmtCommands'

$uri = New-SwisObject $swis -EntityType 'Cli.DeviceTemplates' -Properties @{
    TemplateName           = 'Custom device commands'
    SystemOID              = '1.3.6.1.4.1.9999'
    SystemDescriptionRegex = ''
    AutoDetectType         = 0          # 0 = system OID, 1 = system description
    UseForAutoDetect       = $true
    TemplateXml            = $xml
    Comments               = 'Imported from a lab server'
    Author                 = 'automation'
}
```

All four operations need `manageNodes`. **`IsDefault` templates are read-only** — the schema
says so directly: *"Indicates if the device template is built-in and managed by SolarWinds. If
it is, access is read-only."* Copy a built-in to a new row rather than trying to edit it.

Note the duplication: `TemplateName`, `SystemOID`, `SystemDescriptionRegex` and
`AutoDetectType` exist **both as columns and as attributes inside `TemplateXml`**. Which the
platform reads when they disagree is **not documented and unverified here** — set both to the
same values, and treat the columns as what auto-detection matches on.

### Assigning one to a node

```powershell
New-SwisObject $swis -EntityType 'Cli.DeviceTemplatesNodes' -Properties @{
    TemplateId = $templateId
    NodeId     = $nodeId
}
```

`Cli.DeviceTemplatesNodes` has exactly two columns, and its description carries two rules worth
repeating: **each node can have only one device template**, and **a manual assignment stops
auto-detection for that node**. `NodeId` is the primary key, which is the schema enforcing the
first rule.

So a script that assigns templates is also a script that silently opts nodes out of
auto-detection. Deleting the assignment row is what puts a node back under auto-detect.

## Writing one

Start from a shipped template for a device of the same family and edit it. The vocabulary of
`Name` values is fixed and undocumented, so inventing entries does nothing — an unrecognised
`Name` is not an error, it is simply never looked up.

The order of edits that works:

1. **`RESET` first.** Until pagination is off, nothing else is reliable.
2. **`EnableIdentifier` second.** Log into the device by hand and copy the exact substring your
   privileged prompt contains.
3. **`Startup` and `Running`** to whatever the device calls its two configs.
4. **`DownloadConfig`**, then test with `DownloadConfigOnNodes` passing the edited XML.
5. Only then the upload and erase commands, which change the device.

Test with the `OnNodes` verbs before saving the template, so a bad edit affects one node rather
than every device matching the OID.

**Two ways to make a template that appears to work and does not:**

- **A wrong `EnableIdentifier`** leaves every session unprivileged. Commands run, output comes
  back, and the config is short.
- **A missing `More`** on a device that paginates puts `--More--` into the archived config,
  where it will show up as drift on every subsequent comparison.

## What this repository has not verified

| Claim | Why | How to settle it |
| --- | --- | --- |
| The complete `Command` `Name` vocabulary | The three samples use 23 between them; the product certainly knows more | Compare the shipped templates on your own server: `SELECT TemplateXml FROM Cli.DeviceTemplates WHERE IsDefault = 'True'` |
| The `AutoDetectType` string for system-description matching | Only `BySystemOid` appears | Build a description-matched template in the console and export it |
| That the longest `SystemOID` prefix wins | Two shipped templates overlap (`1.3.6.1.4.1.9` and `1.3.6.1.4.1.9.5.50`) and specificity is the obvious rule | Assign neither manually and check which a Catalyst 6500 auto-detects |
| Whether any command name can be used as a `${…}` macro | Only the two config-mode commands are composed in the samples | Reference another command from a value in a test template |
| Which wins when the columns and the XML attributes disagree | Both hold `TemplateName`, `SystemOID`, `SystemDescriptionRegex` and `AutoDetectType` | Write a row whose column and attribute differ, then check what auto-detect matches |

## See also

- [ncm.md](ncm.md) — NCM's entities, the config archive, connection profiles and the approval
  queue
- [../webui/ncm-change-templates.md](../webui/ncm-change-templates.md) — change templates, which
  are a different artefact: what to send, rather than how to talk to the device
- [../webui/ncm-change-template-language.md](../webui/ncm-change-template-language.md) — the
  change template scripting language, including `${CRLF}`
- [../automation/credentials.md](../automation/credentials.md) — the credentials a CLI session
  authenticates with
