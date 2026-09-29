using Porter.Core;

namespace Porter.Tests;

/// <summary>Shared fixtures. The session never connects — Validate paths do not use it.</summary>
internal static class TestData
{
    public static SwisSession Session() => new("localhost", 17774, false, "u", "p", false);

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
