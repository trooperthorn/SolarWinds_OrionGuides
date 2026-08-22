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

    /// <summary>Whether the caller asked for chain verification. Off by default in the UI,
    /// because a stock installation presents the self-signed "SolarWinds-Orion" certificate.
    /// Unverified sessions still record the presented certificate's fingerprint.</summary>
    public bool VerifyTls { get; }
    public string? PresentedThumbprint { get; private set; }
    public string? PresentedSubject { get; private set; }

    private readonly HttpClient _http;
    private bool _pinUseLogged;
    private bool _tlsNoted;

    public SwisSession(string server, int port, bool windowsAuth, string? username, string? password,
        bool verifyTls)
    {
        Server = server;
        Port = port;
        WindowsAuth = windowsAuth;
        VerifyTls = verifyTls;
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
        if (!VerifyTls)
        {
            // Accepted without verification (the default, for the stock SolarWinds-Orion
            // self-signed certificate) — but never silently: the fingerprint is recorded in
            // the Captain's Log once per session, so a changed certificate is visible.
            if (!_tlsNoted)
            {
                _tlsNoted = true;
                PresentedThumbprint = Convert.ToHexString(SHA256.HashData(cert.RawData));
                PresentedSubject = cert.Subject;
                SessionLog.Log("tls", $"{Server}:{Port}", "unverified-accepted",
                    $"{PresentedSubject} · SHA-256 {PresentedThumbprint}");
            }
            return true;
        }
        // Verification on: a self-signed certificate can still be pinned by SHA-256
        // thumbprint, explicitly, once — and the pin is logged.
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

    /// <summary>POST /Create/{entity} with a JSON property object. Returns the new row's swis URI.</summary>
    public async Task<string> CreateAsync(string entity, object properties, CancellationToken ct = default)
    {
        var body = JsonSerializer.Serialize(properties);
        using var resp = await _http.PostAsync($"Create/{entity}",
            new StringContent(body, Encoding.UTF8, "application/json"), ct);
        var text = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode) throw new SwisException((int)resp.StatusCode, text);
        using var doc = JsonDocument.Parse(text);
        return doc.RootElement.GetString() ?? "";
    }

    /// <summary>POST {swis-uri} with a partial JSON property object — CRUD update.</summary>
    public async Task UpdateAsync(string uri, object properties, CancellationToken ct = default)
    {
        var body = JsonSerializer.Serialize(properties);
        // The swis:// URI goes into the URL path verbatim; a relative-string PostAsync
        // would parse "swis://" as an absolute scheme and never reach the server.
        var target = new Uri(_http.BaseAddress + uri);
        using var resp = await _http.PostAsync(target,
            new StringContent(body, Encoding.UTF8, "application/json"), ct);
        if (!resp.IsSuccessStatusCode)
            throw new SwisException((int)resp.StatusCode, await resp.Content.ReadAsStringAsync(ct));
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
