# Backend security and deployment limits

This service exposes public, read-only scientific data. It has no authentication,
write routes, AI credentials or code-execution tools. CSV paths come from server
configuration, not request parameters. CORS keeps its existing explicit origins;
CORS is not authentication and does not block non-browser clients.

Controls: pagination capped at 100, validated filter fields, bounded URL length,
strict CSV parsing, generic CSV error responses, nosniff/frame/referrer headers.
A global budget allows 240 API GET requests per minute per process. It is shared
by all visitors, resets on restart, and multiplies with workers/replicas. It is
not a distributed rate limiter or DDoS defense. Health is outside the budget.
Trusted edge/proxy protections are required for stronger public traffic control.

Use HTTPS at the hosting edge. Run one worker initially, without --reload:
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
Use the hosting platform's assigned PORT where required. Set FRONTEND_ORIGINS to
the actual frontend origins. Do not disable TLS validation. Do not expose logs.
Swagger remains public intentionally for this public read-only hackathon API.

Environment files and bytecode are ignored under backend. Never commit keys.
AI needs separate POST validation, budgets and secret management before release.
Dependencies were not audited against a vulnerability database in this review.
The uploaded frontend has mock predictions and unsafe future innerHTML response
rendering; backend controls alone do not fix those frontend issues.
