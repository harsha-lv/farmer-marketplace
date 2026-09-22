from app.farmers.verhoeff import verhoeff_check_digit, verhoeff_is_valid
from app.prices.lgd import canonical_state_lgd_code


class FarmIdError(Exception):
    """A farm id does not match the 14-character registry format."""


def make_farm_id(state_lgd_code: str, random_digits: str) -> str:
    state = canonical_state_lgd_code(state_lgd_code)
    if state is None:
        raise FarmIdError("unknown state code")
    if len(random_digits) != 11 or not random_digits.isdigit():
        raise FarmIdError("the random part must be 11 digits")
    return f"{state.zfill(2)}{random_digits}{verhoeff_check_digit(random_digits)}"


def validate_farm_id(farm_id: str, *, state_lgd_code: str | None = None) -> str:
    if len(farm_id) != 14 or not farm_id.isdigit():
        raise FarmIdError("a farm id must be 14 digits")
    state = canonical_state_lgd_code(farm_id[:2])
    if state is None:
        raise FarmIdError("a farm id has an unknown state code")
    if not verhoeff_is_valid(farm_id[2:]):
        raise FarmIdError("a farm id checksum is invalid")
    if state_lgd_code is not None:
        expected = canonical_state_lgd_code(state_lgd_code)
        if expected != state:
            raise FarmIdError("a farm id belongs to a different state")
    return farm_id
