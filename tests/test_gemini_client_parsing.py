from app.clients.gemini_client import _parse_claims_json


def test_parses_clean_json_array():
    assert _parse_claims_json('["Claim A", "Claim B"]') == ["Claim A", "Claim B"]


def test_parses_json_wrapped_in_code_fence():
    text = '```json\n["Claim A", "Claim B"]\n```'
    assert _parse_claims_json(text) == ["Claim A", "Claim B"]


def test_parses_json_wrapped_in_plain_code_fence():
    text = '```\n["Claim A"]\n```'
    assert _parse_claims_json(text) == ["Claim A"]


def test_extracts_array_from_surrounding_commentary():
    text = 'Here are the claims I found:\n["Claim A", "Claim B"]\nLet me know if you need more.'
    assert _parse_claims_json(text) == ["Claim A", "Claim B"]


def test_returns_none_for_empty_claims_list():
    assert _parse_claims_json("[]") == []


def test_returns_none_for_garbage():
    assert _parse_claims_json("I couldn't find any claims.") is None
