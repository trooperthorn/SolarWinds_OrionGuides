# The change template language

The scripting language inside an NCM config change template is small, specific to NCM, and
documented in fragments across SolarWinds' product guide and a handful of THWACK posts. This
page collects it.

**None of this is in the SWIS schema and none of it can be verified by this repository.**
Every construct below is reported from SolarWinds' documentation or from community material,
with the source named. What *is* checked is the entity and property names the examples
navigate, which are ordinary `NCM.` entities — see
[ncm-change-templates.md](ncm-change-templates.md#the-parameter-types-are-swis-entities).

## Two kinds of variable, and they are not interchangeable

This is the first thing to get straight, because the two look similar and behave nothing alike.

| Form | What it is | Resolved by |
| --- | --- | --- |
| `@Name` | A script variable: a parameter, a loop item, or a local you declared | The template engine, at run time |
| `${Name}` | A macro: a setting from NCM's own configuration | NCM, substituted into the command text |

`@` variables are yours. `${}` macros are the platform's, and the documented set is small:

| Macro | Value | Configured in |
| --- | --- | --- |
| `${CRLF}` | Carriage return | — |
| `${StorageAddress}` | TFTP server IP | NCM Settings → TFTP Server |
| `${SCPStorageAddress}` | SCP server IP | NCM Settings → SCP Server |
| `${SCPServerUserName}` | SCP username | NCM Settings → SCP Server |
| `${SCPServerPassword}` | SCP password | NCM Settings → SCP Server |

Whether `${CRLF}` works inside a change template as opposed to a command script is
**unverified**; the community source that lists it flags the same doubt. The full macro list
lives in the NCM Administrator Guide, and `Cirrus.Nodes.ParseMacros(nodeId, macro)` expands one
against a real node, which is the way to find out what a macro produces before you rely on it.
See [../modules/ncm.md](../modules/ncm.md).

The reason to prefer a macro over a literal is that it survives a change of address:

```text
script BaseChangeTemplate(NCM.Nodes @ContextNode)
{
  string @myTFTPImage = '${StorageAddress}' + '/image.bin'
  CLI
  {
    copy tftp://@myTFTPImage flash
  }
}
```

The macro goes inside single quotes, so it is a string literal as far as the script is
concerned, and NCM substitutes it when the command is sent. Move the TFTP server and the
template does not change.

## Declaring and assigning

```text
string @CommandLine = 'copy ftp://' + @User + ':' + @Password + '@' + @FTPServerIP
```

`string` is the type. `+` concatenates. Reassignment does not repeat the type:

```text
string @myip = '10.10.'
@myip = @myip + @ContextNode.AssetTag
@myip = @myip + '.32'
```

**Use single quotes around every string value.** That is SolarWinds' own instruction and it
applies to comparisons as much as assignments.

A loop variable is declared implicitly by being used:

```text
foreach (@portItem in @TargetPorts)
```

`@portItem` was never declared. Its first use is its declaration.

## Operators

Use any of these in a parenthesised condition:

| Operator | Meaning |
| --- | --- |
| `==` | Is equal to |
| `!=` | Is not equal to |
| `>` | Is greater than |
| `>=` | Is greater than or equal to |
| `<` | Is less than |
| `<=` | Is less than or equal to |
| `contains` | Substring, case-insensitive |
| `containsExact` | Substring, case-sensitive |
| `startsWith` | Prefix, case-insensitive |
| `startsWithExact` | Prefix, case-sensitive |
| `endsWith` | Suffix, case-insensitive |
| `endsWithExact` | Suffix, case-sensitive |

The `Exact` suffix is the case-sensitive form in every case, and the bare form is
case-insensitive. That is the opposite default from most languages, and it is worth being
deliberate about: `contains 'gigabit'` matching `GigabitEthernet0/1` is usually what you want
and occasionally exactly what you do not.

```text
if (@ITF.Name == 'FastEthernet0/1')
```

## String functions

| Function | Returns |
| --- | --- |
| `SubString(string str, int startIndex, int length)` | The substring starting at `startIndex`, of `length` characters |
| `StrLength(string str)` | The length of the string |
| `IndexOf(string str, string search)` | The index of the first occurrence of `search` in `str` |
| `GetOctet(string ipAddress, int octetPosition)` | One octet of an IP address |
| `SetOctet(string ipAddr, int octetPosition, string octet)` | The address with that octet replaced |

`GetOctet` and `SetOctet` exist because manipulating addresses by hand with `SubString` and
`IndexOf` is where ACL templates go wrong. Whether `octetPosition` counts from 0 or from 1 is
**not stated in the source and is unverified here** — test it before shipping a template that
rewrites addresses.

These were added for ACL manipulation and announced on the SolarWinds product blog:
[Better support for ACL manipulation in NCM](http://thwack.solarwinds.com/community/solarwinds-community/product-blog/blog/2012/09/13/better-support-for-acl-manipulation-in-ncm).

## Control flow

**`if` and `else`, but no `else if`.** That is the constraint that shapes most templates: a
three-way decision is nested `if`/`else`, not a chain.

```text
if (@IOS_FILENAME contains ' ')
{
}
else
{
}
```

**`foreach` iterates a collection**, which is either an array parameter or a navigation
property:

```text
foreach (@node in @ContextNode)
{
  if (@node.Vendor == 'Cisco')
  {
    CLI
    {
      dir flash:
    }
  }
}
```

Note that `@ContextNode` is iterated even though it was declared `NCM.Nodes` rather than
`NCM.Nodes[]`. The node parameter is a selection of devices, so the body of a template
normally begins by looping over it. Whether a template can rely on that when exactly one
device is selected is **unverified here**.

Loops nest, and nesting them across navigation properties is how a template reaches inventory
data. This runs a command against whichever interface holds a given address:

```text
script BaseChangeTemplate(NCM.Nodes @ContextNode)
{
    foreach (@interfaceItem in @ContextNode.Interfaces)
    {
        foreach (@ip in @interfaceItem.IpAddresses)
        {
            if (@ip.IPAddress contains '10.199.2.1')
            {
                CLI
                {
                    logging source-interface @interfaceItem.InterfaceDescription
                }
            }
        }
    }
}
```

Every hop in that example is a real relationship: `NCM.Nodes` hosts `NCM.Interfaces` through
`Interfaces`, `NCM.Interfaces` hosts `NCM.IpAddresses` through `IpAddresses`, and `IPAddress`
is a property of the latter. Confirm any navigation you are unsure of:

```bash
python3 tools/schema_query.py show NCM.Interfaces
```

## CLI blocks

A `CLI { ... }` block is what actually reaches the device. Everything inside is sent as
command text, with `@` variables substituted first.

```text
CLI
{
  configure terminal
  no access-list 112
  access-list 112 permit tcp @myip 0.0.0.31 host 123.234.123.234 eq 445
}
```

Lines are not quoted and not escaped. That has one important consequence.

### Special characters need a variable

A pipe breaks the script, because the parser sees it before the device does:

```text
show clock | append disk0:show_tech
```

The way around it is to put the character in a string and substitute it back:

```text
script BaseChangeTemplate(NCM.Nodes @ContextNode)
{
  string @PipeSymbol = '|'
  CLI
  {
    show clock @PipeSymbol append disk0:show_tech
  }
}
```

The same trick works for `@` itself, which otherwise starts a variable name. That is why an
FTP URL with credentials is built as a string rather than written inline:

```text
string @CommandLine = 'copy ftp://' + @User + ':' + @Password + '@' + @FTPServerIP
```

The `'@'` in the middle is a literal at-sign, quoted so the parser does not read `@FTPServerIP`
as attached to it.

Which characters need this treatment beyond `|` and `@` is **not documented and is unverified
here**. The safe reading is that any character with meaning to the template parser does.

## Custom properties

Custom properties are attached to nodes, so a template reads them through the node parameter,
by name, with no declaration:

```text
script BaseChangeTemplate (NCM.Nodes @ContextNode)
{
  CLI
  {
    show @ContextNode.MyCustomProperty
  }
}
```

That is the mechanism behind most device-independent templates: put the per-device value in a
custom property, and the template stops needing to know about the device.

```text
script ChangeAccessList (NCM.Nodes @ContextNode)
{
  string @myip = '10.10.'
  @myip = @myip + @ContextNode.AssetTag
  @myip = @myip + '.32'
  CLI
  {
    configure terminal
    no access-list 112
    access-list 112 remark This is a test
    access-list 112 permit tcp @myip 0.0.0.31 host 123.234.123.234 eq 445
  }
}
```

Two cautions the source does not give. A custom property that is empty on a node produces an
empty string in the middle of a command rather than an error, so `access-list 112 permit tcp
10.10..32` is what gets sent — check the property is populated before iterating. And custom
property names are the column names on the custom property entity, so confirm the spelling
rather than trusting the console label:

```sql
SELECT
    cp.Field,
    cp.DataType,
    cp.MaxLength,
    cp.Description
FROM Orion.CustomProperty cp
WHERE cp.TargetEntity = 'Orion.NodesCustomProperties'
ORDER BY cp.Field
```

`Field` is the column name, which is the name a template uses. `Orion.CustomProperty` has no
`Name` property — the human-facing label is `DisplayName` and the two need not match.

See [../automation/custom-properties.md](../automation/custom-properties.md).

Source:
[More automation in NCM: usage of variables and custom properties](http://thwack.solarwinds.com/community/solarwinds-community/product-blog/blog/2012/05/23/more-automation-in-ncm-usage-of-variables-and-custom-properties-in-command-scripts-and-config-change-templates).

## A worked template

Putting the pieces together. This uploads an image from FTP to every selected Cisco device,
asking the user for the server address and the filename:

```text
/*
.CHANGE_TEMPLATE_DESCRIPTION
    Copy an IOS image from an FTP server to flash.

.CHANGE_TEMPLATE_TAGS
    IOS, upgrade, cisco

.PLATFORM_DESCRIPTION
Cisco IOS

.PARAMETER_LABEL @ContextNode
    Devices
.PARAMETER_DESCRIPTION @ContextNode
    Select the devices to copy the image to.

.PARAMETER_LABEL @FTPServerIP
    FTP server
.PARAMETER_LABEL @IOS_FILENAME
    Image filename
*/

script UpgradeIOS (
    NCM.Nodes @ContextNode,
    string @FTPServerIP,
    string @User,
    string @Password,
    string @IOS_FILENAME
)
{
  if (@IOS_FILENAME contains ' ')
  {
  }
  else
  {
    string @CommandLine = 'copy ftp://' + @User + ':' + @Password + '@' + @FTPServerIP + '/' + @IOS_FILENAME + ' flash:' + @IOS_FILENAME
    foreach (@node in @ContextNode)
    {
      if (@node.Vendor == 'Cisco')
      {
        CLI
        {
          @CommandLine
          dir flash:@IOS_FILENAME
        }
      }
    }
  }
}
```

Two things about it are worth stating, because the version of this template that circulates
gets both wrong.

**`@User`, `@Password` and `@IOS_FILENAME` are in the signature.** In the widely-copied
version they are used in `@CommandLine` but never declared, so the user is never asked for
them and the command is assembled from nothing. If a variable is not a parameter, it is not a
question.

**The empty `if` branch is deliberate.** The filename check has nothing to do when the name
contains a space — the point is to skip the copy — and since there is no `else if`, the guard
has to be written as an empty `if` with the work in the `else`. It reads oddly and it is the
idiom the language leaves you.

## Gotchas

**No `else if`.** Nest, or restructure.

**The bare comparison operators are case-insensitive.** `contains`, `startsWith` and
`endsWith` ignore case; the `Exact` forms do not.

**A variable not in the signature is not a question.** It is undefined, and the template runs
with it empty.

**`|` and `@` inside a CLI block break the parser.** Put them in a string variable.

**`${}` and `@` are different things.** A macro is NCM configuration; a variable is yours.
Quoting a macro is correct and necessary.

**Every template needs a node parameter.** `NCM.Nodes @ContextNode` is not optional.

**Test against one device.** The console sends CLI to every selected device, and a template is
source code that nothing type-checks. `Cirrus.Nodes.ParseMacros` previews macro expansion; for
the rest there is no dry run.

## See also

- [ncm-change-templates.md](ncm-change-templates.md) — what a template is, its directives, and
  managing them through `Cirrus.ConfigSnippets`
- [../modules/ncm.md](../modules/ncm.md) — the NCM module and `Cirrus.Nodes.ParseMacros`
- [../automation/custom-properties.md](../automation/custom-properties.md) — defining the
  properties a template reads
- [README.md](README.md) — the rest of this section
