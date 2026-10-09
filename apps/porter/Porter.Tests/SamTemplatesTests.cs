using System.IO;
using Porter.Areas;

namespace Porter.Tests;

public class SamTemplatesTests
{
    [Theory]
    [InlineData("citrix-hypervisor-monitoring.apmtemplate", "6ae07bdb-aabf-4b31-a26a-f74ac1172c6e")]
    [InlineData("ercot-system-conditions-html.apmtemplate", "f0761f31-c2a5-52d1-9de8-008f7b00aadf")]
    [InlineData("thermal-control-suite.apmtemplate", "81f9c292-b65a-41ae-8983-367d8dcf862a")]
    [InlineData("windows-udp-port-exhaustion.apmtemplate", "1bef1ef8-0ff1-46f1-ba01-b67b7efef121")]
    public void CollisionKey_IsTheTemplatesOwnUniqueId_NotAComponentGuid(string file, string templateGuid)
    {
        var text = File.ReadAllText(TestData.RepoFile("scripts", "sam-templates", file));
        // The real exports put ComponentTemplates (each with its own UniqueId) before the
        // template's metadata, so the first UniqueId in document order is a component's.
        var firstInDocument = System.Xml.Linq.XDocument.Parse(text).Descendants()
            .First(e => e.Name.LocalName == "UniqueId").Value.Trim();
        Assert.NotEqual(templateGuid, firstInDocument);

        var v = new SamTemplatesProvider(TestData.Session()).Validate(file, text);

        Assert.True(v.Ok, string.Join("; ", v.Errors));
        var item = Assert.Single(v.Items);
        Assert.Equal(templateGuid, item.Key);
    }
}
