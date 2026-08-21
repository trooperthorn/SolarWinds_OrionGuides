# Accounts, rights and account limitations

Everything you read or write through SWIS happens as some account, and that account changes
what the same query returns. This page covers the account model, the rights that gate verbs,
and account limitations, which are the part that surprises people because they change results
without raising an error.

If you only read one section, read
[Account limitations silently change query results](#account-limitations-silently-change-query-results).
It explains most reports of "the API returns nothing but the web console shows the node".

Grounded in SolarWinds'
[Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/) page and
in the extracted 2026.2 schema.

## The account model

The platform recognises three categories of account, and the distinction is about where the
identity lives rather than about what it can do.

| Category | Where the identity lives | How it authenticates |
| --- | --- | --- |
| Orion account | The Orion database only | The database stores a salted hash of the password |
| Windows or Active Directory account | A local Windows account on the Orion server, or AD | Windows authentication, once the account is authorised in Orion |
| SAML account | An external identity provider | The IdP asserts the identity; Orion maps the claim to an account |

The default `admin` and `guest` accounts created with a new database are Orion accounts.

For Windows and SAML, both individual accounts and **group** accounts are supported. When a
group is authorised, any member of that group can sign in. Members inherit the group's
permissions but get their own storage for preferences, so two people signing in through the
same group share rights and limitations while keeping separate home pages.

SolarWinds' own recommendation is worth repeating: where Active Directory or SAML integration
fits your environment, authorise a small set of directory groups and do the day to day
membership management in the directory, rather than creating one Orion account per person.
That keeps joiners and leavers in one system instead of two. The setup is documented for
[Active Directory](https://support.solarwinds.com/Success_Center/Network_Performance_Monitor_(NPM)/Network_Performance_Monitor_Getting_Started_Guide/060_User_accounts/030_Use_Active_Directory_credentials_for_users)
and for
[SAML](https://documentation.solarwinds.com/en/Success_Center/orionplatform/Content/core-users-SAML-authentication.htm).

## `Orion.Accounts`

One entity holds every account, of every category.

```bash
python3 tools/schema_query.py show Orion.Accounts
```

It declares 39 properties. The ones that matter for automation fall into four groups.

**Identity**

| Property | Type | Notes |
| --- | --- | --- |
| `AccountID` | `System.String` | The username, and the key every account verb takes |
| `AccountType` | `System.Int32` | Which category the account belongs to |
| `AccountSID` | `System.String` | The Windows or directory security identifier, for non-Orion accounts |
| `GroupInfo` | `System.String` | Group membership information for accounts authorised through a group |
| `GroupPriority` | `System.Int16` | Which group's settings win when an account matches several |

**Rights**

`AllowAdmin`, `AllowNodeManagement`, `AllowUnmanage`, `AllowAlertManagement`,
`AllowReportManagement`, `AllowMapManagement`, `AllowOrionMapsManagement`,
`AllowUploadImagesToOrionMaps`, `AllowCustomize`, `AllowManageDashboards`,
`AllowDisableAction`, `AllowDisableAlert`, `AllowDisableAllActions`, `AllowViewCopCheck` and
`CanClearEvents`.

**Account state**

`Enabled`, `Expires`, `LockoutTime`, `BadPwdCount`, `LastLogin` and
`PasswordExpirationDate`. The schema documents the last of those: "If a password expires, it
must be changed or reset to login successfully."

**Limitations**

`LimitationID1`, `LimitationID2` and `LimitationID3`. Three slots, no more. See
[Account limitations](#account-limitations-silently-change-query-results).

### Reading a right gives you `Y` or `N`, writing one takes a boolean

This is the single most common mistake when scripting account changes, and SolarWinds calls
it out on their own page. The `AllowXYZ` properties and `CanClearEvents` are declared as
`System.String` and `System.Char`, and a query returns `"Y"` or `"N"`:

```sql
SELECT a.AccountID, a.AllowAdmin, a.AllowNodeManagement
FROM Orion.Accounts a
WHERE a.AccountID = @accountId
```

When you set them through `UpdateAccount`, you pass a **boolean**: `true` or `false` in JSON,
`$true` or `$false` in PowerShell. Passing the string `"Y"` back is not the round trip it
looks like.

### `AccountType`

`AccountType` is an integer. SolarWinds' account-management page documents four of the values
because the create verbs take them as arguments:

| Value | Meaning | Documented by |
| ---: | --- | --- |
| 2 | Windows user | `CreateWindowsAccount` parameter documentation |
| 3 | Windows group | `CreateWindowsAccount` parameter documentation |
| 5 | SAML user | `CreateSamlAccount` parameter documentation |
| 6 | SAML group | `CreateSamlAccount` parameter documentation |

The value an Orion-only account carries is **not recorded in the published schema** and is
unverified here. Ask your own server rather than assuming:

```sql
SELECT a.AccountType, COUNT(a.AccountID) AS Accounts
FROM Orion.Accounts a
GROUP BY a.AccountType
ORDER BY a.AccountType
```

Cross-reference a few `AccountID` values you recognise against the categories you know they
belong to, and the mapping falls out in one pass.

## The account verbs

All ten verbs on `Orion.Accounts` require the `admin` right. That is consistent with
SolarWinds' statement that "all operations except querying accounts require the `AllowAdmin`
user right".

| Verb | Parameters, in order | Returns |
| --- | --- | --- |
| `CreateOrionAccount` | `accountID`, `password` | `System.Void` |
| `CreateWindowsAccount` | `accountType`, `userOrGroupName`, `adminUser` *(optional)*, `adminPassword` *(optional)* | `System.Void` |
| `CreateSamlAccount` | `accountType`, `userOrGroupName` | `System.Void` |
| `CreateAccount` | `accountType`, `properties` | `System.Void` |
| `CreateVirtualAccount` | `accountID`, `highestPriorityGroupName`, `groupAccountTypeId` | `System.Void` |
| `UpdateAccount` | `accountID`, `properties` | `System.Void` |
| `DeleteAccount` | `accountID` | `System.Void` |
| `ChangePassword` | `accountId`, `password` | `System.Void` |
| `ResetPassword` | `accountId` | `System.Void` |
| `CreateOneTimeLoginToken` | `accountId` | `string` |

Two naming details to know before you generate a client from the contract. The schema spells
the SAML verb `CreateSamlAccount`, while SolarWinds' prose writes it `CreateSAMLAccount`; the
schema spelling is what the REST path uses. And the parameter is `accountID` on
`CreateOrionAccount`, `CreateVirtualAccount` and `UpdateAccount` but `accountId` on
`ChangePassword`, `ResetPassword` and `CreateOneTimeLoginToken`. Neither matters to a
positional caller, because **argument names never travel on the wire**, but both matter to
anything that generates named parameters from the Swagger contract.

### Creating an account

```powershell
Invoke-SwisVerb $swis 'Orion.Accounts' 'CreateOrionAccount' @('reporting-svc', $plaintext)
```

A new account is created "with minimal user rights but no account limitations": it can see
every object and change nothing. That default is the safe one, and it means the second half of
provisioning is always an `UpdateAccount` call.

For a Windows or Active Directory account, `accountType` is `2` for a user and `3` for a
group, and `userOrGroupName` uses `domain\username` form. The optional `adminUser` and
`adminPassword` exist for the case where the Orion services themselves cannot query Active
Directory; supply a directory account that can. The `accountID` of the resulting account is
the `userOrGroupName` you passed.

```powershell
Invoke-SwisVerb $swis 'Orion.Accounts' 'CreateWindowsAccount' @(3, 'EXAMPLE\NOC-Operators')
```

### Updating rights

```bash
python3 tools/schema_query.py verb Orion.Accounts UpdateAccount
```

```text
Orion.Accounts.UpdateAccount
  Updates properties of the specified Account with provided values.
  returns: System.Void
  REST:    POST /Invoke/Orion.Accounts/UpdateAccount
  requires: admin
  parameters (2):
    accountID: string (required)
        Required. Account ID as defined in Orion.Accounts.
    properties: array<System.Collections.Generic.KeyValuePair~System.String_System.Object~> (required)
        Required. A non-empty dictionary of name-value pairs that specify which properties to update.
```

The dictionary carries only the properties you want to change; anything you leave out is left
alone. Remember the boolean rule from above.

```powershell
$rights = @{
    AllowNodeManagement = $true
    AllowUnmanage       = $true
    AllowAlertManagement = $false
    Enabled             = $true
}

Invoke-SwisVerb $swis 'Orion.Accounts' 'UpdateAccount' @('reporting-svc', $rights)
```

Over REST the same call is a positional array whose second element is the dictionary:

```json
{
  "accountID": "reporting-svc",
  "properties": { "AllowNodeManagement": true, "AllowUnmanage": true }
}
```

is **not** the body. The body is the positional array:

```json
["reporting-svc", { "AllowNodeManagement": true, "AllowUnmanage": true }]
```

See [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for the argument encoding in full.

Then verify with a query, because `UpdateAccount` returns `System.Void` and there is nothing
in the response to inspect:

```sql
SELECT a.AccountID, a.Enabled, a.AllowNodeManagement, a.AllowUnmanage, a.AllowAlertManagement
FROM Orion.Accounts a
WHERE a.AccountID = @accountId
```

### Passwords

`ChangePassword` sets a new password; `ResetPassword` sets it to empty. Neither is a way to
read anything back, and there is no verb that returns a password. `Orion.PasswordHistory`
exists and is readable only with `admin`, but it holds `PasswordHash`, `PasswordSalt` and
`PasswordProtocol`, which is history for the purpose of enforcing "do not reuse the last N",
not a credential store.

Never put a password in a script that is committed anywhere. The same rules apply here as to
polling credentials, and they are set out in [credentials.md](credentials.md#security-posture).

### `CreateOneTimeLoginToken`

The only account verb that returns a value. It requires `admin` and takes an `accountId`.
What the token is valid for, and for how long, is not recorded in the published schema and is
unverified here. Treat it as a bearer secret: it is a way to sign in as that account.

## The rights that gate verbs

Verbs declare the right they require, and a permission failure is far more often a missing
right than a bug in the call. Across 2026.2, 329 of the 958 verbs declare one.

```bash
python3 tools/schema_query.py verb Orion.Nodes PollNow
```

```text
Orion.Nodes.PollNow
  It will poll node instance and update its information
  returns: System.Void
  REST:    POST /Invoke/Orion.Nodes/PollNow
  requires: manageNodes
  parameters (1):
    netObjectId: string (required)
```

### Seeing every right, and which verbs each one gates

The rights live in `data/schema/2026.2/verbs.json`, under each verb's `accessControl` list.
Counting them gives the whole permission surface in thirteen lines:

```bash
jq -r '[.[] | .accessControl[]?.right] | group_by(.) | map({right: .[0], verbs: length}) | sort_by(-.verbs) | .[] | "\(.verbs)\t\(.right)"' data/schema/2026.2/verbs.json
```

```text
161	admin
129	manageNodes
21	allowRealTimePolling
13	manageAlerts
10	allowUnmanage
8	system
7	clearEvents
6	manageMaps
4	allowOrionMapsManagement
3	manageReports
2	everyone
1	allowCustomize
1	allowDisableAlert
```

To answer the question you actually have, which is "what does this account need in order to
run my script", list the verbs behind one right:

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

That is the complete list of things a maintenance-window script needs `allowUnmanage` for, and
it is also the argument for why that script's service account does not need `admin`.

Or go the other way and audit one entity:

```bash
jq -r '.[] | select(.entity == "Orion.Nodes") | "\(.name)\t\(.accessControl[0].right // "none declared")"' data/schema/2026.2/verbs.json
```

```text
GetCountOfElementsPerEngineForLicensing	manageNodes
GetListResourcesResult	manageNodes
GetListResourcesResultByEngine	manageNodes
GetScheduledListResourcesStatus	manageNodes
GetScheduledListResourcesStatusByEngine	manageNodes
GetSupportedMetrics	allowRealTimePolling
ImportListResourcesResult	manageNodes
ImportSelectedListResourcesResult	manageNodes
PollNow	manageNodes
PollStatusNow	manageNodes
RediscoverNow	manageNodes
Remanage	allowUnmanage
ScheduleListResources	manageNodes
ScheduleListResourcesForAddress	manageNodes
StartRealTimePolling	allowRealTimePolling
StopRealTimePolling	allowRealTimePolling
Unmanage	allowUnmanage
```

Note what that shows: node management and unmanaging are **separate** rights. An account with
`manageNodes` can repoll and rediscover but cannot open a maintenance window, and an account
with `allowUnmanage` can open one without being able to change node properties. Granting both
is a decision, not a formality.

Entity-level access control is separate from verb-level, and `show` prints it under
`operations`. `Orion.ScheduleTaskDefinition`, for example, allows create, read, update and
delete to `allowUnmanage` and `manageNodes` but reserves `invoke` for `admin`.

### Which account column corresponds to which right

The schema records the right a verb requires, and separately records the columns on
`Orion.Accounts`. It does not publish the mapping between the two. One pairing is documented
by SolarWinds directly: the account-management page states that account operations require the
`AllowAdmin` user right, and every `Orion.Accounts` verb declares `admin`. The rest of the
table below is inferred from the names and is unverified here; confirm it on your own server
by granting one right to a test account and seeing which calls start succeeding.

| Right declared by verbs | Column on `Orion.Accounts` |
| --- | --- |
| `admin` | `AllowAdmin` (documented by SolarWinds) |
| `manageNodes` | `AllowNodeManagement` |
| `allowUnmanage` | `AllowUnmanage` |
| `manageAlerts` | `AllowAlertManagement` |
| `manageReports` | `AllowReportManagement` |
| `clearEvents` | `CanClearEvents` |
| `manageMaps` | `AllowMapManagement` |
| `allowOrionMapsManagement` | `AllowOrionMapsManagement` |
| `allowCustomize` | `AllowCustomize` |
| `allowDisableAlert` | `AllowDisableAlert` |
| `allowRealTimePolling` | No corresponding column exists in 2026.2 |
| `everyone` | Any authenticated account |
| `system` | Internal. Not a user right |

`allowRealTimePolling` is worth its own note. It gates 21 verbs, including
`Orion.Nodes.StartRealTimePolling` and `Orion.Nodes.StopRealTimePolling`, but searching the
2026.2 property data for a matching account column returns nothing, so how it is granted is
**not recorded in the published schema** and is unverified here. If a real-time polling call
fails with a permission error for an account that has `AllowNodeManagement`, that gap is the
first thing to look at, and the settled answer comes from your own server:

```sql
SELECT p.Name, p.Type, p.Summary
FROM Metadata.Property p
WHERE p.Entity.FullName = 'Orion.Accounts'
ORDER BY p.Name
```

### Module roles are a separate layer

Core rights are not the whole permission model. Modules add their own, and they are not
columns on `Orion.Accounts`. NCM entity descriptions say things like "for valid Orion user
with at least WebViewer NCM role", and IPAM keeps its own per-account role assignment:

```sql
SELECT
    r.AccountID,
    r.AccountType,
    r.AllowAdmin,
    r.Admin,
    r.PowerUser,
    r.Operator,
    r.ReadOnly,
    r.NoAccess
FROM IPAM.AccountRoles r
ORDER BY r.AccountID
```

So "the account has `manageNodes`" is not sufficient to conclude that an NCM or IPAM call will
succeed. Check the module's own role model too. See [../modules/ncm.md](../modules/ncm.md) and
[../modules/ipam.md](../modules/ipam.md).

## Account limitations silently change query results

An account limitation restricts the set of objects an account can see. It is applied by SWIS
on the way out, to **query results**, not by raising an error. Two accounts running the same
SWQL text against the same server get different rows, and neither of them is told why.

That single behaviour explains a large share of "the API is broken" reports:

- A query that works in SWQL Studio as `admin` returns zero rows from a service account.
- A scheduled export that used to cover 4,000 nodes quietly covers 900 after someone tightened
  a limitation.
- A count in a report does not match the count on a dashboard, because the dashboard was
  opened by a different person.
- A `WHERE` clause looks wrong and is not, because the rows it would have matched were removed
  before the clause ever saw them.

The diagnostic habit is simple: **before debugging a query that returns too little, run a
count as the same account and as an unrestricted account, and compare.**

```sql
SELECT TOP 1 COUNT(n.NodeID) AS VisibleNodes
FROM Orion.Nodes n
```

If those two numbers differ, the problem is the account, not the query.

### How limitations are stored

| Entity | Holds |
| --- | --- |
| `Orion.Limitations` | One limitation: its type, its definition, and the generated `WhereClause` |
| `Orion.LimitationTypes` | The catalogue of limitation types, and the table and field each one filters on |
| `Orion.LimitationSnapshots` | Pre-evaluated membership: which object URIs one limitation currently resolves to |
| `Orion.ExpandedLimitations` | The expanded form of a limitation, by `LimitationID` |
| `Orion.Accounts` | `LimitationID1`, `LimitationID2`, `LimitationID3` |

Three properties matter more than the rest. `Orion.Limitations.WhereClause` is the filter the
server actually applies, which makes it the fastest way to understand what a limitation does
without reading the console. `Orion.LimitationTypes.Method` says whether the type is matched
by selection, by checkbox list or by pattern, which decides which argument
`CreateLimitation` wants. And `Orion.LimitationSnapshots` turns an abstract definition into the
concrete list of objects it currently covers, which is what you want when someone asks "so
what can this account actually see".

**An account has exactly three limitation slots.** There is no fourth. A design that needs
four distinct restrictions has to be expressed as fewer, broader ones, or through group
membership, and finding that out during a migration is worse than knowing now.

### The limitation verbs

All three require `admin`.

```bash
python3 tools/schema_query.py verb Orion.Limitations CreateLimitation
```

```text
Orion.Limitations.CreateLimitation
  Creates Limitations and optionally assignes them to Accounts.
  returns: number
  REST:    POST /Invoke/Orion.Limitations/CreateLimitation
  requires: admin
  parameters (5):
    limitationTypeID: number (required)
        required. LimitationTypeID from Orion.LimitationTypes.
    selection: string (required)
        required if Limitation is of type "Selection" as defined in Orion.LimitationTypes. A string that will be used to match one value against the Table & Field defined by corresponding Orion.LimitationType.
    checkboxItems: array<string> (required)
        required if Limitation is of type "Checkbox" as defined in Orion.LimitationTypes. An array of strings used to match multiple values against the Table & Field defined by corresponding Orion.LimitationType.
    pattern: string (required)
        required if Limitation is of type "Pattern" as defined in Orion.LimitationTypes. A string that will be used to match multiple values as a text search pattern against the Table & Field defined by corresponding Orion.LimitationType.
    accountID: string (required)
        optional. Account ID as defined in Orion.Accounts. Recommended to always specify this parameter. Advanced usage: omit this parameter to create an un-assigned Limitation, as such it will only be used if explicitly specified using "WITH LIMITATION ID" SWQL expression.
```

Read the parameter notes carefully, because the schema marks all five as required while the
prose says three of them are conditional. Only one of `selection`, `checkboxItems` and
`pattern` is meaningful for any given `limitationTypeID`, and which one depends on that type's
`Method`. Pass a null or an empty value for the other two rather than omitting them, since
the argument list is positional and dropping an element shifts everything after it.

```powershell
# Look up the type first. Never hard-code a LimitationTypeID: they are installation data.
$typeId = Get-SwisData $swis @'
SELECT TOP 1 t.LimitationTypeID
FROM Orion.LimitationTypes t
WHERE t.Name = @name
'@ @{ name = 'Group of Nodes' }

$limitationId = Invoke-SwisVerb $swis 'Orion.Limitations' 'CreateLimitation' `
    @($typeId, $null, @('EMEA-Core', 'EMEA-Edge'), $null, 'noc-emea')
```

`UpdateLimitation` takes `limitationID`, `selection`, `checkboxItems`, `pattern`, changing the
definition of an existing limitation without touching its assignment. `DeleteLimitation` takes
`limitationID` and removes the limitation from any account it was assigned to.

There is no verb for "assign this existing limitation to that account". `CreateLimitation`
assigns as it creates, through its `accountID` argument. Rebinding an existing limitation to a
different account means writing the `LimitationIDn` column on `Orion.Accounts`, and whether
`UpdateAccount` accepts `LimitationID1` in its properties dictionary is **not recorded in the
published schema** and is unverified here. Test it against a throwaway account before
depending on it.

### Limitations attach to views as well

`Orion.Views.LimitationID` and `Orion.Web.View.LimitationID` exist, so a view can carry a
limitation independently of the account looking at it. That is why a page can look narrower
than the account's own limitations would explain. When you are reconciling "what this person
sees" against "what a query returns", the view is the third input after the account and the
limitation.

## Worked queries

### Every account with its rights

The provisioning inventory. Run this before an audit and diff it afterwards.

```sql
SELECT
    a.AccountID,
    a.AccountType,
    a.Enabled,
    a.AllowAdmin,
    a.AllowNodeManagement,
    a.AllowUnmanage,
    a.AllowAlertManagement,
    a.AllowReportManagement,
    a.CanClearEvents,
    a.LastLogin
FROM Orion.Accounts a
ORDER BY a.AccountID
```

Remember that `Enabled` and every `Allow*` column comes back as `Y` or `N`, so a client that
expects booleans has to translate. Filtering in SWQL therefore compares against a string:
`WHERE a.AllowAdmin = 'Y'`, not `WHERE a.AllowAdmin = TRUE`.

### Who has admin

The one query to run on a schedule. Administrative access accumulates, and nothing in the
platform removes it for you.

```sql
SELECT
    a.AccountID,
    a.AccountType,
    a.Enabled,
    a.LastLogin,
    a.Expires,
    a.LockoutTime,
    a.PasswordExpirationDate
FROM Orion.Accounts a
WHERE a.AllowAdmin = 'Y'
ORDER BY a.AccountID
```

Two follow-up questions the columns answer directly. An account with `AllowAdmin = 'Y'` and
`Enabled = 'N'` is a dormant admin, which is a finding rather than a comfort, because enabling
it is one click. An account with `AllowAdmin = 'Y'` and a `LastLogin` from two years ago is
the same finding with more history.

Because group accounts grant their rights to every member, a `Y` on a row whose `AccountType`
is 3 or 6 is not one administrator, it is however many people are in that directory group.

### Accounts that carry a limitation

The first half of "why does this account see less than I expect".

```sql
SELECT
    a.AccountID,
    a.LimitationID1,
    a.LimitationID2,
    a.LimitationID3
FROM Orion.Accounts a
WHERE IsNull(a.LimitationID1, 0) <> 0
   OR IsNull(a.LimitationID2, 0) <> 0
   OR IsNull(a.LimitationID3, 0) <> 0
ORDER BY a.AccountID
```

`IsNull(column, 0) <> 0` covers both ways an unused slot can be represented, because whether
an empty slot holds `0` or `NULL` is not recorded in the schema. Written that way the query is
correct either way.

### What each of those limitations actually does

The second half. Three `UNION` branches because the three slots are three columns, and there
is no navigation property from an account to its limitations.

```sql
SELECT a.AccountID, l.LimitationID, t.Name AS LimitationType, t.EntityType, l.Definition, l.WhereClause
FROM Orion.Accounts a
JOIN Orion.Limitations l ON a.LimitationID1 = l.LimitationID
JOIN Orion.LimitationTypes t ON l.LimitationTypeID = t.LimitationTypeID
UNION
SELECT a.AccountID, l.LimitationID, t.Name AS LimitationType, t.EntityType, l.Definition, l.WhereClause
FROM Orion.Accounts a
JOIN Orion.Limitations l ON a.LimitationID2 = l.LimitationID
JOIN Orion.LimitationTypes t ON l.LimitationTypeID = t.LimitationTypeID
UNION
SELECT a.AccountID, l.LimitationID, t.Name AS LimitationType, t.EntityType, l.Definition, l.WhereClause
FROM Orion.Accounts a
JOIN Orion.Limitations l ON a.LimitationID3 = l.LimitationID
JOIN Orion.LimitationTypes t ON l.LimitationTypeID = t.LimitationTypeID
```

`WhereClause` is the payoff. It is the filter SWIS applies, in text, so you can read it
instead of reverse engineering the effect from row counts.

### Exactly which objects one limitation covers

When someone asks "so what can `noc-emea` see", this answers it in object terms rather than in
definition terms.

```sql
SELECT
    s.LimitationID,
    s.EntityType,
    s.EntityID,
    s.EntityUri
FROM Orion.LimitationSnapshots s
WHERE s.LimitationID = @limitationId
ORDER BY s.EntityType, s.EntityID
```

The entity name says "pre-evaluated", so this is a materialised snapshot rather than a live
evaluation. If it disagrees with what the account sees, the snapshot is stale, not wrong in
principle. Treat a large discrepancy as a signal to check the console rather than as proof.

### The limitation type catalogue

Run this before calling `CreateLimitation`. `LimitationTypeID` values are installation data, so
resolving the type by `Name` at run time is the only portable way to write the call.

```sql
SELECT
    t.LimitationTypeID,
    t.Name,
    t.Description,
    t.EntityType,
    t.Method,
    t.[Table] AS SourceTable,
    t.[Field] AS SourceField,
    t.IsSwisLimitation,
    t.IsGroupOfEntity
FROM Orion.LimitationTypes t
ORDER BY t.Name
```

`Table` and `Field` are bracketed because they collide with SWQL keywords. `Method` is the
column that tells you which of `selection`, `checkboxItems` and `pattern` to fill in.
`IsSwisLimitation` is worth reading: it distinguishes types the information service enforces
from ones that only shape the web console.

### Dormant accounts

Access review material. An account nobody has used in ninety days is either a service account
that should be documented as one, or a leaver.

```sql
SELECT
    a.AccountID,
    a.Enabled,
    a.LastLogin,
    DayDiff(a.LastLogin, GetDate()) AS DaysSinceLastLogin
FROM Orion.Accounts a
WHERE a.LastLogin < AddDay(-90, GetDate())
ORDER BY a.LastLogin
```

`DayDiff(a, b)` counts from `a` to `b`, so the argument order here yields a positive age.
`LastLogin` is a `System.DateTime` and this comparison is in server-local time; see
[../swql/date-and-time.md](../swql/date-and-time.md) for why mixing `GetUtcDate()` with the
`AddX` functions produces the wrong offset.

### Change volume per account

Which accounts are actually doing things, from the audit trail rather than from the account
record.

```sql
SELECT
    e.AccountID,
    t.ActionTypeDisplayName,
    COUNT(e.AuditEventID) AS Events
FROM Orion.AuditingEvents e
JOIN Orion.AuditingActionTypes t ON e.ActionTypeID = t.ActionTypeID
WHERE e.TimeLoggedUtc >= ToUtc(AddDay(-30, GetDate()))
GROUP BY e.AccountID, t.ActionTypeDisplayName
ORDER BY COUNT(e.AuditEventID) DESC
```

`Orion.AuditingEvents.TimeLoggedUtc` is UTC, which is why the bound is wrapped in `ToUtc`.
Full treatment of the audit trail, including how to attribute a specific change to a person,
is in [events-and-auditing.md](events-and-auditing.md).

### Directory-backed accounts

Group accounts are where rights multiply, so it is worth separating them from individual ones.

```sql
SELECT
    a.AccountID,
    a.AccountType,
    a.GroupInfo,
    a.GroupPriority,
    a.AccountSID
FROM Orion.Accounts a
WHERE a.AccountType <> 0
ORDER BY a.AccountID
```

The `<> 0` filter assumes Orion-only accounts carry `AccountType` 0, which is the value this
page marks as unverified above. Run the `GROUP BY a.AccountType` query first and adjust the
predicate to whatever your server actually uses.

## Gotchas

**A permission error is usually a missing right, not a bug.** Look the verb up before you
debug the call: `python3 tools/schema_query.py verb <Entity> <Verb>` prints the right on the
`requires:` line. 403 means the account authenticated and lacks the right; 401 means it did
not authenticate at all.

**Limitations do not raise errors.** They remove rows. Any troubleshooting flow that starts
with "the query must be wrong" will waste time on an account problem. Compare counts across
accounts first.

**Three limitation slots is a hard limit.** Design around it rather than discovering it.

**Rights read as strings and write as booleans.** `"Y"` on the way out, `true` on the way in.

**Do not hard-code `LimitationTypeID` or `LimitationID`.** They are installation data, so a
script that works on the test server fails silently, or worse succeeds against the wrong
limitation, on production. Resolve by `Name` at run time.

**Deleting an account is not reversible and takes its preferences with it.** If the goal is
"this person should not be able to sign in", `Enabled = false` through `UpdateAccount` is
reversible and leaves the audit trail intact.

**Service accounts should be scoped down, not up.** The verb-to-right listing above exists so
you can grant exactly what a script needs. A maintenance-window script needs `allowUnmanage`
and nothing else; giving it `admin` because that is quicker means every future bug in it is an
unbounded one.

**Group membership changes rights without touching Orion.** An account authorised through a
directory group inherits whatever that group has. An audit of `Orion.Accounts` alone will not
show you that somebody joined the group yesterday.

## See also

- [events-and-auditing.md](events-and-auditing.md) for who changed what, and when
- [credentials.md](credentials.md) for polling and discovery credentials, which are a
  different thing from accounts
- [reporting.md](reporting.md) for why a scheduled export's account decides its contents
- [README.md](README.md) for the automation method these pages follow
- [../swis/invoke-verbs.md](../swis/invoke-verbs.md) for how verb arguments are encoded
- [../swis/metadata-introspection.md](../swis/metadata-introspection.md) for asking your own
  server what it supports
- [../reference/verb-index.md](../reference/verb-index.md) for every verb and its parameters
- SolarWinds'
  [Account Management](https://solarwinds.github.io/OrionSDK/docs/account-management/) page
