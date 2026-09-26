"""Agricultural and Festival Calendar Feature Extractor.

Extracts cyclic time embeddings and binary indicators for:
  - Indian festivals (Diwali, Eid, Holi, Dussehra, Makar Sankranti, Pongal, Baisakhi)
  - Mandi closures and holidays (Sundays, national and state APMC gazetted holidays)
  - Crop harvest seasons (Kharif arrival glut, Rabi arrival glut, Zaid harvest)
  - Cyclic harmonic features (sin/cos day-of-year, sin/cos day-of-week)
"""

import math
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class CalendarFeatures:
    target_date: date
    is_festival: bool
    festival_name: str | None
    is_mandi_holiday: bool
    is_harvest_season: bool
    season_name: str | None
    sin_day_of_year: float
    cos_day_of_year: float
    sin_day_of_week: float
    cos_day_of_week: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Fixed and floating festival registry for agricultural markets (2024-2027)
FESTIVAL_CALENDAR: dict[tuple[int, int, int], str] = {
    # 2024
    (2024, 1, 14): "Makar Sankranti / Pongal",
    (2024, 3, 25): "Holi",
    (2024, 4, 11): "Eid-ul-Fitr",
    (2024, 4, 14): "Baisakhi",
    (2024, 6, 17): "Eid-ul-Adha",
    (2024, 8, 19): "Raksha Bandhan",
    (2024, 10, 12): "Dussehra",
    (2024, 11, 1): "Diwali",
    # 2025
    (2025, 1, 14): "Makar Sankranti / Pongal",
    (2025, 3, 14): "Holi",
    (2025, 3, 31): "Eid-ul-Fitr",
    (2025, 4, 14): "Baisakhi",
    (2025, 6, 7): "Eid-ul-Adha",
    (2025, 8, 9): "Raksha Bandhan",
    (2025, 10, 2): "Dussehra",
    (2025, 10, 20): "Diwali",
    # 2026
    (2026, 1, 14): "Makar Sankranti / Pongal",
    (2026, 3, 4): "Holi",
    (2026, 3, 20): "Eid-ul-Fitr",
    (2026, 4, 14): "Baisakhi",
    (2026, 5, 27): "Eid-ul-Adha",
    (2026, 8, 28): "Raksha Bandhan",
    (2026, 10, 20): "Dussehra",
    (2026, 11, 8): "Diwali",
    # 2027
    (2027, 1, 14): "Makar Sankranti / Pongal",
    (2027, 3, 22): "Holi",
    (2027, 3, 10): "Eid-ul-Fitr",
    (2027, 4, 14): "Baisakhi",
    (2027, 5, 17): "Eid-ul-Adha",
    (2027, 8, 17): "Raksha Bandhan",
    (2027, 10, 9): "Dussehra",
    (2027, 10, 29): "Diwali",
}

# Fixed national holidays where wholesale mandis are closed
GAZETTED_NATIONAL_HOLIDAYS: set[tuple[int, int]] = {
    (1, 26),  # Republic Day
    (5, 1),   # May Day / Labor Day
    (8, 15),  # Independence Day
    (10, 2),  # Gandhi Jayanti
}


class CalendarFeatureExtractor:
    """Computes calendar, holiday, and seasonality features for market forecasting."""

    @classmethod
    def get_features(cls, d: date) -> CalendarFeatures:
        year, month, day = d.year, d.month, d.day
        doy = d.timetuple().tm_yday
        dow = d.weekday()  # Monday = 0, Sunday = 6

        # 1. Cyclic features
        # Day of year harmonic
        sin_doy = round(math.sin(2.0 * math.pi * (doy - 1) / 365.25), 6)
        cos_doy = round(math.cos(2.0 * math.pi * (doy - 1) / 365.25), 6)
        # Day of week harmonic
        sin_dow = round(math.sin(2.0 * math.pi * dow / 7.0), 6)
        cos_dow = round(math.cos(2.0 * math.pi * dow / 7.0), 6)

        # 2. Festival check
        fest_name = FESTIVAL_CALENDAR.get((year, month, day))
        is_fest = fest_name is not None

        # 3. Mandi holiday check (Sundays + National Gazetted + Major Festivals)
        is_sunday = dow == 6
        is_gazetted = (month, day) in GAZETTED_NATIONAL_HOLIDAYS
        is_mandi_holiday = is_sunday or is_gazetted or is_fest

        # 4. Harvest Season determination
        # Kharif Harvest: Sep 15 to Nov 30 (doy ~258 to 334)
        # Rabi Harvest: Mar 15 to May 15 (doy ~74 to 135)
        # Zaid Harvest: May 16 to Jun 30 (doy ~136 to 181)
        if (month == 9 and day >= 15) or month in (10, 11):
            is_harvest = True
            season_name = "Kharif Harvest"
        elif (month == 3 and day >= 15) or month == 4 or (month == 5 and day <= 15):
            is_harvest = True
            season_name = "Rabi Harvest"
        elif (month == 5 and day > 15) or month == 6:
            is_harvest = True
            season_name = "Zaid Harvest"
        else:
            is_harvest = False
            season_name = None

        return CalendarFeatures(
            target_date=d,
            is_festival=is_fest,
            festival_name=fest_name,
            is_mandi_holiday=is_mandi_holiday,
            is_harvest_season=is_harvest,
            season_name=season_name,
            sin_day_of_year=sin_doy,
            cos_day_of_year=cos_doy,
            sin_day_of_week=sin_dow,
            cos_day_of_week=cos_dow,
        )
