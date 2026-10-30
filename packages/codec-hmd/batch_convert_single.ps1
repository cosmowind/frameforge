$ErrorActionPreference = "Continue"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

$mcapFiles = Get-ChildItem "./workspace" -Recurse -Filter "*.mcap" | Sort-Object FullName
$total = $mcapFiles.Count
$counter = 0

Write-Host "Processing $($total) mcap files (camera/0 only)..."
Write-Host "Total size: $([math]::Round(($mcapFiles | Measure-Object -Property Length -Sum).Sum/1GB, 2)) GB"
Write-Host "----------------------------------------"

foreach ($file in $mcapFiles) {
    $counter++
    $fileSizeMB = [math]::Round($file.Length/1MB, 2)
    $sessionStart = Get-Date
    Write-Host "[$counter/$total] $($file.FullName)"
    try {
        python "./workspace" $file.FullName --camera 0
        $elap = (Get-Date) - $sessionStart
        Write-Host "  -> Done, ${fileSizeMB}MB, $($elap.TotalSeconds.ToString('F1'))s"
    } catch {
        Write-Host "  -> Error: $_"
    }
}

$sw.Stop()
Write-Host "----------------------------------------"
Write-Host "All done! Total: $counter files"
Write-Host "Total time: $($sw.Elapsed.TotalMinutes.ToString('F1')) min ($($sw.Elapsed.TotalSeconds.ToString('F1')) sec)"
