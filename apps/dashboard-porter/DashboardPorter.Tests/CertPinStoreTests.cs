using System.IO;
using DashboardPorter.Core;

namespace DashboardPorter.Tests;

/// <summary>The atomic write behind CertPinStore.Pin, exercised in a scratch directory —
/// Pin itself writes to %ProgramData%\DashboardPorter, which a test must not touch.</summary>
public sealed class CertPinStoreTests : IDisposable
{
    private readonly string _dir = Directory.CreateTempSubdirectory("dbporter-pins-").FullName;
    public void Dispose() { try { Directory.Delete(_dir, true); } catch (IOException) { } }

    [Fact]
    public void WriteAtomically_CreatesTheFile_AndLeavesNoTempBehind()
    {
        var path = Path.Combine(_dir, "pins.json");
        CertPinStore.WriteAtomically(path, "{\"a:1\":[\"AB\"]}");
        Assert.Equal("{\"a:1\":[\"AB\"]}", File.ReadAllText(path));
        Assert.Equal(new[] { "pins.json" }, Directory.GetFiles(_dir).Select(Path.GetFileName));
    }

    [Fact]
    public void WriteAtomically_ReplacesAnExistingFileWhole()
    {
        var path = Path.Combine(_dir, "pins.json");
        File.WriteAllText(path, new string('x', 4096));
        CertPinStore.WriteAtomically(path, "{}");
        Assert.Equal("{}", File.ReadAllText(path));
        Assert.Single(Directory.GetFiles(_dir));
    }

    [Fact]
    public void WriteAtomically_FailedMove_LeavesTheOldFileIntact_AndNoTemp()
    {
        var path = Path.Combine(_dir, "pins.json");
        File.WriteAllText(path, "{\"kept\":[]}");
        // A read-only target makes the final move fail after the temp file was written:
        // the original must survive whole and the temp file must be cleaned up.
        File.SetAttributes(path, FileAttributes.ReadOnly);
        try
        {
            var ex = Record.Exception(() => CertPinStore.WriteAtomically(path, "{}"));
            Assert.True(ex is IOException or UnauthorizedAccessException, ex?.ToString());
            Assert.Equal("{\"kept\":[]}", File.ReadAllText(path));
            Assert.Empty(Directory.GetFiles(_dir, "*.tmp"));
        }
        finally
        {
            File.SetAttributes(path, FileAttributes.Normal);
        }
    }
}
