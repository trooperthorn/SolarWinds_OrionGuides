# SAM application templates

Importable `.apmtemplate` files for Server and Application Monitor.

| File | Demonstrates |
| --- | --- |
| [citrix-hypervisor-monitoring.apmtemplate](citrix-hypervisor-monitoring.apmtemplate) | Six `LinuxScript`/`TcpPort` components polling a Citrix Hypervisor host over SSH with the `xe` CLI, no AppInsight module required |

The format is documented in
[../../docs/modules/sam-templates.md](../../docs/modules/sam-templates.md), and the module it
belongs to in [../../docs/modules/sam.md](../../docs/modules/sam.md).

## Citrix Hypervisor (XenServer) monitoring

SAM ships no AppInsight for Citrix Hypervisor, so this template gets host status and
performance metrics the way SAM gets anything from a platform it has no purpose-built monitor
for: SSH to the host and read the CLI that ships on it. Citrix Hypervisor's dom0 always carries
`xe`, so no agent or extra package is required on the target.

Full setup, the exact `xe` commands each component runs, required rights, and what is
inferred rather than verified against a real import, are in
[../../docs/modules/sam-citrix-hypervisor-template.md](../../docs/modules/sam-citrix-hypervisor-template.md).
Read it before assigning this template, and test it with `StartTestComponents`
([../../docs/modules/sam-templates.md#test-before-you-assign](../../docs/modules/sam-templates.md#test-before-you-assign))
before rolling it out beyond one host.

## Editing one of these

The two safe edits documented in `sam-templates.md` apply here: a component's `ScriptBody`
(plain text, `<` and `&` XML-escaped) and threshold levels. Regenerate the `UniqueId` GUIDs if
you fork a copy for your own environment, since that value is the template's identity across
servers and across SAM's own dedupe logic.
