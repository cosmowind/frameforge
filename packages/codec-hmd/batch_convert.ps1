$ErrorActionPreference = "Continue"
$startTime = Get-Date
$sw = [System.Diagnostics.Stopwatch]::StartNew()

$mcapFiles = Get-ChildItem "./workspace" -Recurse -Filter "*.mcap"
$total = $mcapFiles.Count
$counter = 0

Write-Host "Start processing $total mcap files..."
Write-Host "Total size: $([math]::Round(($mcapFiles | Measure-Object -Property Length -Sum).Sum/1GB, 2)) GB"
Write-Host "----------------------------------------"

foreach ($file in $mcapFiles) {
    $counter++
    $fileSizeMB = [math]::Round($file.Length/1MB, 2)
    $sessionStart = Get-Date
    Write-Host "[$counter/$total] Processing: $($file.FullName)"
    try {
        python "./workspace" $file.FullName
        $sessionElap = (Get-Date) - $sessionStart
        Write-Host "  -> Done, size: ${fileSizeMB}MB, time: $($sessionElap.TotalSeconds.ToString('F1'))s"
    } catch {
        Write-Host "  -> Error: $_"
    }
}

$sw.Stop()
$totalElap = $sw.Elapsed
Write-Host "----------------------------------------"
Write-Host "All done! Total: $counter files"
Write-Host "Total time: $($totalElap.TotalMinutes.ToString('F1')) min ($($totalElap.TotalSeconds.ToString('F1')) sec)"
