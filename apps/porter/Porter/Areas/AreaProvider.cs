using Porter.Core;

namespace Porter.Areas;

/// <summary>How an area can satisfy the "import as copy" collision policy.</summary>
public enum CopyMode
{
    /// <summary>Colliding files can only be skipped.</summary>
    NotSupported,
    /// <summary>Porter rewrites identities client-side before import (dashboards).</summary>
    ClientRewrite,
    /// <summary>The server itself duplicates on collision, renaming "Copy of …" (reports).</summary>
    ServerRename,
}

/// <summary>One inventory item offered for export. Id is the provider's native identifier
/// rendered as a string (int, GUID, …); Key is the identity used for collision checks at
/// import time; Detail is an optional extra column shown as a tooltip.</summary>
public sealed record AreaItem(string Id, string Name, string Key, bool IsSystem, string Detail = "");

/// <summary>One exported payload, ready for the package writer.</summary>
public sealed record AreaExport(string FileName, byte[] Bytes);

/// <summary>Structured result of validating one staged file — never an exception.
/// SecurityFlags are stronger than warnings: the file will not import until the operator
/// explicitly acknowledges them (auto-executing remediation scripts, embedded secrets).</summary>
public sealed class AreaValidation
{
    public List<string> Errors { get; } = new();
    public List<string> Warnings { get; } = new();
    public List<string> SecurityFlags { get; } = new();
    public List<(string Key, string Name)> Items { get; } = new();
    public string Detail { get; set; } = "";
    public bool Ok => Errors.Count == 0;

    public string Summary =>
        Errors.Count > 0 ? Errors[0]
        : SecurityFlags.Count > 0 ? $"{Detail} · SECURITY: {SecurityFlags[0]}"
        : Warnings.Count > 0 ? $"{Detail} · {Warnings[0]}"
        : Detail.Length > 0 ? $"{Detail} · all checks pass"
        : "all checks pass";
}

/// <summary>Result of the client-side copy transform (CopyMode.ClientRewrite).</summary>
public sealed record CopyRewrite(string Text, List<string> NewNames, List<string> NewKeys, List<string> Notes);

/// <summary>Per-run export options. Only the flags the provider declares are shown.</summary>
public sealed class ExportOptions
{
    public bool StripSensitive = true;
    public string? CipherPassword;
}

public sealed class ImportOptions
{
    public string? CipherPassword;
}

/// <summary>What one file's import produced. Verified means the provider confirmed the
/// object(s) exist on the target — by re-query or by the verb's own return value.</summary>
public sealed record ImportOutcome(bool Verified, string Detail);

/// <summary>
/// The contract every configuration area implements, so ExportView and ImportView stay
/// area-generic. A provider owns everything area-specific: the inventory query, the
/// export/import mechanism, local file validation, collision identity, the copy
/// transform, and post-import verification (folded into ImportAsync so each area can
/// verify the way its verb allows — re-query, returned id, or returned result object).
/// </summary>
public abstract class AreaProvider
{
    protected readonly SwisSession Swis;
    protected AreaProvider(SwisSession swis) => Swis = swis;

    public abstract string Key { get; }
    public abstract string DisplayName { get; }
    /// <summary>Extension for raw exports, dot included (".json", ".xml", ".apmtemplate").</summary>
    public abstract string FileExtension { get; }
    public abstract string FileDialogFilter { get; }
    /// <summary>The mechanism the manifest records for re-import ("Orion.Dashboards.Instances.Import").</summary>
    public abstract string ImportVia { get; }

    public virtual bool CanImport => true;
    public virtual CopyMode CopyMode => CopyMode.NotSupported;
    /// <summary>All selected items produce ONE file (Nodes + Custom Properties CSV).</summary>
    public virtual bool BulkExport => false;
    public virtual bool OffersStripSensitive => false;
    public virtual bool RequiresCipherPassword => false;
    /// <summary>Shown above the export options when set (alerts sensitive-data notice).</summary>
    public virtual string? SecurityNotice => null;

    public abstract Task<List<AreaItem>> ListAsync(CancellationToken ct);

    public virtual Task<AreaExport> ExportAsync(AreaItem item, ExportOptions opt, CancellationToken ct)
        => throw new NotSupportedException($"{DisplayName} does not export per item");

    public virtual Task<AreaExport> ExportBulkAsync(IReadOnlyList<AreaItem> items, ExportOptions opt,
        CancellationToken ct)
        => throw new NotSupportedException($"{DisplayName} does not bulk-export");

    public abstract AreaValidation Validate(string fileName, string text);

    /// <summary>Which of the file's keys already exist on the target: key → existing name.</summary>
    public virtual Task<Dictionary<string, string>> FindCollisionsAsync(
        IReadOnlyCollection<string> keys, CancellationToken ct)
        => Task.FromResult(new Dictionary<string, string>());

    public virtual CopyRewrite AsCopy(string text)
        => throw new NotSupportedException($"{DisplayName} does not support import-as-copy");

    /// <summary>Import one validated file. verifyKeys are the identities to confirm after
    /// the write (already rewritten when the copy policy applied).</summary>
    public virtual Task<ImportOutcome> ImportAsync(string text, IReadOnlyList<string> verifyKeys,
        ImportOptions opt, CancellationToken ct)
        => throw new NotSupportedException($"{DisplayName} does not import");
}

/// <summary>Creates the provider for an area key, or null when the area is not implemented
/// in this build (its card in the catalog says which phase it is pinned to).</summary>
public static class AreaRegistry
{
    public static AreaProvider? Create(string key, SwisSession swis) => key switch
    {
        "dashboards" => new DashboardsProvider(swis),
        "alerts" => new AlertsProvider(swis),
        "reports" => new ReportsProvider(swis),
        "sam" => new SamTemplatesProvider(swis),
        "wpm" => new WpmRecordingsProvider(swis),
        "ncmdevice" => new NcmDeviceTemplatesProvider(swis),
        "nodescp" => new NodesCpProvider(swis),
        "ncmcompliance" => new NcmComplianceProvider(swis),
        _ => null,
    };
}
