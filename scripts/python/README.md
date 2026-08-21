# Python examples

| Script | Does |
| --- | --- |
| [swis_client.py](swis_client.py) | A SWIS REST client and CLI built on the standard library alone |

## Which client to use

For production, use the official client:

```bash
pip install orionsdk
```

```python
from orionsdk import SwisClient

swis = SwisClient("orion.example.com", "admin", password)
rows = swis.query(
    "SELECT Caption, IPAddress FROM Orion.Nodes WHERE Status = @s",
    s=2,
)["results"]
swis.invoke("Orion.Nodes", "PollNow", "N:42")
```

The file here implements the same REST contract with nothing but the standard library. It
exists because the contract is small enough to read in full, and seeing it makes the
wrapped clients easier to reason about. It is also useful when you cannot add a
dependency.

```bash
export SWIS_PASSWORD='...'
python3 swis_client.py --host orion.example.com --user admin \
    query "SELECT TOP 5 Caption, IPAddress FROM Orion.Nodes"

python3 swis_client.py --host orion.example.com --user admin \
    query "SELECT Caption FROM Orion.Nodes WHERE NodeID IN @ids" --param ids='[1,2,3]'

python3 swis_client.py --host orion.example.com --user admin \
    invoke Orion.Nodes PollNow N:42
```

## Things worth knowing

Bind parameters with `@name` rather than formatting them into the query string. Plans get
reused and an injection class disappears. Multi-valued parameters work with `IN @ids` when
the value is a JSON array.

Invoke arguments are positional. Confirm the order before calling:

```bash
python3 ../../tools/schema_query.py verb Orion.Nodes Unmanage
```

SWIS ships a self-signed certificate. Trust it with `--ca-file` rather than disabling
verification; `--insecure` exists for lab use and lets anything on the path read the
credentials being sent.

The official Python client lives at <https://github.com/solarwinds/orionsdk-python>.
