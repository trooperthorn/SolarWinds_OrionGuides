# Troubleshooting SWIS

Organised by what you are looking at, because that is what you have when something breaks.
Each symptom lists its causes in order of how often they turn out to be the answer, and for
each cause the exact command or query that rules it in or out. The ordering is the useful
part: most time lost on a SWIS problem is spent testing the third-likeliest cause first.

Two habits behind the whole page. Work outwards from the layer that failed rather than from
the layer you were thinking about, since a certificate error and a deprecated port both look
like "it does not connect". And prefer a command that distinguishes two causes over one that
confirms the cause you already suspect.

## Triage

| What you are seeing | Section |
|:---|:---|
| Connection refused, or nothing answers | [The connection never lands](#the-connection-never-lands) |
| `certificate verify failed`, `untrusted`, `SSL` in the message | [The TLS handshake fails](#the-tls-handshake-fails) |
| `401 Unauthorized` | [401 Unauthorized](#401-unauthorized) |
| `403`, or a message about permission | [403, or a permission message](#403-or-a-permission-message) |
| `400` on a query that looks fine | [A query fails with 400](#a-query-fails-with-400) |
| `200` and an empty `results` array | [A query returns no rows when you expect some](#a-query-returns-no-rows-when-you-expect-some) |
| The query takes minutes, or the client times out | [A query is slow or times out](#a-query-is-slow-or-times-out) |
| A verb rejects an argument | [A verb fails with a type or argument error](#a-verb-fails-with-a-type-or-argument-error) |
| A verb returns cleanly and nothing changed | [A verb reports success but nothing changes](#a-verb-reports-success-but-nothing-changes) |
| Create is refused | [CRUD rejects a create](#crud-rejects-a-create) |
| Something that worked before an upgrade does not now | [Entity not found after an upgrade](#entity-not-found-after-an-upgrade) |
| The API and the web console disagree | [The numbers disagree with the web console](#the-numbers-disagree-with-the-web-console) |

## The connection never lands

**What you see.** `Connection refused`, `No connection could be made because the target
machine actively refused it`, `Failed to connect`, or a client that hangs until it times
out.

### Causes, in order

**1. The port.** This is the answer far more often than anything else, especially on a
script that used to work. The REST endpoint moved.

| Port | Protocol | Status | Used by |
|:---|:---|:---|:---|
| 17774 | HTTPS (REST/JSON) | Current, from platform release 2023.1 onward | `curl`, Python `orionsdk`, any HTTP client |
| 17778 | HTTPS (REST/JSON) | Deprecated. Was the REST port through 2022.4.1 | Legacy scripts, SWQL Studio's "Orion (v3) over HTTPS" mode |
| 17777 | net.tcp (SOAP) | Current | SWQL Studio, `SwisPowerShell` |

The failure mode is what makes this worth checking first: a request to a port that no longer
serves the API produces a connection-level failure with no response body, so there is nothing
in the error that mentions ports. A script copied from a pre-2023 source stops working after
an upgrade in a way that reads like a firewall or a certificate problem, and people spend a
day on TLS before looking at the number after the colon.

The other direction happens too. A script written against 17774 fails against a server still
on 2022.4.1 or earlier, where REST was on 17778.

**2. A firewall dropping rather than rejecting.** A closed port answers immediately with a
refusal. A dropped packet produces a hang and then a timeout. That difference tells you
whether you are talking to the host at all.

**3. The SolarWinds Information Service is not running** on the target, or the server is
mid-restart after an upgrade.

**4. The wrong host.** An additional web server or a polling engine is not the primary
server, and a name that resolves in your office may not resolve from the automation host.

### What distinguishes them

Test the layers in order. Each command answers exactly one question:

```bash
# 1. Does the name resolve, and to what?
getent hosts orion.example.com

# 2. Does anything answer on the port? Immediate failure means refused; a wait means dropped.
nc -z -v -w5 orion.example.com 17774

# 3. Is the other REST port open instead? If this succeeds and 17774 does not,
#    the server predates 2023.1.
nc -z -v -w5 orion.example.com 17778
```

```powershell
Test-NetConnection -ComputerName orion.example.com -Port 17774
Test-NetConnection -ComputerName orion.example.com -Port 17777   # SOAP, for SwisPowerShell
```

`Test-NetConnection` reports `TcpTestSucceeded` plus the ping result, which separates "the
host is unreachable" from "the host is up and the port is not open".

If you are testing from the Orion server itself, `netstat -ano | findstr 17774` shows
whether anything is listening locally, which distinguishes a stopped service from a network
path problem.

See [../swis/connecting.md](../swis/connecting.md#endpoints-and-ports) for the endpoint
reference, and [../swql/gotchas.md](../swql/gotchas.md#12-port-17778-is-deprecated) for the
deprecation itself.

## The TLS handshake fails

**What you see.** The message depends on the client, but they all mean the same thing:

| Client | Message |
|:---|:---|
| curl | `SSL certificate problem: self-signed certificate` or `unable to get local issuer certificate` |
| Python `requests` / `orionsdk` | `SSLError: ... certificate verify failed: self signed certificate` |
| PowerShell | `The underlying connection was closed: Could not establish trust relationship for the SSL/TLS secure channel` |

### Causes, in order

**1. SWIS is presenting its default self-signed certificate**, which nothing trusts.
SolarWinds documents this directly for the HTTPS transport: expect a warning about the
self-signed certificate SWIS presents. This is the cause almost every time.

**2. The name you connected by is not the name on the certificate.** Connecting by IP
address to a certificate issued for a hostname fails verification even after you trust the
certificate, and the message often says `hostname mismatch` rather than anything about
trust.

**3. A genuine interception.** Rare, and the entire reason not to make "disable verification"
your habit.

### What distinguishes them

Look at the certificate itself before changing any client code:

```bash
openssl s_client -connect orion.example.com:17774 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -fingerprint -sha256
```

A subject and issuer that are the same string is a self-signed certificate, which is cause
1. A subject naming a different host than the one you connected to is cause 2. An issuer you
do not recognise on a network where you expected a self-signed certificate is worth taking
seriously.

### Why the fix is to trust it, not to disable verification

Turning verification off is one flag and it makes the error disappear, which is exactly the
problem. The host running your automation holds credentials for your monitoring system,
which in turn holds SNMP communities, device logins and cloud keys for much of your estate.
Disabling certificate verification on that host means you can no longer detect an
interception on the one path where it would matter most, and you have removed the detection
permanently in exchange for saving five minutes once.

In order of preference:

**Replace the certificate.** If you have an internal CA, issue SWIS a certificate from it and
nothing on any client needs configuring, because the CA is already trusted.

**Pin the self-signed certificate per client.** Export it once, check the fingerprint against
the certificate as seen on the Orion server itself, then point each client at the file:

```bash
openssl s_client -connect orion.example.com:17774 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > orion-swis.pem
openssl x509 -in orion-swis.pem -noout -subject -issuer -dates -fingerprint -sha256
```

- curl: `--cacert /path/to/orion-swis.pem`
- Python `orionsdk`: `SwisClient(host, user, pw, verify="/path/to/orion-swis.pem")`
- Python `requests`: `session.verify = "/path/to/orion-swis.pem"`

This gives you real verification, scoped to one host, with a failure that means something.

**If you truly cannot do either**, disable it on the single client object that talks to
SWIS, never process-wide or machine-wide, and leave a comment saying why. Note that
`orionsdk` defaults to `verify=False`, so a Python integration that says nothing about
verification is already not verifying. Set it explicitly to something better rather than
inheriting that default.

Full detail: [../swis/connecting.md](../swis/connecting.md#tls-and-the-self-signed-certificate).

## 401 Unauthorized

**What you see.** HTTP `401`, or `The remote server returned an error: (401) Unauthorized`.

A `401` is always about identity. You will not get a `401` because an account lacks a right;
that is a `403`. Separating those two saves a lot of time, because they have completely
different fixes.

### Causes, in order

**1. Wrong username or password.** Including the ordinary versions: a password that expired,
a trailing space pasted from a password manager, or a service account whose password was
rotated somewhere your script did not follow.

**2. The Orion account is disabled, expired, or locked out** after failed attempts.

**3. Windows or Active Directory authentication is not enabled on the server**, while the
client is sending a domain identity. The credentials are valid; the server is not configured
to accept that kind of identity.

**4. The documented local-connection limitation.** A `Connect-Swis -Trusted` call, or an
account whose Orion access comes from an AD **group** rather than an individual mapping,
fails when it runs **on the Orion server itself**. SolarWinds states this plainly: local
connection via an AD group account or with `-Trusted` is not allowed. The workarounds are
`-Certificate` on the server, running from a different machine, or an Orion local account
with an explicit username and password. This one looks exactly like a credential problem and
is not.

### What distinguishes them

From an account that does work, read the target account's state:

```sql
SELECT
    a.AccountID,
    a.Enabled,
    a.Expires,
    a.LockoutTime,
    a.BadPwdCount,
    a.PasswordExpirationDate,
    a.LastLogin
FROM Orion.Accounts a
WHERE a.AccountID = @account
```

`Enabled` comes back as `Y` or `N` rather than as a boolean, which is true of every `Allow*`
and `Can*` column on this entity. A non-zero `BadPwdCount` with a recent `LockoutTime` is
cause 2 and tells you something is retrying with a stale password, which is worth finding
before you reset it.

Then test the credentials in isolation, without your script in the way:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -u "$SWIS_USER:$SWIS_PASSWORD" \
  --cacert orion-swis.pem \
  --get --data-urlencode 'query=SELECT TOP 1 NodeID FROM Orion.Nodes' \
  "https://orion.example.com:17774/SolarWinds/InformationService/v3/Json/Query"
```

`200` means the credentials are fine and the problem is in how your client passes them.
`401` means they are not. If a local account works and a domain account does not, you are
looking at cause 3 or cause 4, and the deciding question is where the script is running:
move it to another machine and try again.

Authentication modes in full:
[../swis/connecting.md](../swis/connecting.md#authentication-modes).

## 403, or a permission message

**What you see.** HTTP `403`, or a message naming a right, or a verb that returns an error
mentioning permission. Authentication worked. Something about authorization did not.

### Causes, in order

**1. The account lacks the right the verb declares.** Rights are specific, and the obvious
one is often not the one you need. `Orion.Nodes.Unmanage` requires `allowUnmanage`, which is
**not** implied by `manageNodes`, so a service account provisioned to manage nodes cannot
necessarily unmanage one.

**2. The right is declared on the entity rather than on the verb.** A verb with no rights of
its own is not open to everybody; the entity's `invoke` entry governs. 692 of the 1021 verbs
in 2026.2 declare no right of their own, and 363 of those belong to an entity that does. So
`Orion.NodesCustomProperties.CreateCustomProperty` needs `admin`, and nothing in the verb's
own record says so.

**3. A module role on top of the Orion right.** NCM in particular enforces its own role
model: many `Cirrus.*` and `NCM.*` verb summaries say "Valid for Orion manage node users
with at least WebUploader NCM role", and that requirement is real even though it is prose
rather than an access-control entry.

**4. An account limitation hiding the target object.** Limitations filter query results
silently, so an automation that resolves a NodeID by query and then invokes a verb on it can
fail at either step for the same underlying reason.

### What distinguishes them

Check both levels, in this order:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage       # the right the verb declares
python3 tools/schema_query.py show Orion.Nodes                # the rights the entity declares
```

Then check whether the account holds it. The rights in the schema correspond by name to the
account columns, closely but not exactly: `manageNodes` to `AllowNodeManagement`,
`clearEvents` to `CanClearEvents`, `allowUnmanage` to `AllowUnmanage`.

```sql
SELECT
    a.AccountID,
    a.AllowAdmin,
    a.AllowNodeManagement,
    a.AllowUnmanage,
    a.AllowAlertManagement,
    a.CanClearEvents
FROM Orion.Accounts a
WHERE a.AccountID = @account
```

If the right is there and the call still fails, test cause 4 by asking whether the account
can see the object at all:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.Uri
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

Run that as the failing account. No row means a limitation is hiding it, and the verb was
never going to work regardless of rights.

Full treatment:
[../swis/invoke-verbs.md](../swis/invoke-verbs.md#access-control) and
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

## A query fails with 400

**What you see.** HTTP `400` with a message that usually names the offending token.

A `400` on `/Query` is almost always the SWQL rather than the transport, which is good news:
it is checkable offline in one command.

### Causes, in order

**1. An entity or property that does not exist**, usually a plausible-looking near miss.
`Orion.Node` instead of `Orion.Nodes`. `Orion.VIM.LUNs` instead of `Orion.VIM.Luns`. A
property that exists on a sibling entity but not this one.

**2. A navigation property that was guessed.** Dot-walking only works along declared
relationships. `Orion.APM.Component` has no navigation to a node; the route is
`c.Application.Node`.

**3. `SELECT *`.** There is no such thing in SWQL. Name the columns.

**4. A value concatenated into the query text** that contains a quote or a percent sign.
This one usually produces an error that points at a completely innocent part of the query.

**5. A function that does not exist on this server**, or one called with the wrong number of
arguments.

### What distinguishes them

Offline, before you touch the server:

```bash
echo "SELECT n.Caption, n.Node.Foo FROM Orion.Nodes n" | python3 tools/validate_swql.py -
```

The validator resolves every dotted reference through the schema, including inherited
members, and names the closest real members when it cannot find one. Point it at a file to
check a whole script: it reads `.swql`, `.md`, `.ps1`, `.py` and `.sh`, so a query embedded
in a script is checked too.

To find the right name rather than only learn that yours is wrong:

```bash
python3 tools/schema_query.py find volume capacity --properties
python3 tools/schema_query.py props Orion.Nodes --grep memory
python3 tools/schema_query.py path Orion.APM.Component Orion.Nodes
```

On the server, `Metadata.Property` is the authority for your version:

```sql
SELECT p.Name, p.Type, p.IsKey, p.IsNavigable, p.IsInherited
FROM Metadata.Property p
WHERE p.Entity.FullName = @entityName
ORDER BY p.Name
```

For cause 4, stop concatenating. Bound parameters make the whole class disappear:

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE n.Caption LIKE @pattern
```

## A query returns no rows when you expect some

This is a `200` with `"results": []`, which is not an error and is the most commonly
misdiagnosed symptom on the platform.

### Causes, in order

**1. Account limitations.** SWIS applies the calling account's limitations to every query and
puts nothing in the response to say it did. The same query text legitimately returns
different rows for different accounts, and aggregates are scoped the same way, so a `COUNT`
can disagree with the licensing page and both be right. Rule this out first, not last.

**2. A filter that excludes more than you meant.** The usual suspects: `UnManaged = FALSE`
removing objects in a maintenance window; `Status <> 1` not meaning "broken", because `9` is
Unmanaged and `11` is External; `= NULL`, which is always false and needs `IS NULL`; and a
to-one navigation in the `SELECT` list quietly acting as an inner join, so rows whose parent
is missing disappear rather than coming back with nulls.

**3. A time filter on the wrong clock.** Some date columns are stored UTC and some local, and
there is no flag in the schema that says which. Comparing a UTC column against `GetDate()`
shifts your window by your offset, which returns nothing at all on a narrow window and
returns the wrong hours on a wide one.

**4. The module is not installed, or the feature is not configured.** An entity that does not
exist produces an error rather than an empty result, so a clean empty result points away from
this. An entity that exists with nothing configured, such as a suppression table on a server
where nobody has suppressed anything, produces exactly this.

**5. String comparison.** Case and collation behaviour, and trailing whitespace in a caption
that came from a discovery import.

### What distinguishes them

Cause 1, first and fastest. Run the same query as an account with no limitations and compare
counts, then look at what the failing account carries:

```sql
SELECT
    a.AccountID,
    a.Enabled,
    a.LimitationID1,
    a.LimitationID2,
    a.LimitationID3
FROM Orion.Accounts a
WHERE a.AccountID = @account
```

```sql
SELECT
    l.LimitationID,
    t.Name AS LimitationType,
    t.EntityType,
    l.Definition,
    l.WhereClause
FROM Orion.Limitations l
JOIN Orion.LimitationTypes t ON l.LimitationTypeID = t.LimitationTypeID
ORDER BY l.LimitationID
```

Cause 2: remove predicates one at a time, starting from the whole table, and watch where the
count falls to zero.

```sql
SELECT COUNT(n.NodeID) AS VisibleNodes
FROM Orion.Nodes n
```

Cause 3: measure the column rather than guessing. Pick something written continuously.
`Orion.Engines.KeepAlive` is ideal, because every engine updates it constantly and "now" is
the correct answer for it:

```sql
SELECT TOP 1
    e.ServerName,
    e.KeepAlive,
    e.MinutesSinceKeepAlive,
    MinuteDiff(e.KeepAlive, GetDate())    AS MinutesBehindLocalNow,
    MinuteDiff(e.KeepAlive, GetUtcDate()) AS MinutesBehindUtcNow
FROM Orion.Engines e
WHERE e.ServerType = 'Primary'
```

Whichever of the last two columns is near zero identifies the clock. Apply the same shape to
whatever column your filter uses. The naming convention helps: `TimeLoggedUtc` and
`LastSystemUpTimePollUtc` say so, `Orion.Events.EventTime` documents itself as local, and
everything else needs measuring. See
[../swql/date-and-time.md](../swql/date-and-time.md#measuring-a-columns-timezone).

Cause 4: ask the server what it has.

```sql
SELECT e.FullName, e.BaseType, e.CanCreate, e.CanRead, e.CanInvoke
FROM Metadata.Entity e
WHERE e.FullName LIKE @namePattern
ORDER BY e.FullName
```

Cause 5: compare against a trimmed, case-folded form before concluding the row is missing.

```sql
SELECT n.NodeID, n.Caption
FROM Orion.Nodes n
WHERE ToLower(n.Caption) LIKE ToLower(@pattern)
```

That is deliberately a diagnostic and not a production query: wrapping the filtered column in
a function prevents the database using an index on it. Once you know the row is there, fix
the input rather than keeping the function. See
[../swql/performance.md](../swql/performance.md#4-never-wrap-a-filtered-column-in-a-function).

The longer form of this whole section is
[../swql/gotchas.md](../swql/gotchas.md#1-the-empty-result-set-is-usually-a-permissions-answer).

## A query is slow or times out

**What you see.** A client timeout, a request that takes minutes, or a noticeable load spike
on the database while your report runs.

### Causes, in order

**1. An unbounded result set.** No `TOP`, no `WITH ROWS`. There is no `SELECT *` in SWQL but
there is nothing stopping you selecting every row of a large table.

**2. A historical entity with no time bound.** Events, alert history and the statistics
entities are the largest tables on the system by a wide margin, and the platform is
constantly writing to them.

**3. A function wrapped around a filtered column.** `WHERE Year(e.EventTime) = 2026` cannot
use an index on `EventTime`; `WHERE e.EventTime >= @start AND e.EventTime < @end` can.

**4. A base-entity query.** `SELECT ... FROM System.ManagedEntity` is convenient and has to
consider all 174 entities that inherit from it. Fine occasionally, wrong for anything
scheduled.

**5. A deep dot-walk.** Each navigation step is a join, and a chain such as
`c.Application.Node.Engine.ServerName` is three of them per row.

**6. Aggregating in the client.** Pulling ten thousand rows to count them moves the work to
the slowest link, which is the network.

### What distinguishes them

Ask for the count before you ask for the rows, which is cheap and tells you the shape of the
problem:

```sql
SELECT COUNT(e.EventID) AS MatchingEvents
FROM Orion.Events e
WHERE e.EventTime >= @start
  AND e.EventTime < @end
```

If the count is large, the query is not slow, it is big, and the fix is a bound rather than a
rewrite. Page instead of pulling everything:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress
FROM Orion.Nodes n
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

If the count is small and the query is still slow, cause 3 or cause 4 is likely. Remove one
predicate or one navigation step at a time and re-time it. A half-open window, `>=` with `<`,
is both faster and easier to compose than `BETWEEN`, since consecutive windows neither
overlap nor leave a gap.

[../swql/performance.md](../swql/performance.md) has the six rewrites in full, each with the
before and after.

## A verb fails with a type or argument error

**What you see.** An error naming an argument type, or complaining about the number of
arguments, or a serialisation failure from PowerShell.

### The one fact behind all of it

**Invoke arguments are positional.** The names appear in SolarWinds' documentation and in
their Swagger contract, but they never travel on the wire. Order is the entire contract. A
call with the right arguments in the wrong order does not necessarily fail: if the types
happen to line up, it succeeds and does the wrong thing.

### Causes, in order

**1. The arguments are in the wrong order.** Usually because the signature was recalled
rather than looked up, or copied from documentation for a different version.

**2. The wrong number of arguments.** Optional trailing arguments may be omitted, but not
ones in the middle, and not all versions of a verb have the same arity.
`Orion.SEUM.Transactions.Unmanage` takes four parameters where the node, interface and volume
forms take five, so a five-argument call to it fails.

**3. PowerShell flattened a single array argument.** `@($uris)` where `$uris` is already an
array produces N string arguments instead of one array argument, and the server rejects the
count. The fix is a leading comma: `@( , [string[]]$uris )`.

**4. PowerShell `PSObject` wrappers.** Query results are wrapped objects, not raw ints and
strings, so a serialisation error on something that looks like an integer array wants an
explicit `[int[]]` or `[string[]]` cast.

**5. A `DateTime` passed as a local time where UTC was expected.** This one does not error.
It succeeds and produces a window at the wrong hour.

### What distinguishes them

Read the real signature. Offline:

```bash
python3 tools/schema_query.py verb Orion.AlertActive Acknowledge
```

```text
Orion.AlertActive.Acknowledge
  Acknowledge active alerts, based on array of alert active ids and desired notes.
  returns: boolean
  REST:    POST /Invoke/Orion.AlertActive/Acknowledge
  requires: clearEvents
  parameters (2):
    alertObjectIds: array<number> (required)
    notes: string (required)
```

On the server, ordered by position, which is the definitive answer for your version:

```sql
SELECT
    a.EntityName,
    a.VerbName,
    a.Position,
    a.Name AS ArgumentName,
    a.Type,
    a.IsOptional
FROM Metadata.VerbArgument a
WHERE a.EntityName = @entityName
  AND a.VerbName = @verbName
ORDER BY a.Position
```

`ORDER BY a.Position` is not optional. The rows come back in whatever order the server
chooses otherwise, and reading them in that order is how a reordered call gets written in the
first place.

Calling mechanics per client, including the leading-comma trick and the REST nesting it
corresponds to, are in
[../swis/invoke-verbs.md](../swis/invoke-verbs.md#how-arguments-are-serialised).

## A verb reports success but nothing changes

The most expensive symptom on this page, because nothing tells you it happened. Many verbs
return `System.Void`, so a call that did exactly what you asked and a call that did nothing
produce the same response.

### Causes, in order

**1. The wrong kind of id.** `netObjectId` arguments want a NetObject string, not a bare
integer: node 42 is `"N:42"`, interface 58 is `"I:58"`, volume 9 is `"V:9"`, application 317
is `"AA:317"`. Depending on the release, a bare `42` either errors or silently targets
nothing. Prefixes for every type are in
[../reference/netobject-types.md](../reference/netobject-types.md).

**2. The right kind of id from the wrong column.**
`Orion.AlertActive.Acknowledge(alertObjectIds, notes)` takes `AlertObjectID` values even
though it lives on `Orion.AlertActive`, and `AlertActiveID` is a different number on the
same entity. Passing the wrong one is a well-formed call that acknowledges nothing you meant.

**3. The change is scheduled, not applied.** `Unmanage` with a future `unmanageTime` leaves
`UnManaged` as `false` and sets `UnManageFrom` and `UnManageUntil` to the future window. That
is correct behaviour and looks like failure.

**4. The property is not settable.** An update to a read-only property is accepted and does
nothing. `Metadata.Property.CanUpdate` says which.

**5. You changed a different instance.** Two nodes with the same caption is common enough
that a lookup by caption is a real hazard. Resolve by key or by URI.

### What distinguishes them

**Always verify from the data, never from the response.** After any write, read the state
back:

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.Status,
    n.UnManaged,
    n.UnManageFrom,
    n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID = @nodeId
```

For cause 3, that query distinguishes "nothing happened" from "the window is scheduled":
boundaries set with `UnManaged` still `false` is a future window.

For cause 4, check before you write rather than after:

```sql
SELECT p.Name, p.Type, p.IsKey, p.CanCreate, p.CanUpdate
FROM Metadata.Property p
WHERE p.Entity.FullName = @entityName
ORDER BY p.Name
```

For cause 5, look for the ambiguity directly:

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.Uri
FROM Orion.Nodes n
WHERE n.Caption = @caption
ORDER BY n.NodeID
```

More than one row means your caption lookup has been picking one of them arbitrarily. Recipe
52 in [cookbook.md](cookbook.md#52-are-there-duplicate-captions) finds every such pair at
once.

And for anything that runs unattended, check the audit trail, which records what the API
actually did:

```sql
SELECT TOP 50
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage,
    a.NetObjectType,
    a.NetObjectID
FROM Orion.AuditingEvents a
WHERE a.TimeLoggedUtc > AddHour(-1, GetUtcDate())
ORDER BY a.TimeLoggedUtc DESC
```

## CRUD rejects a create

**What you see.** A create that is refused, or an error naming a property, or a created
entity that does not do anything.

### Causes, in order

**1. The entity does not support create.** SolarWinds says so plainly: there may be entity
types that do not support the CRUD interface or support it only partially, and in those
cases the operations may reject requests. 250 of the 2067 documented entities in 2026.2 are
creatable. Support is per operation rather than all-or-nothing, so an entity can be readable
and updatable with no create at all: `Orion.NodesCustomProperties` is exactly that, because
the row of values exists because the node exists.

**2. The operation belongs to a verb, not to CRUD.** Creating a custom property
*definition* is `Orion.NodesCustomProperties.CreateCustomProperty`, not a CRUD create.
Acknowledging an alert is `Orion.AlertActive.Acknowledge`, not an update. Reaching for
Create on those entities is the wrong interface rather than a permissions problem.

**3. A required property is missing**, or one you supplied is not settable at create time.
`Metadata.Property.CanCreate` distinguishes them.

**4. The right.** Create is gated separately from read. `Orion.Engines` allows read for
`everyone` and restricts create, update and delete to the `system` right, which an ordinary
administrator account does not hold.

**5. The create succeeded and the object does nothing.** Creating a node is not enough to
monitor it: pollers have to be assigned afterwards, and a node with no rows in
`Orion.Pollers` collects nothing while looking entirely configured.

### What distinguishes them

Ask the server what it will accept:

```sql
SELECT e.FullName, e.CanCreate, e.CanRead, e.CanUpdate, e.CanDelete, e.CanInvoke
FROM Metadata.Entity e
WHERE e.FullName = @entityName
```

```sql
SELECT p.Name, p.Type, p.IsKey, p.IsNullable, p.CanCreate, p.CanUpdate
FROM Metadata.Property p
WHERE p.Entity.FullName = @entityName
ORDER BY p.Name
```

Offline, the same answer without a server:

```bash
python3 tools/schema_query.py show Orion.NodesCustomProperties
```

Look at the `operations` line and the access-control table it prints. For cause 2, list the
verbs before assuming CRUD:

```bash
python3 tools/schema_query.py verbs --entity Orion.NodesCustomProperties
```

For cause 5, the check after every node create:

```sql
SELECT n.NodeID, n.Caption, COUNT(p.PollerID) AS PollerCount
FROM Orion.Nodes n
LEFT JOIN Orion.Pollers p
    ON p.NetObjectID = n.NodeID
   AND p.NetObjectType = 'N'
WHERE n.NodeID = @nodeId
GROUP BY n.NodeID, n.Caption
```

See [../swis/crud.md](../swis/crud.md#not-every-entity-supports-crud) and
[../automation/pollers.md](../automation/pollers.md).

## Entity not found after an upgrade

**What you see.** A query or a script that worked before an upgrade now fails naming an
entity, a property, or a verb. Or, worse, it does not fail.

### Causes, in order

**1. The entity was renamed.** Sometimes only in capitalisation, which is the kind of
difference that survives a code review and fails at runtime. `Orion.VIM.LUNs` became
`Orion.VIM.Luns`, and there is no rule to apply instead of looking it up, because
`Orion.SRM.LUNs` is a different entity in a different module and that spelling is correct.

**2. The entity moved namespace.** `Orion.NPM.UCSBlades` is now `Orion.UCS.Blades`;
`Orion.F5.Device` is now `Orion.F5.System.Device`.

**3. The module is no longer licensed or installed.** An unlicensed module's entities are
simply absent, which looks identical to a rename from the client side.

**4. A property changed type**, so a comparison that used to work now does not.

**5. A verb's positional arguments shifted.** This is the dangerous one, and the reason this
section exists. An existing call still has the right number of arguments, still passes type
checking if the types happen to align, and sends them into the wrong slots. Nothing fails.
The wrong node gets unmanaged, or the window is set with the times swapped.

### What distinguishes them

The upgrade reports in this repository classify every change between two published versions
by risk, and they call out the verb signature changes specifically because that class is
silent:

- [../reference/schema-changes-2026.1-to-2026.2.md](../reference/schema-changes-2026.1-to-2026.2.md)
- [../reference/schema-changes-2025.4-to-2026.2.md](../reference/schema-changes-2025.4-to-2026.2.md)

Generate one for any other pair of published versions:

```bash
make schema-diff FROM=2025.4 TO=2026.2
```

For a rename, `data/reference/reconciliation.json` records names that could not be resolved
against the published schema together with the closest real entity, and the offline search is
faster than any of this:

```bash
python3 tools/schema_query.py find LUN
python3 tools/schema_query.py show Orion.VIM.Luns
```

On the server, `Metadata.Entity` is the authority for the version you are actually running:

```sql
SELECT e.FullName, e.BaseType, e.CanCreate, e.CanUpdate, e.CanDelete, e.CanInvoke
FROM Metadata.Entity e
WHERE e.FullName LIKE @namePattern
ORDER BY e.FullName
```

And the retired ones say why they were retired, which is worth checking before building
anything on an entity you found in an old script:

```sql
SELECT e.FullName, e.ObsolescenceReason
FROM Metadata.Entity e
WHERE e.IsObsolete = TRUE
ORDER BY e.FullName
```

For cause 5, re-read every verb signature your automation calls, in position order, against
the version you upgraded to. The `Metadata.VerbArgument` query above does it in one pass, and
it is the only check that catches a silent reorder.

Background: [../swql/gotchas.md](../swql/gotchas.md#13-entity-names-change-between-versions)
and [../platform/versions-and-naming.md](../platform/versions-and-naming.md).

## The numbers disagree with the web console

**What you see.** A count, a total or an average from a query that does not match what the
console shows for the same thing.

### Causes, in order

**1. Account limitations.** The console is usually being read by a person with wide access
and the query is usually being run by a service account with narrow access. Both numbers are
correct for their caller. This is the first thing to check and it explains most cases.

**2. Unmanaged objects.** A query with `UnManaged = FALSE` and a console widget that does not
filter it, or the reverse, count different sets. So do `Status <> 1` and "down", because
Unmanaged is `9` and External is `11`.

**3. To-many navigation multiplying rows.** A `COUNT` over a query that dot-walks to a
to-many relationship counts the product, not the objects. Aggregate over the key you actually
mean.

**4. Unweighted averages over statistics.** Statistics rows cover different spans of time,
recorded in `Weight`, so a plain `Avg()` weights a twenty-second row the same as an hour-long
one. Sum the weighted values and divide by the summed weight instead. Recipes 15 and 25 in
[cookbook.md](cookbook.md#15-what-was-availability-over-a-window) show the shape.

**5. Different time windows.** "Today" in the console is the server's local day; your query's
window may be a rolling 24 hours on a different clock.

### What distinguishes them

Run the same query as an unlimited account and compare. If the numbers converge, it was cause
1 and there is nothing to fix in the query. If they do not, remove one clause at a time until
the two agree, and the clause you removed is your answer.

## What to capture before asking for help

Whether you are opening a support case or handing the problem to a colleague, these five
things turn a description into something diagnosable:

1. The exact request. Full URL including the port, the HTTP method, and the query or verb
   name with its arguments. Redact the credentials, not the port.
2. The exact response. Status code and raw body. Do not assume the body is JSON; SWIS
   returns a JSON error envelope containing a `Message` member, but the shape beyond that is
   not published, so paste what you actually got.
3. The account used, and its rights and limitations, from the queries in the `401` and `403`
   sections above.
4. The platform version, and whether anything was upgraded recently.
5. Whether the same call works from a different machine or as a different account. That
   single comparison separates client problems from server problems better than anything
   else on this page.

## Related pages

- [getting-started.md](getting-started.md) has a checkpoint after every step of a first
  connection
- [cookbook.md](cookbook.md) for the queries themselves
- [../swis/connecting.md](../swis/connecting.md) for ports, authentication modes and TLS
- [../swis/rest-api.md](../swis/rest-api.md#errors) for the REST error contract
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md#common-failure-modes) for verb-specific
  failures in each client
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking your own
  server rather than trusting any offline reference
- [../swql/gotchas.md](../swql/gotchas.md) for the failures that produce wrong answers
  instead of errors
- [../swql/performance.md](../swql/performance.md) for queries that are correct and too slow
- [../reference/unverified.md](../reference/unverified.md) for what this repository declines
  to assert, which is worth reading before treating any of it as authoritative
