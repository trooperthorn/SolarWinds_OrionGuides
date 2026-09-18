# SAM Windows PowerShell Monitor: ERCOT Real-Time System Conditions, read off the HTML page.
# Argument example: conditions   (or: dcties)
#
# Fetches https://www.ercot.com/content/cdr/html/real_time_system_conditions.html on the
# polling engine (Local Host mode) and turns each label/value row of its table into one
# named statistic. ERCOT publishes most of these numbers as JSON too, and the API Poller
# template in scripts/api-pollers/ercot-grid-conditions.apipoller.template reads those;
# this script exists for the values only the page carries (time error, BAAL exceedances,
# net load, wind and PVGR output, the DC_S tie) and as the fallback if the API Poller's
# newest-row paths are not accepted by the platform.
#
# Output contract (named pairs, as SAM's own multi-value script templates use):
#   Message.<Name>: <text>
#   Statistic.<Name>: <number>
# Exit 0 = Up, 1 = Down (page unreachable or no rows matched).
# SAM caps a component at ten pairs, which is why the page is split across two arguments.
$mode = $args[0]
if (!$mode) { $mode = 'conditions' }
$ErrorActionPreference = 'Stop'

# The page label, exactly as ERCOT prints it, to the statistic name the dashboard queries.
$conditions = @{
    'Current Frequency'                                          = 'Frequency'
    'Instantaneous Time Error'                                   = 'Time_Error'
    'Consecutive BAAL Clock-Minute Exceedances (min)'            = 'BAAL_Exceedances'
    'Actual System Demand'                                       = 'System_Demand'
    'Average Net Load'                                           = 'Net_Load'
    'Total System Capacity (not including Ancillary Services)'   = 'System_Capacity'
    'Total Wind Output'                                          = 'Wind_Output'
    'Total PVGR Output'                                          = 'PVGR_Output'
    'Current System Inertia'                                     = 'System_Inertia'
}
$dcties = @{
    'DC_E (East)'        = 'DC_E'
    'DC_L (Laredo VFT)'  = 'DC_L'
    'DC_N (North)'       = 'DC_N'
    'DC_R (Railroad)'    = 'DC_R'
    'DC_S (Eagle Pass)'  = 'DC_S'
}
$wanted = if ($mode -eq 'dcties') { $dcties } else { $conditions }

try {
    # Windows PowerShell 5.1 negotiates TLS 1.0 by default and ercot.com refuses it.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = 'https://www.ercot.com/content/cdr/html/real_time_system_conditions.html'
    $html = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30).Content
    $updated = [regex]::Match($html, 'Last Updated:\s*([^<]+)<').Groups[1].Value.Trim()
    $rows = [regex]::Matches($html, '<td class="tdLeft">([^<]+)</td>\s*<td class="labelClassCenter">([^<]+)</td>')
    $emitted = 0
    foreach ($row in $rows) {
        $label = $row.Groups[1].Value.Trim()
        if (-not $wanted.ContainsKey($label)) { continue }
        $name = $wanted[$label]
        $value = [double]($row.Groups[2].Value.Trim() -replace ',', '')
        Write-Host "Message.${name}: $label = $value (ERCOT page updated $updated)"
        Write-Host "Statistic.${name}: $value"
        $emitted++
    }
    if ($emitted -eq 0) {
        Write-Host "Message: no matching rows on $url; the page layout has changed"
        exit 1
    }
    exit 0
} catch {
    Write-Host "Message: script failed: $($_.Exception.Message)"
    exit 1
}
