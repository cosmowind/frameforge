$ErrorActionPreference = "Stop"
$root = "./workspace"

# Group camera/0 files by session
$files = Get-ChildItem $root -Filter "*.mp4" | Where-Object { $_.Name -match '^session_(\d+)_ego_(\d+)_ego_camera_0\.mp4$' }
$groups = @{}
foreach ($f in $files) {
    if ($f.Name -match '^session_(\d+)_ego_(\d+)_ego_camera_0\.mp4$') {
        $sess = $matches[1]
        if (-not $groups.ContainsKey($sess)) { $groups[$sess] = @() }
        $groups[$sess] += $f
    }
}

# Concat per session
$done = 0
foreach ($sess in ($groups.Keys | Sort-Object)) {
    $clips = $groups[$sess] | Sort-Object { [int]($_.Name -replace '.*ego_(\d+)_ego_camera_0\.mp4','$1') }
    $listFile = Join-Path $root "concat_$sess.txt"
    $content = ($clips | ForEach-Object { "file '$($_.FullName -replace '\\','/')'" }) -join "`n"
    Set-Content -Path $listFile -Value $content -Encoding UTF8
    $outFile = Join-Path $root "session_${sess}_merged.mp4"
    Write-Host "[$sess] $($clips.Count) clips -> session_${sess}_merged.mp4"
    ffmpeg -y -f concat -safe 0 -i $listFile -c copy $outFile >$null 2>&1
    Remove-Item $listFile -Force
    $done++
}

# Remove original clip files
foreach ($f in $files) { Remove-Item $f.FullName -Force -EA SilentlyContinue }
Remove-Item "$root\*.es.h265" -Force -EA SilentlyContinue

Write-Host "----------------------------------------"
Write-Host "Done! $done sessions merged."
Get-ChildItem $root -Filter "session_*_merged.mp4" | ForEach-Object {
    $dur = ffmpeg -i $_.FullName 2>&1 | Select-String 'Duration: (\d+):(\d+):(\d+)\.(\d+)' | ForEach-Object {
        $h,$m,$s,$ms = $_.Matches.Groups[1..4].Value
        [double]"$h*3600+$m*60+$s"
    }
    $durMin = if ($dur) { "{0:N1}min" -f ($dur/60) } else { "?" }
    Write-Host "  $($_.Name) ($durMin)"
}
