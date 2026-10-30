// verify_merge.js — 多文件合并：data0706/session_00026 里 7 个 ego_*.mcap → 1 个 mp4
// 验收标准：
//   - 合并后帧数 = 各文件 camera/0 帧数之和
//   - ffmpeg -v error -i ... -f null - exit 0
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const mcap2mp4 = require('./core.js');

const SESSION_DIR = process.argv[2] || path.resolve(__dirname, '..', 'data0706', 'session_00026');
const OUT = path.resolve(__dirname, 'verify_merge.mp4');
const FFMPEG = process.env.FFMPEG || 'F:/sys/music/ffmpeg-8.0.1/bin/ffmpeg.exe';

const egoFiles = fs.readdirSync(SESSION_DIR)
  .filter(f => /^ego_\d+\.mcap$/i.test(f))
  .sort((a, b) => {
    const na = parseInt(a.match(/\d+/)[0], 10);
    const nb = parseInt(b.match(/\d+/)[0], 10);
    return na - nb;
  });
console.log('session:', SESSION_DIR);
console.log('ego files:', egoFiles.length);

// 1) 解析所有文件，合并 camera/0 帧（按 capture_ns 排序）
const allFrames = [];
let totalCamera0 = 0;
for (const fn of egoFiles) {
  const path_ = path.join(SESSION_DIR, fn);
  const buf = fs.readFileSync(path_);
  const { frames } = mcap2mp4.parseMcap(buf);
  const cam = frames.get('/ego/camera/0') || [];
  totalCamera0 += cam.length;
  console.log(`  ${fn}: ${cam.length} camera/0 frames`);
  for (const f of cam) allFrames.push(f);
}
allFrames.sort((a, b) => a.capture_ns - b.capture_ns);
console.log(`total camera/0 frames: ${totalCamera0} (after sort: ${allFrames.length})`);

// 2) VPS/SPS/PPS + hvcC（用第一帧所在文件的参数集）
const ps = mcap2mp4.scanHevcVpsSpsPps(allFrames);
if (!ps) { console.error('no VPS/SPS/PPS'); process.exit(1); }
console.log(`VPS=${ps.vps.length} SPS=${ps.sps.length} PPS=${ps.pps.length}`);
const spsInfo = mcap2mp4.parseHevcSps(ps.sps);
console.log('SPS parsed:', JSON.stringify(spsInfo));

// 3) 构 hvcC + mux
const hvcC = mcap2mp4.buildHevcHvcC(ps.vps, ps.sps, ps.pps);
const t0 = Date.now();
const mp4 = mcap2mp4.muxMp4({
  frames: allFrames,
  hvcC,
  width: spsInfo && spsInfo.width,
  height: spsInfo && spsInfo.height,
  sps: ps.sps,
});
fs.writeFileSync(OUT, Buffer.from(mp4));
console.log(`mp4: ${(mp4.length / 1024 / 1024).toFixed(1)} MB -> ${OUT} (${Date.now() - t0} ms)`);

// 4) ffprobe 校验
console.log('\n--- ffprobe ---');
try {
  const probe = execSync(
    '"' + FFMPEG.replace('ffmpeg.exe', 'ffprobe.exe') + '"' +
    ' -v error -count_frames -select_streams v:0' +
    ' -show_entries stream=codec_name,width,height,nb_read_frames,duration' +
    ' -of default=noprint_wrappers=1 "' + OUT + '"',
    { encoding: 'utf8' });
  console.log(probe.trim());
  if (!probe.includes('nb_read_frames=' + totalCamera0)) {
    console.error('!! frame count mismatch: expected ' + totalCamera0);
    process.exit(1);
  }
} catch (e) {
  console.error('ffprobe failed:', e.message);
  process.exit(1);
}

// 5) ffmpeg 真解码
console.log('\n--- ffmpeg decode ---');
try {
  const dec = execSync(
    '"' + FFMPEG + '" -v error -i "' + OUT + '" -f null -',
    { encoding: 'utf8' });
  console.log('  exit=0' + (dec.trim() ? ' (warnings from source encoder, ignored)' : ''));
  if (dec.trim()) {
    for (const l of dec.trim().split('\n').slice(0, 3)) console.log('    ' + l);
    if (dec.trim().split('\n').length > 3) console.log('    ...');
  }
} catch (e) {
  console.error('ffmpeg decode failed (exit ' + e.status + '):\n' + (e.stderr || e.stdout || ''));
  process.exit(1);
}

fs.unlinkSync(OUT);
console.log('\n✓ all checks passed');
