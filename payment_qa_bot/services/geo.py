from __future__ import annotations

from typing import Dict


COUNTRY_NAMES: Dict[str, str] = {
    "IN": "India",
    "PK": "Pakistan",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "EG": "Egypt",
    "CI": "Côte d’Ivoire",
    "UZ": "Uzbekistan",
    "AZ": "Azerbaijan",
    "KZ": "Kazakhstan",
    "TH": "Thailand",
    "AR": "Argentina",
    "PH": "Philippines",
    "BR": "Brazil",
    "MX": "Mexico",
    "CO": "Colombia",
    "VN": "Vietnam",
    "TR": "Turkey",
    "BD": "Bangladesh",
}


def flag(code: str) -> str:
    code = code.upper()
    if len(code) != 2 or not code.isalpha():
        return "🌍"
    base = 127397
    return "".join(chr(base + ord(char)) for char in code)


def format_country(code: str) -> str:
    upper = code.upper()
    name = COUNTRY_NAMES.get(upper, upper)
    return f"{flag(upper)} {name}"
