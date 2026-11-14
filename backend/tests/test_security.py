import unittest
from backend.app.security import RequestGuard


def request(guard, query=b'', path='/api/metadata'):
    messages = []
    async def send(message):
        messages.append(message)
    async def receive():
        return {'type': 'http.request', 'body': b''}
    task = guard({'type': 'http', 'method': 'GET', 'path': path,
                  'query_string': query}, receive, send)
    # This guard and the test downstream do not perform asynchronous I/O.
    try:
        task.send(None)
    except StopIteration:
        pass
    else:
        task.close()
        raise AssertionError('Unexpected I/O in isolated guard test')
    return messages


class SecurityTests(unittest.TestCase):
    def setUp(self):
        async def downstream(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{}'})
        self.guard = RequestGuard(downstream)

    def test_headers(self):
        headers = dict(request(self.guard)[0]['headers'])
        self.assertEqual(headers[b'x-content-type-options'], b'nosniff')
        self.assertEqual(headers[b'x-frame-options'], b'DENY')

    def test_oversized_url(self):
        self.assertEqual(request(self.guard, b'x' * 8193)[0]['status'], 414)
        self.assertEqual(request(self.guard, path='/' * 2049)[0]['status'], 414)

    def test_budget_and_health(self):
        for _ in range(240):
            self.assertEqual(request(self.guard)[0]['status'], 200)
        result = request(self.guard)[0]
        self.assertEqual(result['status'], 429)
        self.assertEqual(dict(result['headers'])[b'retry-after'], b'60')
        self.assertEqual(request(self.guard, path='/health')[0]['status'], 200)
