"""Tests for the nonce + MD5 login challenge (no live gateway needed)."""

from att_gateway import auth


def test_hash_password_is_md5_of_code_plus_nonce():
    # Known vector: md5("hello") == 5d41402abc4b2a76b9719d911017c592.
    # Splitting "hello" as code="hel", nonce="lo" proves concatenation + MD5.
    assert auth.hash_password("hel", "lo") == "5d41402abc4b2a76b9719d911017c592"


def test_extract_nonce_from_hidden_input():
    html = '<input type="hidden" name="nonce" value="ABCDEF0123456789abcdef">'
    assert auth.extract_nonce(html) == "ABCDEF0123456789abcdef"


def test_extract_nonce_reversed_attribute_order():
    html = '<input value="0123456789abcdef0123" name="nonce" type="hidden">'
    assert auth.extract_nonce(html) == "0123456789abcdef0123"


def test_extract_nonce_missing_returns_none():
    assert auth.extract_nonce("<html>no nonce here</html>") is None


def test_login_payload_masks_password_and_carries_hash():
    payload = auth.build_login_payload("12@34567/8", "a" * 64)
    assert payload["nonce"] == "a" * 64
    assert payload["password"] == "*" * len("12@34567/8")
    assert payload["hashpassword"] == auth.hash_password("12@34567/8", "a" * 64)
    assert len(payload["hashpassword"]) == 32
