"""Bounded provider requests with connection reuse and transient-error retries.

The small urllib Request/BytesIO interface preserves the existing assistant
adapters. Credentials and response bodies are never included in diagnostics.
"""
import atexit
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
import json
import logging
import math
import ssl
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)
REQUEST_BUDGET_SECONDS = 80
MAX_ATTEMPTS = 3
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_deadline = ContextVar("assistant_provider_deadline", default=None)
_client = None
_client_lock = Lock()


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            # Preserve the system CA trust used by the previous urllib client.
            _client = httpx.Client(
                verify=ssl.create_default_context(), follow_redirects=False,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10,
                                   keepalive_expiry=60),
            )
        return _client


def close_provider_client():
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


atexit.register(close_provider_client)


@contextmanager
def provider_budget(seconds=REQUEST_BUDGET_SECONDS):
    """One budget for retrieval, media and generation, including every retry."""
    existing = _deadline.get()
    end = monotonic() + seconds
    token = _deadline.set(min(existing, end) if existing is not None else end)
    try:
        yield
    finally:
        _deadline.reset(token)


def _retry_delay(headers, attempt):
    value = headers.get("retry-after") if headers else None
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = None
        if delay is not None and math.isfinite(delay):
            return max(0, delay)
    return 0.5 * (2 ** attempt)


def open_provider_response(request, timeout=30):
    """Return a bounded response; retry only transient transport/server failures."""
    deadline = _deadline.get()
    if deadline is None:
        deadline = monotonic() + REQUEST_BUDGET_SECONDS
    host = urlsplit(request.full_url).hostname
    for attempt in range(MAX_ATTEMPTS):
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Assistant provider time budget exhausted.")
        connect = min(10, remaining / 4)
        write = min(10, remaining / 8)
        pool = min(5, remaining / 8)
        limits = httpx.Timeout(connect=connect, write=write, pool=pool,
                               read=min(timeout, remaining - connect - write - pool))
        headers = None
        try:
            with _get_client().stream(
                request.get_method(), request.full_url, content=request.data,
                headers=dict(request.header_items()), timeout=limits,
            ) as response:
                headers = response.headers
                if not 200 <= response.status_code < 300:
                    if response.status_code == 429 and not headers.get("retry-after"):
                        # Gemini supplies RetryInfo in JSON rather than an HTTP header.
                        payload = bytearray()
                        for chunk in response.iter_bytes(chunk_size=16384):
                            if len(payload) + len(chunk) > 65536 or monotonic() >= deadline:
                                break
                            payload.extend(chunk)
                        try:
                            details = json.loads(payload).get("error", {}).get("details", [])
                            for detail in details:
                                if str(detail.get("@type", "")).endswith("RetryInfo"):
                                    delay = float(str(detail.get("retryDelay", "")).removesuffix("s"))
                                    if math.isfinite(delay) and delay >= 0:
                                        headers = httpx.Headers(headers)
                                        headers["retry-after"] = str(delay)
                                        break
                        except (ValueError, TypeError, AttributeError):
                            pass
                    # Do not propagate provider bodies: they may contain prompts or keys.
                    error = HTTPError(request.full_url, response.status_code,
                                      "Provider request failed", headers, BytesIO())
                    error.close()
                    raise error
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if monotonic() >= deadline:
                        raise TimeoutError("Assistant provider time budget exhausted.")
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ValueError("Provider response exceeds the size limit.")
                    body.extend(chunk)
                if monotonic() >= deadline:
                    raise TimeoutError("Assistant provider time budget exhausted.")
                return BytesIO(body)
        except HTTPError as error:
            if error.code not in RETRYABLE_STATUS:
                raise
            failure = error
            reason = f"HTTP {error.code}"
        except httpx.TransportError as error:
            # Certificate failures are configuration failures, not transient outages.
            if isinstance(error.__cause__, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(error):
                raise URLError("Provider TLS certificate verification failed.") from None
            failure = URLError(f"Provider transport failed ({type(error).__name__}).")
            reason = type(error).__name__
        delay = _retry_delay(headers, attempt)
        if attempt + 1 >= MAX_ATTEMPTS or delay > 5 or delay + 1 >= deadline - monotonic():
            logger.warning("Provider request failed host=%s attempts=%s reason=%s", host, attempt + 1, reason)
            raise failure from None
        logger.warning("Retrying provider request host=%s attempt=%s reason=%s", host, attempt + 1, reason)
        sleep(delay)
