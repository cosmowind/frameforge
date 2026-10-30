const fs = require('fs');
const buf = fs.readFileSync('session_00000/extracted.mp4');
const lines = [];
function log(...args) { lines.push(args.join(' ')); }

function walk(buf, start, end, depth=0) {
  let p = start;
  while (p+8 <= end) {
    const sz = buf.readUInt32BE(p);
    const tp = buf.toString('ascii', p+4, p+8);
    if (sz < 8) break;
    log(' '.repeat(depth*2), tp, 'size', sz, '@', p);
    // Recurse for container boxes
    if (['moov','trak','mdia','minf','stbl','edts','udta'].includes(tp)) {
      walk(buf, p+8, p+sz, depth+1);
    }
    p += sz;
  }
}
walk(buf, 0, buf.length);

// Now read all the interesting boxes
const out = [];
const moov = buf.toString('binary').indexOf('moov');
let i = 0;
while (i < lines.length) {
  out.push(lines[i]); i++;
}
const text = out.join('\n');

// Find offsets from text
function findOffset(name) {
  for (const line of lines) {
    if (line.trim().startsWith(name + ' ')) {
      const m = line.match(/@ (\d+)/);
      if (m) return parseInt(m[1]);
    }
  }
  return -1;
}
const sttsOff = findOffset('stts');
const stszOff = findOffset('stsz');
const stssOff = findOffset('stss');
const mdhdOff = findOffset('mdhd');
const tkhdOff = findOffset('tkhd');
const hvcCOff = findOffset('hvcC');

log('--- Detailed box reads ---');
if (sttsOff >= 0) {
  const p = sttsOff;
  const sz = buf.readUInt32BE(p);
  const entry_count = buf.readUInt32BE(p+8+4);
  log('stts entries:', entry_count);
  let total_samples = 0, total_dur = 0;
  for (let i = 0; i < entry_count; i++) {
    const sample_count = buf.readUInt32BE(p+8+4+4+i*8);
    const sample_delta = buf.readUInt32BE(p+8+4+4+i*8+4);
    total_samples += sample_count; total_dur += sample_count * sample_delta;
    if (i < 3 || i > entry_count-3) log('  stts['+i+'] count', sample_count, 'delta', sample_delta, '(t=', (sample_delta/1000).toFixed(3),'ms)');
  }
  log('  total_samples', total_samples, 'total_dur', total_dur, 'ms =>', (total_dur/1000).toFixed(3), 'sec');
  if (entry_count > 0) {
    const firstDelta = buf.readUInt32BE(p+8+4+4+4);
    const firstCount = buf.readUInt32BE(p+8+4+4);
    log('  first delta / first count =', (firstDelta/firstCount).toFixed(3), 'ms/frame (avg over first run)');
    log('  first delta / timescale? Need mdhd timescale...');
  }
}
if (stszOff >= 0) {
  const p = stszOff;
  const sample_size = buf.readUInt32BE(p+8+4);
  const sample_count = buf.readUInt32BE(p+8+4+4);
  log('stsz sample_size', sample_size, 'sample_count', sample_count);
}
if (stssOff >= 0) {
  const p = stssOff;
  const entry_count = buf.readUInt32BE(p+8+4);
  log('stss entries:', entry_count);
  if (entry_count < 20) {
    for (let i = 0; i < entry_count; i++) log('  sync_sample', buf.readUInt32BE(p+8+4+4+i*4));
  }
}
if (mdhdOff >= 0) {
  const p = mdhdOff;
  const ver = buf[p+8];
  const timescale = ver === 0 ? buf.readUInt32BE(p+8+4+4+4) : buf.readUInt32BE(p+8+4+8+8);
  const duration = ver === 0 ? buf.readUInt32BE(p+8+4+4+4+4) : buf.readUInt32BE(p+8+4+8+8+4);
  log('mdhd timescale', timescale, 'duration', duration, '=>', (duration/timescale).toFixed(3), 'sec');
}
if (tkhdOff >= 0) {
  const p = tkhdOff;
  const ver = buf[p+8];
  if (ver === 0) {
    const width_fp = buf.readUInt32BE(p+8+4+4+4+4+4+4+4);
    const height_fp = buf.readUInt32BE(p+8+4+4+4+4+4+4+4+4);
    log('tkhd width', (width_fp/65536).toFixed(2), 'height', (height_fp/65536).toFixed(2));
  } else {
    const width_fp = buf.readUInt32BE(p+8+4+8+8+8+8+8);
    const height_fp = buf.readUInt32BE(p+8+4+8+8+8+8+8+4);
    log('tkhd width', (width_fp/65536).toFixed(2), 'height', (height_fp/65536).toFixed(2));
  }
}
if (hvcCOff >= 0) {
  const p = hvcCOff;
  const sz = buf.readUInt32BE(p);
  log('hvcC size', sz, 'first 80 bytes:');
  log(Array.from(buf.subarray(p+8, p+8+Math.min(sz-8, 80))).map(b=>b.toString(16).padStart(2,'0')).join(' '));
}

fs.writeFileSync('session_00000/_mp4_probe2.txt', lines.join('\n'));
