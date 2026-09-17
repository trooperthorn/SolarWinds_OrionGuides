# SAM Windows PowerShell Monitor: UDP ephemeral port usage.
# Reads the live UDP endpoint table and the configured dynamic port range on
# the target and reports how full the range is, which is the number Windows
# System event Tcpip 4266 fires on when it reaches 100 percent.
# Output contract: Statistic.<name>: <value> / Message.<name>: <text>, exit 0 Up, 2 Warning, 3 Critical.
$ErrorActionPreference = 'Stop'
try {
    $range = netsh int ipv4 show dynamicport udp | Out-String
    $start = [int]([regex]::Match($range, 'Start Port\s*:\s*(\d+)').Groups[1].Value)
    $count = [int]([regex]::Match($range, 'Number of Ports\s*:\s*(\d+)').Groups[1].Value)
    $end = $start + $count - 1
    $endpoints = @(Get-NetUDPEndpoint)
    $inRange = @($endpoints | Where-Object { $_.LocalPort -ge $start -and $_.LocalPort -le $end })
    $pct = if ($count -gt 0) { [math]::Round(100 * $inRange.Count / $count, 2) } else { 0 }
    $top = $inRange | Group-Object OwningProcess | Sort-Object Count -Descending | Select-Object -First 5 | ForEach-Object {
        $p = Get-Process -Id $_.Name -ErrorAction SilentlyContinue
        $n = if ($p) { $p.ProcessName } else { 'pid' }
        "$n($($_.Name))=$($_.Count)"
    }
    Write-Host "Statistic.PercentUsed : $pct"
    Write-Host "Message.PercentUsed : $($inRange.Count) of $count ephemeral UDP ports ($start-$end) in use. Top: $($top -join ', ')"
    Write-Host "Statistic.EphemeralInUse : $($inRange.Count)"
    Write-Host "Message.EphemeralInUse : total UDP endpoints $($endpoints.Count); dynamic range size $count"
    if ($pct -ge 90) { exit 3 } elseif ($pct -ge 70) { exit 2 } else { exit 0 }
} catch {
    Write-Host "Message.PercentUsed : script failed: $($_.Exception.Message)"
    exit 1
}
