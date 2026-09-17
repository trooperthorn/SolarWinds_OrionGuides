# SAM Windows PowerShell Monitor: UDP ephemeral port usage.
# Argument example: percent   (or: count)
#
# Reads the live UDP endpoint table and the configured dynamic port range on
# the host the script runs on and reports how full the range is, which is the
# number Windows System event Tcpip 4266 fires on when it reaches 100 percent.
# Run in Remote Host mode so it executes on the target over WinRM.
#
# Output contract (one pair per component, as SAM's own PowerShell templates use):
#   Message: <text>
#   Statistic: <number>
# Exit 0 = Up, 1 = Down, 2 = Warning, 3 = Critical.
$metric = $args[0]
if (!$metric) { $metric = 'percent' }
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
    if ($metric -eq 'count') {
        Write-Host "Message: $($inRange.Count) of $count ephemeral UDP ports ($start-$end) in use; $($endpoints.Count) UDP endpoints total. Top: $($top -join ', ')"
        Write-Host "Statistic: $($inRange.Count)"
    } else {
        Write-Host "Message: $pct% of the UDP dynamic range ($start-$end, $count ports) in use. Top: $($top -join ', ')"
        Write-Host "Statistic: $pct"
    }
    if ($pct -ge 90) { exit 3 } elseif ($pct -ge 70) { exit 2 } else { exit 0 }
} catch {
    Write-Host "Message: script failed: $($_.Exception.Message)"
    exit 1
}
