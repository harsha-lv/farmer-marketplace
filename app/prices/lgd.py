"""State codes from the Local Government Directory.

District codes are not mapped here. A district directory is a separate dataset.
"""

_STATES = {
    "andaman and nicobar islands": "35",
    "andhra pradesh": "28",
    "arunachal pradesh": "12",
    "assam": "18",
    "bihar": "10",
    "chandigarh": "4",
    "chhattisgarh": "22",
    "delhi": "7",
    "goa": "30",
    "gujarat": "24",
    "haryana": "6",
    "himachal pradesh": "2",
    "jammu and kashmir": "1",
    "jharkhand": "20",
    "karnataka": "29",
    "kerala": "32",
    "ladakh": "37",
    "lakshadweep": "31",
    "madhya pradesh": "23",
    "maharashtra": "27",
    "manipur": "14",
    "meghalaya": "17",
    "mizoram": "15",
    "nagaland": "13",
    "odisha": "21",
    "puducherry": "34",
    "punjab": "3",
    "rajasthan": "8",
    "sikkim": "11",
    "tamil nadu": "33",
    "telangana": "36",
    "the dadra and nagar haveli and daman and diu": "38",
    "tripura": "16",
    "uttarakhand": "5",
    "uttar pradesh": "9",
    "west bengal": "19",
}

_ALIASES = {
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "pondicherry": "puducherry",
    "nct of delhi": "delhi",
    "chhatisgarh": "chhattisgarh",
    "tamilnadu": "tamil nadu",
    "andaman and nicobar": "andaman and nicobar islands",
    "dadra and nagar haveli": "the dadra and nagar haveli and daman and diu",
    "daman and diu": "the dadra and nagar haveli and daman and diu",
}


def normalize_place(name: str) -> str:
    text = name.casefold().replace("&", " and ")
    cleaned = "".join(character if character.isalnum() else " " for character in text)
    return " ".join(cleaned.split())


def state_lgd_code(name: str) -> str | None:
    key = normalize_place(name)
    key = _ALIASES.get(key, key)
    return _STATES.get(key)


def canonical_state_lgd_code(code: str) -> str | None:
    digits = code.strip()
    if not digits.isdigit():
        return None
    padded = digits.zfill(2)
    for value in _STATES.values():
        if value.zfill(2) == padded:
            return value
    return None
