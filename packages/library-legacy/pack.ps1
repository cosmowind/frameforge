# 打包项目到 zip（排除运行时产物 / 用户数据 / 凭据）
# 由 打包备份.bat 调用
param([string]$src = ".")

# 强制 UTF-8 输出（避免在 cmd / 老版 Windows 的 GBK 控制台乱码）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

if (-not (Test-Path $src)) {
    Write-Host "[ERROR] 源目录不存在: $src" -ForegroundColor Red
    exit 1
}
$src = (Resolve-Path $src).Path

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$zipName = "video-sort-package_$ts.zip"
$dst = Join-Path $src $zipName

Write-Host ""
Write-Host "============================================================"
Write-Host "  打包项目到 zip"
Write-Host "============================================================"
Write-Host ("Source:  " + $src)
Write-Host ("Dest:    " + $dst)
Write-Host ""

# 排除规则
$excludeTop    = @('.git','.claude','__pycache__','csv_backups','archive',
                   'logs','dist','build','venv','.venv','.idea','.vscode',
                   'hmd_cache','thumbnails','_thumb_*','node_modules')
$excludeName   = @('cookie.txt','.env','nul')
$excludeSuffix = @('.log','.csv','.zip','.pyc','.pyo','.tmp','.bak')
$excludePrefix = @('_upload_now','_test_','__test_','video-sort-package_')

# 顶层过滤
$items = Get-ChildItem -Path $src -Force | Where-Object {
    $n = $_.Name
    -not ($excludeTop -contains $n) -and
    -not ($excludeName -contains $n) -and
    -not ($excludeSuffix | Where-Object { $n -like ('*' + $_) }) -and
    -not ($excludePrefix | Where-Object { $n -like ($_ + '*') })
}

Write-Host ("Top-level items: " + $items.Count)
$items | Select-Object Name, @{N='KB';E={[math]::Round($_.Length/1KB,1)}} |
    Format-Table -AutoSize

if ($items.Count -eq 0) {
    Write-Host "[ERROR] 没有可打包的项目" -ForegroundColor Red
    exit 1
}

# Sub-directory recursive exclude (handles vendor-upload-pkg/node_modules deep paths)
$innerExclude = @('node_modules','__pycache__','.git','.claude',
                  'hmd_cache','thumbnails','csv_backups',
                  'archive','logs','dist','build','venv','.venv','.idea','.vscode')

# Use .NET ZipArchive directly. Compress-Archive has a known bug where
# multiple -Path entries get flattened to base names; manual entry creation
# preserves the relative path correctly.
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path $dst) { Remove-Item $dst -Force }
$zip = [System.IO.Compression.ZipFile]::Open($dst, 1)  # 1 = ZipArchiveMode.Create
try {
    foreach ($it in $items) {
        if ($it.PSIsContainer) {
            Get-ChildItem -Path $it.FullName -Recurse -File -Force | Where-Object {
                $rel = $_.FullName.Substring($src.Length).TrimStart('\','/')
                $seg = $rel -split '[\\/]'
                -not ($innerExclude | Where-Object { $seg -contains $_ })
            } | ForEach-Object {
                $rel = $_.FullName.Substring($src.Length).TrimStart('\','/').Replace('\','/')
                [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                    $zip, $_.FullName, $rel, 0  # 0 = CompressionLevel.Optimal
                ) | Out-Null
            }
        } else {
            $rel = $it.Name
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $it.FullName, $rel, 0  # 0 = CompressionLevel.Optimal
            ) | Out-Null
        }
    }
} finally {
    $zip.Dispose()
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  打包完成"
Write-Host "============================================================"
Get-Item $dst | Select-Object Name,
    @{N='Size_MB';E={[math]::Round($_.Length/1MB,2)}},
    LastWriteTime | Format-List
Write-Host ""
