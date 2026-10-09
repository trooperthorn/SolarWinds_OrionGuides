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

    private static System.Text.Json.JsonElement Json(string json)
        => System.Text.Json.JsonDocument.Parse(json).RootElement.Clone();

    [Theory]
    [InlineData("{\"Status\":\"Valid\",\"ErrorMessage\":null}", "Valid")]
    [InlineData("{\"Status\":0}", "Valid")]
    [InlineData("{\"Status\":\"isreserved\"}", "IsReserved")]
    [InlineData("{\"Status\":3}", "Exists")]
    [InlineData("{\"status\":\"4\"}", "Error")]
    [InlineData("{\"Status\":1}", "IsSystem")]
    [InlineData("{\"Status\":9}", "Unknown")]
    [InlineData("{\"Status\":\"Maybe\"}", "Unknown")]
    [InlineData("{\"ErrorMessage\":\"x\"}", "Unknown")]
    [InlineData("true", "Unknown")]
    public void ValidationResult_StatusAsStringOrNumber(string json, string expected)
        => Assert.Equal(expected, NodesCpProvider.ParseValidation(Json(json)).Status.ToString());

    [Fact]
    public void ValidationResult_KeepsErrorMessage_AndNullIsNeverValid()
    {
        var r = NodesCpProvider.ParseValidation(Json("{\"Status\":\"Error\",\"ErrorMessage\":\"name too long\"}"));
        Assert.Equal(NodesCpProvider.CpValidationStatus.Error, r.Status);
        Assert.Equal("Error", r.StatusText);
        Assert.Equal("name too long", r.ErrorMessage);

        Assert.Equal(NodesCpProvider.CpValidationStatus.Unknown, NodesCpProvider.ParseValidation(null).Status);
    }
}
