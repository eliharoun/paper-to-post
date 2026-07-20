from __future__ import annotations

import os

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)


def user_agent() -> str:
    """Build a polite User-Agent, embedding the real contact email when configured.

    Polite-pool APIs (Crossref, OpenAlex, PubMed, Unpaywall) ask for a contact
    address in the User-Agent. When CONTACT_EMAIL is set we include it; otherwise
    we send a neutral UA rather than a literal placeholder.
    """
    contact = os.environ.get("CONTACT_EMAIL", "").strip()
    suffix = f"; mailto:{contact}" if contact else ""
    return f"paper-to-post/0.1 (research paper pipeline{suffix})"


class FetchError(RuntimeError):
    """Raised when an HTTP fetch fails after retries. Maps to CLI exit code 2."""


class _RetryableStatus(Exception):
    """Internal: a 5xx/429 worth retrying."""


def get_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    max_attempts: int = 4,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """GET a URL and return the response text, retrying transient errors.

    Raises FetchError on non-2xx after retries or on network failure.
    `transport` is for tests (httpx.MockTransport).
    """
    merged_headers = {"User-Agent": user_agent()}
    if headers:
        merged_headers.update(headers)

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type((httpx.TransportError, _RetryableStatus)),
        reraise=True,
    )
    def _do() -> str:
        with httpx.Client(
            timeout=timeout, transport=transport, follow_redirects=True
        ) as client:
            resp = client.get(url, params=params, headers=merged_headers)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise _RetryableStatus(f"status {resp.status_code}")
            if resp.status_code >= 400:
                raise FetchError(f"GET {url} -> {resp.status_code}")
            return resp.text

    try:
        return _do()
    except _RetryableStatus as exc:
        raise FetchError(str(exc)) from exc
    except httpx.TransportError as exc:
        raise FetchError(f"network error: {exc}") from exc


def post_text(
    url: str,
    *,
    data: dict | None = None,
    headers: dict | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 30.0,
    max_attempts: int = 4,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """POST a form body and return the response text, retrying transient errors.

    Mirrors get_text: same retry policy, polite User-Agent, and `transport`
    injection for tests. `auth` is (username, password) HTTP Basic. Used for
    OAuth token endpoints (e.g. Reddit's application-only grant).
    """
    merged_headers = {"User-Agent": user_agent()}
    if headers:
        merged_headers.update(headers)

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type((httpx.TransportError, _RetryableStatus)),
        reraise=True,
    )
    def _do() -> str:
        with httpx.Client(
            timeout=timeout, transport=transport, follow_redirects=True
        ) as client:
            resp = client.post(url, data=data, auth=auth, headers=merged_headers)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise _RetryableStatus(f"status {resp.status_code}")
            if resp.status_code >= 400:
                raise FetchError(f"POST {url} -> {resp.status_code}")
            return resp.text

    try:
        return _do()
    except _RetryableStatus as exc:
        raise FetchError(str(exc)) from exc
    except httpx.TransportError as exc:
        raise FetchError(f"network error: {exc}") from exc
