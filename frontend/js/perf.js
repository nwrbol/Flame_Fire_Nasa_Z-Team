// ?perf=1 — performance overlay for the 3D scene. Measures, never changes what is drawn.
//  fps, CPU time of one frame (JS: simulation + scene update + WebGL command submission),
//  GPU time (EXT_disjoint_timer_query_webgl2, when the browser exposes it), draw calls and
//  triangles of the whole frame (shadow passes included), live geometries/textures/programs,
//  particles, physics bodies (awake/total), JS heap (Chromium only).
export function createPerf(renderer, extra) {
  const on = new URLSearchParams(location.search).has('perf');
  const gl = renderer.getContext();
  const ext = on ? gl.getExtension('EXT_disjoint_timer_query_webgl2') : null;
  const queries = [];          // pending GPU timer queries (resolved a few frames later)
  let q = null, gpuMs = NaN, gpuSum = 0, gpuN = 0, cpuT = 0;
  const S = { fps: 0, cpu: 0, cpuMax: 0, gpu: NaN, calls: 0, tris: 0, frames: 0 };
  const win = []; let n = 0, t0 = performance.now(), sumCpu = 0, maxCpu = 0;
  renderer.info.autoReset = false;          // count every pass of the frame (shadow maps included)

  let box = null;
  if (on) {
    box = document.createElement('pre');
    box.setAttribute('aria-hidden', 'true');
    box.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:99;margin:0;padding:8px 10px;border-radius:8px;' +
      'background:rgba(0,0,0,.78);color:#9ef59e;font:11px/1.35 ui-monospace,Consolas,monospace;pointer-events:none;white-space:pre';
    document.body.append(box);
  }

  function begin() {
    cpuT = performance.now();
    renderer.info.reset();
    if (ext && !q && queries.length < 4) { q = gl.createQuery(); gl.beginQuery(ext.TIME_ELAPSED_EXT, q); }
  }
  function end() {
    if (q) { gl.endQuery(ext.TIME_ELAPSED_EXT); queries.push(q); q = null; }
    while (queries.length && gl.getQueryParameter(queries[0], gl.QUERY_RESULT_AVAILABLE)) {
      const r = queries.shift();
      if (!gl.getParameter(ext.GPU_DISJOINT_EXT)) { gpuSum += gl.getQueryParameter(r, gl.QUERY_RESULT) / 1e6; gpuN++; }
      gl.deleteQuery(r);
    }
    const cpu = performance.now() - cpuT;
    sumCpu += cpu; maxCpu = Math.max(maxCpu, cpu); n++; S.frames++;
    S.calls = renderer.info.render.calls; S.tris = renderer.info.render.triangles;
    const now = performance.now();
    if (now - t0 >= 1000) {
      S.fps = n * 1000 / (now - t0); S.cpu = sumCpu / n; S.cpuMax = maxCpu; if (gpuN) { gpuMs = gpuSum / gpuN; gpuSum = 0; gpuN = 0; } S.gpu = gpuMs;
      n = 0; sumCpu = 0; maxCpu = 0; t0 = now;
      if (box) draw();
    }
  }
  function snapshot() {
    const m = renderer.info.memory, e = extra();
    return { fps: +S.fps.toFixed(1), cpuMs: +S.cpu.toFixed(2), cpuMaxMs: +S.cpuMax.toFixed(2), gpuMs: isNaN(S.gpu) ? null : +S.gpu.toFixed(2),
      calls: S.calls, triangles: S.tris, geometries: m.geometries, textures: m.textures, programs: renderer.info.programs?.length ?? null,
      heapMB: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null, ...e };
  }
  function draw() {
    const s = snapshot();
    box.textContent =
      `fps        ${s.fps}\n` +
      `CPU ms     ${s.cpuMs}  (max ${s.cpuMaxMs})\n` +
      `GPU ms     ${s.gpuMs ?? 'n/a (no timer query)'}\n` +
      `draw calls ${s.calls}\ntriangles  ${s.triangles.toLocaleString('en')}\n` +
      `geometries ${s.geometries}  textures ${s.textures}  programs ${s.programs}\n` +
      `particles  ${s.particles}\nbodies     ${s.bodiesAwake}/${s.bodies} awake\n` +
      `quality    ${s.quality}  scale ${s.scale}  dpr ${s.dpr}\n` +
      `JS heap    ${s.heapMB ?? 'n/a'} MB`;
  }
  return { on, begin, end, snapshot };
}
