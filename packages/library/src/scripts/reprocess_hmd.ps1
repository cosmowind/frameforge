# reprocess_hmd.ps1 - 批量重新预处理 HMD session
# 使用方法：在项目根目录 PowerShell 中运行 .\src\scripts\reprocess_hmd.ps1

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path "$scriptDir\..\.."
$csvPath = "$projectRoot\runtime\data\video_manager.csv"
$apiBase = "http://localhost:5000"

# 读取 CSV 文件
$rows = Get-Content -Path $csvPath -Encoding UTF8 | Where-Object { $_ -match "hmd" }

Write-Host "Found $($rows.Count) HMD sessions to reprocess"

$count = 0
foreach ($row in $rows) {
    $folder = $row.Split(',')[0]
    $count++
    
    Write-Host "[$count/$($rows.Count)] Starting preprocess for: $folder"
    
    try {
        $body = @{ folder = $folder } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$apiBase/api/hmd/process" `
            -Method Post `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 5
        
        Write-Host "  ✓ Preprocess queued successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "  ✗ Failed to queue preprocess: $_" -ForegroundColor Red
    }
    
    # 避免请求过快
    Start-Sleep -Milliseconds 500
}

Write-Host "`nAll preprocess requests sent. Check Flask console for progress." -ForegroundColor Cyan
Write-Host "You can also check status at: $apiBase/api/hmd/queue-status" -ForegroundColor Cyan
