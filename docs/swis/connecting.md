# Connecting to SWIS

Before you can query or change anything, you need to reach the SolarWinds Information
Service and authenticate. This page covers which port and endpoint to use, which
authentication modes exist, and how to open a connection from PowerShell, Python and curl.

Grounded in the official
[Connecting to SWIS](https://solarwinds.github.io/OrionSDK/docs/connecting-to-swis/) and
[REST](https://solarwinds.github.io/OrionSDK/docs/rest/) pages.

## Endpoints and ports

There are two transports into SWIS, and they listen on different ports.

| Port | Protocol | Status | Used by |
|:---|:---|:---|:---|
| 17774 | HTTPS (REST/JSON) | Current, from platform release 2023.1 onward | curl, Python `orionsdk`, any HTTP client |
| 17778 | HTTPS (REST/JSON) | **Deprecated.** Was the REST port through 2022.4.1, will be removed in a future release | Legacy scripts, older SWQL Studio "over HTTPS" mode |
| 17777 | net.tcp (SOAP) | Current | SWQL Studio, `SwisPowerShell` (`Connect-Swis`) |

The REST base path is:

```
/SolarWinds/InformationService/v3/Json
```

So a full REST base URL is:

```
https://<orion-server>:17774/SolarWinds/InformationService/v3/Json
```

Only `https` is offered. The Swagger contract published with the schema declares
`"schemes": ["https"]` and a single security definition, `basicAuth`.

The port move is documented in
[SWIS REST API Port Deprecation, did you know?](https://thwack.solarwinds.com/product-forums/the-orion-platform/f/orion-sdk/98142/swis-rest-api-port-deprecation-did-you-know).
If you inherit a script that hard-codes 17778, change it to 17774 and confirm the target
server is on 2023.1 or later. If a script must straddle both, make the port a variable and
fall back rather than guessing.

## Authentication modes

SWIS accepts three kinds of identity. Which ones are available depends on the transport.

### Orion local account

A username and password managed in the Orion Web Console. This is the mode every REST
example in the official documentation uses (`Authorization: Basic ...`). It is the only mode
the REST endpoint's Swagger contract declares.

Because these are Orion accounts, the account limitations configured for them apply to
everything they read through SWIS. Give integrations their own account with the narrowest
role and limitation set that still does the job.

### Active Directory

Two variants:

- **Username and password.** The credentials you supply to the `Orion (v3)` server type in
  SWQL Studio, or to `Connect-Swis -Username/-Password`, may belong to an Active Directory
  account rather than an Orion local account. The credentials are sent to the Orion server,
  which authenticates them.
- **Kerberos, current Windows token.** The `Orion (v3) AD` server type in SWQL Studio, and
  `Connect-Swis -Trusted`, send the caller's existing Windows token. No password is
  transmitted. This requires Windows Authentication with Active Directory to be enabled on
  the Orion server; see
  [Enable Windows Authentication with Active Directory in the Orion Platform](https://documentation.solarwinds.com/en/Success_Center/orionplatform/Content/Core-Windows-Authentication-with-Active-Directory-sw2411.htm).

### Client certificate

SWQL Studio's `Orion (v3) Certificate` server type, and `Connect-Swis -Certificate`, look
for a certificate whose common name is **SolarWinds-Orion** on the local machine and present
it as the client certificate in the TLS handshake.

Two practical constraints from the official documentation:

- It is generally only available when running on the Orion server itself.
- The process must be running elevated (past UAC) to read the certificate's private key.

This is the mode to reach for when you need an unattended job on the Orion server that has
no password to store.

## The local connection limitation

This one catches people out, so it is worth quoting directly. From the official
[Connecting to SWIS](https://solarwinds.github.io/OrionSDK/docs/connecting-to-swis/) page:

> Because of current limitation, LOCAL connection via AD group account or with `-Trusted`
> option is not allowed. You can either use certificate for connection or connect from
> remote machine.

In other words: a scheduled task running **on the Orion server** that authenticates by
Windows token, either through `-Trusted` or through an account whose Orion access comes from
an AD *group* rather than an individual account mapping, will fail. Your options are:

1. Use `Connect-Swis -Certificate` on the Orion server (elevated).
2. Run the script from a different machine and use `-Trusted` from there.
3. Use an Orion local account with an explicit username and password.

## PowerShell

Install the module from the PowerShell Gallery. You will need an elevated PowerShell
session:

```powershell
Install-Module -Name SwisPowerShell
Import-Module SwisPowerShell
```

`Connect-Swis` returns a connection object that you pass to every other cmdlet. It defaults
to `localhost` if you omit `-Hostname`.

### Username and password

```powershell
$hostname = 'myorion.example.com'
$user     = 'admin'
$password = 'swordfish'
$swis = Connect-Swis -Hostname $hostname -Username $user -Password $password
```

A practical note: the official documentation snippet writes this as `$host = '12.153.24.2'`.
`$Host` is a PowerShell automatic variable, so assigning to it fails in a normal session.
The official sample scripts in the SDK repository use `$hostname`, and so should you.

Do not leave a plaintext password in a script that lives on disk. Prefer `-Credential`.

### Interactive or stored credential

```powershell
$hostname = 'myorion.example.com'
$creds = Get-Credential          # prompts for username and password
$swis  = Connect-Swis -Hostname $hostname -Credential $creds
```

`-Credential` takes a `PSCredential`, so it also works with a credential loaded from a
secret store or built from an encrypted string. See
[Get-Credential](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-credential).

### Current Windows identity (Kerberos)

```powershell
$hostname = 'myorion.example.com'
$swis = Connect-Swis -Hostname $hostname -Trusted
```

Remember the local connection limitation above: this will not work when run on the Orion
server itself.

### Client certificate

```powershell
$swis = Connect-Swis -Hostname 'localhost' -Certificate
```

Run this elevated, on the Orion server, with the `SolarWinds-Orion` certificate present in
the local machine store.

### Confirming the connection works

```powershell
Get-SwisData $swis 'SELECT TOP 3 NodeID, Caption, IPAddress FROM Orion.Nodes ORDER BY NodeID'
```

`NodeID`, `Caption` and `IPAddress` are all real properties of `Orion.Nodes` in 2026.2.

## Python

SolarWinds publishes an official Python client,
[`orionsdk`](https://github.com/solarwinds/orionsdk-python), on PyPI.

```bash
pip install orionsdk
```

The client's constructor signature in `orionsdk` 0.5.0 is:

```python
SwisClient(hostname, username, password, port=17774, verify=False, session=None, timeout=30)
```

The default port is already 17774, so on a current platform release you do not need to pass
it. `verify=False` is the default, which is the wrong default for production; see the TLS
section below.

```python
from orionsdk import SwisClient

swis = SwisClient(
    "myorion.example.com",
    "admin",
    "swordfish",
    verify="/etc/ssl/certs/orion-swis.pem",   # do not leave this as False
)

rows = swis.query(
    "SELECT TOP 3 NodeID, Caption, IPAddress FROM Orion.Nodes ORDER BY NodeID"
)
for row in rows["results"]:
    print(row["NodeID"], row["Caption"], row["IPAddress"])
```

The client builds `https://{hostname}:{port}/SolarWinds/InformationService/v3/Json/` and
sets HTTP basic auth from the username and password you pass. Two behaviours worth knowing
because they are easy to trip over:

- If you supply your own `requests.Session` through `session=`, the constructor still
  overwrites that session's `auth`, `headers` and `verify`. You cannot use `session=` to
  smuggle in Kerberos or client-certificate authentication and expect it to survive.
- On a 4xx or 5xx response the client tries to parse the body as JSON and lift the
  `Message` member into the exception's reason before calling `raise_for_status()`. That is
  where SWIS error text surfaces.

Because the constructor always installs basic auth, `orionsdk` covers the Orion local
account and AD username/password modes. Kerberos and client-certificate authentication over
REST are not exposed by this client; if you need them, drive the REST endpoint directly with
`requests` or use PowerShell.

## curl

Every REST call is HTTPS with basic auth. The simplest smoke test is a query:

```bash
curl -sS -u 'admin:swordfish' \
  --cacert /etc/ssl/certs/orion-swis.pem \
  --get \
  --data-urlencode 'query=SELECT TOP 3 NodeID, Caption FROM Orion.Nodes ORDER BY NodeID' \
  'https://myorion.example.com:17774/SolarWinds/InformationService/v3/Json/Query'
```

`--data-urlencode` with `--get` is doing real work here: SWQL contains spaces, commas and
frequently quotes and `%` wildcards, all of which must be percent-encoded in a query string.
Hand-building the URL is how you end up with a 400 that looks like a SWQL syntax error.

For anything with parameters, POST a JSON body instead and let SWIS bind the values. See
[rest-api.md](rest-api.md#parameter-binding).

## TLS and the self-signed certificate

By default SWIS presents a self-signed certificate. The official documentation says so
plainly for the HTTPS transport: "Expect a warning popup about the self-signed certificate
that SWIS will present in this case."

Every client therefore hits a verification failure on first contact, and the tempting fix is
to turn verification off. Do not make that a global habit. Disabling verification everywhere
means you can no longer detect an interception between your automation host and your
monitoring system, which is exactly the host that holds credentials for the rest of your
estate.

Handle it deliberately, in order of preference:

**1. Replace the certificate.** If your organization has an internal CA, issue SWIS a
certificate from it. Then nothing special is needed on any client, because the CA is already
trusted.

**2. Pin the self-signed certificate per client.** Export it once and point each client at
that file. Exporting with OpenSSL:

```bash
openssl s_client -connect myorion.example.com:17774 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > orion-swis.pem
```

Inspect the fingerprint before you trust it, ideally comparing against the certificate as
seen on the Orion server itself:

```bash
openssl x509 -in orion-swis.pem -noout -subject -issuer -dates -fingerprint -sha256
```

Then use it explicitly:

- curl: `--cacert /path/to/orion-swis.pem`
- Python `orionsdk`: `SwisClient(host, user, pw, verify="/path/to/orion-swis.pem")`
- Python `requests` directly: `session.verify = "/path/to/orion-swis.pem"`

This gives you real verification, scoped to one host, with a failure that means something.

**3. Disable verification, scoped and documented.** If you genuinely cannot do either of the
above, disable it on the single client object that talks to SWIS, never process-wide or
machine-wide, and leave a comment saying why. In `orionsdk` that is the default
(`verify=False`), which is precisely why you should set it explicitly to something better
rather than relying on the default.

For the SOAP transport, the official documentation shows an `-IgnoreSslErrors` switch on
`Connect-Swis` in its legacy Virtualization Manager appliance example. That example is
specific to the `-Soap12` appliance connection, so treat its applicability to a standard
Orion connection as unverified and test it on your own server before relying on it.

## Troubleshooting a failed connection

| Symptom | Likely cause |
|:---|:---|
| Connection refused on 17774 | Server is on 2022.4.1 or earlier; try 17778 |
| Connection refused on 17778 | Server is on 2023.1 or later; use 17774 |
| TLS verification failure | Self-signed certificate not trusted by the client; see above |
| 401 Unauthorized | Wrong credentials, or the Orion account is disabled |
| Works remotely, fails on the Orion server with `-Trusted` | The documented local connection limitation; use `-Certificate` |
| Query returns fewer rows than the web console shows | Account limitations are being applied to that account, which is SWIS working correctly |

## Next

- [rest-api.md](rest-api.md) for the REST request and response contract.
- [crud.md](crud.md) for creating and changing entities.
- [uris.md](uris.md) for addressing individual entity instances.
