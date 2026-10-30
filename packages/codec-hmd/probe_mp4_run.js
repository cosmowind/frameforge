const fs = require('fs');
const out = fs.createWriteStream('session_00000/_mp4_probe.txt');
const orig = console.log;
console.log = (...args) => { out.write(args.join(' ') + '\n'); };
require('./probe_mp4.js');
out.end();
console.log = orig;
