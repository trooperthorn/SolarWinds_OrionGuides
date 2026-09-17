# Vendor-shipped API Poller templates

Three `.apipoller.template` files from SolarWinds' own published template library, kept
**unmodified** as reference material for
[../../../docs/polling/api-poller-vendor-templates.md](../../../docs/polling/api-poller-vendor-templates.md).

| File | Guid | Shows |
| --- | --- | --- |
| [microsoft-azure-virtual-machine.apipoller.template](microsoft-azure-virtual-machine.apipoller.template) | `65cad739-146c-43f2-b0d0-ad62806af524` | Nine metrics from **one** request, addressed by array index; OAuth 2.0 Azure credentials; `${SUBSCRIPTION_ID}`, `${USERGROUP_ID}` and `${VM_NAME}` assign-time parameters |
| [servicenow.apipoller.template](servicenow.apipoller.template) | `852e512a-bce6-457d-a19e-a168ffa27f4d` | Eight separate requests; `Type=Header`, reading a count out of `X-Total-Count` with a JSONPath filter rather than out of the body |
| [microsoft-365-exchange-mailboxes.apipoller.template](microsoft-365-exchange-mailboxes.apipoller.template) | `f300fa71-ef7e-4d13-8ffe-b27949fdafa7` | `Type=ArrayCount`, counting array elements; a `Key` element with no schema counterpart; `<Body>` omitted entirely |

Two things were changed and nothing else: the filenames, to lower case with hyphens, and the
line endings, which this repository stores as LF. The XML is the vendor's, element for element
and character for character, including the `${NAME}` placeholders and the prose in each
`Description`.

## These are not validated by `make check`

`tools/check_api_poller_templates.py` globs `scripts/api-pollers/*.apipoller.template`,
non-recursively, so this directory is outside the build gate by construction. That is
deliberate: these files are evidence, and editing one to satisfy a check would destroy what
makes it worth keeping.

Run the checker against them on purpose and it reports the omitted `<Body>` in the Microsoft 365
template, which is a real difference from the format the guides document:

```bash
python3 tools/check_api_poller_templates.py scripts/api-pollers/vendor-examples/*.apipoller.template
```

The Azure and ServiceNow files pass unchanged.

[../example-service-status.apipoller.template](../example-service-status.apipoller.template) is
the maintained, validated, importable sample. Start there if you want a template to copy.

## These are templates, not pollers

Every `ValueToMonitor` in all three carries `xsi:nil="true"` thresholds, and `PollingInterval`
is nil as well, even where the `Description` states an interval in prose. A template is meant
to be assigned across many targets whose baselines differ, so the operator supplies the numbers.
**Imported as-is, none of these alerts on anything.**

Each one's `Description` also lists its prerequisites, and they are not optional: an OAuth 2.0
credential with the right scope, a Microsoft Graph permission, or a ServiceNow Performance
Analytics subscription. Read it before assigning.

## Provenance

Published by SolarWinds for public download and covered by
[../../../CONTRIBUTING.md](../../../CONTRIBUTING.md)'s rule on material SolarWinds publishes.
They contain no credentials, no keys and no hostname from any real installation: every
instance-specific value in them is a `${NAME}` placeholder supplied when the template is
assigned.
