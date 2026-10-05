"""Public HTTP/model admission controls; inactive for non-HTTP benchmark calls."""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit
from starlette.responses import JSONResponse


def integer_env(name, default, minimum=1, maximum=1000000):
    try:
        value = int(os.getenv(name, str(default)))
        if not minimum <= value <= maximum:
            raise ValueError
        return value
    except ValueError:
        raise RuntimeError(f'Invalid deployment setting: {name}') from None


@dataclass(frozen=True)
class Settings:
    concurrent_requests: int = 32
    concurrent_workflows: int = 1
    rate_requests: int = 6
    rate_window_seconds: int = 60
    max_request_bytes: int = 32768
    max_calls_per_workflow: int = 128
    daily_request_allowance: int = 500
    public_output_tokens: int | None = None

    @classmethod
    def from_environment(cls):
        return cls(
            concurrent_requests=integer_env('AFL_MAX_CONCURRENT_REQUESTS', 32, maximum=256),
            concurrent_workflows=integer_env('AFL_MAX_CONCURRENT_WORKFLOWS', 1, maximum=8),
            rate_requests=integer_env('AFL_RATE_LIMIT_REQUESTS', 6, maximum=1000),
            rate_window_seconds=integer_env('AFL_RATE_LIMIT_WINDOW_SECONDS', 60, maximum=86400),
            max_request_bytes=integer_env('AFL_MAX_REQUEST_BYTES', 32768, minimum=1024, maximum=1048576),
            max_calls_per_workflow=integer_env('AFL_MAX_MODEL_CALLS_PER_WORKFLOW', 128, maximum=1024),
            daily_request_allowance=integer_env('AFL_DAILY_MODEL_REQUEST_LIMIT', 500, maximum=1000000),
            public_output_tokens=integer_env('AFL_MODEL_MAX_OUTPUT_TOKENS', 4096, minimum=128, maximum=32768) if os.getenv('AFL_MODEL_MAX_OUTPUT_TOKENS') else None,
        )


def cors_origins():
    origins = [origin.strip() for origin in os.getenv('AFL_CORS_ORIGINS', '').split(',') if origin.strip()]
    for origin in origins:
        url = urlsplit(origin)
        if url.scheme not in {'http', 'https'} or not url.netloc or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise RuntimeError('Invalid deployment setting: AFL_CORS_ORIGINS')
    return origins


def budget_path():
    # Resolve at runtime so disposable test/acceptance database settings remain isolated.
    from backend.app.storage import regressions
    return Path(os.getenv('AFL_BUDGET_DATABASE_PATH') or regressions.DATABASE_PATH.with_name('afl_public_budget.sqlite3'))


class PublicLimitExceeded(Exception):
    def __init__(self, message, retry_after=60):
        super().__init__(message)
        self.retry_after = retry_after


class DailyAllowance:
    def __init__(self, path):
        self.path = Path(path)

    def initialize(self):
        with sqlite3.connect(self.path, timeout=15) as db:
            db.execute('CREATE TABLE IF NOT EXISTS public_budget (day TEXT PRIMARY KEY, reserved_requests INTEGER NOT NULL)')

    def reserve(self, allowance, request_slots):
        now = datetime.now(timezone.utc)
        day = now.date().isoformat()
        with sqlite3.connect(self.path, timeout=15) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO public_budget VALUES (?, 0)', (day,))
            used = db.execute('SELECT reserved_requests FROM public_budget WHERE day = ?', (day,)).fetchone()[0]
            if used + request_slots > allowance:
                retry = max(1, 86400 - (now.hour * 3600 + now.minute * 60 + now.second))
                raise PublicLimitExceeded('Daily model request allowance exhausted; retry after the UTC daily reset.', retry)
            db.execute('UPDATE public_budget SET reserved_requests = reserved_requests + ? WHERE day = ?', (request_slots, day))
            db.execute('DELETE FROM public_budget WHERE day < ?', (day,))


class WorkflowBudget:
    def __init__(self, settings, retries):
        self.settings = settings
        self.attempt_slots = retries + 1
        self.calls = 0
        self.rejection = None

    def reserve(self):
        try:
            if self.calls >= self.settings.max_calls_per_workflow:
                raise PublicLimitExceeded('Model-call limit for this workflow reached.')
            DailyAllowance(budget_path()).reserve(self.settings.daily_request_allowance, self.attempt_slots)
            self.calls += 1
        except PublicLimitExceeded as error:
            self.rejection = error
            raise


_public_budget = ContextVar('afl_public_workflow_budget', default=None)


@contextmanager
def public_workflow_budget(settings, retries):
    budget = WorkflowBudget(settings, retries)
    token = _public_budget.set(budget)
    try:
        yield budget
    finally:
        _public_budget.reset(token)


def reserve_model_request():
    budget = _public_budget.get()
    if budget is not None:
        budget.reserve()


def public_output_limit():
    budget = _public_budget.get()
    return budget.settings.public_output_tokens if budget is not None else None


class PublicAdmissionMiddleware:
    """Bound HTTP concurrency, POST body size and per-peer API write attempts.

    Ignore caller-controlled forwarded headers. A trusted ingress may normalize the
    ASGI peer through explicitly configured Uvicorn proxy handling.
    """
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.lock = Lock()
        self.active = 0
        self.peers = {}
        self.last_cleanup = 0

    def admit(self, scope):
        with self.lock:
            if self.active >= self.settings.concurrent_requests:
                return 'Request capacity exceeded; retry shortly.'
            if scope['method'] == 'POST' and scope['path'].startswith('/api/'):
                now = monotonic()
                cutoff = now - self.settings.rate_window_seconds
                if now - self.last_cleanup >= self.settings.rate_window_seconds:
                    self.peers = {key: entries for key, entries in self.peers.items() if entries and entries[-1] > cutoff}
                    self.last_cleanup = now
                peer = (scope.get('client') or ('unknown', 0))[0]
                if peer not in self.peers and len(self.peers) >= 10000:
                    return 'Rate-limit capacity exceeded; retry shortly.'
                entries = self.peers.setdefault(peer, deque())
                while entries and entries[0] <= cutoff:
                    entries.popleft()
                if len(entries) >= self.settings.rate_requests:
                    return 'API request rate exceeded; retry after the rate window.'
                entries.append(now)
            self.active += 1
            return None

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            if scope['type'] == 'lifespan':
                with self.lock:
                    self.peers.clear()
                    self.active = 0
            return await self.app(scope, receive, send)
        denial = self.admit(scope)
        if denial:
            response = JSONResponse({'detail': denial}, status_code=429, headers={'Retry-After': str(self.settings.rate_window_seconds)})
            return await response(scope, receive, send)
        try:
            if scope['method'] in {'POST', 'PUT', 'PATCH'}:
                chunks, size = [], 0
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    chunk = message.get('body', b'')
                    size += len(chunk)
                    if size > self.settings.max_request_bytes:
                        response = JSONResponse({'detail': 'Request body exceeds the configured size limit.'}, status_code=413)
                        return await response(scope, receive, send)
                    chunks.append(chunk)
                    if not message.get('more_body', False):
                        break
                body = b''.join(chunks)
                delivered = False
                async def bounded_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {'type': 'http.request', 'body': body, 'more_body': False}
                    return await receive()
                return await self.app(scope, bounded_receive, send)
            return await self.app(scope, receive, send)
        finally:
            with self.lock:
                self.active -= 1
