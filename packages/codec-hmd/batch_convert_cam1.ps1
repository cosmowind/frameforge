$ErrorActionPreference = "Continue"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

$mcapFiles = Get-ChildItem "./workspace" -Recurse -Filter "*.mcap" | Sort-Object FullName
$total = $mcapFiles.Count
$counter = 0

Write-Host "Processing $($total) mcap files (camera/1 only)..."

foreach ($file in $mcapFiles) {
    $counter++
    Write-Host "[$counter/$total] $($file.Name)"
    python "./workspace" $file.FullName --camera 1
}

$sw.Stop()
Write-Host "----------------------------------------"
Write-Host "Done! Total time: $($sw.Elapsed.TotalMinutes.ToString('F1')) min ($($sw.Elapsed.TotalSeconds.ToString('F1')) sec)"
