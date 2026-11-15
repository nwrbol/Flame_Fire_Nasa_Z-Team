"""Profile the 3D scene with ?perf=1: 4 environments x 3 camera modes.

Headless Edge: GPU numbers are not trustworthy (often a software or virtual GPU), so the table
reports the CPU side of a frame, draw calls and triangles. Real fps: open /?perf=1 in Chrome.

Usage:
  .venv\\Scripts\\python.exe -m e2e.perf_profile --label before
  .venv\\Scripts\\python.exe -m e2e.perf_profile --label after --cpu 4 --mobile
Writes docs/perf/<label>.json and prints a Markdown table.
"""
import argparse
import gzip
import json
import math
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'perf'
ENVS = ('earth', 'moon', 'mars', 'space')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def bundle_size():
    files = [p for p in (ROOT / 'frontend').rglob('*') if p.is_file() and 'node_modules' not in p.parts and 'src' not in p.parts
             and p.suffix in ('.js', '.css', '.html')]
    raw = sum(p.stat().st_size for p in files)
    gz = sum(len(gzip.compress(p.read_bytes(), 9)) for p in files)
    return round(raw / 1024), round(gz / 1024)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', default='run')
    ap.add_argument('--cpu', type=float, default=1, help='CPU throttling rate (CDP), e.g. 4')
    ap.add_argument('--mobile', action='store_true', help='phone emulation: 390x844, DPR 3, touch')
    ap.add_argument('--quality', default='', help='force ?quality=low|medium|high')
    ap.add_argument('--seconds', type=float, default=3.2)
    a = ap.parse_args()

    port = free_port(); base = f'http://127.0.0.1:{port}'
    srv = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', str(port)], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(base + '/health', timeout=1); break
        except OSError:
            time.sleep(.2)
    rows, meta = [], {}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel='msedge', headless=True)
            ctx = b.new_context(bypass_csp=True, **({'viewport': {'width': 390, 'height': 844}, 'device_scale_factor': 3, 'is_mobile': True, 'has_touch': True}
                                   if a.mobile else {'viewport': {'width': 1280, 'height': 900}}))
            p = ctx.new_page()
            if a.cpu > 1:
                ctx.new_cdp_session(p).send('Emulation.setCPUThrottlingRate', {'rate': a.cpu})
            url = base + '/?perf=1' + (f'&quality={a.quality}' if a.quality else '')
            p.goto(url)
            p.evaluate("document.getElementById('scene3d').scrollIntoView({block:'center'})")
            p.wait_for_function('window.cabin3d && performance.getEntriesByName("mf-3d-first-frame").length', timeout=120000)
            meta['first_frame_ms'] = round(p.evaluate('performance.getEntriesByName("mf-3d-first-frame")[0].startTime'))
            meta['renderer'] = p.evaluate("(() => { const gl = cabin3d.renderer.getContext(); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : 'n/a'; })()")
            for env in ENVS:
                t_click = time.perf_counter()
                p.click(f'[data-env="{env}"]')
                p.evaluate("document.getElementById('scene3d').scrollIntoView({block:'center'})")
                p.wait_for_function(f"cabin3d.viewEnv === '{env}'", timeout=120000, polling=50)
                meta.setdefault('env_switch_ms', {})[env] = round((time.perf_counter() - t_click) * 1000)
                p.wait_for_timeout(1500)
                for mode, pos in (('overview', None), ('corner', [1.8, 2.1, 1.3]), ('window-close', [-.95, 1.5, -1.3])):
                    if pos is None:
                        p.evaluate("cabin3d.setView('overview')")
                    else:
                        p.evaluate(f'cabin3d.setCamera({pos}, [0, 1.2, 0])')
                    p.wait_for_timeout(int(a.seconds * 1000))
                    s = p.evaluate('cabin3d.perf()')
                    rows.append({'env': env, 'mode': mode, **s})
            b.close()
    finally:
        srv.terminate(); srv.wait(10)
    meta['bundle_kb'], meta['bundle_gzip_kb'] = bundle_size()
    meta.update(cpu_throttle=a.cpu, mobile=a.mobile, quality=a.quality or 'auto')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{a.label}.json').write_text(json.dumps({'meta': meta, 'rows': rows}, indent=1), encoding='utf-8')
    print(json.dumps(meta))
    print('| env | camera | fps | CPU ms (avg / max) | GPU ms | draw calls | triangles | geom | tex | particles | awake bodies | heap MB | quality |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        print(f"| {r['env']} | {r['mode']} | {r['fps']} | {r['cpuMs']} / {r['cpuMaxMs']} | {r['gpuMs']} | {r['calls']} | {r['triangles']:,} | {r['geometries']} | {r['textures']} | "
              f"{r['particles']} | {r['bodiesAwake']}/{r['bodies']} | {r['heapMB']} | {r['quality']} |")


if __name__ == '__main__':
    main()
