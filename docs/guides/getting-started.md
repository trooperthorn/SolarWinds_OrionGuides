# Getting started

This page takes you from a machine with nothing installed to two things: a query that
returns rows from your own server, and a change that you made through the API and then
proved was made. Everything else in these guides assumes you have done this once.

The path is deliberately linear, and after each step there is a checkpoint that shows what
the failure looks like when that step is the one that went wrong. Most of the time lost on
a first SWIS connection is spent debugging the wrong layer: a certificate error read as a
credential problem, or a deprecated port read as a firewall rule. The checkpoints exist to
stop that.

| Step | You end up with |
|---:|:---|
| 1 | The Orion SDK tools installed, including SWQL Studio |
| 2 | A scripting client: `SwisPowerShell`, `orionsdk`, or plain `curl` |
| 3 | An authenticated connection to your server |
| 4 | Rows back from a first query |
| 5 | An understanding of what those rows are and are not |
| 6 | A node unmanaged and remanaged, with both states verified |

## Before you start

Three things, none of which the tools can supply for you.

**The hostname of the Orion server.** Not a URL and not a port, just the name or address
you would type into the web console.

**An Orion account.** Reading needs nothing special. The change in step 6 needs the
`allowUnmanage` right, which corresponds to the `AllowUnmanage` column on `Orion.Accounts`
and is a different right from `manageNodes`. If you are doing this with an account someone
else provisioned, check first:

```sql
SELECT a.AccountID, a.Enabled, a.AllowAdmin, a.AllowNodeManagement, a.AllowUnmanage
FROM Orion.Accounts a
WHERE a.AccountID = @account
```

Those columns come back as the strings `Y` and `N` rather than as booleans, which is why
the query above does not filter on `TRUE`. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

**A network path to the right port.** There are three, and they are not interchangeable.

| Port | Protocol | Status | Used by |
|:---|:---|:---|:---|
| 17774 | HTTPS (REST/JSON) | Current, from platform release 2023.1 onward | `curl`, Python `orionsdk`, any HTTP client |
| 17778 | HTTPS (REST/JSON) | Deprecated. Was the REST port through 2022.4.1 | Legacy scripts, older SWQL Studio "over HTTPS" mode |
| 17777 | net.tcp (SOAP) | Current | SWQL Studio, `SwisPowerShell` |

The full endpoint and authentication reference is
[../swis/connecting.md](../swis/connecting.md#endpoints-and-ports). You do not need to read
it to finish this page, but you will want it the first time something is strange.

## Step 1: install the Orion SDK tools

The Orion SDK is SolarWinds' own open-source package. It contains SWQL Studio, a graphical
query tool; the `SwisPowerShell` module; and a large set of sample scripts. Download the
installer from the
[OrionSDK releases page](https://github.com/solarwinds/OrionSDK/releases), or, if you have
[Chocolatey](https://chocolatey.org/), install it from there:

```text
choco install orionsdk
```

The installer is Windows only. If you work from Linux or macOS, skip to the Python or curl
client in step 2; nothing on the rest of this page needs SWQL Studio.

Install SWQL Studio anyway if you can, because it answers a question no offline reference
can. It renders the entity tree **of the server you connected to**, so it tells you which
entities that installation actually has, which depends on which modules are licensed. This
repository documents version 2026.2 with its 2067 entities; your server is the authority on
your server.

### Checkpoint

| What you see | What it means |
|:---|:---|
| The installer refuses to run | Not Windows. Use the Python or curl client instead. |
| SWQL Studio opens but the entity tree is empty | You have not connected yet. The tree is populated from the server, not from the install. |
| You cannot install software on this machine | Everything below except SWQL Studio works from a standard PowerShell or Python install. |

## Step 2: install a scripting client

Pick one. They all talk to the same service and none of them can do something the others
cannot, so the choice is about which language your automation is already written in.

### PowerShell

SolarWinds publishes
[`SwisPowerShell`](https://www.powershellgallery.com/packages/SwisPowerShell) on the
PowerShell Gallery. Install it from an elevated session:

```powershell
Install-Module -Name SwisPowerShell
Import-Module SwisPowerShell
Get-Command -Module SwisPowerShell
```

That last line is the verification, and it is worth running: it lists the seven cmdlets you
will use, which is a shorter list than most people expect. `Connect-Swis` opens a
connection, `Get-SwisData` runs a query, `Invoke-SwisVerb` calls a verb, and
`New-SwisObject`, `Get-SwisObject`, `Set-SwisObject` and `Remove-SwisObject` are the CRUD
four.

`SwisPowerShell` connects over the SOAP transport on port 17777, not over REST.

### Python

SolarWinds publishes [`orionsdk`](https://github.com/solarwinds/orionsdk-python) on PyPI.

```bash
pip install orionsdk
python3 -c "import orionsdk; print(orionsdk.__name__)"
```

`orionsdk` speaks REST on port 17774. Its constructor is
`SwisClient(hostname, username, password, port=17774, verify=False, session=None, timeout=30)`,
so the port default is already correct on a current platform release.

If you would rather not add a dependency, this repository ships a dependency-free client
that does the same job in about two hundred lines:
[../../scripts/python/swis_client.py](../../scripts/python/swis_client.py). It is also the
fastest way to see what the REST calls actually look like.

### curl

Nothing to install. The REST surface is small enough to drive by hand, and doing so once is
the best way to be able to tell later whether a problem is in your code or in the platform.
Worked examples are in
[../../scripts/curl/swis-rest-examples.sh](../../scripts/curl/swis-rest-examples.sh).

### Checkpoint

| What you see | Cause | Fix |
|:---|:---|:---|
| `The term 'Connect-Swis' is not recognized as the name of a cmdlet` | The module is installed but not imported into this session, or not installed at all | `Import-Module SwisPowerShell`; if that fails, `Install-Module -Name SwisPowerShell` from an elevated session |
| `Install-Module : The term 'Install-Module' is not recognized` | PowerShell older than 5.0, which has no PowerShellGet | Install the module by hand from the SDK, or upgrade PowerShell |
| `ModuleNotFoundError: No module named 'orionsdk'` | Installed into a different interpreter than the one you are running | `python3 -m pip install orionsdk`, using the same `python3` you will run the script with |
| `Install-Module` fails with an untrusted-repository prompt | The PSGallery repository is not trusted on this machine | Answer yes, or set the repository policy deliberately |

## Step 3: connect

### PowerShell

```powershell
Import-Module SwisPowerShell
$hostname = 'orion.example.com'
$swis = Connect-Swis -Hostname $hostname -Credential (Get-Credential)
```

Use `$hostname`, not `$host`. `$Host` is a PowerShell automatic variable and assigning to it
fails. SolarWinds' own documentation snippet uses `$host`, and their sample scripts use
`$hostname`; follow the samples.

`-Credential` prompts, which keeps the password out of the file and out of your shell
history. The other authentication modes, including Kerberos with `-Trusted` and the client
certificate with `-Certificate`, are covered in
[../swis/connecting.md](../swis/connecting.md#authentication-modes). One limitation is worth
knowing now because it looks like a bug: `-Trusted` does not work when the script is running
**on the Orion server itself**. That is documented behaviour, not a broken install.

### Python

```python
from orionsdk import SwisClient

swis = SwisClient(
    "orion.example.com",
    "svc-automation",
    password,                                 # read from a secret store, never hard-coded
    verify="/etc/ssl/certs/orion-swis.pem",   # see the TLS note below
)
```

### curl

```bash
export SWIS_HOST=orion.example.com
export SWIS_USER=svc-automation
read -rs SWIS_PASSWORD; export SWIS_PASSWORD

curl -sS -u "$SWIS_USER:$SWIS_PASSWORD" \
  --cacert /etc/ssl/certs/orion-swis.pem \
  --get \
  --data-urlencode 'query=SELECT TOP 1 NodeID FROM Orion.Nodes' \
  "https://$SWIS_HOST:17774/SolarWinds/InformationService/v3/Json/Query"
```

`--data-urlencode` with `--get` rather than a hand-built URL. SWQL contains spaces, commas
and often quotes and `%` wildcards, and every one of them has to be percent-encoded. A
hand-built URL is how you get a 400 that reads like a SWQL syntax error.

### A word about the certificate

SWIS presents a self-signed certificate by default, so every client fails verification on
first contact. The tempting fix is to turn verification off globally. Do not: the machine
running your automation holds credentials for your monitoring system, which in turn holds
credentials for much of your estate, and disabling verification means you can no longer
detect an interception on that path.

Export the certificate once and trust it explicitly:

```bash
openssl s_client -connect orion.example.com:17774 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > orion-swis.pem
openssl x509 -in orion-swis.pem -noout -subject -issuer -dates -fingerprint -sha256
```

Then pass it: `--cacert` for curl, `verify="/path/to/orion-swis.pem"` for `orionsdk`. The
full argument, including the case for replacing the certificate from an internal CA, is in
[../swis/connecting.md](../swis/connecting.md#tls-and-the-self-signed-certificate).

### Checkpoint

This is where most first attempts stop. The distinguishing question is at which layer the
failure happened: TCP, TLS, or HTTP.

| What you see | Layer | Likely cause |
|:---|:---|:---|
| `Connection refused`, `No connection could be made` on 17774 | TCP | The server is on 2022.4.1 or earlier, where REST was on 17778 |
| `Connection refused` on 17778 | TCP | The server is on 2023.1 or later. Use 17774 |
| The connection hangs and eventually times out | TCP | A firewall is dropping rather than rejecting. A rejected port answers immediately |
| `certificate verify failed`, `unable to get local issuer certificate`, `SSL: CERTIFICATE_VERIFY_FAILED` | TLS | The self-signed certificate is not trusted by this client. Trust it, do not disable verification |
| `401 Unauthorized` | HTTP | Wrong username or password, or the Orion account is disabled |
| `403` or a permission message | HTTP | Authentication worked. The account lacks the right the operation needs |
| PowerShell connects but every query returns nothing | HTTP | Almost certainly account limitations. See step 5 |

The clean way to separate TCP from TLS from HTTP is to test them in order:

```bash
# TCP only: does anything answer on the port?
nc -z -w5 orion.example.com 17774 && echo "port open"

# TLS only: does the handshake complete, and whose certificate is it?
openssl s_client -connect orion.example.com:17774 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -dates

# HTTP: authentication, with verification satisfied
curl -sS -o /dev/null -w '%{http_code}\n' -u "$SWIS_USER:$SWIS_PASSWORD" \
  --cacert orion-swis.pem \
  --get --data-urlencode 'query=SELECT TOP 1 NodeID FROM Orion.Nodes' \
  "https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Query"
```

`200` from the last one means everything works. Anything else, and you now know which of the
three layers to look at. [troubleshooting.md](troubleshooting.md) goes symptom by symptom.

## Step 4: your first query

The same query in each client. `Orion.Nodes` is the entity every installation has, and
`NodeID`, `Caption`, `IPAddress` and `Status` are four of its 102 properties.

```sql
SELECT TOP 5 n.NodeID, n.Caption, n.IPAddress, n.Status
FROM Orion.Nodes n
ORDER BY n.Caption
```

```powershell
Get-SwisData $swis 'SELECT TOP 5 NodeID, Caption, IPAddress, Status FROM Orion.Nodes ORDER BY Caption'
```

```python
rows = swis.query(
    "SELECT TOP 5 NodeID, Caption, IPAddress, Status FROM Orion.Nodes ORDER BY Caption"
)
for row in rows["results"]:
    print(row["NodeID"], row["Caption"], row["IPAddress"], row["Status"])
```

```bash
curl -sS -u "$SWIS_USER:$SWIS_PASSWORD" --cacert orion-swis.pem --get \
  --data-urlencode 'query=SELECT TOP 5 NodeID, Caption, IPAddress, Status FROM Orion.Nodes ORDER BY Caption' \
  "https://$SWIS_HOST:17774/SolarWinds/InformationService/v3/Json/Query"
```

Two things in that query are conventions rather than decorations. `TOP 5` bounds the result
set, and there is no `SELECT *` in SWQL, so an unbounded query against a large installation
is a genuine production risk rather than a style problem. The `n` alias costs nothing on a
single-entity query and becomes necessary the moment you join.

### Checkpoint

| What you see | Cause |
|:---|:---|
| `400` with a message naming your entity or column | A SWQL error: a misspelled entity or property. Check with `python3 tools/schema_query.py show Orion.Nodes` |
| `200` and `"results": []` | Not an error. Either the installation has no nodes, or account limitations are filtering them. See step 5 |
| A JSON body you cannot read | Pipe it through `jq .`, or use the `-w '%{http_code}'` form above to see the status separately |
| Rows, but far fewer than the web console shows | Account limitations. This is SWIS working correctly |

## Step 5: read the result properly

You have rows. Four things about them are not obvious.

**The column names are exactly your `SELECT` list**, aliases included. `SELECT n.Caption`
produces a member called `Caption`; `SELECT n.Caption AS NodeName` produces `NodeName`.
Alias anything ambiguous, because a query that walks to two entities with a `Caption` each
will otherwise hand you two members with the same name.

**`Status` is an integer, and the integer is not self-describing.** Join `Orion.StatusInfo`
rather than hard-coding numbers, so the query stays correct if SolarWinds adds a status:

```sql
SELECT TOP 5
    n.Caption,
    n.IPAddress,
    n.Status AS StatusId,
    s.StatusName,
    s.ShortDescription
FROM Orion.Nodes n
JOIN Orion.StatusInfo s ON n.Status = s.StatusId
ORDER BY s.Ranking, n.Caption
```

`Up` is `1` and `Down` is `2`, but `Unmanaged` is `9` and `External` is `11`, so "not up" and
"broken" are different questions. The full table is
[../reference/status-codes.md](../reference/status-codes.md).

**The result was filtered for you, invisibly.** SWIS applies the calling account's
limitations to every query, and nothing in the response says how many rows were removed.
SolarWinds describes this as a feature of going through SWIS rather than the database, and
it is, but it means "the query returns nothing" is at least as often a permissions answer as
a data answer. Rule it out before you debug the SQL:

```sql
SELECT a.AccountID, a.Enabled, a.LimitationID1, a.LimitationID2, a.LimitationID3
FROM Orion.Accounts a
WHERE a.AccountID = @account
```

**Values belong in parameters, not in the query text.** Bound parameters get their plans
reused and remove an injection class, and they save you from quoting problems:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
```

```powershell
Get-SwisData $swis 'SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @vendor' @{ vendor = 'Cisco' }
```

```python
swis.query("SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @vendor", vendor="Cisco")
```

Multi-valued parameters work too, with `IN @ids` and an array. Over raw REST, parameters go
in a POST body rather than the query string; see
[../swis/rest-api.md](../swis/rest-api.md#parameter-binding).

At this point you have a working read path. [cookbook.md](cookbook.md) is the next thing to
open, and it is organised by the question you are asking rather than by entity.

## Step 6: your first safe change

Unmanaging and remanaging a node is the right first write, for three reasons: it is
reversible in one call, it changes something you can see immediately in the web console, and
it exercises the two things that go wrong with every other verb, which are the argument
format and the timezone.

Before you start, understand what it does. An unmanaged object is not polled at all, so
there is a gap in its charts for the duration. That is fine on a test node and is the reason
to think twice on a real one. If you want alerts silenced but data kept, the tool is
`Orion.AlertSuppression` instead; see
[../automation/maintenance-mode.md](../automation/maintenance-mode.md).

### The verb, as the schema declares it

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

```text
Orion.Nodes.Unmanage
  Set the given node into maintenance mode so the node polling is disabled
  returns: System.Void
  REST:    POST /Invoke/Orion.Nodes/Unmanage
  requires: allowUnmanage
  parameters (5):
    netObjectId: string (required)
    unmanageTime: string (required)
    remanageTime: string (required)
    isRelative: boolean (required)
    allowOverlapping: boolean (optional)
```

`Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)`, and
`Remanage(netObjectId)` to undo it. Two facts about that signature decide whether your call
works:

- **Arguments are positional.** The names above appear in the documentation and in
  SolarWinds' Swagger contract, but they never travel on the wire. Order is the entire
  contract, and a reordered call does not fail cleanly.
- **`netObjectId` wants a NetObject string, not an id.** Node 42 is `"N:42"`. Passing `42`
  either errors or silently targets nothing depending on the release. Prefixes for every
  type are in [../reference/netobject-types.md](../reference/netobject-types.md).

### Pick a target and read its state first

```sql
SELECT n.NodeID, n.Caption, n.Status, n.UnManaged, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.Caption = @caption
```

`UnManaged`, `UnManageFrom` and `UnManageUntil` are inherited from `System.ManagedEntity`.
`Orion.Nodes` does not declare them, and they are queryable on it regardless, which is true
of every managed object type. Write down what this query returns. It is your "before".

### Make the change

Ten minutes, starting now, with both ends computed as absolute UTC times.

```powershell
$nodeId   = 42
$startUtc = [datetime]::UtcNow
$endUtc   = $startUtc.AddMinutes(10)

Invoke-SwisVerb $swis 'Orion.Nodes' 'Unmanage' @(
    "N:$nodeId",
    $startUtc,
    $endUtc,
    $false,     # isRelative: two absolute times, not a duration
    $false      # allowOverlapping
) | Out-Null
```

```python
from datetime import datetime, timedelta, timezone

start = datetime.now(timezone.utc)
end = start + timedelta(minutes=10)
swis.invoke("Orion.Nodes", "Unmanage", "N:42", start.isoformat(), end.isoformat(), False, False)
```

```bash
curl -sS -X POST -u "$SWIS_USER:$SWIS_PASSWORD" --cacert orion-swis.pem \
  -H 'Content-Type: application/json' \
  -d '["N:42","2026-09-01T21:00:00Z","2026-09-01T21:10:00Z",false,false]' \
  "https://$SWIS_HOST:17774/SolarWinds/InformationService/v3/Json/Invoke/Orion.Nodes/Unmanage"
```

Both times are handled as UTC. Convert at the boundary, in your own code, rather than
letting the caller's locale decide. A window that opens four hours late, discovered the
morning after a change, is the normal way this goes wrong.

`isRelative` is `false` here and should almost always be false. Set to `true`, the third
argument stops being an instant and becomes a duration carried in a time of day, so its date
part is discarded. SolarWinds' own recommendation is to pass `false` and compute the end
yourself.

### Verify, because the verb told you nothing

`Unmanage` returns `System.Void`. A successful call and a call that did nothing look
identical from the response, so the read-back is not optional:

```sql
SELECT n.NodeID, n.Caption, n.Status, n.UnManaged, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

You should see `UnManaged` as `true` and the two window boundaries set. If the window is
scheduled but has not opened yet, `UnManaged` is still `false` while the boundaries hold a
future window, which is expected rather than a failure.

### Put it back

```powershell
Invoke-SwisVerb $swis 'Orion.Nodes' 'Remanage'      @("N:$nodeId") | Out-Null
Invoke-SwisVerb $swis 'Orion.Nodes' 'PollStatusNow' @("N:$nodeId") | Out-Null
```

```python
swis.invoke("Orion.Nodes", "Remanage", "N:42")
swis.invoke("Orion.Nodes", "PollStatusNow", "N:42")
```

`Remanage` ends the window immediately whatever `UnManageUntil` says. `PollStatusNow` then
refreshes the status so the console reflects reality instead of waiting for the next cycle.
Note that `PollStatusNow` requires `manageNodes`, a different right from the `allowUnmanage`
that `Remanage` requires, so an account that can end a maintenance window cannot necessarily
force a poll. Run the verification query once more and confirm you are back where you
started.

### Checkpoint

| What you see | Cause | Fix |
|:---|:---|:---|
| A permission error on `Unmanage` | The account lacks `allowUnmanage`, which is not implied by `manageNodes` | Grant `AllowUnmanage` on the account |
| The call succeeds and `UnManaged` never changes | A bare `42` was passed where `"N:42"` was expected | Use the NetObject string |
| A type error on one of the arguments | The arguments are in the wrong order | Re-read the signature with `schema_query.py verb`; order is the whole contract |
| The window opens hours off | Local time sent as UTC | Convert explicitly at the boundary |
| An error about an overlapping window | A window is already scheduled on that node | Remanage first, or pass `true` for `allowOverlapping` deliberately |
| The node is unmanaged and will not come back | `UnManageUntil` has passed but the flag is stuck | Call `Remanage` explicitly. The query in [cookbook.md](cookbook.md#58-what-is-still-unmanaged-after-its-window-closed) finds all of them |

### Leave a trail you can read later

Every change made through SWIS lands in the audit trail, which is the first thing to check
when someone asks what happened:

```sql
SELECT TOP 50 a.TimeLoggedUtc, a.AccountID, a.AuditEventMessage, a.NetObjectType, a.NetObjectID
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > AddHour(-1, GetUtcDate())
ORDER BY a.TimeLoggedUtc DESC
```

`TimeLoggedUtc` is already UTC, so it is compared against `GetUtcDate()` and not
`GetDate()`. Mixing those up is the single most common source of a query that returns
nothing or returns yesterday; [../swql/date-and-time.md](../swql/date-and-time.md) is worth
twenty minutes before you write anything time-bounded.

## Where to go next

You now have the two halves of everything else: a read path and a write path.

- [cookbook.md](cookbook.md) is the page to keep open. It is indexed by the question rather
  than by the entity, and every query in it is validated.
- [troubleshooting.md](troubleshooting.md) is organised by symptom, for when something that
  worked stops working.
- [../swql/README.md](../swql/README.md) for the query language, and
  [../swql/gotchas.md](../swql/gotchas.md) for the things that silently produce wrong
  results rather than errors.
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for calling verbs properly in each
  client, including the PowerShell array-argument trap.
- [../swis/crud.md](../swis/crud.md) for creating and deleting entities, which is a
  different interface from Invoke.
- [../automation/README.md](../automation/README.md) for the query-first method that the
  task guides all follow.
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking your own
  server what it has, which beats any offline reference when the two disagree.

Offline, without a server: `python3 tools/schema_query.py show <Entity>` answers most
schema questions, and `python3 tools/validate_swql.py <file>` checks a query before you run
it. Both are described in [../../tools/README.md](../../tools/README.md).
