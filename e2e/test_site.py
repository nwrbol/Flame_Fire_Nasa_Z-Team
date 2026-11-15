"""End-to-end checks in a real browser (Playwright + the installed Microsoft Edge).

Run:  .venv\\Scripts\\python.exe -m unittest e2e.test_site
Saves screenshots of the four environments to docs/screenshots/.
"""
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'docs' / 'screenshots'

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@unittest.skipIf(sync_playwright is None, 'playwright is not installed')
class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--port', str(cls.port)],
                                      cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.base + '/health', timeout=1)
                break
            except OSError:
                time.sleep(.2)
        cls.pw = sync_playwright().start()
        cls.swiftshader = False
        try:
            cls.open_page(args=[])
            if not cls.page.evaluate('!!window.cabin3d'):
                # no WebGL in this headless browser: retry with the software renderer
                cls.browser.close(); cls.swiftshader = True
                cls.open_page(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        except Exception as error:  # pragma: no cover
            cls.pw.stop(); cls.server.terminate()
            raise unittest.SkipTest(f'Edge not available: {error}')

    @classmethod
    def open_page(cls, args):
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True, args=args)
        # bypass_csp only for the test driver: the site's strict CSP (no 'unsafe-eval') blocks
        # Playwright's string expressions; the page itself is unchanged.
        cls.page = cls.browser.new_page(viewport={'width': 1280, 'height': 900}, color_scheme='dark', bypass_csp=True)
        cls.requests = []
        cls.page.on('request', lambda r: cls.requests.append(r.url))
        cls.page.goto(cls.base + '/')
        cls.page.wait_for_function("typeof ENVS !== 'undefined' && ENVS && (window.cabin3d || !document.getElementById('no3d').hidden)")
        cls.page.wait_for_timeout(1500)
        cls.page.evaluate("document.documentElement.style.scrollBehavior='auto';document.querySelectorAll('.reveal').forEach(n=>{n.style.transition='none';n.classList.add('in')})")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.terminate(); cls.server.wait(10)

    def set_env(self, env):
        self.page.click(f'[data-env="{env}"]')
        self.page.wait_for_function(f'env === "{env}" && (!window.cabin3d || window.cabin3d.g === ENVS.environments.find(e => e.id === "{env}").g_ms2)')
        self.page.wait_for_timeout(400)

    def set_conditions(self, o2, kpa):
        self.page.evaluate(f"$('o2').value={o2};$('kpa').value={kpa};updateSim()")
        self.page.wait_for_timeout(300)

    def text(self, sel):
        # textContent, not innerText: headings are upper-cased by CSS only
        return self.page.text_content(sel).strip()

    def test_1_panel_and_button_removed(self):
        self.assertIsNone(self.page.query_selector('#knows'))
        self.assertIsNone(self.page.query_selector('#dropBtn'))
        self.assertNotIn('Drop test', self.page.inner_text('body'))
        self.assertNotIn('What NASA knows', self.page.content())

    def test_2_everything_floats_in_open_space(self):
        # no straps: in 0 g every item is a dynamic body released above its place and drifting
        self.set_env('space'); self.page.wait_for_timeout(1500)
        r = self.page.evaluate("""window.cabin3d.items.filter(i => !i.excluded).map(i => ({ name: i.name, strap: 'strap' in i,
            type: i.body.type, y: i.body.position.y, rest: i.home.y }))""")
        self.assertEqual(len(r), 12)
        for item in r:
            with self.subTest(item=item['name']):
                self.assertFalse(item['strap'])
                self.assertEqual(item['type'], 1)                          # CANNON.Body.DYNAMIC
                self.assertGreater(item['y'], item['rest'] + .02)          # lifted off its surface
        self.set_env('earth'); self.page.wait_for_timeout(3000)
        # with g everything comes to rest on its surface (a tall bottle may tip over: up to 0.1 m lower)
        st = self.page.evaluate("window.cabin3d.items.filter(i => !i.excluded).map(i => ({ n: i.name, dy: i.body.position.y - i.home.y, v: i.body.velocity.length() }))")
        for item in st:
            with self.subTest(item=item['n']):
                self.assertLess(item['v'], .05)                         # settled (below the engine's sleep speed, 0.04 m/s)
                self.assertTrue(-.1 < item['dy'] < .05, item)           # on its shelf / bench / floor

    def test_4_no_network_requests(self):
        external = [u for u in self.requests if not u.startswith(self.base) and not u.startswith('data:')]
        self.assertEqual(external, [])

    def test_5_screenshots(self):
        SHOTS.mkdir(parents=True, exist_ok=True)
        presets = {'earth': (21, 101), 'moon': (34, 56.5), 'mars': (34, 56.5), 'space': (21, 101)}
        for env, (o2, kpa) in presets.items():
            self.set_env(env)
            self.set_conditions(o2, kpa)
            # keep the environment buttons visible below the sticky header
            self.page.evaluate("const r=document.querySelector('.env-seg').getBoundingClientRect();scrollBy(0,r.top-80)")
            self.page.wait_for_timeout(3500)          # let items fall / float and smoke develop
            self.page.screenshot(path=str(SHOTS / f'{env}.png'), full_page=False)
            self.assertTrue((SHOTS / f'{env}.png').stat().st_size > 20000)
            # porthole view and the moment of a drop
            self.page.evaluate("window.cabin3d.setView('window')"); self.page.wait_for_timeout(1300)
            self.scene_shot(f'{env}-window.png')
            self.page.evaluate("window.cabin3d.setView('drop')")
            if env != 'space':
                exp = (2 * 1.0 / self.page.evaluate('window.cabin3d.g')) ** .5
                self.page.evaluate("window.__drop = null; window.cabin3d.dropTest(r => { if (r.done) window.__drop = r; })"); self.page.wait_for_timeout(int(exp * 1000 * .55))
            else:
                self.page.evaluate("window.__drop = null; window.cabin3d.dropTest(r => { if (r.done) window.__drop = r; })"); self.page.wait_for_timeout(1200)
            self.scene_shot(f'{env}-drop.png')
            self.page.wait_for_function('window.__drop', timeout=15000)
            self.page.evaluate("window.cabin3d.setView('overview')")

    def scene_shot(self, name):
        self.page.evaluate("document.querySelector('nav').style.visibility='hidden'")
        self.page.locator('#scene3d').screenshot(path=str(SHOTS / name))
        self.page.evaluate("document.querySelector('nav').style.visibility=''")

    def drop(self, env):
        self.set_env(env)
        self.page.wait_for_timeout(800)
        # no button any more: call the scene's drop test directly (book from 1.00 m)
        self.page.evaluate("window.__drop = null; window.cabin3d.dropTest(r => { if (r.done) window.__drop = r; })")
        self.page.wait_for_function('window.__drop', timeout=20000)
        r = self.page.evaluate('window.__drop')
        d = {'env': r['env'], 'h': r['h'], 'measured': f"{r['elapsed']:.4f}" if r['landed'] else 'none'}
        self.assertEqual(d['env'], env)
        return d

    def test_6_drop_times_follow_g(self):
        # free fall from h = 1 m: t = sqrt(2h/g) -> Earth 0.45 s, Mars 0.73 s, Moon 1.11 s (±5 %)
        want = {'earth': .4516, 'mars': .7323, 'moon': 1.1111}
        got = {}
        for env, t in want.items():
            with self.subTest(env=env):
                d = self.drop(env)
                got[env] = float(d['measured'])
                self.assertAlmostEqual(got[env], t, delta=t * .05, msg=f'{env}: measured {got[env]:.3f} s')
                self.assertAlmostEqual(float(d['h']), 1.0)
        print('\nDrop from 1 m (measured):', {k: round(v, 4) for k, v in got.items()})
        (SHOTS / 'drop_times.txt').write_text(f'{got}\n', encoding='utf-8')
        # must fail if every environment gives the same time
        self.assertGreater(got['mars'] / got['earth'], 1.4)
        self.assertGreater(got['moon'] / got['mars'], 1.3)
        # open space: g = 0, the book does not fall
        self.assertEqual(self.drop('space')['measured'], 'none')

    def test_7_scene_gravity_is_environments_json(self):
        envs = {e['id']: e['g_ms2'] for e in self.page.evaluate('ENVS.environments')}
        for env, g in envs.items():
            with self.subTest(env=env):
                self.set_env(env); self.page.wait_for_timeout(300)
                self.assertEqual(self.page.evaluate('window.cabin3d.g'), g)
                self.assertAlmostEqual(self.page.evaluate('-window.cabin3d.world.gravity.y'), g, places=9)
                self.assertEqual(self.page.evaluate('window.cabin3d.STEP'), 1 / 120)

    def test_8_fps(self):
        out = {}
        for env in ('earth', 'moon', 'mars', 'space'):
            self.set_env(env)
            self.page.evaluate("document.getElementById('scene3d').scrollIntoView()")
            self.page.wait_for_timeout(2500)
            out[env] = round(self.page.evaluate('window.cabin3d.fps'), 1)
        print('\nFPS (headless Edge, ' + ('SwiftShader' if self.swiftshader else 'GPU') + '):', out)
        (SHOTS / 'fps.txt').write_text(f"{'SwiftShader' if self.swiftshader else 'GPU'} {out}\n", encoding='utf-8')
        self.assertTrue(all(v > 0 for v in out.values()))


    def phone(self):
        ctx = self.browser.new_context(viewport={'width': 375, 'height': 667}, is_mobile=True, has_touch=True,
                                       device_scale_factor=2, bypass_csp=True)
        page = ctx.new_page(); page.goto(self.base + '/'); page.wait_for_timeout(1200)
        return ctx, page

    def test_9_mobile_chat_fits_and_closes(self):
        ctx, page = self.phone()
        try:
            rect = "e => { const b = document.querySelector(e).getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; }"
            page.evaluate('scrollTo(0, 1400)'); page.tap('#chatFab'); page.wait_for_timeout(500)
            chat, close = page.evaluate(rect, '.chat'), page.evaluate(rect, '#chatClose')
            self.assertEqual([round(v) for v in chat], [0, 0, 375, 667])            # full screen, nothing outside
            self.assertTrue(0 <= close[1] and close[3] <= 667 and close[2] <= 375)  # close button on screen
            self.assertGreaterEqual(close[2] - close[0], 40)                         # finger-sized
            self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#chatInput')).fontSize"), '16px')
            self.assertEqual(page.evaluate('getComputedStyle(document.body).overflow'), 'hidden')
            self.assertNotEqual(page.evaluate('document.activeElement.id'), 'chatInput')  # no keyboard pop-up
            # on-screen keyboard: the visible viewport shrinks; header and composer must stay visible
            page.evaluate("document.documentElement.style.setProperty('--vv-h', '360px')"); page.wait_for_timeout(300)
            self.assertLessEqual(page.evaluate(rect, '.composer')[3], 360)
            self.assertGreaterEqual(page.evaluate(rect, '#chatClose')[1], 0)
            page.tap('#chatClose'); page.wait_for_timeout(300)
            self.assertFalse(page.evaluate("document.body.classList.contains('chat-open')"))
            self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), 375)
        finally:
            ctx.close()

    def test_10_theme_switch(self):
        ctx = self.browser.new_context(viewport={'width': 1280, 'height': 900}, color_scheme='light', bypass_csp=True)
        page = ctx.new_page()
        try:
            page.goto(self.base + '/'); page.wait_for_timeout(1000)
            bg = lambda: page.evaluate('getComputedStyle(document.body).backgroundColor')
            self.assertEqual(bg(), 'rgb(246, 245, 241)')                       # follows the system (light)
            page.click('#themeBtn'); page.wait_for_timeout(200)
            self.assertEqual(page.evaluate('document.documentElement.dataset.theme'), 'dark')
            self.assertEqual(bg(), 'rgb(15, 15, 14)')
            self.assertEqual(page.get_attribute('#themeBtn', 'aria-label'), 'Switch to light theme')
            page.screenshot(path=str(SHOTS / 'theme-dark.png'))
            page.reload(); page.wait_for_timeout(800)
            self.assertEqual(bg(), 'rgb(15, 15, 14)')                          # remembered after reload
            page.click('#themeBtn'); page.wait_for_timeout(200)
            self.assertEqual(bg(), 'rgb(246, 245, 241)')
            page.screenshot(path=str(SHOTS / 'theme-light.png'))
        finally:
            ctx.close()

if __name__ == '__main__':
    unittest.main()
