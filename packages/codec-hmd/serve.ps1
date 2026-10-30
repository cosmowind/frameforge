# serve.ps1 — 启动一个本地静态 HTTP 服务来跑 hmd-player.html
# 解决 file:// 协议下 ESM import 被 CORS 拦截的问题
#
# 用法：右键此文件 → "使用 PowerShell 运行"
# 浏览器会自动打开 http://localhost:8000/hmd-player.html

$port = 8000
$dir  = $PSScriptRoot
$addr = "http://localhost:$port/"

# 优先用 python（很多机器装过），其次用 node
$py = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command py -ErrorAction SilentlyContinue)
if ($py) {
    Write-Host "用 Python 启动静态服务在 $addr" -ForegroundColor Green
    Start-Process $addr
    & $py.Source -m http.server $port
    return
}

# fallback: 用我们自己的 Node 写一个最简静态服务
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    Write-Host "用 Node 启动静态服务在 $addr" -ForegroundColor Green
    Start-Process $addr
    & $node -e @"
const http = require('http'); const fs = require('fs'); const path = require('path');
const ROOT = process.argv[1] || '.';
const TYPES = { '.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.hmd':'application/octet-stream','.h265':'video/hevc','.mp4':'video/mp4'};
http.createServer((req,res)=>{
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p==='/') p='/hmd-player.html';
  const fp = path.join(ROOT,p);
  fs.readFile(fp,(err,data)=>{
    if(err){res.writeHead(404);res.end('not found '+p);return;}
    res.writeHead(200,{'Content-Type':TYPES[path.extname(fp)]||'application/octet-stream'});
    res.end(data);
  });
}).listen($port, () => console.log('listening on $addr'));
"@ $dir
    return
}

Write-Host "没找到 Python 也没找到 Node。" -ForegroundColor Red
Write-Host "请用浏览器双击 hmd-player-all-in-one.html 即可（自包含版，不需要 HTTP 服务）。"
