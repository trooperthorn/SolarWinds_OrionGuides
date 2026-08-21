# The SWIS REST/JSON API

This is the HTTP contract for the SolarWinds Information Service. It is the interface to use
from anything that is not Windows PowerShell, and it is the interface the official Python
client and the Go, Java and Perl samples all speak.

Grounded in the official
[REST](https://solarwinds.github.io/OrionSDK/docs/rest/) page and in the Swagger contract
published alongside the 2026.2 schema.

## Base URL and transport

```
https://<orion-server>:17774/SolarWinds/InformationService/v3/Json
```

- Port **17774** from platform release 2023.1 onward. Port 17778 was the REST port through
  2022.4.1 and is deprecated. See [connecting.md](connecting.md#endpoints-and-ports).
- HTTPS only. The Swagger contract declares `"schemes": ["https"]`.
- Authentication is HTTP basic. The Swagger contract declares exactly one security
  definition, `basicAuth`, and every official example carries an
  `Authorization: Basic ...` header. (`Authorization: Basic YWRtaW46` in the official
  examples decodes to `admin:`, an `admin` account with an empty password, which is a lab
  setup and not something to copy.)
- Request bodies are JSON and need `Content-Type: application/json`. Responses are JSON.

## The path surface

The Swagger contract for 2026.2 publishes 1319 paths. Four of them are generic and the rest
are per-entity or per-verb.

| Path | Methods | Interface |
|:---|:---|:---|
| `/Query` | `GET`, `POST` | Query (read only) |
| `/{uri}` | `GET`, `POST`, `DELETE` | CRUD read, update, delete |
| `/BulkUpdate` | `POST` | Bulk update |
| `/BulkDelete` | `POST` | Bulk delete |
| `/Create/{Entity}` | `POST` | CRUD create, 378 such paths |
| `/Invoke/{Entity}/{Verb}` | `POST` | Invoke, 937 such paths |

`GET /Query` has Swagger `operationId` `Query`; `POST /Query` has `QueryWithParameters`.
The CRUD operations on `/{uri}` are `Read`, `Update` and `Delete` respectively.

## Query

### GET with a URL-encoded query

The simplest form. The whole SWQL statement goes in the `query` query-string parameter,
percent-encoded.

```text
GET https://localhost:17774/SolarWinds/InformationService/v3/Json/Query?query=SELECT+Uri+FROM+Orion.Pollers+ORDER+BY+PollerID+WITH+ROWS+1+TO+3+WITH+TOTALROWS HTTP/1.1
Authorization: Basic YWRtaW46
Host: localhost:17774
Accept: */*
```

Response:

```json
HTTP/1.1 200 OK
Content-Type: application/json

{"totalRows":13,"results":[{"Uri":"swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=4"},{"Uri":"swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6"},{"Uri":"swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=7"}]}
```

Reformatted:

```json
{
    "totalRows": 13,
    "results": [
        { "Uri": "swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=4" },
        { "Uri": "swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6" },
        { "Uri": "swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=7" }
    ]
}
```

With curl, let the tool do the encoding:

```bash
curl -sS -u 'admin:swordfish' --cacert orion-swis.pem --get \
  --data-urlencode 'query=SELECT Uri FROM Orion.Pollers ORDER BY PollerID WITH ROWS 1 TO 3 WITH TOTALROWS' \
  'https://myorion.example.com:17774/SolarWinds/InformationService/v3/Json/Query'
```

`GET /Query` is fine for fixed, hand-written queries and for exploring. It is a poor choice
for anything that interpolates user or database values into the SWQL text, for the reasons
in the next section.

### POST with bound parameters

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/Query HTTP/1.1
Authorization: Basic YWRtaW46
Host: localhost:17774
Content-Type: application/json

{"query":"SELECT Uri FROM Orion.Pollers WHERE PollerID=@p ORDER BY PollerID WITH ROWS 1 TO 3 WITH TOTALROWS","parameters":{"p":9}}
```

Reformatted:

```json
{
  "query": "SELECT Uri FROM Orion.Pollers WHERE PollerID=@p ORDER BY PollerID WITH ROWS 1 TO 3 WITH TOTALROWS",
  "parameters": {
    "p": 9
  }
}
```

Response:

```json
{"totalRows":1,"results":[{"Uri":"swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=9"}]}
```

The Swagger request schema is minimal and exact:

```json
{
  "QueryRequest": {
    "required": ["query"],
    "type": "object",
    "properties": {
      "query":      { "type": "string" },
      "parameters": { "type": "object" }
    }
  }
}
```

`query` is required, `parameters` is optional, and `parameters` is a free-form object whose
member names are the parameter names without the `@` sigil.

## Parameter binding

A SWQL parameter is written `@name` in the query text and supplied as a member called
`name` in the `parameters` object. It matters for three separate reasons.

**Correctness.** Values that contain quotes, backslashes or percent signs do not need
escaping when bound. Concatenate a caption like `O'Brien-DC1` into SWQL text and you get a
syntax error; bind it and it just works. The official PowerShell guidance says the same
thing: parameters avoid "the need to deal with encoding embedded quote characters and other
syntactical issues."

**Safety.** String concatenation into a query language is injection, and SWQL is a query
language. SWQL cannot write data, so the blast radius is smaller than SQL injection, but an
attacker who can shape your query text can still read entities your query never intended to
touch, and account limitations are the only thing standing between them and the rest of the
data your service account can see.

**Types.** Bound values keep their JSON type. An integer stays an integer, a boolean stays a
boolean, and you are not relying on SWIS to parse a literal you formatted by hand. This is
particularly valuable for dates, where the alternative is guessing at a string format.

```json
{
  "query": "SELECT NodeID, Caption, IPAddress FROM Orion.Nodes WHERE Vendor = @vendor AND Status = @status",
  "parameters": {
    "vendor": "Cisco",
    "status": 2
  }
}
```

`Vendor`, `Status`, `NodeID`, `Caption` and `IPAddress` are all real `Orion.Nodes`
properties. `Status = 2` is Down.

From PowerShell the same idea uses a hash table:

```powershell
Get-SwisData $swis 'SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @v' @{ v = 'Cisco' }
```

From Python the client turns keyword arguments into the `parameters` object:

```python
rows = swis.query(
    "SELECT NodeID, Caption FROM Orion.Nodes WHERE Vendor = @v",
    v="Cisco",
)
```

### Multi-valued parameters for IN clauses

A parameter can be a JSON array, which is how you drive `WHERE x IN (...)` without building
a comma-separated list by hand:

```json
{
  "query": "SELECT NodeID, Caption FROM Orion.Nodes WHERE NodeID IN @ids",
  "parameters": {
    "ids": [2, 4, 6]
  }
}
```

Note the syntax: `IN @ids`, with no parentheses around the parameter. The array supplies the
whole list.

This is the right way to fetch a specific set of objects in one round trip, and it composes
well with `WITH ROWS` when the set is large enough to need chunking.

## Paging with WITH ROWS and WITH TOTALROWS

Both clauses are trailing modifiers on the SWQL statement, not REST parameters.

- `WITH ROWS <first> TO <last>` returns a window of the result set. In the official example,
  `WITH ROWS 1 TO 3` against a 13-row result set returns 3 rows, so the bounds are 1-based
  and inclusive.
- `WITH TOTALROWS` adds a `totalRows` member to the response envelope carrying the count the
  query would have returned without the window. That is what lets you compute how many pages
  there are.

```sql
SELECT NodeID, Caption
FROM Orion.Nodes
ORDER BY NodeID
WITH ROWS 1 TO 500 WITH TOTALROWS
```

Always pair `WITH ROWS` with an `ORDER BY`. Without a deterministic sort there is no
guarantee that page 2 continues where page 1 stopped, and you can silently skip or duplicate
rows. `ORDER BY` on the key property (`NodeID` here) is the safe default.

A paging loop then looks like this:

```python
page_size = 500
first = 1
while True:
    # The row window is built into the query text. These are integers this code
    # generates itself, never external input, so there is nothing to bind here.
    resp = swis.query(
        "SELECT NodeID, Caption FROM Orion.Nodes "
        f"ORDER BY NodeID WITH ROWS {first} TO {first + page_size - 1} WITH TOTALROWS"
    )
    for row in resp["results"]:
        print(row["NodeID"], row["Caption"])
    total = resp.get("totalRows", 0)
    first += page_size
    if first > total:
        break
```

Whether `WITH ROWS` accepts bound parameters in place of literals is not stated in the
official documentation, so this example keeps the bounds as literals. If you want to bind
them, test it against your own server first.

## The response envelope

The Swagger response schema for both `GET /Query` and `POST /Query`:

```json
{
  "QueryResponse": {
    "type": "object",
    "properties": {
      "results":   { "type": "array", "items": { "type": "object" } },
      "totalRows": { "type": "number" }
    }
  }
}
```

Both members are optional in the schema. In practice:

- `results` is an array of objects, one per row. Each object's member names are the column
  names as they appear in the `SELECT` list, including any aliases you gave them.
- `totalRows` appears in the official examples that ask for `WITH TOTALROWS`. Treat it as
  present only when you asked for it, and read it defensively.

Column naming follows your `SELECT` list exactly, so alias anything ambiguous:

```sql
SELECT n.Caption AS NodeCaption, n.Interfaces.Caption AS InterfaceCaption
FROM Orion.Nodes n
```

`Orion.Nodes.Interfaces` is a real navigation property leading to `Orion.NPM.Interfaces`.

## Invoke

Verbs are called by POSTing to `/Invoke/{Entity}/{Verb}`.

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/Invoke/Metadata.Entity/GetAliases HTTP/1.1
Authorization: Basic YWRtaW46
Content-Type: application/json

["SELECT B.Caption FROM Orion.Nodes B"]
```

Response:

```json
{"B":"Orion.Nodes"}
```

The critical detail, stated in the official documentation:

> When calling SWIS verbs with REST API, you need to provide the arguments as a JSON array.
> Verb arguments are positional, not named.

The body is a bare JSON array, and the order is the verb's declared parameter order. Sending
an object with parameter names will not work. Get the order from the schema before you call:

```bash
python3 tools/schema_query.py verb Orion.Nodes Unmanage
```

which prints, for 2026.2:

```
parameters (5):
  netObjectId: string (required)
  unmanageTime: string (required)
  remanageTime: string (required)
  isRelative: boolean (required)
  allowOverlapping: boolean (optional)
```

so the body is:

```json
["N:1", "2026-08-21T18:00:00Z", "2026-08-21T20:00:00Z", false, false]
```

794 of the 958 verbs in 2026.2 publish typed parameters in the Swagger contract, so for
those the names, types, order and required flags are all checkable before you write the
call.

## Create

`POST /Create/{Entity}` with a JSON object of property values. The response body is the URI
of the new entity as a JSON string.

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/Create/Orion.Pollers HTTP/1.1
Authorization: Basic YWRtaW46
Content-Type: application/json

{"PollerType":"hi from curl 2", "NetObject":"N:123", "NetObjectType":"N", "NetObjectID":123}
```

```json
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

"swis:\/\/tdanner-dev.swdev.local\/Orion\/Orion.Pollers\/PollerID=19"
```

`PollerType`, `NetObject`, `NetObjectType` and `NetObjectID` are all real `Orion.Pollers`
properties in 2026.2, alongside `PollerID` and `Enabled`. See [crud.md](crud.md) for the
full create, read, update, delete cycle.

## Read, Update and Delete on `/{uri}`

The URI goes directly into the path, unencoded, exactly as the official examples show.

```text
GET https://localhost:17774/SolarWinds/InformationService/v3/Json/swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6
```

```json
{"PollerID":6,"PollerType":"V.Details.SNMP.Generic","NetObject":"V:1","NetObjectType":"V","NetObjectID":1,"DisplayName":null,"Description":null,"InstanceType":"Orion.Pollers","Uri":"swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6"}
```

Note that `DisplayName`, `Description`, `InstanceType` and `Uri` come back even though they
are not declared on `Orion.Pollers`: they are inherited from `System.Entity`.

Update is a `POST` to the same path with only the properties you are changing:

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/swis://tdanner-dev.swdev.local/Orion/Orion.Pollers/PollerID=6
Content-Type: application/json

{"PollerType":"hi from curl"}
```

```text
HTTP/1.1 200 OK
Content-Length: 0
```

Delete is a `DELETE` to the same path and also returns an empty 200.

Swagger describes these responses precisely: read returns "the properties of the read
object", update returns "an empty response", delete returns "an empty response". Do not
write code that expects a body back from update or delete.

## BulkUpdate

Applies one property bag to many URIs in a single request.

```json
{
  "BulkUpdateRequest": {
    "required": ["uris", "properties"],
    "type": "object",
    "properties": {
      "uris":       { "type": "array", "items": { "type": "string" } },
      "properties": { "type": "object" }
    }
  }
}
```

Both members are required. Example from the official documentation:

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/BulkUpdate HTTP/1.1
Content-Type: application/json

{
"uris":[
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=1",
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=2",
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=3"
],
"properties":
{
"NextPoll":"7/1/2014 9:06:19 AM",
"NextRediscovery":"7/1/2014 2:59:09 PM"
}
}
```

The URIs here navigate from a node into its volumes. `Orion.Nodes.Volumes` is a real
navigation property leading to `Orion.Volumes`, and `NextPoll` and `NextRediscovery` are
real `Orion.Volumes` properties.

The same mechanism works against custom properties, by pointing the URIs at each object's
`CustomProperties` navigation property:

```json
{
  "uris":[
    "swis://mrxinu.local/Orion/Orion.Nodes/NodeID=81/CustomProperties",
    "swis://mrxinu.local/Orion/Orion.Nodes/NodeID=82/CustomProperties",
    "swis://mrxinu.local/Orion/Orion.Nodes/NodeID=83/CustomProperties",
    "swis://mrxinu.local/Orion/Orion.Nodes/NodeID=84/CustomProperties"
  ],
  "properties":{
    "City": "Serenity Valley"
  }
}
```

`Orion.Nodes.CustomProperties` is a real navigation property leading to
`Orion.NodesCustomProperties`. `City` is a user-defined custom property, so it will exist
only if someone created it on your server; the property names in this body are whatever your
installation defines.

Both bulk operations return an empty 200 on success.

## BulkDelete

```json
{
  "BulkDeleteRequest": {
    "required": ["uris"],
    "type": "object",
    "properties": {
      "uris": { "type": "array", "items": { "type": "string" } }
    }
  }
}
```

```text
POST https://localhost:17774/SolarWinds/InformationService/v3/Json/BulkDelete HTTP/1.1
Content-Type: application/json

{
"uris":[
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=548",
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=545",
"swis://dev-che-mjag-01./Orion/Orion.Nodes/NodeID=4/Volumes/VolumeID=546"]
}
```

A natural pattern is to build the URI list from a query, since `Uri` is available on every
entity:

```sql
SELECT Uri, Caption, VolumeType
FROM Orion.Volumes
WHERE NodeID = @nodeId
```

then feed `results[*].Uri` straight into `BulkDelete`. `NodeID`, `Caption` and `VolumeType`
are real `Orion.Volumes` properties, so you can narrow the selection on `VolumeType` once
you have seen which values your server actually stores.

## Errors

Successful responses are `200`. On failure, the official Python client parses the response
body as JSON and reads a `Message` member to produce the error reason, which tells you that
SWIS returns a JSON error envelope containing `Message`. The exact shape of that envelope is
not published in the Swagger contract, so treat anything beyond the presence of `Message` as
unverified; you can confirm what your server returns by sending a deliberately invalid query
such as `SELECT Nonsense FROM Orion.Nodes` and printing the raw response body.

Practical handling:

- Do not assume a failure body is JSON. Fall back to the raw text.
- A 400 on a query is almost always SWQL: a misspelled entity or property, or a value
  concatenated into the text that should have been bound.
- A 401 is authentication; see [connecting.md](connecting.md).
- An empty result set is a `200` with `"results": []`, not an error. If a query that should
  return rows returns none, check whether account limitations are filtering them out.

## Next

- [crud.md](crud.md) for the full create, read, update, delete lifecycle with worked
  examples.
- [uris.md](uris.md) for how to construct the URIs these operations consume.
- [connecting.md](connecting.md) for ports, authentication and TLS.
