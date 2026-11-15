"""Liquid Glass buttons: every visible button keeps text contrast >= 4.5:1 in both themes, has a
visible focus ring, and does not animate under prefers-reduced-motion.

Contrast is measured on real pixels: each button is screenshotted with its text hidden, so the glass
is measured exactly as rendered (blur, gradient, whatever is behind it), and compared with the text
colour. Screenshots: docs/screenshots/glass/.

Run:  .venv\\Scripts\\python.exe -m unittest e2e.test_glass
"""
import io
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'docs' / 'screenshots' / 'glass'

try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
except ImportError:  # pragma: no cover
    sync_playwright = None

BUTTONS = '.btn, .chip, .theme-btn, .seg button, .pager button, .fab'


def lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = rgb
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


def worst_background(png, text):
    """Of the glass pixels, the one closest in luminance to the text (the worst case, not the average)."""
    img = Image.open(io.BytesIO(png)).convert('RGB')
    w, h = img.size
    px = [img.getpixel((x, y)) for y in range(h // 4, h - h // 4) for x in range(w // 6, w - w // 6)]
    px.sort(key=lum)
    lt = lum(text)
    # ignore the 3 % most extreme pixels (edge highlights, anti-aliased rim)
    trimmed = px[len(px) * 3 // 100: len(px) - len(px) * 3 // 100] or px
    return min(trimmed, key=lambda p: abs(lum(p) - lt))


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@unittest.skipIf(sync_playwright is None, 'playwright / Pillow not installed')
class GlassTests(unittest.TestCase):
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
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True)
        SHOTS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.terminate(); cls.server.wait(10)

    def page(self, theme, **kw):
        ctx = self.browser.new_context(viewport={'width': 1280, 'height': 900}, **kw)
        ctx.add_init_script(f"localStorage.setItem('mf-theme', '{theme}')")
        p = ctx.new_page(); p.goto(self.base + '/')
        p.wait_for_function("typeof ENVS !== 'undefined' && ENVS && document.querySelector('.chip')", timeout=60000)
        p.wait_for_timeout(800)
        return p

    def test_stylesheet_served(self):
        with urllib.request.urlopen(self.base + '/css/glass.css') as r:
            self.assertEqual(r.status, 200)
            self.assertIn('text/css', r.headers['content-type'])
            self.assertEqual(r.headers['cache-control'], 'no-cache')
            self.assertIn(b'.glass-btn', r.read())

    def check_contrast(self, theme):
        p = self.page(theme)
        p.screenshot(path=str(SHOTS / f'page-{theme}.png'))
        p.evaluate("document.getElementById('scene3d').scrollIntoView({block:'center'})"); p.wait_for_timeout(600)
        p.screenshot(path=str(SHOTS / f'scene-{theme}.png'))
        p.evaluate('scrollTo(0,0)')
        bad, n = [], 0
        for loc in p.locator(BUTTONS).all():
            if not loc.is_visible():
                continue
            box = loc.bounding_box()
            if not box or box['width'] < 20 or box['height'] < 16:
                continue
            label = (loc.inner_text() or loc.get_attribute('aria-label') or '?').strip()[:24]
            if not label.strip() or label == '?':
                continue                                 # icon-only buttons: no text to measure
            color = loc.evaluate("e => getComputedStyle(e).color")
            rgb = tuple(int(float(c)) for c in color[color.index('(') + 1:color.index(')')].split(',')[:3])
            loc.scroll_into_view_if_needed(); p.mouse.move(0, 0); p.wait_for_timeout(350)   # no hover state
            loc.evaluate("e => { e.dataset.c = e.style.color; e.style.setProperty('transition','none','important');"
                         " e.style.setProperty('color','transparent','important');"
                         " e.style.setProperty('text-shadow','none','important');"
                         " e.querySelectorAll('*').forEach(c => c.style.setProperty('visibility','hidden','important')) }")
            png = loc.screenshot()
            loc.evaluate("e => { e.style.color = e.dataset.c; e.style.removeProperty('text-shadow'); e.style.removeProperty('transition');"
                         " e.querySelectorAll('*').forEach(c => c.style.removeProperty('visibility')) }")
            ratio = contrast(rgb, worst_background(png, rgb)); n += 1
            if ratio < 4.5:
                bad.append(f'{ascii(label)} {ratio:.2f}')
        p.context.close()
        print(f'\n{theme}: {n} buttons measured', 'all >= 4.5:1' if not bad else bad)
        self.assertGreater(n, 8)
        self.assertEqual(bad, [], f'{theme}: contrast below 4.5:1')

    def test_contrast_light(self): self.check_contrast('light')
    def test_contrast_dark(self): self.check_contrast('dark')

    def test_focus_ring_and_hover(self):
        p = self.page('light')
        chip = p.locator('.chip').first
        chip.focus(); p.keyboard.press('Shift+Tab'); p.keyboard.press('Tab')   # keyboard focus -> :focus-visible
        style = p.evaluate("[getComputedStyle(document.activeElement).outlineStyle, getComputedStyle(document.activeElement).outlineWidth]")
        self.assertEqual(style[0], 'solid'); self.assertNotEqual(style[1], '0px')
        btn = p.locator('.btn').first; btn.scroll_into_view_if_needed(); btn.hover(); p.wait_for_timeout(450)
        self.assertIn('matrix(1.04', btn.evaluate('e => getComputedStyle(e).transform'))
        bf = btn.evaluate('e => getComputedStyle(e).backdropFilter || getComputedStyle(e).webkitBackdropFilter')
        self.assertIn('blur(16px)', bf)
        p.locator('.hero, header, main').first.screenshot(path=str(SHOTS / 'hover-light.png'))
        p.context.close()

    def test_reduced_motion(self):
        p = self.page('light', reduced_motion='reduce')
        btn = p.locator('.btn').first; btn.scroll_into_view_if_needed(); btn.hover(); p.wait_for_timeout(200)
        self.assertEqual(btn.evaluate('e => getComputedStyle(e).transform'), 'none')
        self.assertTrue(btn.evaluate("e => getComputedStyle(e).transitionDuration.split(',').every(d => parseFloat(d) === 0)"))
        p.context.close()

    def test_demo_page(self):
        ctx = self.browser.new_context(viewport={'width': 1000, 'height': 560}); p = ctx.new_page()
        p.goto((ROOT / 'docs' / 'liquid-glass-demo.html').as_uri()); p.wait_for_timeout(500)
        p.locator('.glass-btn--primary').first.hover(); p.wait_for_timeout(450)
        p.screenshot(path=str(SHOTS / 'demo.png'))
        ctx.close()


if __name__ == '__main__':
    unittest.main()
