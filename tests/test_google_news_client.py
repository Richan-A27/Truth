import pytest


@pytest.mark.integration
async def test_search_returns_documents_with_titles_and_links():
    from app.clients.google_news_client import search

    docs = await search("bats echolocation", limit=5)
    assert docs
    assert all(d.title for d in docs)
    assert all(d.url.startswith("http") for d in docs)
    assert all(d.source == "google_news" for d in docs)


def test_parse_pub_date_handles_rfc822_format():
    from app.clients.google_news_client import _parse_pub_date

    parsed = _parse_pub_date("Tue, 08 Sep 2026 05:00:00 GMT")
    assert parsed is not None
    assert parsed.year == 2026 and parsed.month == 9 and parsed.day == 8


def test_parse_pub_date_handles_missing_value():
    from app.clients.google_news_client import _parse_pub_date

    assert _parse_pub_date(None) is None
    assert _parse_pub_date("not a date") is None
