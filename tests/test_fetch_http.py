import httpx
import pytest

from scripts.lib.fetch_http import FetchError, get_text


def test_get_text_returns_body():
    def handler(request):
        assert request.headers["user-agent"].startswith("paper-to-post")
        return httpx.Response(200, text="hello")

    transport = httpx.MockTransport(handler)
    out = get_text("https://example.com/x", params={"a": "1"}, transport=transport)
    assert out == "hello"


def test_get_text_raises_fetcherror_on_500():
    transport = httpx.MockTransport(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(FetchError):
        get_text("https://example.com/x", transport=transport, max_attempts=2)


def test_get_text_follows_redirects():
    # arXiv redirects http -> https; get_text must follow or bodies come back empty.
    def handler(request):
        if request.url.scheme == "http":
            return httpx.Response(301, headers={"Location": "https://example.com/x"})
        return httpx.Response(200, text="final body")

    transport = httpx.MockTransport(handler)
    out = get_text("http://example.com/x", transport=transport)
    assert out == "final body"


def test_post_text_sends_form_and_basic_auth():
    import base64

    import httpx

    from scripts.lib.fetch_http import post_text

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = req.content.decode()
        seen["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, text='{"access_token": "tok"}')

    t = httpx.MockTransport(handler)
    out = post_text(
        "https://example.com/token",
        data={"grant_type": "client_credentials"},
        auth=("id", "secret"),
        transport=t,
    )
    assert '"access_token": "tok"' in out
    assert seen["body"] == "grant_type=client_credentials"
    expected = "Basic " + base64.b64encode(b"id:secret").decode()
    assert seen["auth"] == expected
    assert seen["ua"].startswith("paper-to-post/")


def test_post_text_raises_on_4xx():
    import httpx
    import pytest

    from scripts.lib.fetch_http import FetchError, post_text

    t = httpx.MockTransport(lambda req: httpx.Response(401, text="no"))
    with pytest.raises(FetchError):
        post_text("https://example.com/token", data={"a": "b"}, transport=t)


def test_get_text_retries_transient_timeout_then_succeeds():
    # A read timeout on the first attempt should be retried, not fatal, so a
    # tarpitting server that eventually answers still yields a body.
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("tarpit", request=request)
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    out = get_text(
        "https://example.com/x", transport=transport, max_attempts=3, timeout=1.0
    )
    assert out == "ok"
    assert calls["n"] == 2


def test_get_text_uses_jittered_backoff():
    # Retries must be de-synchronized (jitter) so parallel callers don't hammer a
    # throttled API in lockstep. The retry wait exposes randomness.
    import inspect

    src = inspect.getsource(get_text)
    assert "wait_random_exponential" in src
