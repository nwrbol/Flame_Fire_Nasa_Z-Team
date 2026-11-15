import csv
import json
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import knowledge
from backend.app.main import engine_module, knowledge_engine_data, knowledge_environments, knowledge_facts
from backend.app.security import CSP

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / 'backend' / 'data' / 'firegap_dataset' / 'firegap_dataset'

# Values read from the NASA NSSDCA Planetary Fact Sheets (retrieved 2026-11-15):
# Earth: standard gravity 9.80665 m/s^2 (CODATA 2018, quoted on earthfact.html)
# Moon: surface gravity 1.62 m/s^2 (moonfact.html); Mars: surface gravity (mean) 3.73 m/s^2 (marsfact.html)
NASA_G = {'earth': 9.80665, 'moon': 1.62, 'mars': 3.73, 'space': 0.0}
NASA_URL = {'earth': 'earthfact.html', 'moon': 'moonfact.html', 'mars': 'marsfact.html'}


class BundledEnv(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for key in ('EXPERIMENTS_CSV', 'EXPERIMENTS_ID_COLUMN', 'CSV_DELIMITER', 'EXPERIMENTS_IS_TEST_DATA'):
            os.environ.pop(key, None)


class EnvironmentTests(unittest.TestCase):
    def test_gravity_matches_nasa(self):
        envs = {e['id']: e for e in knowledge_environments()['environments']}
        self.assertEqual(set(envs), set(NASA_G))
        for env_id, g in NASA_G.items():
            with self.subTest(env=env_id):
                self.assertAlmostEqual(envs[env_id]['g_ms2'], g, places=5)
                if env_id in NASA_URL:
                    self.assertTrue(envs[env_id]['url'].startswith('https://nssdc.gsfc.nasa.gov/planetary/factsheet/'))
                    self.assertTrue(envs[env_id]['url'].endswith(NASA_URL[env_id]))
                    self.assertTrue(envs[env_id]['page_updated'])
        self.assertAlmostEqual(envs['moon']['g_ms2'] / NASA_G['earth'], envs['moon']['g_rel'], places=2)
        self.assertTrue(knowledge_environments()['retrieved'])
        # only open space has direct PSI data; PSI has nothing at lunar or Martian gravity
        self.assertEqual([e for e in envs if envs[e]['psi_direct']], ['space'])


class GravityRegimeTests(unittest.TestCase):
    def test_column_filled_from_study_platform(self):
        rows = list(csv.DictReader((DATASET / 'tests.csv').open(encoding='utf-8-sig')))
        self.assertIn('gravity_regime', rows[0])
        studies = {s['psi_id']: s for s in json.loads((DATASET / 'studies.json').read_text(encoding='utf-8'))}
        empty = [r['test_id'] for r in rows if not r['gravity_regime']]
        self.assertEqual(empty, [])
        for r in rows:
            platform = studies[r['psi_id']]['platform']
            self.assertTrue('Space Station' in platform or 'Cygnus' in platform, platform)
            self.assertEqual(r['gravity_regime'], 'microgravity')


class EngineTests(BundledEnv):
    def test_engine_module_is_unchanged_plus_export(self):
        body = engine_module().body.decode('utf-8')
        original = knowledge.ENGINE_JS.read_text(encoding='utf-8')
        self.assertTrue(body.startswith(original))
        self.assertEqual(body[len(original):].strip(), 'export { assess, describe, FAMILY_LABEL, OUTCOME_TEXT, CLOSE, NEAR };')

    def test_engine_data_matches_archive_prototype(self):
        html = (DATASET / 'assistant' / 'firegap_assistant.html').read_text(encoding='utf-8')
        ref = json.loads(re.search(r'const DATA = (\{.*\});\n', html).group(1))
        ours = knowledge_engine_data()
        self.assertEqual(len(ours['tests']), len(ref['tests']))
        for a, b in zip(ref['tests'], ours['tests']):
            self.assertEqual(a, {k: v for k, v in b.items() if k != 'gravity'})
            self.assertEqual(b['gravity'], 'microgravity')


class FactTests(unittest.TestCase):
    def test_moon_mars_facts(self):
        wanted = {'X10', 'X11', 'X12', 'X13', 'X14', 'X15', 'X16', 'X17', 'X18', 'X22', 'X23', 'X24', 'X31'}
        for env in ('moon', 'mars'):
            ids = {f['id'] for f in knowledge_facts(env)['facts']}
            self.assertTrue(wanted <= ids, env)

    def test_verified_flags_and_sources(self):
        raw = {r['id']: r for r in csv.DictReader((DATASET / 'data' / 'facts_all.csv').open(encoding='utf-8-sig'))}
        for env in ('earth', 'moon', 'mars', 'space'):
            for f in knowledge_facts(env)['facts']:
                with self.subTest(fact=f['id']):
                    self.assertEqual(f['excerpt_only'], raw[f['id']]['verified'] == 'аннотация/выдержка')
                    self.assertEqual(f['verified'], 'abstract/excerpt only' if f['excerpt_only'] else 'full text read')
                    self.assertEqual(f['url'] or '', raw[f['id']]['url'])
                    self.assertTrue(f['where'])                       # page / section always shown
                    self.assertIsNone(re.search('[А-Яа-яЁё]', f['fact'] + f['caveat'] + f['where'] + f['source_title']))
                    if raw[f['id']]['caveat']:
                        self.assertTrue(f['caveat'], 'caveat present in the CSV must be shown')

    def test_flow_numbers_have_sources(self):
        ids = [f['id'] for f in knowledge_facts('space')['flow_sources']]
        self.assertEqual(ids, ['G13', 'X20', 'G06'])


class OfflineTests(unittest.TestCase):
    def test_no_network_in_page_or_csp(self):
        page = (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
        loaded = re.findall(r'<(?:script|link|img)\b[^>]*(?:src|href)="(https?:)?//', page)
        self.assertEqual(loaded, [])
        self.assertNotIn('googleapis', page)
        self.assertNotIn(b'https://', CSP)
        for js in (ROOT / 'frontend' / 'js').glob('*.js'):
            self.assertIsNone(re.search(r"from\s+'https?://|import\(\s*'https?://", js.read_text(encoding='utf-8')), js.name)


if __name__ == '__main__':
    unittest.main()
