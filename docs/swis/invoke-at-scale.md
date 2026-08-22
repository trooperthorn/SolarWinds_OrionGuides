# Invoke at scale, and how it goes wrong

[invoke-verbs.md](invoke-verbs.md) is the contract: how a verb is called, how arguments
serialise, how to discover a signature. [verb-catalog.md](verb-catalog.md) is the menu. This
page is about what happens when you point that at a production estate and let it run.

Invoke is the only interface that expresses a named operation, and it is under-used for a
reason that is worth naming: **it is the least guarded thing in SWIS.** A query cannot break
anything. A CRUD write touches one row and you have its URI. A verb can be a single call with
no arguments that acts on everything.

Everything below is derived from the 2026.2 contract in `data/`, and the numbers are
reproducible from it.

## The shape of the surface

| Of 1021 verbs | Count | Why it matters |
| --- | ---: | --- |
| Return `System.Void` | 355 | Nothing comes back. Success and silence are the same value |
| Take no parameters at all | 173 | Nothing scopes them. Whatever they act on is implicit |
| Take at least one array argument | 252 | The caller chooses the blast radius |
| Take **only** an array argument | 61 | One call, arbitrary width, no other scoping |
| Have a destructive-sounding name | 142 | `Delete`, `Remove`, `Clear`, `Purge`, `Reset`, `Disable`, and friends |
| Declare **no right** at the verb level | 692 | Two thirds of them. See below |
| Take 10 or more parameters | 51 | Positional, so a mis-ordered call is a silent wrong action |

The widest verb takes **23 parameters**, all positional. Argument names never travel on the
wire, so nothing about a 23-argument call is self-describing at the point of failure.

Reproduce any of that:

```bash
python3 tools/schema_query.py stats
```

## Authorization is thinner than it looks

**692 of the 1021 verbs declare no right of their own.** That does not mean they are open, and
it does not mean they are closed — it means the answer is somewhere else, and you have to look
at two levels to find it.

| Where the gate is | Verbs |
| --- | ---: |
| The verb declares a right | 329 |
| The verb declares none, the entity gates `invoke` | 363 |
| The verb declares none **and** the entity gates nothing | 266 |
| Contract-only, no entity record to check | 63 |

**266 verbs have no declared authorization at either level.** `Cirrus.ApproveQueue` is a
whole entity in that position: `AddRequest`, `ApproveRequest`, `DeclineRequest`,
`DeleteRequest`, `SetApprovalMode` and `UpdateApprovalUsers` all sit there — the approval
workflow for config changes, with nothing in the contract saying who may drive it.

Read that carefully. It is a statement about **the published contract**, not a claim that the
server enforces nothing. The platform has authorization mechanisms the SWIS contract does not
model — NCM's own role system is the clearest case, and several verb summaries name it in
prose ("For valid Orion user with at least WebViewer NCM role") while declaring no SWIS right
at all. **This repository can verify the contract and cannot verify the server.** Where the
two might disagree, test on a system you can afford to be wrong about.

The practical rule stands either way: **check both levels before you assume a verb is safe to
expose**, and never infer a verb's rights from the entity's CRUD rights. They differ in both
directions. [dependencies.md](../automation/dependencies.md) has CRUD on `manageNodes` and its
verbs on `admin`; [api-pollers.md](../polling/api-pollers.md) has the reverse.

## The four dangerous shapes

A verb is worth extra care when it has any of these, and needs a review when it has several.

**No parameters.** Nothing you pass scopes it. 173 verbs are in this position. Most are
harmless getters, and a few are not.

**Only an array argument.** 61 verbs. The array is the entire scope, so the blast radius is
exactly whatever your script put in it — including whatever it put in it by accident.

**A `System.Void` return.** 355 verbs. You get no id, no count, no per-item result. A verb
that did nothing and a verb that did everything return the same thing.

**A destructive name.** 142 verbs.

Twelve verbs have three of the four at once — an array in, nothing out, and a destructive
name:

```bash
python3 tools/schema_query.py verb Cirrus.ConfigArchive DeleteConfigs
```

| Verb | Right |
| --- | --- |
| `Cirrus.ConfigArchive.DeleteConfigs` | none declared |
| `Cirrus.Nodes.DeleteEOSData` | none declared |
| `Cirrus.Settings.DeleteRegExPatterns` | none declared |
| `NCM.FirmwareDefinitions.DeleteFirmwareDefinitions` | none declared |
| `NCM.FirmwareOperations.DeleteFirmwareOperations` | none declared |
| `NCM.FirmwareStorage.DeleteFirmwareImages` | none declared |
| `Orion.Container.DeleteDefinitions` | none declared |
| `Orion.SRM.BusinessLayer.DeleteArrays` | none declared |
| `Orion.SRM.BusinessLayer.DeleteCredentials` | none declared |
| `Orion.ADM.NodeInventory.Disable` | `manageNodes` |
| `Orion.AssetInventory.Polling.DisablePollingForNodes` | `manageNodes` |
| `Orion.HardwareHealth.HardwareItemThreshold.ClearThresholds` | `manageNodes` |

Nine of the twelve declare no right at the verb level.

## The verb that deletes nodes over licence

One verb deserves its own section, because it is the clearest example of every property above
in one place:

```bash
python3 tools/schema_query.py verb Cirrus.Nodes DeleteOverLicenseNodes
```

```text
Cirrus.Nodes.DeleteOverLicenseNodes
  Deletes random nodes which are above the current licence.
            For valid Orion user with at least WebViewer NCM role.
  returns: System.Void
  REST:    POST /Invoke/Cirrus.Nodes/DeleteOverLicenseNodes
  parameters: none
```

That summary is SolarWinds' own, quoted verbatim. It takes no arguments, returns nothing, and
the prose names the lowest NCM role as sufficient. The entity itself grants `read,invoke` to
`everyone`:

```bash
python3 tools/schema_query.py show Cirrus.Nodes
```

### "Random" is misleading, and the real rule is worse

The summary says *random*. It is not. Licence limitation on this platform is applied in
**primary key order**, so the nodes counted as being over licence are the ones with the
**highest `NodeID` values** — and `Orion.Nodes.NodeID` is a `System.Int32` that increments as
nodes are added.

The set this verb deletes is therefore **the most recently added nodes**. That is worse than
random, not better: the newest nodes are the ones somebody has just onboarded, the ones a
migration script has just created, and the ones least likely to be in a backup taken before
the work started.

It also means the at-risk set is knowable in advance rather than a matter of chance.
`Cirrus.NCMNodeLicenseStatus` names it directly — two columns, one of which is the answer:

```sql
SELECT
    ls.NodeID,
    ls.LicensedByNCM,
    ls.OrionNode.Caption,
    ls.OrionNode.IPAddress
FROM Cirrus.NCMNodeLicenseStatus ls
WHERE ls.LicensedByNCM = 'No'
ORDER BY ls.NodeID DESC
```

Every row that comes back is a node this verb would remove. Run it before anyone runs the
verb, and run it after onboarding a batch of devices, because that is exactly when the answer
changes.

The estate-wide position is on `Orion.Licensing.UtilizationSummary`:

```sql
SELECT
    us.ElementTypeID,
    us.Used,
    us.LicenseSize,
    us.Remaining,
    us.Overage,
    us.HasOverage,
    us.Saturation
FROM Orion.Licensing.UtilizationSummary us
ORDER BY us.Saturation DESC
```

`HasOverage` is the flag that says a delete would find something to do, and `Overage` is how
many. Alert on the first and you get warning before the licence position becomes somebody's
cleanup decision.

The primary-key ordering is **operational behaviour of the licensing system, not something the
schema states**, and the deletion order the verb actually uses is not recorded anywhere in the
contract. Both are unverified here. What the schema does give you is the two queries above,
which describe the same set from the licensing side without depending on the verb's internals.

### Why it is the worst shape in the contract

No scope to get wrong, no confirmation to read, no result to check, and a set that changes
every time somebody adds a device. A script that calls it cannot know what it did, and a query
afterwards can only tell you what is gone by comparing against a list you took first — which
is the argument for taking that list on a schedule rather than at the moment you need it.

`Cirrus.Nodes.DeleteAllVulnerabilityData` is the same shape with a smaller radius, and its
summary adds that the verb "will be removed in a future version of the product" — so it is
both destructive and deprecated.

**Treat the no-parameter destructive verbs as a review list, not a reference.** There are nine.

## Automation runaways

These are the failure modes that turn a working script into an incident. Each one is a real
property of the interface rather than a hypothetical.

### The scope that re-derives itself

The most common one, and the least dramatic-looking.

```text
1. Query for nodes matching a condition.
2. For each, invoke a verb that changes whether the condition holds.
3. Loop.
```

If step 2 changes what step 1 matches, the second pass has a different set. If it changes it
the other way, the set never empties and the loop never ends. A script that unmanages nodes
that are down, then re-queries for nodes that are down, is fine; a script that acts on nodes
*not* in maintenance and puts them into maintenance will terminate, and one that acts on
nodes in an alerting state while its action clears the alert will oscillate.

**Take the scope once, into a list, and iterate the list.** Never re-query inside the loop.
This is the same rule [../automation/README.md](../automation/README.md) states for writes
generally, and Invoke is where it bites hardest because a verb can change more than the
property you filtered on.

### The retry storm

355 verbs return `System.Void`. A timeout on one of them is genuinely ambiguous: the call may
have succeeded and the response been lost, or it may never have run.

A retry loop that treats every timeout as "did not happen" will re-invoke, and for a verb that
is not idempotent that is a second real action. `Orion.Nodes.PollNow` retried is a wasted
poll. `Cirrus.ConfigArchive.ExecuteScript` retried is the script running twice on the device.

**Classify before you retry**, and see the idempotency table below. When a verb is not safely
repeatable and the outcome is ambiguous, the correct move is to stop and query, not to try
again.

### The poll storm

`Orion.Nodes.PollNow` takes one `netObjectId` and returns `System.Void`. There is no bulk
form. So "poll everything" is a loop, and a loop with no delay issues as many requests as it
can.

The polling engines have a fixed capacity that
[../platform/architecture.md](../platform/architecture.md) describes, and an on-demand poll
competes with scheduled polling for it. A script that walks ten thousand nodes as fast as the
API accepts calls does not fail — it degrades the thing it is monitoring, and the symptom is
polling latency across the estate rather than an error in your script.

The same applies to the 21 verbs gated on `allowRealTimePolling`, which exist precisely
because real-time polling is expensive enough to need its own right.

### The array you built wrong

61 verbs take an array as their only argument. The array is the scope, so an off-by-one in the
query that built it is an off-by-one in what gets deleted.

Two specific ways this goes wrong:

- **A query that returned everything** because a `WHERE` clause compared against `NULL` and
  matched differently than you assumed. See [../swql/gotchas.md](../swql/gotchas.md).
- **A client that splatted the array**, so what you meant as one argument of many elements
  arrived as many arguments. That one usually errors, but see the single-array-argument
  pitfall in [invoke-verbs.md](invoke-verbs.md#the-single-array-argument-pitfall) — when the
  verb takes exactly one array parameter it can also silently do the wrong thing.

**Count the array before you pass it, and compare the count to what you expected.** A hard
numeric bound is the cheapest control there is.

### The account that could do more than the task needed

An automation account provisioned with `admin` because a right was hard to work out will
happily invoke all 161 `admin` verbs, not just the one you tested. The account is the blast
radius when the script has a bug.

[../guides/building-integrations.md](../guides/building-integrations.md#grant-the-narrowest-set-of-rights)
covers provisioning; the Invoke-specific part is that **an account limitation does not
constrain a verb the way it constrains a query**. Limitations scope what the account can
*see*. Whether they scope what a verb can *act on* is **not stated in the schema and is
unverified here** — do not rely on a limitation as a safety control for Invoke without testing
it.

## Scaling a script for an external tool

### There is no bulk Invoke

`BulkUpdate` and `BulkDelete` exist for CRUD; see
[bulk-operations.md](bulk-operations.md). **There is no equivalent for verbs.** The only
batching Invoke offers is a verb that happens to take an array, and that is a property of the
individual verb rather than of the interface.

So the shape of any Invoke automation over many objects is a loop, and everything below is
about making that loop safe to run unattended.

### Classify every verb you call

Before a verb goes into an unattended script, answer three questions about it:

| Question | How to answer |
| --- | --- |
| Is it idempotent? | Does calling it twice differ from calling it once? |
| Is the result observable? | Is there a query that shows whether it worked? |
| What is its scope? | Which arguments bound it, and what happens if one is empty? |

The third question has a specific trap: **an empty array is not always a no-op.** Whether a
verb given an empty list does nothing or does everything is not stated anywhere in the
contract, and it is **unverified here**. Guard the call rather than the verb:

```python
if not ids:
    return 0            # never invoke with an empty scope
```

Broad idempotency classes, as a starting point rather than an answer:

| Class | Examples | Retry safe |
| --- | --- | --- |
| Set a state | `Unmanage`, `Remanage`, `Disable` | Usually yes — the second call sets the same state |
| Trigger an action | `PollNow`, `ExecuteScript`, `TestAlertingAction` | No — the action happens again |
| Create | `AddNodes`, `CreateCustomProperty`, `AddSnippet` | No — usually creates a duplicate |
| Delete by id | `DeleteSnippets`, `DeleteConfigs` | Usually yes — the second call finds nothing |
| Acknowledge | `Orion.AlertActive.Acknowledge` | Usually yes |

"Usually" is doing real work in that table. None of it is stated in the schema; it is inferred
from what the verbs do and is **unverified here**. Test the specific verb.

### Throttle deliberately

Pick a rate and hold to it rather than running as fast as the API allows. A serial loop with a
small delay is the right default, and it is fast enough for almost everything:

```python
import time

RATE_PER_SECOND = 5
interval = 1.0 / RATE_PER_SECOND

for node_id in scope:
    swis.invoke("Orion.Nodes", "PollNow", f"N:{node_id}")
    time.sleep(interval)
```

Concurrency is rarely worth it here. The work happens on the polling engines, not in the API
call, so parallel Invoke calls queue work faster without completing it faster —
and they make the failure mode harder to reason about.

### Checkpoint, so a rerun is not a redo

An unattended script that dies halfway through 4,000 non-idempotent calls has left the estate
in a state nobody wrote down. Record progress as you go:

```python
import json, os

def run(scope, state_path):
    done = set()
    if os.path.exists(state_path):
        with open(state_path) as fh:
            done = set(json.load(fh))

    for node_id in scope:
        if node_id in done:
            continue
        swis.invoke("Orion.Nodes", "PollNow", f"N:{node_id}")
        done.add(node_id)
        with open(state_path, "w") as fh:
            json.dump(sorted(done), fh)
```

Writing the file every iteration is deliberate. A crash between the call and the record is the
case the checkpoint exists for, and buffering the writes reintroduces it.

### Verify with a query, not with the response

This is the rule that makes the rest work. For 355 verbs the response tells you nothing at
all, and for the rest it tells you less than a read-back does.

```sql
SELECT
    n.NodeID,
    n.Caption,
    n.UnManaged,
    n.UnManageFrom,
    n.UnManageUntil
FROM Orion.Nodes n
WHERE n.NodeID IN @ids
```

Take the same scope you acted on, query the property you changed, and compare. Three numbers
are worth logging on every run: **intended**, **invoked**, **confirmed**. When the third is
lower than the second you have found a real problem, and no exception was raised to tell you.

### Bound the blast radius numerically

```python
MAX_PER_RUN = 500

if len(scope) > MAX_PER_RUN:
    raise SystemExit(
        f"scope is {len(scope)} objects, limit is {MAX_PER_RUN}; "
        f"re-run with an explicit override if this is intended"
    )
```

A ceiling that a human has to raise deliberately is the control that catches the `WHERE`
clause that matched the whole estate. Set it to a little above the largest run you expect, not
to the size of the estate.

### Dry run by default

Make the destructive step opt-in, and print what would happen without it. SolarWinds' own
`Update.Captions.ps1` sample ships with the write line commented out for exactly this reason.
In PowerShell, `[CmdletBinding(SupportsShouldProcess)]` gives you `-WhatIf` for free.

## Gotchas

**A verb's rights are not its entity's rights.** Check both, in both directions.

**`System.Void` means you must read back.** It is not a signal of success.

**Argument names never travel.** Order is the whole contract, and 51 verbs take ten or more
positional arguments. Look the signature up for the version you are running, every time.

**An optional trailing argument may be omitted, a middle one may not.** See
[invoke-verbs.md](invoke-verbs.md#optional-trailing-arguments-may-be-omitted).

**A verb summary may name a role the SWIS contract does not model.** NCM's WebViewer,
Engineer and Administrator roles appear in verb prose and in no `accessControl` block.

**An empty array argument is undefined behaviour** as far as the contract goes. Guard it.

**Account limitations scope what an account sees.** Whether they scope what a verb acts on is
unverified here.

**Nothing rate-limits you.** The interface will accept calls faster than the platform can act
on them, and the consequence lands on polling rather than on your script.

## See also

- [invoke-verbs.md](invoke-verbs.md) — the calling contract, serialisation, discovery and
  access control
- [verb-catalog.md](verb-catalog.md) — the verbs worth knowing, grouped by task
- [bulk-operations.md](bulk-operations.md) — `BulkUpdate` and `BulkDelete`, which are CRUD and
  not Invoke
- [../guides/building-integrations.md](../guides/building-integrations.md) — accounts, secrets,
  retries and paging for an integration generally
- [../automation/README.md](../automation/README.md) — write the SELECT first, and make it the
  scope
- [../platform/architecture.md](../platform/architecture.md) — why an on-demand poll competes
  with scheduled polling
