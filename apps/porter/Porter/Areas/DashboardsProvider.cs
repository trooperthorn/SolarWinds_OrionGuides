using System.IO;
using System.Text;
using System.Text.Json;
using Porter.Core;

namespace Porter.Areas;

/// <summary>
/// Modern Dashboards — the Phase-1 verification area, now behind the provider contract.
/// Export:  Orion.Dashboards.Instances.Export(dashboardId) → the JSON definition.
/// Import:  Orion.Dashboards.Instances.Import(definition) → void, so verification
///          re-queries the file's dashboard unique_keys and reports the new ids.
/// Copy:    client-side structural rewrite (DashboardsArea.AsCopy).
/// </summary>
public sealed class DashboardsProvider : AreaProvider
{
    private readonly DashboardsArea _area;

    public DashboardsProvider(SwisSession swis) : base(swis) => _area = new DashboardsArea(swis);

    public override string Key => "dashboards";
    public override string DisplayName => "Modern Dashboards";
    public override string FileExtension => ".json";
    public override string FileDialogFilter => "Dashboard files|*.json";
    public override string ImportVia => "Orion.Dashboards.Instances.Import";
    public override CopyMode CopyMode => CopyMode.ClientRewrite;

    public override async Task<List<AreaItem>> ListAsync(CancellationToken ct)
        => (await _area.ListAsync(ct))
            .Select(d => new AreaItem(d.Id.ToString(), d.Name, d.UniqueKey, d.IsSystem))
            .ToList();

    public override async Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
    {
        var definition = await _area.ExportAsync(int.Parse(item.Id), ct);
        return new AreaExport(PackageWriter.Sanitize(item.Name) + FileExtension,
            Encoding.UTF8.GetBytes(definition));
    }

    public override AreaValidation Validate(string fileName, string text)
    {
        var d = DashboardValidator.Validate(text);
        var v = new AreaValidation { Detail = $"{d.WidgetCount} widgets · {d.QueryCount} queries" };
        v.Errors.AddRange(d.Errors);
        v.Warnings.AddRange(d.Warnings);
        v.Items.AddRange(d.Dashboards);
        return v;
    }

    public override async Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
    {
        var hits = await _area.FindCollisionsAsync(keys, ct);
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var (key, name) in hits) map[key] = name;
        return map;
    }

    public override CopyRewrite AsCopy(string text)
    {
        var (copyText, newNames, newKeys, notes) = DashboardsArea.AsCopy(text);
        return new CopyRewrite(copyText, newNames, newKeys, notes);
    }

    public override async Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
    {
        await _area.ImportAsync(text, ct);
        var found = await _area.VerifyAsync(verifyKeys, ct);
        var expected = verifyKeys.Count(k => k.Length > 0);
        if (found.Count >= expected && found.Count > 0)
            return new ImportOutcome(true,
                string.Join(", ", found.Select(f => $"\"{f.Name}\" (id {f.Id})")));
        return new ImportOutcome(false,
            "import call succeeded but no data returned when reading it back (No Data Returned)");
    }
}
