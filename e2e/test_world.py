"""No 'canvas' anywhere: with a magenta clear colour (?testbg) every pixel of the 3D view must be
covered by the world (sky, stars, ground, hills, bodies, cabin). Any magenta pixel fails the test.

Run:  .venv\\Scripts\\python.exe -m unittest e2e.test_world      (screenshots: docs/screenshots/world/)
"""
import io
import math
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'docs' / 'screenshots' / 'world'

try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
except ImportError:  # pragma: no cover
    sync_playwright = None


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def magenta_pixels(png_bytes):
    """Pixels close to #ff00ff (also anti-aliased blends with it)."""
    img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
    data = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    return sum(1 for r, g, b in data if r > 150 and b > 150 and g < 100 and r - g > 100 and b - g > 100)


@unittest.skipIf(sync_playwright is None, 'playwright / Pillow not installed')
class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port(); cls.base = f'http://127.0.0.1:{cls.port}'
        cls.server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', str(cls.port)],
                                      cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base + '/health', timeout=1); break
            except OSError:
                time.sleep(.2)
        cls.pw = sync_playwright().start()
        cls.swiftshader = False
        cls.open([])
        if not cls.page.evaluate('!!window.cabin3d'):          # no WebGL in headless: software renderer
            cls.browser.close(); cls.swiftshader = True
            cls.open(['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        SHOTS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def open(cls, args):
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True, args=args)
        cls.page = cls.browser.new_page(viewport={'width': 1280, 'height': 900}, bypass_csp=True)
        cls.page.goto(cls.base + '/?testbg=1')
        cls.page.wait_for_function("typeof ENVS !== 'undefined' && ENVS && (window.cabin3d || !document.getElementById('no3d').hidden)", timeout=60000)
        # only the WebGL canvas is checked: hide page chrome that overlaps it
        cls.page.add_style_tag(content='nav, .illus, .cam-seg, .fab { visibility: hidden !important; }')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.terminate(); cls.server.wait(10)

    def set_env(self, env):
        self.page.click(f'[data-env="{env}"]')
        self.page.evaluate("document.getElementById('scene3d').scrollIntoView()")
        self.page.wait_for_function(f"window.cabin3d.worldEnv === '{env}'")
        self.page.wait_for_timeout(1300)                      # environment fade finished

    def shot(self, name):
        png = self.page.locator('#scene3d canvas').screenshot()
        (SHOTS / name).write_bytes(png)
        return magenta_pixels(png)

    def views(self, env):
        m = self.page.evaluate('window.cabin3d.MODES.outside')
        t = m['target']; out = []
        def orbit(dist, polar, az):
            return [t[0] + dist * math.sin(polar) * math.sin(az), t[1] + dist * math.cos(polar), t[2] + dist * math.sin(polar) * math.cos(az)]
        out.append(('min-distance', orbit(m['min'], 1.1, .6), t))
        out.append(('max-distance', orbit(m['max'], 1.1, .6), t))
        out.append(('horizon', orbit(m['max'], m['polar'], 2.2), t))                      # grazing, along the horizon
        out.append(('horizon-back', orbit(m['max'] * .6, m['polar'], -2.6), t))
        out.append(('look-up', [6, 1.6, 9], [-4, 45, -30]))                               # standing low, looking up at the sky
        out.append(('top-down', orbit(m['max'], .05, 0), t))
        if env == 'space':
            out.append(('from-below', orbit(m['max'], math.pi * .92, 1.0), t))          # no ground in orbit: below too
        return out

    def check_env(self, env):
        self.set_env(env)
        found = {}
        for name, pos, target in self.views(env):
            self.page.evaluate(f'window.cabin3d.setCamera({pos}, {target})'); self.page.wait_for_timeout(450)
            found[name] = self.shot(f'{env}-{name}.png')
        self.page.evaluate("window.cabin3d.setMode('inside', true)"); self.page.wait_for_timeout(600)
        found['inside-window'] = self.shot(f'{env}-inside-window.png')
        self.page.evaluate("window.cabin3d.setMode('outside', true)"); self.page.wait_for_timeout(600)
        found['outside-default'] = self.shot(f'{env}-outside.png')
        bad = {k: v for k, v in found.items() if v}
        self.assertEqual(bad, {}, f'{env}: magenta (uncovered) pixels in {bad}')

    def test_earth(self): self.check_env('earth')
    def test_moon(self): self.check_env('moon')
    def test_mars(self): self.check_env('mars')
    def test_space(self): self.check_env('space')

    def test_camera_limits(self):
        # outside: whole module visible, never beyond the built world; polar limit keeps us above ground
        self.set_env('earth')
        m = self.page.evaluate('window.cabin3d.MODES')
        self.assertGreaterEqual(m['outside']['min'], 4)          # whole 4.4 m module fits at min distance
        self.assertLessEqual(m['outside']['max'], 6000 / 10)     # far inside the 6 km world
        self.assertLess(m['outside']['polar'], math.pi / 2)
        self.page.evaluate("window.cabin3d.setMode('outside', true)"); self.page.wait_for_timeout(300)
        lim = self.page.evaluate('[cabin3d.controls.minDistance, cabin3d.controls.maxDistance, cabin3d.controls.maxPolarAngle, cabin3d.camera.near, cabin3d.camera.far]')
        self.assertEqual(lim[:2], [m['outside']['min'], m['outside']['max']])
        self.assertLess(lim[2], math.pi / 2)
        self.assertGreaterEqual(lim[3], .05)
        self.assertGreater(lim[4], 20000)
        self.set_env('space'); self.page.evaluate("window.cabin3d.setMode('outside', true)"); self.page.wait_for_timeout(300)
        self.assertAlmostEqual(self.page.evaluate('cabin3d.controls.maxPolarAngle'), math.pi)   # no ground: free orbit
        self.page.evaluate("window.cabin3d.setMode('inside', true)")

    def test_fps(self):
        out = {}
        page = self.browser.new_page(viewport={'width': 1280, 'height': 900}, bypass_csp=True)   # own page: normal colours
        page.goto(self.base + '/'); page.wait_for_function('window.cabin3d', timeout=60000)
        for env in ('earth', 'moon', 'mars', 'space'):
            page.click(f'[data-env="{env}"]'); page.evaluate("document.getElementById('scene3d').scrollIntoView()")
            page.wait_for_function(f"window.cabin3d.worldEnv === '{env}'"); page.wait_for_timeout(1300)
            for mode in ('inside', 'outside'):
                page.evaluate(f"window.cabin3d.setMode('{mode}', true)"); page.wait_for_timeout(2200)
                out[f'{env}-{mode}'] = round(page.evaluate('window.cabin3d.fps'), 1)
        page.close()
        print('\nFPS (headless Edge, ' + ('SwiftShader' if self.swiftshader else 'GPU') + '):', out)
        (SHOTS / 'fps.txt').write_text(f"{'SwiftShader' if self.swiftshader else 'GPU'} {out}\n", encoding='utf-8')
        self.assertTrue(all(v > 0 for v in out.values()))


if __name__ == '__main__':
    unittest.main()
