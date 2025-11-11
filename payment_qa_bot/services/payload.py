from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Dict, Optional


PKG_PATTERN = re.compile(r"^pkg_(?P<pkg>[a-z0-9]+)_geo_(?P<geo>[A-Za-z]{2})$")
CALC_PATTERN = re.compile(
    r"^calc_geo(?P<geo>[A-Za-z]{2})_tests(?P<tests>\d+)_opt<(?P<opts>[^>]*)>(?:_sign<(?P<sign>[^>]+)>)?$"
)
ORDER_PATTERN = re.compile(r"^o1_(?P<data>[A-Za-z0-9_-]+)$")

OPTION_MAP = {
    "w": "withdraw_required",
    "W": "withdraw_required",
    "k": "kyc_required",
    "K": "kyc_required",
    "c": "custom_test_required",
    "C": "custom_test_required",
}


@dataclass(slots=True)
class PayloadData:
    source: str
    geo: Optional[str] = None
    tests_count: Optional[int] = None
    withdraw_required: Optional[bool] = None
    custom_test_required: Optional[bool] = None
    kyc_required: Optional[bool] = None
    custom_test_text: Optional[str] = None
    payment_method: Optional[str] = None
    site_url: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    comments: Optional[str] = None
    package_type: Optional[str] = None
    payout_key: Optional[str] = None
    price_total: Optional[int] = None
    payload_fingerprint: Optional[str] = None


@dataclass(slots=True)
class PayloadParseResult:
    ok: bool
    data: PayloadData
    error: Optional[str] = None


class SignatureMismatchError(Exception):
    """Raised when payload signature is invalid."""


def _verify_signature(raw: str, provided: str, secret: bytes) -> None:
    digest = hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    provided = provided.rstrip("=")
    if not hmac.compare_digest(expected, provided):
        raise SignatureMismatchError("Invalid payload signature")


def parse_payload(payload: str, secret: Optional[bytes] = None) -> PayloadParseResult:
    payload = payload.strip()
    order_match = ORDER_PATTERN.match(payload)
    if order_match:
        encoded = order_match.group("data")
        padding = "=" * (-len(encoded) % 4)
        try:
            raw_bytes = base64.urlsafe_b64decode(encoded + padding)
            raw_json = raw_bytes.decode("utf-8")
            parsed: Dict[str, object] = json.loads(raw_json)
        except Exception:  # noqa: BLE001 - payload is user-controlled
            return PayloadParseResult(ok=False, data=PayloadData(source="tg"), error="invalid_payload")

        fingerprint = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        data = PayloadData(source="site")
        data.geo = str(parsed.get("geo", "")).upper() or None
        tests_value = parsed.get("tests")
        if isinstance(tests_value, int) and 1 <= tests_value <= 100:
            data.tests_count = tests_value
        method_value = parsed.get("method")
        if isinstance(method_value, str) and method_value.strip():
            data.payment_method = method_value.strip()
        payout_value = parsed.get("payout")
        if isinstance(payout_value, str) and payout_value:
            data.payout_key = payout_value
        withdraw_value = parsed.get("withdraw")
        if isinstance(withdraw_value, bool):
            data.withdraw_required = withdraw_value
        kyc_value = parsed.get("kyc")
        if isinstance(kyc_value, bool):
            data.kyc_required = kyc_value
        price_value = parsed.get("price")
        if isinstance(price_value, int) and price_value >= 0:
            data.price_total = price_value
        comments_value = parsed.get("comments")
        if isinstance(comments_value, str):
            data.comments = comments_value.strip() or None
        site_value = parsed.get("site")
        if isinstance(site_value, str):
            data.site_url = site_value.strip() or None
        login_value = parsed.get("login")
        if isinstance(login_value, str):
            data.login = login_value.strip() or None
        password_value = parsed.get("password")
        if isinstance(password_value, str):
            data.password = password_value.strip() or None
        data.payload_fingerprint = fingerprint
        return PayloadParseResult(ok=True, data=data, error=None)

    pkg_match = PKG_PATTERN.match(payload)
    if pkg_match:
        data = PayloadData(source="site")
        data.geo = pkg_match.group("geo").upper()
        data.package_type = pkg_match.group("pkg")
        return PayloadParseResult(ok=True, data=data, error=None)

    raw_for_signature = payload
    provided_signature: Optional[str] = None
    if "_sign<" in payload:
        unsigned, _, rest = payload.partition("_sign<")
        if rest.endswith(">"):
            provided_signature = rest[:-1]
        else:
            provided_signature = rest
        raw_for_signature = unsigned
    calc_match = CALC_PATTERN.match(payload)
    if calc_match:
        if provided_signature and secret:
            _verify_signature(raw_for_signature, provided_signature, secret)
        data = PayloadData(source="site")
        data.geo = calc_match.group("geo").upper()
        tests = int(calc_match.group("tests"))
        if 1 <= tests <= 100:
            data.tests_count = tests
        opts = calc_match.group("opts")
        for char in opts:
            key = OPTION_MAP.get(char)
            if key:
                setattr(data, key, True)
        return PayloadParseResult(ok=True, data=data, error=None)

    return PayloadParseResult(ok=False, data=PayloadData(source="tg"), error="unsupported_payload")


def build_payload_hash(fingerprint: Optional[str], user_id: int) -> Optional[str]:
    if not fingerprint:
        return None
    raw = f"{fingerprint}:{user_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
