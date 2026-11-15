"""The camera never leaves the room. In ?testbg mode everything outside the room is magenta
(#ff00ff clear colour, no background); screenshots from extreme camera positions must contain no
magenta pixel. Through the porthole the camera must see the window view (the dome behind the
glass), never empty space or the dome's edge.

Run:  .venv\\Scripts\\python.exe -m unittest e2e.test_room      (screenshots: docs/screenshots/room/)
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
SHOTS = ROOT / 'docs' / 'screenshots' / 'room'
SAVE = {'max-az0', 'max-az135', 'look-up', 'look-down', 'wall-x+', 'graze-z-', 'corner-+++', 'corner---+', 'window-straight', 'window-oblique'}

try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
except ImportError:  # pragma: no cover
    sync_playwright = None


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def magenta(img):
    data = img.get_flattened_data() if hasattr(img, 'get_flattened_data') else img.getdata()
    return sum(1 for r, g, b in data if r > 150 and b > 150 and g < 100 and r - g > 100 and b - g > 100)


@unittest.skipIf(sync_playwright is None, 'playwright / Pillow not installed')
class RoomTests(unittest.TestCase):
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
        cls.args = []
        cls.open()
        if not cls.page.evaluate('!!window.cabin3d'):          # no WebGL in headless: software renderer
            cls.browser.close()
            cls.args = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
            cls.open()
        SHOTS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def open(cls):
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True, args=cls.args)
        cls.page = cls.browser.new_page(viewport={'width': 1280, 'height': 900}, bypass_csp=True)
        cls.page.goto(cls.base + '/?testbg=1')
        cls.page.wait_for_function("typeof ENVS !== 'undefined' && ENVS && (window.cabin3d || !document.getElementById('no3d').hidden)", timeout=60000)
        cls.page.add_style_tag(content='nav, .illus, .fab { visibility: hidden !important; }')   # only the WebGL canvas is checked

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.terminate(); cls.server.wait(10)

    def set_env(self, env):
        self.page.click(f'[data-env="{env}"]')
        self.page.evaluate("document.getElementById('scene3d').scrollIntoView({block:'center'})")
        self.page.wait_for_function(f"window.cabin3d.viewEnv === '{env}'", timeout=30000)
        self.page.wait_for_timeout(1300)                      # fade finished

    def place(self, pos, target):
        self.page.evaluate(f'window.cabin3d.setCamera({list(pos)}, {list(target)})')
        self.page.wait_for_timeout(260)                       # a few frames: controls + clamp applied

    def inside(self):
        """camera inside the room box shrunk by 0.3 m (tiny tolerance), polar angle within limits"""
        return self.page.evaluate("""(() => { const c = cabin3d, p = c.camera.position, r = c.ROOM, e = 1e-6;
          return p.x >= r.min.x - e && p.x <= r.max.x + e && p.y >= r.min.y - e && p.y <= r.max.y + e && p.z >= r.min.z - e && p.z <= r.max.z + e; })()""")

    def views(self):
        L = self.page.evaluate('({ r: cabin3d.ROOM, l: cabin3d.LIMITS, c: cabin3d.CENTER })')
        c = [L['c']['x'], L['c']['y'], L['c']['z']]; mn = L['r']['min']; mx = L['r']['max']
        out, far = [], L['l']['maxDistance'] * 2           # try to go beyond every limit
        for k in range(8):                                  # all angles around, at (beyond) max distance
            a = k * math.pi / 4
            out.append((f'max-az{k * 45}', [c[0] + far * math.sin(a), c[1], c[2] + far * math.cos(a)], c))
        out.append(('look-up', [c[0] + .3, c[1] - 3, c[2] + .2], c))            # below the polar limit -> looking up
        out.append(('look-down', [c[0] + .3, c[1] + 3, c[2] + .2], c))          # above it -> looking down
        for ax, sign in (('x', 1), ('x', -1), ('y', 1), ('y', -1), ('z', 1), ('z', -1)):
            pos = list(c); i = 'xyz'.index(ax); pos[i] += sign * 5                 # through each wall, floor and ceiling
            out.append((f'wall-{ax}{"+" if sign > 0 else "-"}', pos, c))
            edge = list(c); edge[i] = (mx if sign > 0 else mn)[ax]               # facing that wall from close up
            back = list(edge); back[i] -= sign * .45
            out.append((f'face-{ax}{"+" if sign > 0 else "-"}', back, edge))
        for ax in 'xz':                                     # grazing along a wall at the 0.3 m margin
            for sign in (1, -1):
                pos = [mx['x'], c[1], mn['z']] if ax == 'x' else [mn['x'], c[1], mx['z'] if sign > 0 else mn['z']]
                tgt = [mx['x'], c[1], mx['z']] if ax == 'x' else [mx['x'], c[1], pos[2]]
                if ax == 'x' and sign < 0:
                    pos = [mn['x'], c[1], mx['z']]; tgt = [mn['x'], c[1], mn['z']]
                out.append((f'graze-{ax}{"+" if sign > 0 else "-"}', pos, tgt))
        for sx in (1, -1):                                  # from every corner of the room
            for sy in (1, -1):
                for sz in (1, -1):
                    pos = [(mx if sx > 0 else mn)['x'] * 1.5, (mx if sy > 0 else mn)['y'] + sy, (mx if sz > 0 else mn)['z'] * 1.5]
                    out.append((f'corner-{"+" if sx > 0 else "-"}{"+" if sy > 0 else "-"}{"+" if sz > 0 else "-"}', pos, c))
        win = [-.95, 1.5, -1.6]
        out += [('window-straight', [-.95, 1.5, -.9], win), ('window-oblique', [.6, 1.0, -1.0], win),
                ('window-high-left', [-1.8, 2.1, -.6], win), ('window-far', [1.8, .3, 1.3], win), ('window-low', [-.6, .35, -1.2], win)]
        return out

    def check_env(self, env):
        self.set_env(env)
        bad, outside = {}, []
        for name, pos, target in self.views():
            self.place(pos, target)
            if not self.inside():
                outside.append(name)
            png = self.page.locator('#scene3d canvas').screenshot()
            img = Image.open(io.BytesIO(png)).convert('RGB')
            n = magenta(img)
            if n:
                bad[name] = n
            if name in SAVE or n:
                img.thumbnail((720, 720)); img.save(SHOTS / f'{env}-{name}.png', optimize=True)
            if name.startswith('window'):
                r = self.page.evaluate('window.cabin3d.windowCheck()')
                self.assertTrue(r['ok'], f'{env} {name}: {r}')
        self.assertEqual(outside, [], f'{env}: camera left the room at {outside}')
        self.assertEqual(bad, {}, f'{env}: magenta pixels (space outside the room) at {bad}')

    def test_earth(self): self.check_env('earth')
    def test_moon(self): self.check_env('moon')
    def test_mars(self): self.check_env('mars')
    def test_space(self): self.check_env('space')

    def test_window_shows_view(self):
        """through the porthole the first opaque thing seen is the window view (never empty space)"""
        self.set_env('earth')
        for pos in ([-.95, 1.5, -.9], [.6, 1.0, -1.0], [-1.8, 2.1, -.6], [-.6, .35, -1.2], [-.2, 1.9, -1.2]):
            self.place(pos, [-.95, 1.5, -1.6])
            r = self.page.evaluate('window.cabin3d.windowCheck()')
            self.assertTrue(r['ok'], f'from {pos}: {r}')

    def test_limits_and_input(self):
        """wheel and drag far beyond the limits: the camera stays in the room, polar angle limited"""
        self.set_env('space')
        self.page.evaluate("window.cabin3d.setView('overview')"); self.page.wait_for_timeout(300)
        box = self.page.locator('#scene3d canvas').bounding_box(); cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        self.page.mouse.move(cx, cy)
        for _ in range(40):
            self.page.mouse.wheel(0, 400)                   # zoom out as far as it goes
        self.page.wait_for_timeout(800)
        self.assertTrue(self.inside())
        for dx, dy in ((900, 0), (0, 700), (0, -1400), (-1800, 300)):
            self.page.mouse.move(cx, cy); self.page.mouse.down(); self.page.mouse.move(cx + dx, cy + dy, steps=12); self.page.mouse.up()
            self.page.wait_for_timeout(500)
            self.assertTrue(self.inside())
            polar = self.page.evaluate('cabin3d.controls.getPolarAngle()')
            lim = self.page.evaluate('[cabin3d.LIMITS.minPolar, cabin3d.LIMITS.maxPolar]')
            self.assertGreaterEqual(polar, lim[0] - 1e-3); self.assertLessEqual(polar, lim[1] + 1e-3)
        for _ in range(40):
            self.page.mouse.wheel(0, -400)                  # zoom in as far as it goes
        self.page.wait_for_timeout(800)
        self.assertTrue(self.inside())
        L = self.page.evaluate('[cabin3d.camera.fov, cabin3d.camera.near, cabin3d.controls.enablePan, cabin3d.controls.enableDamping]')
        self.assertTrue(50 <= L[0] <= 80); self.assertGreaterEqual(L[1], .05); self.assertFalse(L[2]); self.assertTrue(L[3])
        png = self.page.locator('#scene3d canvas').screenshot()
        self.assertEqual(magenta(Image.open(io.BytesIO(png)).convert('RGB')), 0)

    def test_pinch_zoom(self):
        """two-finger pinch on a touch screen obeys the same limits"""
        ctx = self.browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True, bypass_csp=True)
        p = ctx.new_page(); p.goto(self.base + '/?testbg=1')
        p.wait_for_function('window.cabin3d', timeout=60000)
        p.evaluate("document.getElementById('scene3d').scrollIntoView({block:'center'})"); p.wait_for_timeout(500)
        box = p.locator('#scene3d canvas').bounding_box(); cx, cy = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
        cdp = ctx.new_cdp_session(p)
        for spread in (-1, 1, -1):                          # pinch in (zoom out), out (zoom in), in again
            for _ in range(3):
                d0, d1 = (140, 10) if spread < 0 else (10, 140)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': cx - d0, 'y': cy}, {'x': cx + d0, 'y': cy}]})
                for k in range(1, 11):
                    d = d0 + (d1 - d0) * k / 10
                    cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': cx - d, 'y': cy}, {'x': cx + d, 'y': cy}]})
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                p.wait_for_timeout(300)
            p.wait_for_timeout(600)
            ok = p.evaluate("""(() => { const p = cabin3d.camera.position, r = cabin3d.ROOM, e = 1e-6;
              return p.x >= r.min.x - e && p.x <= r.max.x + e && p.y >= r.min.y - e && p.y <= r.max.y + e && p.z >= r.min.z - e && p.z <= r.max.z + e; })()""")
            self.assertTrue(ok)
        ctx.close()


if __name__ == '__main__':
    unittest.main()
