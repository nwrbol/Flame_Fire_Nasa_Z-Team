import unittest
from backend.app.security import CHAT_BUDGET_PER_CLIENT, MAX_BODY, RequestGuard


def request(guard, query=b'', path='/api/metadata', method='GET', body=b'', headers=None,
            client='1.2.3.4', chunks=None):
    messages = []
    parts = chunks if chunks is not None else [body]
    queue = [{'type': 'http.request', 'body': p, 'more_body': i < len(parts) - 1} for i, p in enumerate(parts)]

    async def send(message):
        messages.append(message)

    async def receive():
        return queue.pop(0) if queue else {'type': 'http.disconnect'}

    if headers is None:
        headers = [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())] \
            if method == 'POST' else []
    task = guard({'type': 'http', 'method': method, 'path': path, 'query_string': query,
                  'headers': headers, 'client': (client, 5000)}, receive, send)
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
        self.received = []

        async def downstream(scope, receive, send):
            if scope['method'] == 'POST':
                self.received.append((await receive())['body'])
            content_type = b'text/html' if scope['path'] == '/' else b'application/json'
            await send({'type': 'http.response.start', 'status': 200, 'headers': [(b'content-type', content_type)]})
            await send({'type': 'http.response.body', 'body': b'{}'})
        self.guard = RequestGuard(downstream)

    def test_headers(self):
        headers = dict(request(self.guard)[0]['headers'])
        self.assertEqual(headers[b'x-content-type-options'], b'nosniff')
        self.assertEqual(headers[b'x-frame-options'], b'DENY')
        self.assertNotIn(b'content-security-policy', headers)

    def test_csp_on_page(self):
        headers = dict(request(self.guard, path='/')[0]['headers'])
        csp = headers[b'content-security-policy']
        self.assertIn(b"frame-ancestors 'none'", csp)
        self.assertIn(b"connect-src 'self'", csp)

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

    def test_chat_body_is_replayed(self):
        body = b'{"message":"hi"}'
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=body)[0]['status'], 200)
        self.assertEqual(self.received, [body])

    def test_chat_body_limits(self):
        big = b'x' * (MAX_BODY + 1)
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=big)[0]['status'], 413)
        # Declared length lies: chunked body larger than the limit is still rejected.
        lying = [(b'content-type', b'application/json'), (b'content-length', b'10')]
        status = request(self.guard, path='/api/chat', method='POST', headers=lying,
                         chunks=[b'x' * MAX_BODY, b'x'])[0]['status']
        self.assertEqual(status, 413)
        bad_len = [(b'content-type', b'application/json'), (b'content-length', b'abc')]
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', headers=bad_len)[0]['status'], 413)
        self.assertEqual(self.received, [])

    def test_chat_requires_json_content_type(self):
        plain = [(b'content-type', b'text/plain'), (b'content-length', b'2')]
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=b'{}', headers=plain)[0]['status'], 415)

    def test_chat_rate_limit_per_client(self):
        for _ in range(CHAT_BUDGET_PER_CLIENT):
            self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=b'{}')[0]['status'], 200)
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=b'{}')[0]['status'], 429)
        # Another client still has its own allowance.
        self.assertEqual(request(self.guard, path='/api/chat', method='POST', body=b'{}', client='5.6.7.8')[0]['status'], 200)


if __name__ == '__main__':
    unittest.main()
