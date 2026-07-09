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
