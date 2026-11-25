import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tradebot.exness.signing import EMPTY_BODY_HASH, b64url_decode, load_private_key, sign_headers

# Exness dokumanindaki sentetik vektor (RFC 8032 Test 1 anahtari; gercek bir kimlik bilgisi degildir).
VECTOR_KEY = (
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
)
VECTOR_DATA = (
    "eyJhcGlfa2V5IjoiZXhuc2stc3ludGhldGljLWV4YW1wbGUiLCJpZGVtcG90ZW5jeV9rZXkiOiIiLCJ0aW1lc3RhbXAiOjE3"
    "NzM2NTYwNzAxMjMsInNpZ25fdmVyc2lvbiI6MSwibWV0aG9kIjoiR0VUIiwicGF0aCI6Ii92MS90cmFkaW5nL2FjY2Vzcy1w"
    "b2ludD9hY2NvdW50X2lkPTEyMzQ1NiIsImJvZHlfaGFzaCI6IjQ3REVRcGo4SEJTYS1fVEltVy01SkNldVFlUmttNU5NcEpX"
    "WkczaFN1RlUifQ"
)
VECTOR_SIGN = "l-H_Acia8YoTjKFMg-3fon3NOEX8TalNVA7c01DQ9dHb7pVBJC4y06qC-DbpETzh1KToiOprqEV6uzN3t69ICQ"


def _key():
    return load_private_key(VECTOR_KEY)


def _sign(**overrides):
    args = dict(method="GET", path="/v1/x", body=b"", api_key="exnsk-test", key=_key(),
                idempotency_key="", timestamp_ms=1773656070123)
    args.update(overrides)
    return sign_headers(**args)


def _payload(headers):
    return json.loads(b64url_decode(headers["EXN-DATA"]))


def test_official_test_vector():
    headers = _sign(path="/v1/trading/access-point?account_id=123456", api_key="exnsk-synthetic-example")
    assert headers["EXN-DATA"] == VECTOR_DATA
    assert headers["EXN-SIGN"] == VECTOR_SIGN
    assert headers["EXN-TIMESTAMP"] == "1773656070123"
    assert headers["EXN-SIGN-VERSION"] == "1"
    assert headers["EXN-IDEMPOTENCY-KEY"] == ""
    assert headers["EXN-API-KEY"] == "exnsk-synthetic-example"


def test_empty_body_hash():
    assert EMPTY_BODY_HASH == "47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU"
    assert _payload(_sign())["body_hash"] == EMPTY_BODY_HASH


def test_body_hash_covers_exact_body_bytes():
    a = _payload(_sign(method="POST", body=b'{"a":1}', idempotency_key="order-1"))
    b = _payload(_sign(method="POST", body=b'{"a": 1}', idempotency_key="order-1"))
    assert a["body_hash"] != b["body_hash"] != EMPTY_BODY_HASH


def test_signature_verifies_over_decoded_payload():
    headers = _sign(method="POST", body=b'{"volume":"0.01"}', idempotency_key="bot-abc123")
    _key().public_key().verify(b64url_decode(headers["EXN-SIGN"]), b64url_decode(headers["EXN-DATA"]))


def test_payload_field_order_and_types():
    payload = b64url_decode(_sign()["EXN-DATA"]).decode()
    assert list(json.loads(payload)) == ["api_key", "idempotency_key", "timestamp", "sign_version",
                                         "method", "path", "body_hash"]
    assert '"timestamp":1773656070123' in payload and '"sign_version":1' in payload
    assert " " not in payload


def test_no_padding():
    for body in (b"", b"a", b"ab", b"abc"):
        headers = _sign(method="POST", body=body, idempotency_key="order-1")
        assert all("=" not in value for value in headers.values())


def test_get_requires_empty_idempotency():
    with pytest.raises(ValueError):
        _sign(method="GET", idempotency_key="order-1")


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "PUT"])
def test_mutating_requires_nonempty_idempotency(method):
    with pytest.raises(ValueError):
        _sign(method=method, idempotency_key="")


@pytest.mark.parametrize("bad", ["abcd", "x" * 129, "has space", "slash/key", "türkçe-key"])
def test_idempotency_key_shape_enforced(bad):
    with pytest.raises(ValueError):
        _sign(method="POST", idempotency_key=bad)


def test_method_uppercased_and_path_includes_query_exactly():
    path = "/v1/market-data/accounts/1/candles?instrument=EURUSD&timeframe=M15&from=2026-03-16T12%3A00%3A00%2B00%3A00&count=5"
    payload = _payload(_sign(method="get", path=path))
    assert payload["path"] == path and payload["method"] == "GET"


def test_path_must_be_a_path_not_a_url():
    with pytest.raises(ValueError):
        _sign(path="https://host/v1/x")


def test_load_private_key_formats():
    seed = bytes.fromhex(VECTOR_KEY[:64])
    expected = _key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pem = Ed25519PrivateKey.from_private_bytes(seed).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    candidates = [VECTOR_KEY, VECTOR_KEY[:64], pem, pem.replace("\n", "\\n"),
                  base64.b64encode(seed).decode(), base64.urlsafe_b64encode(seed).decode().rstrip("=")]
    for raw in candidates:
        public = load_private_key(raw).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        assert public == expected


def test_load_private_key_rejects_mismatched_public_half_without_leaking():
    broken = VECTOR_KEY[:64] + "00" * 32
    with pytest.raises(ValueError) as error:
        load_private_key(broken)
    assert VECTOR_KEY[:16] not in str(error.value)
    with pytest.raises(ValueError):
        load_private_key("not-a-key")
