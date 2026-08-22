namespace Porter.Areas;

public sealed record AreaInfo(string Key, string Name, string Mechanism, string Note,
    bool Enabled, string Phase);

/// <summary>
/// The eleven configuration areas and their real SWIS route, verified against the
/// extracted 2026.2 contract. Enabled = implemented in this build. The pinned areas stay
/// visible so users learn what the platform cannot do, instead of hunting for a button.
/// </summary>
public static class AreaCatalog
{
    public static readonly IReadOnlyList<AreaInfo> All = new[]
    {
        new AreaInfo("dashboards", "Modern Dashboards", "verb pair",
            "Export(dashboardId) → JSON · Import(definition) · verified after import by unique_key",
            true, "Flight-ready"),
        new AreaInfo("alerts", "Alerts", "verb pair",
            "Export strips sensitive data by default · import always creates (collisions skip by name) · needs manageAlerts",
            true, "Flight-ready"),
        new AreaInfo("reports", "Reports", "query + verb",
            "SELECT Definition → CreateReport (create-only; collisions skip by name) · schedules have no route",
            true, "Flight-ready"),
        new AreaInfo("sam", "SAM Templates", "verb pair",
            "ExportTemplate / ImportTemplate (.apmtemplate) · script bodies travel verbatim — review for secrets",
            true, "Flight-ready"),
        new AreaInfo("wpm", "WPM Recordings", "verb pair",
            "Export/Import with the platform's mandatory cipher password · transactions themselves have no route",
            true, "Flight-ready"),
        new AreaInfo("ncmdevice", "NCM Device Templates", "query + CRUD",
            "TemplateXml column out, CRUD row in · built-ins (IsDefault) are read-only",
            true, "Flight-ready"),
        new AreaInfo("nodescp", "Nodes + Custom Properties", "bulk CSV",
            "One CSV out · creates missing definitions (needs admin) · values matched by IP with Caption fallback",
            true, "Flight-ready"),
        new AreaInfo("ncmcompliance", "NCM Compliance Reports", "deep verb pair",
            "Console-compatible XML round trip · auto-executing remediation rules blocked until acknowledged",
            true, "Flight-ready"),
        new AreaInfo("discovery", "Discovery + Credentials", "partial by design",
            "Secrets never leave a server (write-only) · v2 ships a guided replay with re-entry",
            false, "In Dry Dock · v2"),
        new AreaInfo("undp", "Universal Device Pollers", "export-only",
            "Definitions have no SWIS create · export sheet + assignment sync planned",
            false, "In Dry Dock · v2"),
        new AreaInfo("devicestudio", "Device Studio Templates", "no route",
            "2026.2 charts no route — metadata only, no definition column, no verbs · re-check each release",
            false, "Uncharted"),
    };
}
