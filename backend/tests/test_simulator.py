import asyncio
import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.app import simulator
from backend.app.main import export, load_dataset, safe_cell, sim_materials, sim_nearest
from backend.tests.test_csv_data import request

BUNDLED_ENV = {'EXPERIMENTS_CSV': '', 'EXPERIMENTS_ID_COLUMN': '', 'CSV_DELIMITER': ',', 'EXPERIMENTS_IS_TEST_DATA': ''}


class BundledSimulatorTests(unittest.TestCase):
    """Runs against the real FireGap dataset shipped with the backend."""

    def setUp(self):
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        for key in BUNDLED_ENV:
            os.environ.pop(key, None)
        self.rows, _, _ = load_dataset()

    def test_every_row_has_a_family(self):
        missing = [r['values']['material'] for r in self.rows if simulator.family_of(r['values']) is None]
        self.assertEqual(missing, [])
        ids = {m['id'] for m in sim_materials()['materials']}
        self.assertTrue({'pmma', 'sibal', 'nomex', 'wax', 'methanol', 'heptane', 'ethylene', 'bre'} <= ids)

    def test_material_list_order_and_labels(self):
        mats = sim_materials()['materials']
        kinds = [m['kind'] for m in mats]
        # grouped: solids, droplets, gas flames, then the burner rig in its own group
        self.assertEqual(sorted(set(kinds), key=kinds.index), ['solid', 'droplet', 'gas', 'rig'])
        self.assertEqual([m['id'] for m in mats if m['kind'] == 'rig'], ['bre'])
        for kind in set(kinds):
            group = [m for m in mats if m['kind'] == kind]
            known = [m['tests'] for m in group if not m['fallback']]
            self.assertEqual(known, sorted(known, reverse=True), kind)       # richest data first
            if any(m['fallback'] for m in group):
                self.assertTrue(group[-1]['fallback'], kind)                  # "unknown" last
        for m in mats:
            self.assertNotIn('/', m['label'])                                 # one style: Name (detail)
            self.assertEqual(m['label'].count('('), m['label'].count(')'))
        self.assertIn('ethylene', next(m['label'] for m in mats if m['id'] == 'bre'))

    def test_family_rules_order(self):
        fam = lambda **v: simulator.family_of({'material': '', 'material_class': '', 'experiment': '', **v})
        # "material not stated; PMMA likely" must not be counted as PMMA
        self.assertEqual(fam(material='2 cm sphere', material_class='spherical sample (material not stated; PMMA likely)'), 'solid_unlabelled')
        # BRE burns methane: must not fall into "ethane"
        self.assertEqual(fam(material='gas burner (100% CH4)', experiment='ACME BRE'), 'bre')
        self.assertEqual(fam(material='ethane', experiment='ACME CFI-G'), 'ethane')
        self.assertEqual(fam(material='Cotton-Fiberglass (SIBAL)'), 'sibal')

    def test_iss_pmma_is_covered(self):
        result = sim_nearest(material='pmma', o2=21, pressure=101, flow=None, thickness=None)
        self.assertTrue(result['within'])
        self.assertGreater(result['n_within'], 10)
        self.assertLessEqual(result['gaps']['o2'], simulator.TOL_O2)

    def test_lunar_base_gap(self):
        # 34 % O2 at 56.5 kPa: never tested on PMMA, but tested with the ACME burning-rate emulator
        pmma = sim_nearest(material='pmma', o2=34, pressure=56.5, flow=None, thickness=None)
        self.assertFalse(pmma['within'])
        self.assertEqual(pmma['n_within'], 0)
        self.assertGreater(pmma['gaps']['pressure'], 40)
        bre = sim_nearest(material='bre', o2=34, pressure=56.5, flow=None, thickness=None)
        self.assertTrue(bre['within'])
        self.assertEqual(bre['test']['outcome'], 'burned')
        self.assertIsNotNone(bre['test']['burn_time_s'])

    def test_coverage_and_missing_counts(self):
        mats = {m['id']: m for m in sim_materials()['materials']}
        pmma = mats['pmma']
        self.assertTrue(any(a <= 21 <= b for a, b in pmma['coverage']['o2']))
        self.assertFalse(any(a <= 56.5 <= b for a, b in pmma['coverage']['pressure']))
        self.assertGreater(pmma['missing']['flow'], 0)        # mostly not recorded -> "not recorded"
        self.assertEqual(mats['methanol']['coverage']['thickness'], [])

    def test_unknown_material(self):
        with self.assertRaises(HTTPException) as error:
            sim_nearest(material='unobtainium', o2=21, pressure=101, flow=None, thickness=None)
        self.assertEqual(error.exception.status_code, 404)

    def test_outcome_parsing(self):
        self.assertEqual(simulator.outcome({'ug_outcome': 'hot flame; self-extinguished'}), 'extinguished')
        self.assertEqual(simulator.outcome({'ug_outcome': 'no hot flame ignited'}), 'extinguished')
        self.assertEqual(simulator.outcome({'ug_outcome': 'burning when fuel flow was terminated'}), 'burned')
        self.assertIsNone(simulator.outcome({'ug_outcome': ''}))


class ExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'x.csv'
        path.write_text('id,label,value,code\n1,=HYPERLINK("http://evil"),-3.5,007\n2,@SUM(A1),2,008\n3,+cmd,,009\n',
                        encoding='utf-8')
        env = patch.dict(os.environ, {'EXPERIMENTS_CSV': str(path), 'EXPERIMENTS_ID_COLUMN': 'id',
                                      'CSV_DELIMITER': ',', 'EXPERIMENTS_IS_TEST_DATA': 'true'})
        env.start()
        self.addCleanup(env.stop)

    def test_safe_cell(self):
        self.assertEqual(safe_cell('=1+1'), "'=1+1")
        self.assertEqual(safe_cell('@x'), "'@x")
        self.assertEqual(safe_cell('-3.5'), '-3.5')       # real negative numbers stay
        self.assertEqual(safe_cell('PMMA'), 'PMMA')

    def test_csv_escapes_formulas_and_keeps_all_rows(self):
        response = export(format='csv', filters='{}', filter_field=None, filter_value=None, q=None)
        text = response.body.decode('utf-8')
        self.assertTrue(text.startswith('﻿'))
        rows = list(csv.reader(io.StringIO(text.lstrip('﻿'))))
        self.assertEqual(rows[0], ['id', 'label', 'value', 'code'])
        self.assertEqual([r[1] for r in rows[1:]], ["'=HYPERLINK(\"http://evil\")", "'@SUM(A1)", "'+cmd"])
        self.assertEqual(rows[1][2], '-3.5')
        self.assertIn('attachment; filename="firegap_tests.csv"', response.headers['content-disposition'])

    def test_csv_respects_filter_and_search(self):
        response = export(format='csv', filters='{}', filter_field='code', filter_value='008', q=None)
        self.assertEqual(len(response.body.decode('utf-8').strip().splitlines()), 2)
        response = export(format='csv', filters='{}', filter_field=None, filter_value=None, q='cmd')
        self.assertEqual(len(response.body.decode('utf-8').strip().splitlines()), 2)
        self.assertIn('_search.csv', response.headers['content-disposition'])

    def test_xlsx(self):
        from openpyxl import load_workbook
        response = export(format='xlsx', filters='{}', filter_field=None, filter_value=None, q=None)
        book = load_workbook(io.BytesIO(response.body))
        sheet = book['tests']
        values = list(sheet.iter_rows(values_only=True))
        self.assertEqual(values[0], ('id', 'label', 'value', 'code'))
        self.assertEqual(values[1][1], "'=HYPERLINK(\"http://evil\")")   # text, not a formula
        self.assertEqual(values[1][2], -3.5)                             # numeric column -> number
        self.assertEqual(values[1][3], '007')                            # identifiers keep zeros
        self.assertIn('source', book.sheetnames)

    def test_export_route_and_bad_format(self):
        code, body, headers = asyncio.run(request('/api/export', 'format=csv'))
        self.assertEqual(code, 200)
        self.assertIn(b'attachment', headers[b'content-disposition'])
        self.assertEqual(asyncio.run(request('/api/export', 'format=pdf'))[0], 422)

    def test_scripts_are_revalidated(self):
        # regression: a cached old cabin3d.js kept showing removed geometry after an update
        for path in ('/js/cabin3d.js', '/vendor/cannon-es.js'):
            with self.subTest(path=path):
                code, _, headers = asyncio.run(request(path))
                self.assertEqual(code, 200)
                self.assertEqual(headers[b'cache-control'], b'no-cache')
                self.assertIn(b'etag', headers)

    def test_assets_only(self):
        self.assertEqual(asyncio.run(request('/assets/hero-flame.webp'))[0], 200)
        for path in ('/assets/../index.html', '/node_modules/three/package.json', '/frontend/index.html'):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(request(path))[0], 404)


if __name__ == '__main__':
    unittest.main()
