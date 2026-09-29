using Porter.Core;

namespace Porter.Tests;

public class PackageWriterTests
{
    [Theory]
    [InlineData("Core Router 1", "Core_Router_1")]
    [InlineData("a/b:c*d?", "a_b_c_d")]
    [InlineData("___", "unnamed")]
    [InlineData("", "unnamed")]
    public void Sanitize_ReplacesUnsafeCharacters(string input, string expected)
        => Assert.Equal(expected, PackageWriter.Sanitize(input));

    [Fact]
    public void ToolName_ComesFromTheAssemblyVersion()
        => Assert.Matches(@"^Porter \d+\.\d+\.\d+$", PackageWriter.ToolName);
}
