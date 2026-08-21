# Sample SWQL queries

Worked queries grouped by subject. Every statement in this directory is checked against
the extracted 2026.2 schema by `tools/validate_swql.py` on each build, so the entity
names, property names and navigation properties are known to exist rather than merely
believed to.

| File | Covers |
| --- | --- |
| [01-nodes.swql](01-nodes.swql) | Inventory, status, maintenance windows, polling method, parameters |
| [02-interfaces.swql](02-interfaces.swql) | Interface inventory, utilization, errors, duplex, peak traffic |
| [03-volumes-and-capacity.swql](03-volumes-and-capacity.swql) | Disk capacity, growth, I/O pressure, estate totals |
| [04-applications.swql](04-applications.swql) | SAM applications and components, templates, failures |
| [05-alerts.swql](05-alerts.swql) | Active alerts, acknowledgement, definitions, history, noise |
| [06-events-and-auditing.swql](06-events-and-auditing.swql) | Events, event types, and the audit trail of who changed what |
| [07-groups-and-dependencies.swql](07-groups-and-dependencies.swql) | Groups, membership, rollup, dependencies |
| [08-schema-introspection.swql](08-schema-introspection.swql) | Asking a live server about its own schema and verbs |
| [09-engines-and-health.swql](09-engines-and-health.swql) | Polling engines, load balance, licence headroom |
| [10-virtualization.swql](10-virtualization.swql) | VMs, hosts, clusters, datastores, snapshots, capacity forecasts |
| [11-ncm-configs.swql](11-ncm-configs.swql) | NCM devices, config archives, compliance, end of life |
| [12-udt-and-storage.swql](12-udt-and-storage.swql) | Device tracking by MAC/IP/port, and array-side storage |
| [13-hardware-wireless-ipam.swql](13-hardware-wireless-ipam.swql) | Hardware sensors, access points and clients, subnet utilization |
| [14-netflow-traffic.swql](14-netflow-traffic.swql) | Flow sources, top talkers, traffic by application, protocol and country |

## Running them

These are plain SWQL. Paste one into SWQL Studio, or run it through any client:

```bash
# curl
export SWIS_HOST=orion.example.com SWIS_USER=admin SWIS_PASSWORD='...'
../curl/swis-rest-examples.sh query-basic

# Python
python3 ../python/swis_client.py --host "$SWIS_HOST" --user "$SWIS_USER" \
    query "$(sed -n '/^SELECT TOP 100/,/^ORDER BY n.Caption/p' 01-nodes.swql)"
```

```powershell
# PowerShell
$swis = Connect-Swis -Hostname orion.example.com -Trusted
Get-SwisData $swis "SELECT TOP 10 Caption, IPAddress FROM Orion.Nodes"
```

## Conventions these files follow

The conventions are not stylistic. Each one prevents a specific failure:

- **Bounded result sets.** `TOP n` or `WITH ROWS a TO b`. There is no `SELECT *` in SWQL,
  and an unbounded query against a large installation is a real production risk.
- **Bound parameters** (`@name`) rather than string concatenation, so plans get reused and
  an injection class disappears. Multi-valued parameters work with `IN @ids`.
- **Time bounds on anything historical.** Events, alert history and statistics entities are
  the largest tables on the system.
- **Status resolved by joining `Orion.StatusInfo`** rather than hard-coding integers, so
  the query stays correct if SolarWinds adds a status.
- **`UnManaged = FALSE`** when the question is "what is actually broken" rather than "what
  is in a maintenance window".

## A caveat about results

Account limitations apply to everything read through SWIS. Two accounts running the same
query against the same server can legitimately get different rows. When a query returns
nothing you expected, check the account's limitations before you debug the SQL.

Queries that depend on a module return nothing if that module is not installed. Interfaces
need NPM, applications need SAM, and so on. See
[../../docs/reference/entity-index.md](../../docs/reference/entity-index.md) for which
namespace an entity belongs to.

## Adding a query

Validate before committing:

```bash
python3 ../../tools/validate_swql.py your-file.swql
```

See [../../CONTRIBUTING.md](../../CONTRIBUTING.md).
