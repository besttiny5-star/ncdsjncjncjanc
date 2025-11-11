from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Set


def _parse_admin_ids(raw: str) -> Set[int]:
    result: Set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.lstrip("+-").isdigit():
            result.add(int(chunk))
    return result


def _parse_geo_list(raw: str) -> List[str]:
    items: List[str] = []
    for chunk in raw.split(","):
        code = chunk.strip().upper()
        if len(code) == 2 and code.isalpha():
            items.append(code)
    return items


@dataclass(slots=True)
class Config:
    bot_token: str
    db_path: str
    admin_ids: Set[int]
    wallet_trc20: str
    help_contact: str
    payload_secret: Optional[bytes]
    encryption_key: Optional[bytes]
    default_language: str
    geo_whitelist: List[str]
    api_host: str
    api_port: int


def load_config() -> Config:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    db_path = os.getenv("DB_URL") or os.getenv("BOT_DB_PATH", "sqlite+aiosqlite:///./bot.db")
    if db_path.startswith("sqlite+"):
        db_path = db_path.split("sqlite+", maxsplit=1)[-1]

    wallet = os.getenv("P2P_WALLET_TRC20", "")
    help_contact = os.getenv("P2P_HELP_CONTACT", "@support")

    secret = os.getenv("PAYLOAD_HMAC_SECRET")
    payload_secret = secret.encode("utf-8") if secret else None

    encryption = os.getenv("ENCRYPTION_KEY")
    encryption_key = encryption.encode("utf-8") if encryption else None

    default_lang = os.getenv("BOT_DEFAULT_LANG", "en").lower()
    if default_lang not in {"en", "ru"}:
        default_lang = "en"

    geo_whitelist = _parse_geo_list(
        os.getenv(
            "BOT_GEO_WHITELIST",
            "IN,BD,PK,ID,MY,TH,PH,EG,KZ,UZ,CI,AR",
        )
    )

    api_host = os.getenv("API_HOST", "0.0.0.0")
    try:
        api_port = int(os.getenv("API_PORT", "8080"))
    except ValueError:
        api_port = 8080

    return Config(
        bot_token=token,
        db_path=db_path,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", os.getenv("PAYMENT_QA_ADMIN_IDS", ""))),
        wallet_trc20=wallet,
        help_contact=help_contact,
        payload_secret=payload_secret,
        encryption_key=encryption_key,
        default_language=default_lang,
        geo_whitelist=geo_whitelist,
        api_host=api_host,
        api_port=api_port,
    )
