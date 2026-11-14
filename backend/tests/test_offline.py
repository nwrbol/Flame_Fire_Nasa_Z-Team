"""Loader and route-function tests; no event loop or network required.

These complement, and do not replace, test_csv_data's ASGI HTTP tests.
"""
import csv
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.params import Query
from backend.app.csv_data import read_dataset
from backend.app.main import app, experiment, experiments, health, investigations, metadata


def list_records(**kwargs):
    defaults = {name: parameter.default.default if isinstance(parameter.default, Query)
                else parameter.default
                for name, parameter in inspect.signature(experiments).parameters.items()}
    return experiments(**(defaults | kwargs))


class OfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'test.csv'
        self.path.write_text('id,label,extra\n001,alpha,10\n002,beta,20\n003,alpha,\n', encoding='utf-8')
        env = patch.dict(os.environ, {'EXPERIMENTS_CSV': str(self.path),
                                     'EXPERIMENTS_ID_COLUMN': '', 'CSV_DELIMITER': ',',
                                     'EXPERIMENTS_IS_TEST_DATA': 'true'})
        env.start()
        self.addCleanup(env.stop)

    def test_utf8_bom_all_columns_and_exact_values(self):
        for encoding in ('utf-8', 'utf-8-sig'):
            self.path.write_text('id,material,value,empty\n001,"Café, A", 1.2300 ,\n', encoding=encoding)
            rows, columns = read_dataset(self.path)
            self.assertEqual(rows[0], {'id': '001', 'values': {'id': '001', 'material': 'Café, A', 'value': ' 1.2300 ', 'empty': ''}})
            self.assertEqual(len(columns), 4)

    def test_no_name_description_or_id_stable_hash(self):
        self.path.write_text('label,value\na,1\nb,2\n')
        first, _ = read_dataset(self.path)
        self.assertEqual(first, read_dataset(self.path)[0])
        self.path.write_text('value,label\n2,b\n1,a\n')
        self.assertEqual(first[0]['id'], read_dataset(self.path)[0][1]['id'])
        self.assertEqual(len(first[0]['id']), 64)

    def test_invalid_data(self):
        for content in ('', 'a,a\nx,y\n', ' ,x\na,b\n', 'id,x\n1,a\n1,b\n',
                        'id,x\n,a\n', 'id,x\n  ,a\n', 'id,x\n1\n',
                        'id,x\n1,a,b\n', 'x\na\na\n', 'x\n"unterminated'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises((ValueError, csv.Error)):
                    read_dataset(self.path)

    def test_custom_id_and_delimiter(self):
        self.path.write_text('sample;label\n01;demo\n')
        self.assertEqual(read_dataset(self.path, 'sample', ';')[0][0]['id'], '01')
        with self.assertRaises(ValueError):
            read_dataset(self.path, 'missing', ';')
        self.path.write_text('id,sample\n1,a\n1,b\n')
        with self.assertRaises(ValueError):
            read_dataset(self.path, 'sample')

    def test_identifiers_are_not_inferred_as_numbers(self):
        self.path.write_text('id,code\n001,002\n')
        self.assertEqual([c['inferred_type'] for c in metadata()['columns']], ['string', 'string'])

    def test_metadata_types_unknown_units(self):
        self.path.write_text('integer,number,flag,text,empty\n1,1.25,true,demo,\n2,2e-3,false,other,\n')
        result = metadata()
        self.assertEqual([c['inferred_type'] for c in result['columns']], ['integer', 'number', 'boolean', 'string', 'unknown'])
        self.assertTrue(all(c['unit'] is None for c in result['columns']))
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['filter_fields'], ['integer', 'number', 'flag', 'text', 'empty'])

    def test_filter_before_pagination_and_legacy(self):
        for query in ({'limit': 1, 'offset': 1, 'filter_field': 'label', 'filter_value': 'alpha'},
                      {'page': 2, 'page_size': 1, 'filters': '{"label":"alpha"}'}):
            data = list_records(**query)
            self.assertEqual(data['experiments'][0]['id'], '003')
            self.assertEqual(data['pagination']['total'], 2)
            self.assertEqual(data['pagination']['offset'], 1)
        self.assertEqual(list_records(offset=99)['experiments'], [])
        self.assertEqual(list_records(filter_field='extra', filter_value='')['experiments'][0]['id'], '003')

    def test_filter_errors(self):
        for kwargs, status in [({'filters': '[]'}, 422), ({'filters': 'bad'}, 422),
                               ({'filters': '{"extra":1}'}, 422),
                               ({'filters': '{"missing":"x"}'}, 400),
                               ({'filter_field': 'missing', 'filter_value': 'x'}, 400),
                               ({'filter_field': 'label'}, 400),
                               ({'limit': 2, 'page': 1}, 400),
                               ({'filters': '{"label":"alpha"}', 'filter_field': 'label', 'filter_value': 'beta'}, 400)]:
            with self.subTest(kwargs=kwargs), self.assertRaises(HTTPException) as error:
                list_records(**kwargs)
            self.assertEqual(error.exception.status_code, status)

    def test_detail_and_missing_id(self):
        self.assertEqual(experiment('001')['experiment']['values']['extra'], '10')
        with self.assertRaises(HTTPException) as error:
            experiment('missing')
        self.assertEqual(error.exception.status_code, 404)

    def test_missing_csv_independent_catalogue_health(self):
        self.path.unlink()
        self.assertEqual(health(), {'status': 'ok'})
        data = investigations()
        self.assertEqual(data['total'], 10)
        self.assertEqual(len({r['id'] for r in data['investigations']}), 10)
        for row in data['investigations']:
            self.assertTrue({'id', 'name', 'series', 'description', 'source_url', 'data_status'} <= row.keys())
            self.assertEqual(row['data_status'], 'description_only_csv_not_connected')
        for call in (list_records, metadata, lambda: experiment('001')):
            with self.assertLogs('backend.app.main', level='ERROR'), self.assertRaises(HTTPException) as error:
                call()
            self.assertEqual(error.exception.status_code, 500)

    def test_invalid_encoding_api_error(self):
        self.path.write_bytes(b'id,label\n1,\xff\n')
        with self.assertLogs('backend.app.main', level='ERROR'), self.assertRaises(HTTPException) as error:
            list_records()
        self.assertEqual(error.exception.status_code, 500)

    def test_empty_dataset(self):
        self.path.write_text('id,label\n')
        self.assertEqual(list_records()['experiments'], [])
        self.assertEqual(metadata()['total'], 0)

    def test_mock_labels(self):
        self.assertTrue(list_records()['is_test_data'])
        for data in (list_records(), metadata(), experiment('001')):
            self.assertTrue(data['is_test_data'])
            self.assertEqual(data['data_source'], 'csv')

    def test_bundled_firegap_dataset(self):
        os.environ.pop('EXPERIMENTS_CSV', None)
        os.environ.pop('EXPERIMENTS_IS_TEST_DATA', None)
        data = list_records(limit=1)
        self.assertFalse(data['is_test_data'])
        self.assertEqual(data['pagination']['total'], 1372)
        self.assertEqual(len(metadata()['columns']), 61)
        record = data['experiments'][0]
        self.assertEqual(experiment(record['id'])['experiment'], record)
        self.assertIn('data_quality_note', record['values'])
        self.assertEqual(list_records(filter_field='experiment', filter_value='FLEX')['pagination']['total'], 274)
        catalogue = {r['id']: r for r in investigations()['investigations']}
        self.assertEqual(catalogue['flex']['data_status'], 'analyst_csv_connected')
        self.assertEqual(catalogue['flex-2']['data_status'], 'description_only_csv_not_connected')

    def test_firegap_preserves_every_source_value(self):
        from backend.app.main import DEFAULT_CSV
        with DEFAULT_CSV.open(encoding='utf-8-sig', newline='') as stream:
            originals = list(csv.DictReader(stream))
        records, _ = read_dataset(DEFAULT_CSV)
        self.assertEqual([r['values'] for r in records], originals)
        self.assertEqual(len({r['id'] for r in records}), len(originals))
        with self.assertRaises(ValueError):
            read_dataset(DEFAULT_CSV, 'test_id')

    def test_openapi_routes_and_validation_schema(self):
        schema = app.openapi()
        for path in ('/health', '/api/investigations', '/api/metadata', '/api/experiments', '/api/experiments/{experiment_id}'):
            self.assertIn('get', schema['paths'][path])
        params = {p['name']: p for p in schema['paths']['/api/experiments']['get']['parameters']}
        self.assertEqual(params['limit']['schema']['anyOf'][0]['maximum'], 100)
        self.assertEqual(params['offset']['schema']['anyOf'][0]['minimum'], 0)


if __name__ == '__main__':
    unittest.main()
