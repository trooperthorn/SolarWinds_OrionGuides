using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;

namespace Porter.Core;

/// <summary>
/// One authenticated connection to a SWIS REST endpoint (default port 17774).
/// Every call the tool makes goes through QueryAsync or InvokeAsync — both are
/// strings-in / JSON-out, so no SolarWinds SDK is required.
/// </summary>
public sealed class SwisSession : IDisposable
{
    public string Server { get; }
    public int Port { get; }
    public string? Username { get; }
    public bool WindowsAuth { get; }

    /// <summary>Set when the last connection attempt failed on an unpinned certificate.</summary>
    public string? LastUntrustedThumbprint { get; private set; }
    public string? LastUntrustedSubject { get; private set; }

    private readonly HttpClient _http;
    private bool _pinUseLogged;

    public SwisSession(string server, int port, bool windowsAuth, string? username, string? password)
    {
        Server = server;
        Port = port;
        WindowsAuth = windowsAuth;
        Username = windowsAuth ? null : username;

        var handler = new HttpClientHandler
        {
            PreAuthenticate = true,
            // "Connect as my current Windows account" — no password ever entered or stored.
            UseDefaultCredentials = windowsAuth,
            ServerCertificateCustomValidationCallback = ValidateCertificate,
        };
        _http = new HttpClient(handler)
        {
            BaseAddress = new Uri($"https://{server}:{port}/SolarWinds/InformationService/v3/Json/"),
            Timeout = TimeSpan.FromSeconds(180),
        };
        if (!windowsAuth)
        {
            var raw = Encoding.UTF8.GetBytes($"{username}:{password}");
            _http.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Basic", Convert.ToBase64String(raw));
        }
    }

    private bool ValidateCertificate(HttpRequestMessage request, X509Certificate2? cert,
        X509Chain? chain, System.Net.Security.SslPolicyErrors errors)
    {
        if (errors == System.Net.Security.SslPolicyErrors.None) return true;
        if (cert is null) return false;
        // STIG posture: verification is never switched off. A self-signed certificate can be
        // pinned by SHA-256 thumbprint, explicitly, once — and the pin is logged.
        var thumb = Convert.ToHexString(SHA256.HashData(cert.RawData));
        if (CertPinStore.IsPinned(Server, Port, thumb))
        {
            if (!_pinUseLogged)
            {
                _pinUseLogged = true;
                SessionLog.Log("cert-pin", $"{Server}:{Port}", "accepted-by-pin", thumb);
            }
            return true;
        }
        LastUntrustedThumbprint = thumb;
        LastUntrustedSubject = cert.Subject;
        return false;
    }

    public async Task<JsonElement> QueryAsync(string swql,
        Dictionary<string, object?>? parameters = null, CancellationToken ct = default)
    {
        var body = JsonSerializer.Serialize(new
        {
            query = swql,
            parameters = parameters ?? new Dictionary<string, object?>(),
        });
        using var resp = await _http.PostAsync("Query",
            new StringContent(body, Encoding.UTF8, "application/json"), ct);
        var text = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode) throw new SwisException((int)resp.StatusCode, text);
        using var doc = JsonDocument.Parse(text);
        return doc.RootElement.GetProperty("results").Clone();
    }

    /// <summary>POST /Invoke/{entity}/{verb} with a positional-array body. Returns null for void verbs.</summary>
    public async Task<JsonElement?> InvokeAsync(string entity, string verb, object?[] args,
        CancellationToken ct = default)
    {
        var body = JsonSerializer.Serialize(args);
        using var resp = await _http.PostAsync($"Invoke/{entity}/{verb}",
            new StringContent(body, Encoding.UTF8, "application/json"), ct);
        var text = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode) throw new SwisException((int)resp.StatusCode, text);
        if (string.IsNullOrWhiteSpace(text) || text == "null") return null;
        using var doc = JsonDocument.Parse(text);
        return doc.RootElement.Clone();
    }

    /// <summary>Cheap universal reachability check — one row from the metadata the schema always has.</summary>
    public async Task TestAsync(CancellationToken ct = default)
    {
        await QueryAsync("SELECT TOP 1 Name FROM Metadata.Entity WHERE FullName = 'Orion.Nodes'", null, ct);
    }

    public void Dispose() => _http.Dispose();
}

public sealed class SwisException : Exception
{
    public int StatusCode { get; }

    public SwisException(int status, string body) : base(Summarise(status, body))
        => StatusCode = status;

    private static string Summarise(int status, string body)
    {
        try
        {
            using var doc = JsonDocument.Parse(body);
            if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                doc.RootElement.TryGetProperty("Message", out var m))
                return $"SWIS {status}: {m.GetString()}";
        }
        catch (JsonException) { }
        var trimmed = body.Length > 400 ? body[..400] : body;
        return $"SWIS {status}: {trimmed}";
    }
}
