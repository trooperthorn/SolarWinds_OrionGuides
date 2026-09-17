# API Poller templates

Importable `.apipoller.template` files for the SolarWinds Platform API Poller.

| File | Demonstrates |
| --- | --- |
| [example-service-status.apipoller.template](example-service-status.apipoller.template) | A numeric metric and a text status mapped to numbers, in one two-metric template |
| [citrix-hypervisor-xenapi.apipoller.template](citrix-hypervisor-xenapi.apipoller.template) | **Experimental.** A three-request chain (login, then two dependent calls) against Citrix Hypervisor's XenAPI. The variable-substitution syntax between requests is inferred, not confirmed — read the caveats before importing |

The format is documented in
[../../docs/polling/api-pollers.md](../../docs/polling/api-pollers.md#the-apipollertemplate-file-format),
along with the six Invoke verbs that import, export and assign these.

## The sample

Two `ValueToMonitor` entries against one request, chosen to show both ways a value reaches a
status:

- **Queue Depth** — a value that is already numeric, thresholded directly. No string rules
  needed.
- **Service State** — a text value (`operational`, `degraded`, `maintenance`, `outage`) mapped
  to numbers, because **the platform evaluates status on numbers only**. The mapping is what
  makes a word-answering API monitorable at all. Unmatched values fall back to `5`.

`DisplayName` is the caption an operator reads. It describes the metric rather than the raw
value at `Path`, which nobody sees.

**The fallback is the part to copy.** It sits above the critical threshold of `2`, so a status
string none of the four rules recognise reads as critical rather than healthy. If the provider
renames a state, you hear about it. A fallback of `0` would silently classify the new string as
normal and turn the alert off exactly when something changed — which is why
`tools/check_api_poller_templates.py` reports that arrangement.

The URL is `api.example.invalid`, which does not resolve. **Replace the URL, the two JSONPath
expressions and the state vocabulary before importing.** Regenerate the `Guid` too — it is the
template's identity across servers.

## Importing it

```powershell
$xml = Get-Content -Raw '.\example-service-status.apipoller.template'
$templateId = Invoke-SwisVerb $swis 'Orion.APIPoller.Templates' 'ImportTemplate' @($xml)
```

Then assign it to a node with `AssignTemplate`, supplying any credential, proxy, SSL and
timeout settings through the `configuration` and `parameters` arrays — **the export carries
none of those**. See
[../../docs/polling/api-pollers.md](../../docs/polling/api-pollers.md#the-verbs).

## Checking a template before you import it

```bash
python3 tools/check_api_poller_templates.py scripts/api-pollers/example-service-status.apipoller.template
```

It works on any template file, not only the ones here — point it at an export from your own
server to check its structure and to be told about a fallback that hides unknown values.

## Multi-request templates

`citrix-hypervisor-xenapi.apipoller.template` is the one file here with more than one
`RequestDetails`. It exists to demonstrate the login-then-call chain a session-based API
demands, and it comes with an explicit warning attached: the syntax it uses to carry a
`RequestVariable` from the login response into a later request's `Body` is inferred from the
feature's stated purpose, not read off a real export, because no such export exists in this
repository yet. See
[../../docs/modules/sam-citrix-hypervisor-template.md#the-api-poller-alternative](../../docs/modules/sam-citrix-hypervisor-template.md#the-api-poller-alternative)
for how to confirm the real syntax on your own server before relying on this shape, and for why
the SAM template in [../sam-templates/](../sam-templates/) is the better-tested route to the
same metrics.

## Sanitisation

These files contain no hostnames, credentials, API keys or data from a real installation.
Anything contributed here must be the same — see [../../CONTRIBUTING.md](../../CONTRIBUTING.md).
An exported template does **not** contain credentials, but it does contain every URL, header
name and header value the poller sends, so read one before sharing it.
