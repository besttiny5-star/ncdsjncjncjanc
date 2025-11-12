from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Dict, Optional


PKG_PATTERN = re.compile(r"^pkg_(?P<pkg>[a-z0-9]+)_geo_(?P<geo>[A-Za-z]{2})$")
CALC_PATTERN = re.compile(
    r"^calc_geo(?P<geo>[A-Za-z]{2})_tests(?P<tests>\d+)_opt<(?P<opts>[^>]*)>(?:_sign<(?P<sign>[^>]+)>)?$"
)
CALC_V1_PATTERN = re.compile(
    r"^calc_v1_geo(?P<geo>[A-Za-z]{2})_tests(?P<tests>\d+)_payout(?P<payout>[NWK])"
    r"(?:_method<(?P<method>[^>]+)>)?"
    r"(?:_site<(?P<site>[^>]+)>)?"
    r"(?:_login<(?P<login>[^>]+)>)?"
    r"(?:_password<(?P<password>[^>]+)>)?"
    r"(?:_comments<(?P<comments>[^>]+)>)?"
    r"(?:_price(?P<price>\d+))?"
    r"(?:_sign<(?P<sign>[^>]+)>)?$"
)
REF_PATTERN = re.compile(r"^calc_ref_(?P<token>[A-Za-z0-9_-]{4,128})$")

OPTION_MAP: Dict[str, str] = {
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
    price_total: Optional[int] = None
    reference_token: Optional[str] = None


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


def _decode_segment(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    chunk = value
    padding = (-len(chunk)) % 4
    if padding:
        chunk += "=" * padding
    try:
        return base64.urlsafe_b64decode(chunk).decode("utf-8")
    except Exception:
        return None


def parse_payload(payload: str, secret: Optional[bytes] = None) -> PayloadParseResult:
    payload = payload.strip()
    ref_match = REF_PATTERN.match(payload)
    if ref_match:
        data = PayloadData(source="site", reference_token=ref_match.group("token"))
        return PayloadParseResult(ok=False, data=data, error="payload_reference")
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
        provided_signature = rest[:-1] if rest.endswith(">") else rest
        raw_for_signature = unsigned

    calc_v1_match = CALC_V1_PATTERN.match(payload)
    if calc_v1_match:
        if provided_signature and secret:
            _verify_signature(raw_for_signature, provided_signature, secret)
        data = PayloadData(source="site")
        data.geo = calc_v1_match.group("geo").upper()
        tests = int(calc_v1_match.group("tests"))
        if 1 <= tests <= 25:
            data.tests_count = tests
        payout_code = calc_v1_match.group("payout")
        if payout_code == "W":
            data.withdraw_required = True
            data.kyc_required = False
        elif payout_code == "K":
            data.withdraw_required = True
            data.kyc_required = True
        else:
            data.withdraw_required = False
            data.kyc_required = False
        decoded_method = _decode_segment(calc_v1_match.group("method"))
        if decoded_method:
            data.payment_method = decoded_method
        decoded_site = _decode_segment(calc_v1_match.group("site"))
        if decoded_site:
            data.site_url = decoded_site
        decoded_login = _decode_segment(calc_v1_match.group("login"))
        if decoded_login is not None:
            data.login = decoded_login
        decoded_password = _decode_segment(calc_v1_match.group("password"))
        if decoded_password is not None:
            data.password = decoded_password
        decoded_comments = _decode_segment(calc_v1_match.group("comments"))
        if decoded_comments is not None:
            data.comments = decoded_comments
        price_value = calc_v1_match.group("price")
        if price_value and price_value.isdigit():
            data.price_total = int(price_value)
        return PayloadParseResult(ok=True, data=data, error=None)

    calc_match = CALC_PATTERN.match(payload)
    if calc_match:
        if provided_signature and secret:
            _verify_signature(raw_for_signature, provided_signature, secret)
        data = PayloadData(source="site")
        data.geo = calc_match.group("geo").upper()
        tests = int(calc_match.group("tests"))
        if 1 <= tests <= 25:
            data.tests_count = tests
        opts = calc_match.group("opts")
        for char in opts:
            key = OPTION_MAP.get(char)
            if key:
                setattr(data, key, True)
        return PayloadParseResult(ok=True, data=data, error=None)

    return PayloadParseResult(ok=False, data=PayloadData(source="tg"), error="unsupported_payload")
