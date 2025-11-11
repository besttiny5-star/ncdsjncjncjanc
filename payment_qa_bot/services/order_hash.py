from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


NORMALIZED_FIELDS = (
    "source",
    "geo",
    "tests_count",
    "method_user_text",
    "withdraw_required",
    "custom_test_required",
    "kyc_required",
    "site_url",
    "comments",
    "price_eur",
    "payment_network",
    "payment_wallet",
)


def build_payload_hash(user_id: int, data: Dict[str, Any]) -> str:
    """Return a stable hash for deduplication of identical orders."""

    normalized: Dict[str, Any] = {"user_id": int(user_id)}
    for field in NORMALIZED_FIELDS:
        if field in data:
            normalized[field] = data[field]
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
