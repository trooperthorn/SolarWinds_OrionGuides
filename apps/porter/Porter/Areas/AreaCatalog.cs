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
            true, "Base"),
        new AreaInfo("alerts", "Alerts", "verb pair",
            "Export can strip sensitive data (accounts, passwords, tokens) or password-protect it",
            false, "Next build"),
        new AreaInfo("reports", "Reports", "query + verb",
            "SELECT Definition → CreateReport · the server duplicates on collision (\"Copy of\")",
            false, "Next build"),
        new AreaInfo("sam", "SAM Templates", "verb pair",
            "ExportTemplate / ImportTemplate · dry run via StartTestComponents",
            false, "Next build"),
        new AreaInfo("wpm", "WPM Transactions", "verb pair",
            "Recording Export/Import with a mandatory file-cipher password · Exists(guid) collision check",
            false, "Next build"),
        new AreaInfo("ncmdevice", "NCM Device Templates", "query + CRUD",
            "TemplateXml column out, CRUD row in · built-ins (IsDefault) are read-only",
            false, "Next build"),
        new AreaInfo("nodescp", "Nodes + Custom Properties", "query + CRUD",
            "Table out as CSV · ValidateCustomProperty pre-flight · match nodes by IP/Caption",
            false, "Next build"),
        new AreaInfo("ncmcompliance", "NCM Compliance Reports", "deep verb pair",
            "GetPolicyReport(id, true) nests policies+rules · pinned: remediation-script safety gate",
            false, "Pinned · v2"),
        new AreaInfo("discovery", "Discovery + Credentials", "partial by design",
            "Secrets never leave a server (write-only) · v2 ships a guided replay with re-entry",
            false, "Pinned · v2"),
        new AreaInfo("undp", "Universal Device Pollers", "export-only",
            "Definitions have no SWIS create · export sheet + assignment sync planned",
            false, "Pinned · v2"),
        new AreaInfo("devicestudio", "Device Studio Templates", "no route",
            "2026.2 exposes metadata only — no definition column, no verbs · re-check each release",
            false, "Pinned"),
    };
}
