# Scripts

Working examples for querying and automating SolarWinds Orion / Observability
Self-Hosted, in the four forms people actually use.

| Directory | Contents |
| --- | --- |
| [swql/](swql/) | 188 verified sample queries, grouped by subject |
| [powershell/](powershell/) | `SwisPowerShell` module examples |
| [python/](python/) | A dependency-light REST client and CLI |
| [curl/](curl/) | The raw wire protocol, with nothing in between |

Every SWQL statement in `swql/` is checked against the extracted schema on each build, so
the entity, property and navigation names in them are known to exist. See
[swql/README.md](swql/README.md).

## Choosing a client

They are not equivalent, and picking the wrong one costs an afternoon.

**PowerShell (`SwisPowerShell`)** is the richest client and the one SolarWinds' own
samples use. It speaks the SOAP endpoint on port 17777, supports Windows and certificate
authentication as well as local Orion accounts, and wraps CRUD and Invoke in cmdlets
(`Get-SwisData`, `New-SwisObject`, `Set-SwisObject`, `Invoke-SwisVerb`). If you are on
Windows and automating changes, start here.

```powershell
Install-Module -Name SwisPowerShell -Scope CurrentUser
$swis = Connect-Swis -Hostname orion.example.com -Trusted
Get-SwisData $swis "SELECT TOP 5 Caption, IPAddress FROM Orion.Nodes"
```

**Python (`orionsdk`)** is the official cross-platform client and the right choice for
integrations that run somewhere other than Windows. It speaks REST on port 17774.

```bash
pip install orionsdk
```

```python
from orionsdk import SwisClient
swis = SwisClient("orion.example.com", "admin", password)
print(swis.query("SELECT TOP 5 Caption, IPAddress FROM Orion.Nodes"))
```

**curl** is not a production client, but it is the fastest way to prove where a problem
lives. Every other client is a wrapper around the same handful of REST calls, so if curl
works and your code does not, the problem is in your code.

The file in [python/](python/) implements the REST contract directly with nothing but the
standard library. It exists because the contract is small enough to read in full, and
seeing it makes the wrapped clients easier to reason about. For production, prefer
`orionsdk`.

## Before you run anything that writes

The query interface cannot change anything, so reading is safe. Writing is not, and a
script that unmanages the wrong set of nodes will suppress the alerts you needed.

- Run the `SELECT` first. Confirm the exact set you are about to act on.
- Use `-WhatIf` where the script supports it. The PowerShell examples here do.
- Start with one object, verify the result, then widen the scope.
- Prefer a bounded window. `Unmanage` takes an explicit end time; use it rather than
  relying on remembering to remanage.

## Credentials

None of these scripts hard-code a password, and none should. They read from a prompt or
from an environment variable, and the curl examples deliberately require the password to
be exported rather than passed inline, where it would land in shell history and in the
process table.

Give an integration its own Orion account with the narrowest role and limitation set that
still does the job. Account limitations apply to everything read through SWIS, which is
both a safety feature and a common source of "the query returns nothing" confusion.

## TLS

SWIS ships with a self-signed certificate, so a first connection usually fails
verification. The fix is to trust it, not to switch verification off:

```bash
openssl s_client -connect orion.example.com:17774 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > orion-ca.pem
export SWIS_CACERT=orion-ca.pem
```

Both the curl and Python examples accept a CA file. They also accept an insecure flag,
which is acceptable in a lab and nowhere else: it lets anything on the network path read
the credentials being sent.

## Adding a script

Validate any SWQL you add, then follow the conventions in
[../CONTRIBUTING.md](../CONTRIBUTING.md):

```bash
python3 ../tools/validate_swql.py your-file.swql
```
