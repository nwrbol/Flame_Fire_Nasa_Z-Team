"""Small ASGI guard for the public read-only API; no user data is stored."""
import json
from collections import deque
from threading import Lock
from time import monotonic


class RequestGuard:
    def __init__(self, app):
        self.app = app
        self.requests = deque()
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def safe_send(message):
            if message['type'] == 'http.response.start':
                message = dict(message)
                message['headers'] = list(message.get('headers', [])) + [
                    (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'),
                    (b'referrer-policy', b'no-referrer'),
                ]
            await send(message)

        status, detail = None, None
        if len(scope.get('query_string', b'')) > 8192 or len(scope.get('path', '')) > 2048:
            status, detail = 414, 'Request URL is too long'
        elif scope.get('path', '').startswith('/api/') and scope['method'] == 'GET':
            # Global per-process budget: bounded memory, no trusting forwarded IPs.
            now = monotonic()
            with self.lock:
                while self.requests and self.requests[0] <= now - 60:
                    self.requests.popleft()
                if len(self.requests) >= 240:
                    status, detail = 429, 'API request limit reached; retry later'
                else:
                    self.requests.append(now)
        if status:
            headers = [(b'content-type', b'application/json')]
            if status == 429:
                headers.append((b'retry-after', b'60'))
            await safe_send({'type': 'http.response.start', 'status': status, 'headers': headers})
            return await safe_send({'type': 'http.response.body', 'body': json.dumps({'detail': detail}).encode()})
        await self.app(scope, receive, safe_send)
