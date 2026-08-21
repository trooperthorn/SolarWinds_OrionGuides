# Building integrations against SWIS

This page is for software that talks to SWIS on a schedule or in response to events: a
CMDB sync, a ticketing bridge, a chatops bot, an inventory exporter, a provisioning
pipeline. It is not about ad hoc queries. The guidance differs because the failure modes
differ.

An ad hoc query runs once, with a person watching, against a server that person knows. An
integration runs unattended, for years, against a server that gets upgraded, gains and
loses modules, and hands out different data depending on which account asks. Everything
below follows from that difference.

If you are writing a one-off script instead, start at
[../automation/README.md](../automation/README.md), which covers the same interfaces from
the perspective of a task you are doing once.

## What an integration has to survive

| Event | What breaks if you did not plan for it |
| --- | --- |
| A platform upgrade | An entity, property or verb you named is gone, or a verb gained an argument and your positional call now sends values into the wrong slots |
| A module is unlicensed or uninstalled | Queries against its entities start failing, and the entity is genuinely absent rather than empty |
| Someone tightens the integration's account limitation | Queries silently return fewer rows, with no error anywhere |
| The Orion server restarts mid-request | A write you cannot tell succeeded or failed |
| Your own code is restarted mid-run | Whatever "resume" means for your job has to be expressible as a query |
| The database is busy | Your slow query becomes everyone's slow query |

Each section below is one of those.

## 1. Choose the interface deliberately, once

SWIS has four interfaces and they are not interchangeable. Picking per call site produces
an integration that unmanages nodes by writing `UnManaged = true` in one place and by
calling a verb in another, which is how two code paths end up disagreeing about what the
product state actually is.

| Interface | Route | Integration uses it for | Cannot |
| --- | --- | --- | --- |
| Query | `POST /Query` | Everything you read: scope, verification, reconciliation, incremental sync | Change anything. The query interface is read only. |
| CRUD | `POST /Create/{Entity}`, then `GET`, `POST`, `DELETE` on `/{uri}` | Creating and deleting instances, and setting property values on one instance | Express an operation that is more than property assignment |
| Invoke | `POST /Invoke/{Entity}/{Verb}` | Named operations: `Unmanage`, `Remanage`, `PollNow`, `Acknowledge` | Be discovered by guessing. Argument order is the contract. |
| Bulk | `POST /BulkUpdate`, `POST /BulkDelete` | One property change or delete applied across many URIs | Report per-item results |

Three rules that matter more for a long-lived integration than for a script:

**If the operation has a name in the web console, it has a verb, and the verb does more
than the property write.** `Orion.Nodes.Unmanage` sets `UnManaged`, `UnManageFrom` and
`UnManageUntil` together and stops collection for the window. A `BulkUpdate` that sets
`UnManaged` writes one column and leaves the rest of the platform's idea of the node
inconsistent with it. See [../swis/bulk-operations.md](../swis/bulk-operations.md#when-not-to-use-bulk).

**Read the scope before you change it, and read it back afterwards.** The query is not
overhead; it is the only per-item evidence you get from `BulkUpdate` and `BulkDelete`,
which both return an empty 200.

**Everything is a POST, including reads.** `POST /Query` is a read and `POST /Invoke/...`
is a write, so no transport-level rule keyed on the HTTP method can tell them apart. That
single fact decides how retries have to be built; see
[section 7](#7-retry-safely-and-know-what-repeats-cleanly).

The full mechanics of each interface are in [../swis/rest-api.md](../swis/rest-api.md),
[../swis/crud.md](../swis/crud.md), [../swis/invoke-verbs.md](../swis/invoke-verbs.md) and
[../swis/bulk-operations.md](../swis/bulk-operations.md).

## 2. Give the integration its own account

Not a shared `admin`, not a person's account, and not the account another integration
already uses. One account per integration buys three things that are hard to retrofit:
an audit trail that names the integration, a blast radius you can describe in a sentence,
and the ability to disable exactly one thing when it misbehaves.

### Grant the narrowest set of rights

Verbs declare the right they require, so the right set is derivable rather than a matter
of taste. `Orion.Nodes.Unmanage` and `Orion.Nodes.Remanage` require the `allowUnmanage`
right; `Orion.Nodes.PollNow` requires the `manageNodes` right. Those are separate rights,
and an integration that only opens maintenance windows does not need the second one.

```bash
jq -r '.[] | select(.accessControl[]?.right == "allowUnmanage") | "\(.entity).\(.name)"' data/schema/2026.2/verbs.json
```

```text
Orion.AlertSuppression.ResumeAlerts
Orion.AlertSuppression.SuppressAlerts
Orion.Cloud.Instances.Remanage
Orion.Cloud.Instances.Unmanage
Orion.NPM.Interfaces.Remanage
Orion.NPM.Interfaces.Unmanage
Orion.Nodes.Remanage
Orion.Nodes.Unmanage
Orion.Volumes.Remanage
Orion.Volumes.Unmanage
```

That is the complete list of what `allowUnmanage` unlocks, which is a much easier thing to
put in a change request than "the integration needs permissions". The account model, the
rights, the `Orion.Accounts` verbs and the `Y`/`N` versus boolean trap are all in
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md).

### Use an account limitation as a blast radius control

An account limitation restricts the objects an account can see, and SWIS applies it to
query results on the way out. For an integration that should only touch one region or one
group, a limitation is a real containment boundary rather than a convention in your code.

It has a consequence you have to design around: **limitations are applied silently.** A
query that should return four thousand nodes returns nine hundred and no error is raised.
An integration that treats "no rows" as "nothing to do" will quietly stop working the day
someone tightens the limitation.

Give the integration a canary. Record the visible object count at startup, log it, and
alert when it moves by more than you expect:

```sql
SELECT TOP 1 COUNT(n.NodeID) AS VisibleNodes
FROM Orion.Nodes n
```

An account has exactly three limitation slots (`LimitationID1`, `LimitationID2` and
`LimitationID3` on `Orion.Accounts`), so a design that needs four distinct restrictions
has to be expressed some other way. See
[../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md#account-limitations-silently-change-query-results).

### The audit trail is the reason to keep the account distinct

Changes made through SWIS are attributed to the account that made them, which is what
turns "something unmanaged forty nodes last night" into an answerable question:

```sql
SELECT TOP 200
    a.AuditEventID,
    a.TimeLoggedUtc,
    a.AccountID,
    a.AuditEventMessage
FROM Orion.AuditingEvents a
WHERE a.AccountID = @accountId
  AND a.TimeLoggedUtc >= @since
ORDER BY a.AuditEventID DESC
```

`Orion.AuditingEvents` is covered in
[../automation/events-and-auditing.md](../automation/events-and-auditing.md).

## 3. Authentication and secret handling

SWIS REST is HTTPS with HTTP basic authentication, on port 17774 from platform release
2023.1 onward. The Swagger contract declares exactly one security definition, `basicAuth`.
That makes the account password a bearer credential in the plainest sense: anything that
can read it can be your integration.

**Never in source, never on a command line.** A password on a command line lands in shell
history and in the process table, where any local user can read it. Read it from a secret
manager where you have one, and from the environment where you do not.

**One secret per integration, rotatable without a code change.** `ChangePassword` takes
`accountId, password` and requires the `admin` right, so rotation is an operation someone
else can perform against your integration's account without touching your deployment, as
long as your deployment reads the secret at startup rather than baking it in.

**Verify TLS.** By default SWIS presents a self-signed certificate, and the tempting fix
is to turn verification off. Do not: the connection you are disabling verification on is
the one carrying a credential to your monitoring system, which in turn holds credentials
for the rest of your estate. Export the certificate once and point the client at it, or
issue SWIS a certificate from your internal CA. The commands are in
[../swis/connecting.md](../swis/connecting.md#tls-and-the-self-signed-certificate).

**Know what your client library does with credentials.** The official Python client's
constructor is
`SwisClient(hostname, username, password, port=17774, verify=False, session=None, timeout=30)`.
Two details matter here: `verify=False` is the default, and if you pass your own
`requests.Session` the constructor still overwrites that session's `auth`, `headers` and
`verify`, so you cannot use `session=` to install Kerberos or client-certificate
authentication.

**Treat `Orion.Accounts.CreateOneTimeLoginToken` as a secret too.** It is the only account
verb that returns a value, and that value is a way to sign in as the account. What it is
valid for and for how long is not recorded in the published schema and is unverified here;
confirm the behaviour on your own server before building anything on it.

## 4. One client, reused, with explicit timeouts

Create the client once for the life of the process and share it. Each new HTTPS connection
costs a TCP handshake plus a TLS handshake before a single byte of SWQL moves, and an
integration that builds a fresh connection per query spends most of its time in
handshakes.

Set both timeouts explicitly, and set them differently:

- **Connect timeout: short.** A few seconds. If the server is not answering, you want to
  know now, not in two minutes.
- **Read timeout: long enough for the slowest query you actually issue.** Aggregations
  over history entities are legitimately slow. The official Python client's default
  `timeout` is 30 seconds, which is a reasonable starting point for reads and too short
  for some reporting queries.

Never leave the read timeout unset. A request with no timeout is a thread that can hang
until the process is restarted, and the symptom presents as "the integration stopped
working" with nothing in the logs.

Keep concurrency small and deliberate. One connection issuing queries in sequence is the
right default; the database behind SWIS is shared with the polling engines and the web
console, and your fan-out competes with polling. If you do parallelise, cap it, and
serialise writes so that two workers cannot open overlapping maintenance windows on the
same node.

## 5. Bind every parameter, every time

A SWQL parameter is written `@name` in the query text and supplied as a member called
`name` in the `parameters` object.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.Status
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
  AND n.Status = @status
ORDER BY n.NodeID
```

For an integration the argument is stronger than "it is tidier". Values arriving from
another system are exactly the values that contain apostrophes, percent signs and
backslashes; a caption like `O'Brien-DC1` concatenated into query text is a syntax error,
and bound it is nothing at all. Bound values also keep their JSON types, which matters
most for dates, where the alternative is guessing at a literal format.

A set of ids goes in as one multi-valued parameter rather than as a hand-built list, and
there are no parentheses around it:

```sql
SELECT n.NodeID, n.Caption, n.Uri
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
ORDER BY n.NodeID
```

Two limits worth knowing before you design around parameters. **Parameters are values, not
fragments**: entity names and property names cannot be parameterised, so a "generic"
integration that takes an entity name from configuration is building query text and needs
to validate that name against `Metadata.Entity` rather than trusting it. And **whether
`WITH ROWS` accepts bound parameters in place of literals is not stated in the official
documentation**, so the paging code below formats integers it generated itself into the
query text, which is not user input and not an injection path.

## 6. Page large result sets

`WITH ROWS <first> TO <last>` takes a window of the result set and `WITH TOTALROWS` adds a
`totalRows` member to the response envelope carrying the count the query would have
returned without the window. Both are trailing modifiers on the SWQL statement, not REST
parameters. The bounds are 1-based and inclusive.

```sql
SELECT n.NodeID, n.Caption, n.IPAddress, n.Status, n.UnManaged
FROM Orion.Nodes n
ORDER BY n.NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

Four rules make paging correct rather than approximately correct:

1. **`ORDER BY` must be deterministic**, and ordering by the key property is the safe
   default. Without a total order, page 2 is not guaranteed to continue where page 1
   stopped, so rows can be skipped or repeated.
2. **Ask for `WITH TOTALROWS` on the first page only.** It is a count over the unwindowed
   result, so requesting it on every page pays for it on every page.
3. **There is no cursor and no snapshot.** The `QueryRequest` schema has exactly two
   members, `query` and `parameters`, so each page is an independent query against live
   data. If rows are inserted or deleted while you page, the windows shift under you.
   Where that matters, page over a stable key range instead of a row window, or accept
   that a full pass is eventually consistent and reconcile on the next run.
4. **For a set you already know, do not page at all.** Bind the ids as one multi-valued
   parameter and take the whole answer in one round trip.

### Incremental sync beats a full pass

The cheapest large query is the one you do not run. For anything append-only, keep a
watermark and query forward from it:

```sql
SELECT TOP 1000
    e.EventID,
    e.EventTime,
    e.EventType,
    e.NetObjectValue,
    e.Message
FROM Orion.Events e
WHERE e.EventID > @lastEventId
ORDER BY e.EventID
```

Watermark on the identity column rather than on the timestamp. `Orion.Events.EventTime` is
documented in the schema as "Date and time when the event occurred, displayed in local
time", so a time-based watermark inherits every timezone and daylight-saving edge in
[../swql/date-and-time.md](../swql/date-and-time.md), while `EventID` inherits none of
them. Persist the watermark only after the batch has been fully processed downstream, so
a crash re-reads a batch rather than skipping one.

## 7. Retry safely, and know what repeats cleanly

### Retry by cause, not by status family

| Outcome | Retry? | Why |
| --- | --- | --- |
| Connection refused, DNS failure, TLS failure, read timeout on a **query** | Yes, with backoff | Nothing was read; repeating is free |
| Read timeout on a **write** | No, not blindly | The write may have succeeded. Resolve it with a query, then decide |
| 500, 502, 503, 504 on a query | Yes, with backoff | Server-side and usually transient |
| 400 | No | A 400 on a query is almost always SWQL: a misspelled entity or property, or a value that should have been bound. Repeating sends the same mistake again |
| 401 | No | Credentials. Fail loudly; a retry loop against a locked-out account makes the lockout worse |
| 403 | No | A missing right, not a transient fault. See [../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md) |

Because reads and writes are both POSTs, a blanket retry policy configured on the HTTP
transport cannot distinguish them. Configure retries at the call site, where you know
which one you are making.

### Which operations survive being repeated

| Operation | Safe to repeat? | Notes |
| --- | --- | --- |
| Any query | Yes | Read only by construction |
| `Orion.Nodes.PollNow(netObjectId)` | Yes | It polls the node again. The cost is one extra poll |
| `Orion.Nodes.Remanage(netObjectId)` | Yes | Documented as "Enables polling on node if it was unmanaged before", so a second call on an already-managed node has nothing to do |
| `Orion.Nodes.Unmanage(netObjectId, unmanageTime, remanageTime, isRelative, allowOverlapping)` | **No** | See below |
| CRUD update on a URI with the same property bag | Yes | Writing the same values twice leaves the same values |
| `BulkUpdate` with the same properties and URIs | Yes | Same reasoning, and the read-back is the verification either way |
| CRUD create | **No** | The request carries no client-supplied identity, so nothing can recognise a repeat |
| CRUD delete, `BulkDelete` | Unverified | Whether a second delete of an already-deleted URI errors or succeeds quietly is not recorded in the published schema. Test it on your own server before relying on either |
| `Orion.AlertActive.Acknowledge(alertObjectIds, notes)` | Unverified | Whether re-acknowledging an acknowledged alert is a no-op or an error is not recorded in the published schema; confirm on your own server |

**`Unmanage` is the one to internalise.** Its fifth argument, `allowOverlapping`, is
optional and controls whether a window overlapping an existing one is accepted. Scheduling
a second window over an existing one is refused unless you pass `true`. So a blind retry
after a timeout is wrong in both directions: with `allowOverlapping` false the retry fails
even though the first call succeeded, and with it true the retry stacks a second window on
the node. Resolve the state instead:

```sql
SELECT n.NodeID, n.Caption, n.UnManaged, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
ORDER BY n.NodeID
```

The same shape applies to create. A create returns the URI of the new instance in the
response body and nothing else carries it, so a create whose response you never saw is in
an unknown state. Recover by querying for the object by whatever natural key you used
(caption, IP address, name) before deciding whether to create it again.

### Back off, and cap the attempts

Exponential backoff with a small jitter, a hard cap on attempts, and a dead-letter path
for what still fails. An integration that retries forever against a server that is down
turns one outage into two, because the retries arrive together the moment the server comes
back.

## 8. Respect the database you are sharing

There is one SQL Server behind SWIS and the polling engines are writing to it constantly.
Your integration's queries are not free and they are not isolated.

- **Time-bound everything historical.** Statistics, events and audit entities are the
  largest tables on the system, and an unbounded scan of one is a genuine production risk
  rather than a slow query.
- **Bound every result set** with `TOP n` or a row window, including the ones you are sure
  are small. "Sure it is small" is a statement about the installation you developed
  against.
- **Select only the columns you need.** There is no `SELECT *` in SWQL, which is a feature
  here: name the columns and the wide ones stay out of the result.
- **Ask once for many objects.** `WHERE n.NodeID IN @ids` in one round trip beats a loop
  of single-id lookups, both for you and for the server.
- **Batch bulk operations in the low hundreds.** There is no documented maximum, which is
  not the same as there being none, and a smaller batch also means a failure costs less.
- **Schedule heavy passes off peak, and make them interruptible.** A nightly full
  reconciliation that can resume from a watermark is much easier to live with than one
  that has to complete.

The measurement techniques, the rewrites, and the reasons behind each of these are in
[../swql/performance.md](../swql/performance.md).

## 9. Feature-detect, do not version-check

The obvious design is to read the platform version at startup and branch on it. It does
not work here, for a reason worth stating precisely: **the schema depends on the version
and on which modules are licensed and installed.** Two servers on the same platform
release legitimately expose different entity sets. A version comparison answers a question
you do not have.

There is also no endpoint that reports the platform release. The Swagger contract's
`info.version` is `3.0.0`, which is the service contract version, the `v3` in the base
path, not the product release.

### Ask the schema the question you actually have

`Metadata.*` exposes the schema as ordinary queryable entities, which makes every
capability question a query with an answer.

**Does this entity exist, and what may I do to it?**

```sql
SELECT FullName, BaseType, CanCreate, CanRead, CanUpdate, CanDelete, CanInvoke
FROM Metadata.Entity
WHERE FullName IN @entities
ORDER BY FullName
```

An entity missing from the result is absent from that server, which is the answer you
wanted. `CanCreate` and `CanInvoke` tell you which interfaces will accept it before you
write code against it.

**Does this verb exist, and what does it take, in what order?** This is the important one,
because arguments are positional. A release that inserts an argument in the middle of a
signature leaves your existing call with the right number of arguments and the wrong
meaning for each of them.

```sql
SELECT EntityName, VerbName, Position, Name, Type, IsOptional
FROM Metadata.VerbArgument
WHERE EntityName = @entity AND VerbName = @verb
ORDER BY Position
```

Assert at startup that the positions and names are the ones you built the call for, and
refuse to run if they are not. Failing at startup with "Orion.Nodes.Unmanage argument 3 is
`isRelative` in my code and `X` on this server" is a much better outcome than a call that
succeeds against the wrong slots.

**Does this property exist, and can I write it?**

```sql
SELECT p.Name, p.Type, p.IsKey, p.CanUpdate
FROM Metadata.Property p
WHERE p.Entity.FullName = @entity AND p.Name = @property
```

Note the join style: `Metadata.Property` and `Metadata.Verb` have no `EntityName`
property, so they are filtered through the `Entity` navigation property. Only
`Metadata.VerbArgument` carries flat `EntityName` and `VerbName` columns, which is why the
verb-argument query above needs no join.

**Does this server have this SWQL function?**

```sql
SELECT Name
FROM Metadata.Functions
WHERE Name = @functionName
```

**Which modules does the platform think it has?** This is the licensing view of the same
question, and it is the one to log at startup:

```sql
SELECT Name, LicenseName, Version, Family, IsEval, IsExpired
FROM Orion.InstalledModule
ORDER BY Name
```

`Orion.InstalledModule` declares no access restrictions in the schema, so a read-only
account can run it. The row values themselves are installation data: which row corresponds
to the platform core, and how its `Version` string relates to the release number, are not
recorded in the published schema and are unverified here. Run the query on your own server
once and read the rows before you match on any of them.

### Cache the answers, and know when to invalidate

The schema changes when a module is installed or the platform is upgraded, not between
requests, so a capability probe on every call is waste. `Metadata.Entity` publishes a verb
for exactly this:

```text
Metadata.Entity.GetSchemaLoadTime() -> string
```

It takes no arguments and reports when the server last loaded its schema, which makes it a
cheap cache-invalidation key: probe once at startup, then re-probe only when the load time
changes. It is also the thing to check after a module is licensed, because until the
schema reloads the new entities are not there to find.

### Degrade, do not crash

Once capabilities are a data structure rather than an assumption, degrading is
straightforward: skip the NCM part of the sync when `Cirrus.Nodes` is absent, fall back to
per-node updates when a bulk path is unavailable, and log at startup which optional
features are switched off and why. The failure you are avoiding is the one where an
unlicensed module takes down the half of the integration that had nothing to do with it.

## 10. A worked example

A skeleton that does the things above: one reused session, explicit timeouts, retries only
where they are safe, capability preflight at startup, paged reads, and a write path that
resolves state instead of blindly retrying.

```python
"""orion_sync.py: a resilient SWIS integration skeleton.

Reads the password from the environment, verifies TLS against a pinned certificate,
feature-detects everything it depends on at startup, and pages every read.

    SWIS_PASSWORD=... python3 orion_sync.py
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time

import requests
from requests.adapters import HTTPAdapter

BASE_PATH = "/SolarWinds/InformationService/v3/Json"
LOG = logging.getLogger("orion-sync")


class SwisError(RuntimeError):
    """A SWIS request failed. Carries the server's message where one was returned."""


class SwisPermanentError(SwisError):
    """The request will fail the same way if repeated: bad SWQL, auth, or rights."""


class Swis:
    """One long-lived client for the process.

    The session is reused so that TCP and TLS handshakes are amortised across calls,
    and both timeouts are explicit: a short connect timeout fails fast when the server
    is unreachable, and a longer read timeout tolerates a genuinely slow aggregation.

    Note what is deliberately absent: there is no retry policy on the transport
    adapter. Reads and writes are both POSTs here, so the transport cannot tell them
    apart, and a retried Invoke is not the same kind of event as a retried Query.
    Retries live at the call site instead.
    """

    def __init__(self, host, username, password, *, port=17774, ca_bundle=None,
                 connect_timeout=5.0, read_timeout=60.0):
        self.base = f"https://{host}:{port}{BASE_PATH}"
        self.timeout = (connect_timeout, read_timeout)
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # A pinned certificate, not False. This is the connection that carries a
        # credential to the system holding credentials for everything else.
        self.session.verify = ca_bundle or True
        self.session.mount("https://", HTTPAdapter(pool_connections=2, pool_maxsize=2))

    def close(self):
        self.session.close()

    # -- transport -----------------------------------------------------------------

    def _post(self, path, body):
        url = f"{self.base}/{path.lstrip('/')}"
        response = self.session.post(url, json=body, timeout=self.timeout)
        if response.status_code == 200:
            return response.json() if response.content else None

        # SWIS returns its error text in a JSON "Message" member. Do not assume the
        # body is JSON: fall back to the raw text.
        try:
            detail = response.json().get("Message", response.text)
        except ValueError:
            detail = response.text
        message = f"HTTP {response.status_code} from {url}: {detail}"
        if response.status_code in (400, 401, 403, 404):
            raise SwisPermanentError(message)
        raise SwisError(message)

    def _with_retry(self, attempts, fn):
        """Retry transport failures and 5xx. Permanent errors are raised immediately."""
        delay = 0.5
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except SwisPermanentError:
                raise
            except (SwisError, requests.RequestException) as exc:
                if attempt == attempts:
                    raise
                sleep_for = delay + random.uniform(0, delay / 2)
                LOG.warning("attempt %d/%d failed (%s); retrying in %.1fs",
                            attempt, attempts, exc, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 30.0)

    # -- read ----------------------------------------------------------------------

    def query(self, swql, **parameters):
        """Run a SWQL query. Safe to retry: the query interface cannot write."""
        body = {"query": swql}
        if parameters:
            body["parameters"] = parameters
        result = self._with_retry(4, lambda: self._post("Query", body))
        return (result or {}).get("results", [])

    def paged(self, swql, page_size=500, **parameters):
        """Yield every row of a query, one page at a time.

        The caller supplies the SELECT with its ORDER BY and no row window; this
        appends the window. Order by a key property: without a deterministic order
        there is no guarantee that page 2 continues where page 1 stopped.

        The window bounds are integers this function generated, never external input,
        so formatting them into the text is not an injection path. Whether WITH ROWS
        accepts bound parameters is not documented, which is why they are literals.
        """
        first = 1
        total = None
        body = {"query": None, "parameters": parameters or {}}
        while True:
            last = first + page_size - 1
            window = f" WITH ROWS {first} TO {last}"
            if total is None:
                window += " WITH TOTALROWS"      # first page only: it costs a count
            body["query"] = swql.rstrip().rstrip(";") + window
            payload = self._with_retry(4, lambda: self._post("Query", dict(body)))
            rows = (payload or {}).get("results", [])
            if total is None:
                total = (payload or {}).get("totalRows", len(rows))
                LOG.info("paging %d row(s) in pages of %d", total, page_size)
            yield from rows
            first += page_size
            if not rows or first > total:
                return

    # -- write ---------------------------------------------------------------------

    def invoke(self, entity, verb, args, *, idempotent=False):
        """Invoke a verb. Arguments are POSITIONAL: the order is the whole contract.

        Retried only when the caller states the verb is safe to repeat. A timed-out
        write is not a failed write, and the correct recovery is a query, not a
        second attempt.
        """
        call = lambda: self._post(f"Invoke/{entity}/{verb}", list(args))
        return self._with_retry(3, call) if idempotent else call()


# -- capability preflight -----------------------------------------------------------

ENTITIES_NEEDED = ["Orion.Nodes", "Orion.NodesCustomProperties"]
ENTITIES_OPTIONAL = ["Cirrus.Nodes"]

# What this integration believes it is calling. Checked against the server at startup,
# because arguments are positional: an inserted argument leaves a call with the right
# number of values and the wrong meaning for each one.
VERBS_NEEDED = {
    ("Orion.Nodes", "Unmanage"): ["netObjectId", "unmanageTime", "remanageTime",
                                  "isRelative", "allowOverlapping"],
    ("Orion.Nodes", "Remanage"): ["netObjectId"],
}


def preflight(swis):
    """Return the set of capabilities present, or raise if a required one is missing."""
    wanted = ENTITIES_NEEDED + ENTITIES_OPTIONAL
    rows = swis.query(
        "SELECT FullName, CanCreate, CanRead, CanUpdate, CanInvoke "
        "FROM Metadata.Entity WHERE FullName IN @entities ORDER BY FullName",
        entities=wanted,
    )
    present = {row["FullName"] for row in rows}

    missing = [name for name in ENTITIES_NEEDED if name not in present]
    if missing:
        raise SystemExit(f"required entities absent from this server: {', '.join(missing)}")
    for name in ENTITIES_OPTIONAL:
        if name not in present:
            LOG.warning("optional entity %s absent; that part of the sync is disabled", name)

    for (entity, verb), expected in VERBS_NEEDED.items():
        rows = swis.query(
            "SELECT Position, Name, Type, IsOptional FROM Metadata.VerbArgument "
            "WHERE EntityName = @entity AND VerbName = @verb ORDER BY Position",
            entity=entity, verb=verb,
        )
        actual = [row["Name"] for row in rows]
        if not actual:
            raise SystemExit(f"{entity}.{verb} does not exist on this server")
        if actual[:len(expected)] != expected:
            raise SystemExit(
                f"{entity}.{verb} signature changed: expected {expected}, server says {actual}"
            )

    schema_loaded = swis.invoke("Metadata.Entity", "GetSchemaLoadTime", [], idempotent=True)
    LOG.info("schema last loaded at %s; capabilities: %s",
             schema_loaded, ", ".join(sorted(present)))
    return present


# -- the work ------------------------------------------------------------------------

NODES_IN_SCOPE = """
SELECT n.NodeID, n.Caption, n.IPAddress, n.Status, n.UnManaged, n.Uri
FROM Orion.Nodes n
WHERE n.Vendor = @vendor
ORDER BY n.NodeID
"""

WINDOW_STATE = """
SELECT n.NodeID, n.Caption, n.UnManaged, n.UnManageFrom, n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
ORDER BY n.NodeID
"""


def visible_node_count(swis):
    """The account-limitation canary. Log it every run and alert when it moves."""
    rows = swis.query("SELECT TOP 1 COUNT(n.NodeID) AS VisibleNodes FROM Orion.Nodes n")
    return rows[0]["VisibleNodes"] if rows else 0


def open_window(swis, node_id, start_utc, end_utc):
    """Open a maintenance window, resolving state rather than retrying blindly.

    Unmanage is not safe to repeat: a second window over an existing one is refused
    unless allowOverlapping is true, and with it true a retry stacks a second window.
    So the write is issued once, and any uncertainty is settled with a query.
    """
    try:
        swis.invoke(
            "Orion.Nodes", "Unmanage",
            [f"N:{node_id}", start_utc, end_utc, False, False],
            idempotent=False,
        )
    except SwisPermanentError:
        raise
    except (SwisError, requests.RequestException) as exc:
        LOG.warning("Unmanage on node %s did not return cleanly (%s); checking state",
                    node_id, exc)

    rows = swis.query(WINDOW_STATE, ids=[node_id])
    if not rows or not rows[0]["UnManaged"]:
        raise SwisError(f"node {node_id} is not unmanaged after the call")
    LOG.info("node %s unmanaged from %s until %s",
             node_id, rows[0]["UnManageFrom"], rows[0]["UnManageUntil"])


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    password = os.environ.get("SWIS_PASSWORD")
    if not password:
        sys.exit("SWIS_PASSWORD is not set. Do not pass the password on the command line.")

    swis = Swis(
        os.environ["SWIS_HOST"],
        os.environ["SWIS_USER"],
        password,
        ca_bundle=os.environ.get("SWIS_CA_BUNDLE"),
    )
    try:
        preflight(swis)
        LOG.info("account can see %d node(s)", visible_node_count(swis))

        for row in swis.paged(NODES_IN_SCOPE, page_size=500, vendor="Cisco"):
            LOG.debug("node %s %s %s", row["NodeID"], row["Caption"], row["IPAddress"])
            # ... reconcile the row against the other system here ...
    finally:
        swis.close()


if __name__ == "__main__":
    main()
```

Three details in that file are the ones worth copying rather than the structure:

- `SwisPermanentError` exists so that the retry helper can tell "the server is having a
  moment" from "my SWQL is wrong". Without the distinction, a typo in a query becomes four
  identical failed requests and a confusing log.
- `preflight` compares the **argument names in position order** against what the code
  believes, and exits rather than guessing. That is the check that catches the upgrade
  that reordered a signature, which is the failure this platform produces silently.
- `open_window` treats a failed write as an unknown outcome and resolves it with a query.
  That pattern generalises to every non-idempotent operation here.

## Before you ship

- [ ] The integration has its own Orion account, with only the rights its verbs declare.
- [ ] The account's limitations, if any, are documented, and the visible-object count is
      logged every run.
- [ ] The password comes from the environment or a secret manager, never from source or a
      command line, and is read at startup so it can be rotated without a deploy.
- [ ] TLS verification is on, against a pinned certificate or an internal CA.
- [ ] One client object per process, with explicit connect and read timeouts.
- [ ] Every value in every query is bound, and every result set is bounded.
- [ ] Every historical query is time-bounded.
- [ ] Retries are at the call site, distinguish permanent from transient, back off, and
      cap.
- [ ] Non-idempotent writes recover by querying state, not by repeating.
- [ ] Startup asserts every entity, verb and verb signature the code depends on, and logs
      the optional features it is switching off.
- [ ] Every query was validated before it shipped:
      `python3 tools/validate_swql.py your-file.py`.

## Where to go next

- [../swis/rest-api.md](../swis/rest-api.md) for the request and response contract in full
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for the whole
  `Metadata.*` surface, which is what section 9 is built on
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the positional argument contract
  and per-client argument encoding
- [../swis/bulk-operations.md](../swis/bulk-operations.md) for batch sizing and why the
  read-back is part of the operation
- [../swql/performance.md](../swql/performance.md) for the query patterns that keep you off
  the database's critical path
- [../automation/accounts-and-permissions.md](../automation/accounts-and-permissions.md)
  for rights, limitations and the account model
- [../reference/glossary.md](../reference/glossary.md) for any term on this page you would
  rather look up than infer

Official upstream sources:

- [About SWIS](https://solarwinds.github.io/OrionSDK/docs/about-swis/)
- [REST](https://solarwinds.github.io/OrionSDK/docs/rest/)
- [Orion SDK wiki](https://github.com/solarwinds/OrionSDK/wiki)
