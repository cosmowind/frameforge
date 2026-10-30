// hmd-decode.cjs — CJS wrapper that bridges to hmd-decode.esm.js via dynamic import().
//
// Node's require() cannot load ESM (.esm.js) files directly.
// This wrapper uses import() to dynamically load the ESM module at runtime,
// then exposes the same { parse, splitStereo, dedupParamSets } interface.
//
// Two access patterns are supported:
//   1. Direct object: require('./hmd-decode.cjs') → { parse, splitStereo, dedupParamSets }
//      Each method internally awaits the ESM load, so they are all async.
//   2. Init function:  const hmdDecode = require('./hmd-decode.cjs');
//      if (typeof hmdDecode === 'function') { const m = await hmdDecode(); ... }
//      This is the "wrapper path" — call the async init to get the raw module.

let _esm = null;

async function _load() {
  if (!_esm) {
    _esm = await import('./hmd-decode.esm.js');
  }
  return _esm;
}

// Export async wrapper methods (same interface as ESM, but each call awaits _load)
module.exports = {
  async parse(...args)      { const m = await _load(); return m.parse(...args); },
  async splitStereo(...args) { const m = await _load(); return m.splitStereo(...args); },
  async dedupParamSets(...args) { const m = await _load(); return m.dedupParamSets(...args); },
};
