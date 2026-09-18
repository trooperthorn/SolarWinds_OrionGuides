# Embedding webviews and placing nodes on a map

Two separate questions come up together often enough to answer on one page: how to get an
external webpage into the SolarWinds Platform Web Console, and how to get nodes positioned on
a map by geographic coordinate rather than by hand. Neither is a SWQL question. The console
mechanics below are official, documented product behaviour and cannot be checked against the
extracted schema the way the rest of this repository is; where a fact *is* schema-backed
(`Orion.Nodes.Location`, `Orion.WorldMap.Point`) it is verified against 2026.2 and cited as
such, and everywhere else this page cites SolarWinds' own documentation directly rather than
asserting from memory.

## Getting a webpage into the console

Two supported mechanisms, both configured in the Web Console with admin rights and neither
requiring custom development.

**Custom HTML widget** embeds a page inside an existing view, alongside other resources. Edit
the view, Add Widgets, search "Custom HTML", drop it on the page, then edit the new widget and
supply a title, subtitle, and HTML containing an `<iframe>`:

```html
<iframe src="https://your-app.example.com" width="100%" height="600"></iframe>
```

The target must be served over HTTPS, or the browser blocks the frame outright. Creating or
editing a Custom HTML widget has required admin rights since platform release 2020.2.5.
[Source][custom-html].

**External Website view** registers a page as its own navigable entry rather than a tile on a
dashboard: Settings → All Settings → External Websites → Add, then set a Menu Title, an
optional Page Title, the URL, and which menu bar it appears under (Admin restricts it to
administrators, under My Dashboards → Home). This is the better fit when the target should be
a full page a user navigates to, not a widget sharing space with other resources. [Source][ext-sites].

For a custom map view built against your own node data — the shape this page leads to — the
Custom HTML route is usually the one that matters: it puts your page inside the console's
existing navigation and layout rather than off to the side as a separate link.

## Placing nodes on a map by coordinate

### `Location` is text, not a coordinate

`Orion.Nodes.Location` is `sysLocation`, a single free-text `System.String` property:

```
Orion.Nodes properties
  Location   System.String
```

Verified directly against the extracted 2026.2 schema (`tools/schema_query.py props
Orion.Nodes --grep location`). It holds whatever an operator or an SNMP agent put there —
`"Rack 4, DC2"`, `"Lancaster, PA"`, a raw `"lat,long"` pair, or nothing. Nothing about the
property enforces a geocodable format, which is the root of most Worldwide Map placement
trouble: the field the map tries to read from is exactly as reliable as whoever populated it.

### The coordinate itself lives in a separate entity, not a custom property

The console UI presents map coordinates as if they were two more columns in the Custom
Property Editor, labelled "Longitude (World Map)" and "Latitude (World Map)". Schematically
they are not custom properties at all. They are a dedicated entity that targets `Orion.Nodes`:

```
Orion.WorldMap.Point   [2026.2]
  inherits: System.Entity -> Orion.WorldMap.Point
  operations: create, delete, invoke, read, update
    read                                requires everyone
    create,read,update,delete,invoke    requires manageNodes

  properties (7)
    PointId          System.Int32
    Instance         System.String
    InstanceID       System.String
    Latitude         System.Double
    Longitude        System.Double
    AutoAdded        System.Boolean
    StreetAddress    System.String

  targetRelationships (3)
    Group   -> Orion.Groups
    Label   -> Orion.WorldMap.PointLabel
    Node    -> Orion.Nodes
```

Verified against 2026.2 (`tools/schema_query.py show Orion.WorldMap.Point`). A sibling entity,
`Orion.WorldMap.PointLabel`, holds the location's display name. Both are plain CRUD entities —
`create`, `read`, `update`, `delete` — with no verbs of their own, gated by `manageNodes`. A
point's `AutoAdded` flag distinguishes a location the geocoder placed from one entered by hand,
which is the schema-level version of the "manual placement is never overwritten" rule described
below.

The practical consequence: querying or writing map placement through SWIS is a query or a CRUD
call against `Orion.WorldMap.Point` joined back to `Orion.Nodes` through the `Node` target
relationship, not a read or write of a `Longitude`/`Latitude` property on `Orion.Nodes` itself
and not a `NodesCustomProperties` field. A worked example:

```sql
SELECT wp.PointId, wp.Latitude, wp.Longitude, wp.StreetAddress, wp.AutoAdded,
       wp.Node.NodeID, wp.Node.Caption
FROM Orion.WorldMap.Point wp
WHERE wp.Node.NodeID IS NOT NULL
ORDER BY wp.Node.Caption
```

This query is schema-checked and passes `tools/validate_swql.py`. Whether `Orion.WorldMap.Point`
accepts a CRUD `Create` supplying `InstanceID`/`Instance`/`Latitude`/`Longitude` directly against
a node, without going through the console's own placement flow, is **not recorded in the
published schema** and is unverified here; the entity's `canCreate`/`canUpdate` flags say the
interface is open, but the exact property combination a create call needs has to be confirmed
against a live server before it is relied on.

### How SolarWinds' own UI populates it

Two paths, both documented, neither going through SWIS directly from the operator's side:

**Automatic geolocation** (Settings → Web Console Settings → Worldwide Map Settings → enable
Automatic Geolocation) runs each node's `Location` value through the MapQuest geocoder.
Accepted input formats: `"City, State"`, `"City, State, ZIP"`, `"ZIP"` alone,
`"Street, City, State"`, or a raw `"latitude,longitude"` pair with no spaces. Placement can take
up to an hour to appear, and it never overwrites a node that has been positioned manually — that
is what `Orion.WorldMap.Point.AutoAdded` is recording. [Source][auto-geo].

**Manual and bulk entry** goes through Settings → Manage Nodes → Custom Property Editor, which
exposes the `Longitude (World Map)` / `Latitude (World Map)` columns for direct typing (avoid
extra whitespace in the value), or through an export/import round-trip: export a custom property
that already holds coordinates from Settings → All Settings → Manage Custom Properties, then
re-import the file with "Update existing custom property values" turned off and the columns
mapped onto `Longitude (World Map)` and `Latitude (World Map)`. Values set this way are not
touched by Automatic Geolocation even if it is later enabled. [Source][manual-coords].
[Source][custom-loc-prop].

### Using your own GPS custom property

If nodes already carry a GPS grid coordinate in a custom property you maintain (rather than
`Location`), that property is not read by the Worldwide Map directly — the widget only reads
`Orion.WorldMap.Point`. Two ways to connect the two:

1. **Round-trip through the console**, as above: export the custom property, re-import mapping
   it onto `Longitude (World Map)` / `Latitude (World Map)`. Keeps the built-in Worldwide Map
   widget as the renderer, and your custom property stays the value you edit going forward — the
   import is a one-time or periodic sync, not the source of truth.
2. **Bypass the Worldwide Map widget entirely** and render your own map (Leaflet, Mapbox, or the
   A-ORG-2 globe) inside a Custom HTML-embedded page that reads the custom property straight from
   `Orion.NodesCustomProperties` over SWIS. This is the better fit when the coordinate property
   is the durable source of truth and syncing it into a second SolarWinds-owned field is an
   extra moving part you would rather not maintain. It also sidesteps whatever
   `Orion.WorldMap.Point` will or will not accept from a direct CRUD call, since your renderer
   never touches that entity.

Both paths need the custom property itself, defined once at Settings → All Settings → Manage
Custom Properties → Add Custom Property, entity type Nodes. [Source][custom-loc-prop].

## Which approach fits which goal

| Goal | Use |
| --- | --- |
| Show an existing external app inside a console page | Custom HTML widget with an `<iframe>` |
| Give the external app its own console nav entry | External Website view |
| Use SolarWinds' built-in map, coordinates already clean | Automatic Geolocation from `Location` |
| Use SolarWinds' built-in map, coordinates come from your own property | Export/import round-trip onto `Longitude (World Map)` / `Latitude (World Map)` |
| A custom-built map is the actual deliverable (e.g. an external globe/map app) | Custom HTML iframe embedding that app, with the app reading node coordinates from your custom property over SWIS directly — `Orion.WorldMap.Point` is not involved |

## Related pages

- [../schema/README.md](../schema/README.md) for `Orion.Nodes` and the custom-properties
  entity family
- [building-integrations.md](building-integrations.md) for connecting an external application
  to SWIS safely: its own account, bound parameters, capability preflight
- [../webui/custom-query-widget.md](../webui/custom-query-widget.md) for turning a SWQL result
  into a linked, icon-bearing console widget, the nearest built-in analogue to a custom map pin
  list
- [../reference/unverified.md](../reference/unverified.md) for the collected list of claims this
  repository declines to assert without a live server, including the `Orion.WorldMap.Point`
  create call above

[custom-html]: https://support.solarwinds.com/SuccessCenter/s/article/Use-the-Custom-HTML-widget-to-display-HTML-based-data-in-the-Orion-Web-Console
[ext-sites]: https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-creating-and-editing-external-website-views-sw1301.htm
[auto-geo]: https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-automatic-placement-of-nodes-sw3059.htm
[manual-coords]: https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-place-object-into-worldmap-using-coordinates.htm
[custom-loc-prop]: https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-creating-a-custom-location-property.htm
