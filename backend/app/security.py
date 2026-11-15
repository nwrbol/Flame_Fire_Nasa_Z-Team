"""Small ASGI guard for the public API; no user data is stored."""
import json
from collections import deque
from threading import Lock
from time import monotonic

MAX_BODY = 64 * 1024          # chat payload: 1000-char question + 6 turns x 1500 chars (UTF-8, JSON-escaped)
API_BUDGET = 240              # GET /api/* per minute, whole process
CHAT_BUDGET = 30              # POST /api/chat per minute, whole process (LLM cost cap)
CHAT_BUDGET_PER_CLIENT = 8    # POST /api/chat per minute, per client address
MAX_TRACKED_CLIENTS = 2048

# The page has inline script/style; everything else is same-origin (no fonts or CDNs from the network).
CSP = (b"default-src 'self'; script-src 'self' 'unsafe-inline'; "
       b"style-src 'self' 'unsafe-inline'; "
       b"font-src 'self'; img-src 'self' data:; connect-src 'self'; "
       b"object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def _take(window, now, limit):
    """Sliding 60 s window: record a hit and return True if under the limit."""
    while window and window[0] <= now - 60:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


class RequestGuard:
    def __init__(self, app):
        self.app = app
        self.requests = deque()
        self.chat_requests = deque()
        self.chat_clients = {}
        self.lock = Lock()

    def _chat_allowed(self, client, now):
        with self.lock:
            if len(self.chat_clients) > MAX_TRACKED_CLIENTS:  # bounded memory
                self.chat_clients = {k: v for k, v in self.chat_clients.items() if v and v[-1] > now - 60}
            window = self.chat_clients.setdefault(client, deque())
            if not _take(window, now, CHAT_BUDGET_PER_CLIENT):
                return False
            if not _take(self.chat_requests, now, CHAT_BUDGET):
                window.pop()
                return False
            return True

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def safe_send(message):
            if message['type'] == 'http.response.start':
                message = dict(message)
                headers = list(message.get('headers', []))
                headers += [(b'x-content-type-options', b'nosniff'),
                            (b'x-frame-options', b'DENY'),
                            (b'referrer-policy', b'no-referrer'),
                            (b'permissions-policy', b'camera=(), microphone=(), geolocation=()')]
                if any(k.lower() == b'content-type' and v.startswith(b'text/html') for k, v in headers) \
                        and scope.get('path') == '/':
                    headers.append((b'content-security-policy', CSP))
                # page scripts change with the site: always revalidate (ETag -> cheap 304), so a
                # browser never runs a stale scene script against a newer page
                if scope.get('path', '').startswith(('/js/', '/vendor/')) and \
                        not any(k.lower() == b'cache-control' for k, _ in headers):
                    headers.append((b'cache-control', b'no-cache'))
                message['headers'] = headers
            await send(message)

        path, method = scope.get('path', ''), scope['method']
        headers = {k.lower(): v for k, v in scope.get('headers', [])}
        status, detail, replay = None, None, None
        if len(scope.get('query_string', b'')) > 8192 or len(path) > 2048:
            status, detail = 414, 'Request URL is too long'
        elif path.startswith('/api/') and method == 'GET':
            # Global per-process budget: bounded memory, no trusting forwarded IPs.
            with self.lock:
                if not _take(self.requests, monotonic(), API_BUDGET):
                    status, detail = 429, 'API request limit reached; retry later'
        elif method not in ('GET', 'HEAD', 'OPTIONS'):
            declared = headers.get(b'content-length', b'0')
            if not declared.isdigit() or int(declared) > MAX_BODY:
                status, detail = 413, 'Request body is too large'
            elif path == '/api/chat' and not headers.get(b'content-type', b'').split(b';')[0].strip() == b'application/json':
                # Forces a CORS preflight for cross-site browsers (no "simple" text/plain POSTs).
                status, detail = 415, 'Content-Type must be application/json'
            else:
                # Read the body here so chunked uploads cannot exceed the limit either.
                chunks, size = [], 0
                while True:
                    message = await receive()
                    if message['type'] != 'http.request':
                        return
                    chunk = message.get('body', b'')
                    size += len(chunk)
                    if size > MAX_BODY:
                        status, detail = 413, 'Request body is too large'
                        break
                    chunks.append(chunk)
                    if not message.get('more_body'):
                        replay = b''.join(chunks)
                        break
                if not status and path == '/api/chat':
                    client = (scope.get('client') or ('unknown', 0))[0]
                    if not self._chat_allowed(client, monotonic()):
                        status, detail = 429, 'AI request limit reached; retry later'
        if status:
            out = [(b'content-type', b'application/json')]
            if status == 429:
                out.append((b'retry-after', b'60'))
            await safe_send({'type': 'http.response.start', 'status': status, 'headers': out})
            return await safe_send({'type': 'http.response.body', 'body': json.dumps({'detail': detail}).encode()})

        if replay is not None:
            sent = False

            async def replay_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': replay, 'more_body': False}
                return await receive()
            return await self.app(scope, replay_receive, safe_send)
        await self.app(scope, receive, safe_send)
