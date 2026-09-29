using Porter.Areas;

namespace Porter.Tests;

public class NodesCpTests
{
    private static string Row(params string[] cells) => string.Join(",", cells.Select(NodesCpProvider.CsvCell));

    [Fact]
    public void RoundTrip_PreservesQuotedMultilineCellAndCommas()
    {
        var note = "line one, with comma\nline \"two\"";
        var text = "Caption,IPAddress,Note\n" + Row("core-1", "10.0.0.1", note) + "\n";

        var v = new AreaValidation();
        var table = NodesCpProvider.ParseTable(text, v);

        Assert.NotNull(table);
        Assert.True(v.Ok);
        var row = Assert.Single(table!.Rows);
        Assert.Equal("core-1", row.Caption);
        Assert.Equal("10.0.0.1", row.Ip);
        Assert.Equal(note, row.Values[0]);
    }

    [Theory]
    [InlineData("=SUM(A1)")]
    [InlineData("+1")]
    [InlineData("-2")]
    [InlineData("@cmd")]
    public void FormulaLeaders_GetQuotePrefixOnExport_AndLoseItOnImport(string value)
    {
        var cell = NodesCpProvider.CsvCell(value);
        Assert.StartsWith("'" + value[0], cell);

        var table = NodesCpProvider.ParseTable("Caption,IPAddress,Note\n" + Row("n", "1.1.1.1", value) + "\n",
            new AreaValidation());
        Assert.Equal(value, table!.Rows[0].Values[0]);
    }

    [Fact]
    public void OrdinaryApostrophe_IsNotStripped()
    {
        Assert.Equal("'hello", NodesCpProvider.Unprefix("'hello"));
        Assert.Equal("'=x", NodesCpProvider.Unprefix("''=x"));   // exactly one quote removed
        Assert.Equal("''=x", NodesCpProvider.CsvCell("'=x"));    // a literal "'=x" is guarded too, so it round-trips
        Assert.Equal("plain", NodesCpProvider.CsvCell("plain"));
    }
}
