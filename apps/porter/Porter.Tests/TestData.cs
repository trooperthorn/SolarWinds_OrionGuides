using Porter.Core;

namespace Porter.Tests;

/// <summary>Shared fixtures. The session never connects — Validate paths do not use it.</summary>
internal static class TestData
{
    public static SwisSession Session() => new("localhost", 17774, false, "u", "p", false);

    /// <summary>A file from the repository checkout (real samples under scripts/), found by
    /// walking up from the test binaries to the folder that holds AGENTS.md.</summary>
    public static string RepoFile(params string[] parts)
    {
        var dir = new System.IO.DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !System.IO.File.Exists(System.IO.Path.Combine(dir.FullName, "AGENTS.md")))
            dir = dir.Parent;
        if (dir is null) throw new InvalidOperationException("repository root not found above the test binaries");
        return System.IO.Path.Combine(new[] { dir.FullName }.Concat(parts).ToArray());
    }

    public const string Dashboard = """
        {
          "version": 1,
          "dashboards": [
            { "unique_key": "dash-1", "name": "Ops",
              "widgets": [ { "unique_key": "w-1" }, { "unique_key": "w-2" } ] }
          ],
          "widgets": [
            { "unique_key": "w-1",
              "dataSource": { "properties": { "swql": "SELECT Name FROM Orion.Nodes WHERE Name = 'Ops'" } } },
            { "unique_key": "w-2" }
          ]
        }
        """;
}
