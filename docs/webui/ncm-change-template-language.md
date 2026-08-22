# The change template language

The scripting language inside an NCM config change template is small, specific to NCM, and
documented in fragments across SolarWinds' product guide and a handful of THWACK posts. This
page collects it.

**None of this is in the SWIS schema and none of it can be verified by this repository.**
Every construct below is reported from SolarWinds' documentation or from community material,
with the source named. What *is* checked is the entity and property names the examples
navigate, which are ordinary `NCM.` entities — see
[ncm-change-templates.md](ncm-change-templates.md#the-parameter-types-are-swis-entities).

## What language is this?

It reads like something you have seen before, and that is not an accident, but it is not any
existing language. The contract offers no help: `Cirrus.ConfigSnippets.AdvancedScript` is a
plain `System.String` and nothing in the schema names a parser, a grammar or a language
version. So what follows is a **syntactic comparison against the documented material only**,
not a claim about how SolarWinds implemented it.

The short answer: **a bespoke DSL, assembled from four recognisable conventions.** Nothing
matches it end to end, and every individual feature has a clear ancestor.

| Feature | In a template | Closest existing form | Verdict |
| --- | --- | --- | --- |
| Blocks and comments | `{ }`, `//`, `/* */` | C family | C-family |
| Loop | `foreach (@x in @y)` | C# `foreach (var x in y)` | C# |
| Declaration | `string @x = 'y'` | C#, Java, C | Type-first, C-family |
| Array parameter | `NCM.Interfaces[] @p` | C#, Java | Suffix `[]`, C-family |
| Variable sigil | `@name` | **T-SQL** `DECLARE @name` | T-SQL |
| String literal | `'single quotes'` | **T-SQL**, SQL | SQL, not C# |
| Concatenation | `+` | T-SQL and C# both | Either |
| Built-in functions | `SubString`, `IndexOf` | **.NET `String`** methods | .NET, as free functions |
| Word operators | `contains`, `startsWith`, `endsWith` | .NET `String` methods, used infix | Bespoke as operators |
| Case-sensitive variants | `containsExact` | Nothing standard | Bespoke |
| Doc block | `.PARAMETER_LABEL @x` in a comment | **PowerShell comment-based help** | PowerShell |
| Macro | `${StorageAddress}` | Shell, Java properties, Velocity, MSBuild | Generic |
| Member access | `@node.Vendor` | Universal | Resolves against SWIS entities |
| Device block | `CLI { }` | Nothing standard | Bespoke |

### The four ancestors

**C# supplies the body.** `foreach (@x in @y)` is the giveaway: Java writes
`for (X x : list)`, JavaScript writes `for (x of list)`, VB writes `For Each x In y`, and
Velocity writes `#foreach($x in $list)` with no braces. Only the C# form combines `foreach`,
the keyword `in`, and braces. Type-first declarations and the `[]` array suffix point the same
way.

**T-SQL supplies the variables and the strings.** `@name` as a variable sigil is T-SQL's
`DECLARE @foo`, not C#. Perl uses `@` too, but only for arrays, and `@ContextNode` is not an
array. Single-quoted string literals are SQL rather than C#, which uses double quotes. So the
sigil and the quoting come from the database side of the house.

**.NET supplies the function library.** `SubString(string str, int startIndex, int length)` is
`String.Substring(int startIndex, int length)` with the receiver moved into the first
argument, and `IndexOf(string str, string search)` is `String.IndexOf(string value)` the same
way. Even the way SolarWinds documents them — return type first, typed parameters — is C#
signature notation. `contains`, `startsWith` and `endsWith` are `String.Contains`,
`String.StartsWith` and `String.EndsWith` promoted to infix operators.

**PowerShell supplies the documentation block.** This is the least obvious and the most
exact. PowerShell's comment-based help is a block comment containing dotted keywords:

```text
<#
.SYNOPSIS
.DESCRIPTION
.PARAMETER Name
#>
```

A change template writes `.CHANGE_TEMPLATE_DESCRIPTION` and `.PARAMETER_LABEL @ContextNode`
inside `/* */`. Same idea, same shape, same trick of parsing a comment — including a directive
that takes a parameter name as its argument.

**Why that mixture?** It is what you would predict from the vendor. Orion is a .NET product on
SQL Server, and its verb payload types are .NET namespaces like
`SolarWinds.NCM.Contracts.InformationService.ConfigSnippet`. Engineers writing C# and T-SQL
all day, designing a small language for network administrators, reached for the conventions
already in their hands.

### If you know C#, what does not transfer

This is the practical half of the comparison. The body looks enough like C# that the
differences are the things that will catch you.

| C# habit | In a template |
| --- | --- |
| `"double quotes"` | Single quotes only |
| `else if` | Unverified; every example nests instead |
| `;` terminators | Not used |
| `var` | No inference; write the type |
| `str.Length`, `str.Substring(..)` | `StrLength(@str)`, `SubString(@str, ..)` — free functions, not methods |
| `str.Contains(x)` is **case-sensitive** | `contains` is **case-insensitive**; `containsExact` is the sensitive one |
| `&&`, `\|\|`, `!` | **Not documented at all** — see below |
| `for`, `while`, `do` | Only `foreach` is documented |
| `return`, methods, `try`/`catch` | None documented |
| Arithmetic on numbers | Only `+` on strings is documented |

The case-sensitivity inversion in the middle of that table is the one most likely to produce a
template that works in testing and misfires later. In .NET, `Contains` is ordinal and
case-sensitive; here the bare word is the insensitive form and you opt *in* to sensitivity
with `Exact`.

**Boolean combinators are the notable gap.** No SolarWinds material and no community example
this repository has seen shows two conditions combined in one `if`. Whether `&&`, `and`, `AND`
or anything else works is **unverified here**. The documented way to express a conjunction is
a nested `if`, and that is what the examples do. Test before relying on anything shorter.

### What it is not

Ruled out by direct comparison, in case any of these were your first guess:

- **Not PowerShell.** Variables would be `$name`, the block comment `<# #>`, operators
  `-contains` and `-eq`.
- **Not Perl.** `@` marks an array there, and `@ContextNode` is not one.
- **Not T-SQL**, despite the sigil and quotes. T-SQL has no braces, no `foreach`, and requires
  `DECLARE`/`SET`.
- **Not Velocity, Jinja or a template engine of that family.** Those use directive prefixes
  (`#foreach`, `{% for %}`) rather than braces, and have no type declarations.
- **Not Tcl**, which Cisco EEM uses and which a network engineer might reasonably expect.
- **Not JavaScript.** No `var`/`let`, no `for...of`, and types on parameters.

The one construct with no ancestor at all is `CLI { }`: a block whose contents leave the
language entirely and become device command text, with variable substitution on the way out.
The nearest analogues are inline assembly in C or a heredoc in a shell — a region where the
host language stops interpreting and starts emitting.

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

`int` is the other scalar type SolarWinds documents, alongside `string` and a SWIS entity.
What operations `int` supports is **not documented and is unverified here** — no source this
repository has seen performs arithmetic in a template, and the only operator shown on any
value is `+` joining strings.

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

**`if` and `else`.** Whether a chained `else if` works is where two SolarWinds sources read
differently, so treat it as **unverified**. The community walkthrough states flatly that "else
works, if else not supported"; SolarWinds' own introduction lists the supported statements as
"If, If Else, and Foreach", which most naturally means `if` and `if`-with-`else` rather than a
chain. Nothing in either source shows a chain being used.

Every shipped and community example expresses a multi-way decision as nested `if`/`else`, so
that is the form this page uses and the safe one to write.

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
normally begins by looping over it. SolarWinds' own shipped "Change Cisco Enable Password"
template does exactly this — `foreach (@Node in @ContextNode)` against a parameter declared
`NCM.Nodes` — so the form is theirs, not a community workaround.

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

Sources for this page: SolarWinds' introduction of the feature in NCM 6.0,
[NCM Config Change Templates](http://thwack.solarwinds.com/blogs/orion-product-team-blog/archive/2010/11/30/ncm-config-change-templates/)
(2010-11-30), which is where the parameter-pair requirement, the `int`/`string`/`swis.entity`
types and the shipped enable-password template come from; SolarWinds' *Understanding Config
Change Template Semantics* help topic, which both blog posts point at for the full grammar;
and
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

**The empty `if` branch is deliberate, and it is SolarWinds' own idiom.** Their shipped
"Change Cisco Enable Password" template guards a password containing a space exactly this way:

```text
if (@NewPassword contains ' ')
{}
else
{
  foreach (@Node in @ContextNode)
```

The guard has nothing to do in the failing case — the point is to skip the change — and with
no chained `else if` to fall through to, an empty `if` with the work in the `else` is what the
language leaves you. It reads oddly and it is correct.

## Gotchas

**`else if` is unverified.** Two SolarWinds sources read differently and no example uses a
chain. Nest instead.

**The bare comparison operators are case-insensitive.** `contains`, `startsWith` and
`endsWith` ignore case; the `Exact` forms do not.

**A variable not in the signature is not a question.** It is undefined, and the template runs
with it empty.

**`|` and `@` inside a CLI block break the parser.** Put them in a string variable.

**`${}` and `@` are different things.** A macro is NCM configuration; a variable is yours.
Quoting a macro is correct and necessary.

**Every template needs a node parameter.** `NCM.Nodes @ContextNode` is not optional.

**Read the Preview step.** The console's run wizard resolves every variable, evaluates the
conditionals, walks the loops and shows the exact command text per device before sending
anything, and the editor has a Validate button beside Submit. Both are worth using: a template
that branches on vendor or a custom property produces different output per device, so expand
the one you are least sure about rather than the first in the list. See
[ncm-change-templates.md](ncm-change-templates.md#running-one-and-the-preview-that-makes-it-safe).

**The API gets neither.** Nothing in `Cirrus.ConfigSnippets` exposes a preview or a validate
verb, so a template driven entirely through the API has no dry run at all.
`Cirrus.Nodes.ParseMacros` previews macro expansion and nothing else.

## See also

- [ncm-change-templates.md](ncm-change-templates.md) — what a template is, its directives, and
  managing them through `Cirrus.ConfigSnippets`
- [../modules/ncm.md](../modules/ncm.md) — the NCM module and `Cirrus.Nodes.ParseMacros`
- [../automation/custom-properties.md](../automation/custom-properties.md) — defining the
  properties a template reads
- [README.md](README.md) — the rest of this section
