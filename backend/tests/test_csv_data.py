import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
from backend.app.csv_data import read_dataset
from backend.app.main import app


async def request(path, query='', method='GET', headers=()):
    messages = []
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        messages.append(message)
    await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': query.encode(), 'root_path': '', 'headers': list(headers), 'server': ('test', 80), 'client': ('test', 1)}, receive, send)
    body = b''.join(m.get('body', b'') for m in messages)
    return messages[0]['status'], body, dict(messages[0]['headers'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'data.csv'
        self.path.write_text('id,label,extra\n001,alpha,10\n002,beta,20\n003,alpha,\n', encoding='utf-8-sig')
        self.env = patch.dict(os.environ, {'EXPERIMENTS_CSV': str(self.path), 'EXPERIMENTS_ID_COLUMN': 'id', 'CSV_DELIMITER': ',', 'EXPERIMENTS_IS_TEST_DATA': 'true'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def get(self, path, **query):
        code, body, _ = asyncio.run(request(path, urlencode(query)))
        return code, json.loads(body)

    def test_health_and_metadata(self):
        self.assertEqual(self.get('/health'), (200, {'status': 'ok'}))
        code, data = self.get('/api/metadata')
        self.assertEqual(code, 200)
        self.assertEqual([c['name'] for c in data['columns']], ['id', 'label', 'extra'])
        self.assertTrue(data['is_test_data'])
        self.assertFalse(data['ai_available'])

    def test_filter_pagination_detail(self):
        code, data = self.get('/api/experiments', filters='{"label":"alpha"}', page_size=1, page=2)
        self.assertEqual(code, 200)
        self.assertEqual(data['pagination']['total'], 2)
        self.assertEqual(data['experiments'][0]['id'], '003')
        self.assertEqual(self.get('/api/experiments/001')[1]['experiment']['values']['extra'], '10')
        self.assertEqual(self.get('/api/experiments/missing')[0], 404)
        self.assertEqual(self.get('/api/experiments', page=99)[1]['experiments'], [])

    def test_bad_queries(self):
        for query in ({'page': 0}, {'page_size': 101}, {'filters': '[]'}, {'filters': '{"label":1}'}, {'filters': 'bad'}):
            self.assertEqual(self.get('/api/experiments', **query)[0], 422)
        self.assertEqual(self.get('/api/experiments', filters='{"unknown":"x"}')[0], 400)

    def test_limit_offset_and_simple_filters(self):
        code, data = self.get('/api/experiments', limit=1, offset=1,
                              filter_field='label', filter_value='alpha')
        self.assertEqual(code, 200)
        self.assertEqual(data['experiments'][0]['id'], '003')
        self.assertEqual(data['pagination']['total'], 2)
        self.assertEqual(data['pagination']['offset'], 1)
        self.assertEqual(self.get('/api/experiments', offset=100)[1]['experiments'], [])
        for query in ({'limit': 0}, {'limit': 101}, {'offset': -1}, {'offset': 'bad'}):
            self.assertEqual(self.get('/api/experiments', **query)[0], 422)
        for query in ({'filter_field': 'unknown', 'filter_value': 'x'},
                      {'filter_field': 'label'}, {'filter_value': 'alpha'},
                      {'page': 1, 'limit': 20}):
            self.assertEqual(self.get('/api/experiments', **query)[0], 400)

    def test_catalogue_and_health_without_csv(self):
        self.path.unlink()
        code, data = self.get('/api/investigations')
        self.assertEqual(code, 200)
        self.assertEqual(data['total'], 10)
        self.assertEqual(len({item['id'] for item in data['investigations']}), 10)
        for item in data['investigations']:
            self.assertTrue({'id', 'name', 'series', 'description', 'source_url', 'data_status'} <= item.keys())
            self.assertEqual(item['data_status'], 'description_only_csv_not_connected')
        self.assertEqual(self.get('/health')[0], 200)
        for path in ('/api/experiments', '/api/metadata', '/api/experiments/001'):
            with self.assertLogs('backend.app.main', level='ERROR'):
                self.assertEqual(self.get(path)[0], 500)

    def test_metadata_units_and_empty_filter(self):
        code, data = self.get('/api/metadata')
        self.assertEqual(code, 200)
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['filter_fields'], ['id', 'label', 'extra'])
        self.assertTrue(all(column['unit'] is None for column in data['columns']))
        self.assertEqual(self.get('/api/experiments', filter_field='extra', filter_value='')[1]['experiments'][0]['id'], '003')

    def test_mock_labels_are_preserved(self):
        for path in ('/api/experiments', '/api/metadata', '/api/experiments/001'):
            self.assertTrue(self.get(path)[1]['is_test_data'])

    def test_invalid_csv(self):
        for content in ('', 'a,a\nx,y\n', 'id,x\n1,a\n1,b\n', 'id,x\n1\n'):
            self.path.write_text(content)
            with self.assertRaises(ValueError):
                read_dataset(self.path)
        with self.assertLogs('backend.app.main', level='ERROR'):
            self.assertEqual(self.get('/api/experiments')[0], 500)

    def test_hash_stability_and_empty_dataset(self):
        self.path.write_text('label,value\na,1\nb,2\n')
        first, _ = read_dataset(self.path)
        self.path.write_text('value,label\n2,b\n1,a\n')
        second, _ = read_dataset(self.path)
        self.assertEqual(first[0]['id'], second[1]['id'])
        self.path.write_text('label,value\n')
        rows, columns = read_dataset(self.path)
        self.assertEqual(rows, [])
        self.assertEqual(len(columns), 2)

    def test_cors(self):
        code, _, headers = asyncio.run(request('/api/experiments', method='OPTIONS', headers=[(b'origin', b'http://localhost:5173'), (b'access-control-request-method', b'GET')]))
        self.assertEqual(code, 200)
        self.assertEqual(headers[b'access-control-allow-origin'], b'http://localhost:5173')
        _, _, headers = asyncio.run(request('/health', headers=[(b'origin', b'https://untrusted.example')]))
        self.assertNotIn(b'access-control-allow-origin', headers)


if __name__ == '__main__':
    unittest.main()
