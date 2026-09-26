from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class CommodityQualityStandard:
    standard_id: str
    commodity_label: str
    optimum_moisture: Decimal
    grade_a_moisture_max: Decimal
    grade_a_foreign_matter_max: Decimal
    grade_a_damaged_max: Decimal
    grade_b_moisture_max: Decimal
    grade_b_foreign_matter_max: Decimal
    grade_b_damaged_max: Decimal
    grade_c_moisture_max: Decimal
    grade_c_foreign_matter_max: Decimal
    grade_c_damaged_max: Decimal


COMMODITY_STANDARDS: dict[str, CommodityQualityStandard] = {
    "wheat": CommodityQualityStandard(
        standard_id="AGMARK-WHEAT-2024",
        commodity_label="Wheat (Gehun)",
        optimum_moisture=Decimal("12.0"),
        grade_a_moisture_max=Decimal("12.0"),
        grade_a_foreign_matter_max=Decimal("1.0"),
        grade_a_damaged_max=Decimal("2.0"),
        grade_b_moisture_max=Decimal("14.0"),
        grade_b_foreign_matter_max=Decimal("2.0"),
        grade_b_damaged_max=Decimal("4.0"),
        grade_c_moisture_max=Decimal("15.0"),
        grade_c_foreign_matter_max=Decimal("3.0"),
        grade_c_damaged_max=Decimal("6.0"),
    ),
    "paddy": CommodityQualityStandard(
        standard_id="AGMARK-PADDY-2024",
        commodity_label="Paddy / Rice (Dhan)",
        optimum_moisture=Decimal("13.0"),
        grade_a_moisture_max=Decimal("13.0"),
        grade_a_foreign_matter_max=Decimal("1.0"),
        grade_a_damaged_max=Decimal("2.0"),
        grade_b_moisture_max=Decimal("14.5"),
        grade_b_foreign_matter_max=Decimal("2.0"),
        grade_b_damaged_max=Decimal("4.0"),
        grade_c_moisture_max=Decimal("16.0"),
        grade_c_foreign_matter_max=Decimal("3.5"),
        grade_c_damaged_max=Decimal("6.0"),
    ),
    "onion": CommodityQualityStandard(
        standard_id="AGMARK-ONION-2024",
        commodity_label="Onion (Pyaz)",
        optimum_moisture=Decimal("10.0"),
        grade_a_moisture_max=Decimal("10.0"),
        grade_a_foreign_matter_max=Decimal("1.0"),
        grade_a_damaged_max=Decimal("2.0"),
        grade_b_moisture_max=Decimal("12.0"),
        grade_b_foreign_matter_max=Decimal("2.5"),
        grade_b_damaged_max=Decimal("5.0"),
        grade_c_moisture_max=Decimal("14.0"),
        grade_c_foreign_matter_max=Decimal("4.0"),
        grade_c_damaged_max=Decimal("10.0"),
    ),
    "maize": CommodityQualityStandard(
        standard_id="AGMARK-MAIZE-2024",
        commodity_label="Maize / Corn (Makka)",
        optimum_moisture=Decimal("12.0"),
        grade_a_moisture_max=Decimal("12.0"),
        grade_a_foreign_matter_max=Decimal("1.5"),
        grade_a_damaged_max=Decimal("2.5"),
        grade_b_moisture_max=Decimal("14.0"),
        grade_b_foreign_matter_max=Decimal("2.5"),
        grade_b_damaged_max=Decimal("5.0"),
        grade_c_moisture_max=Decimal("15.0"),
        grade_c_foreign_matter_max=Decimal("4.0"),
        grade_c_damaged_max=Decimal("8.0"),
    ),
    "pulses": CommodityQualityStandard(
        standard_id="AGMARK-PULSES-2024",
        commodity_label="Pulses / Chana / Tur",
        optimum_moisture=Decimal("10.0"),
        grade_a_moisture_max=Decimal("10.0"),
        grade_a_foreign_matter_max=Decimal("1.0"),
        grade_a_damaged_max=Decimal("2.0"),
        grade_b_moisture_max=Decimal("12.0"),
        grade_b_foreign_matter_max=Decimal("2.0"),
        grade_b_damaged_max=Decimal("4.0"),
        grade_c_moisture_max=Decimal("14.0"),
        grade_c_foreign_matter_max=Decimal("3.5"),
        grade_c_damaged_max=Decimal("7.0"),
    ),
    "oilseeds": CommodityQualityStandard(
        standard_id="AGMARK-OILSEEDS-2024",
        commodity_label="Oilseeds / Soybean / Mustard",
        optimum_moisture=Decimal("10.0"),
        grade_a_moisture_max=Decimal("10.0"),
        grade_a_foreign_matter_max=Decimal("1.0"),
        grade_a_damaged_max=Decimal("2.0"),
        grade_b_moisture_max=Decimal("12.0"),
        grade_b_foreign_matter_max=Decimal("2.0"),
        grade_b_damaged_max=Decimal("4.0"),
        grade_c_moisture_max=Decimal("14.0"),
        grade_c_foreign_matter_max=Decimal("3.5"),
        grade_c_damaged_max=Decimal("7.0"),
    ),
    "general": CommodityQualityStandard(
        standard_id="AGMARK-GENERAL-2024",
        commodity_label="General Agricultural Produce",
        optimum_moisture=Decimal("12.0"),
        grade_a_moisture_max=Decimal("12.0"),
        grade_a_foreign_matter_max=Decimal("1.5"),
        grade_a_damaged_max=Decimal("3.0"),
        grade_b_moisture_max=Decimal("14.0"),
        grade_b_foreign_matter_max=Decimal("3.0"),
        grade_b_damaged_max=Decimal("6.0"),
        grade_c_moisture_max=Decimal("16.0"),
        grade_c_foreign_matter_max=Decimal("5.0"),
        grade_c_damaged_max=Decimal("10.0"),
    ),
}

COMMODITY_ALIASES: dict[str, str] = {
    "wheat": "wheat",
    "gehun": "wheat",
    "gehu": "wheat",
    "atta": "wheat",
    "paddy": "paddy",
    "rice": "paddy",
    "dhan": "paddy",
    "chawal": "paddy",
    "basmati": "paddy",
    "onion": "onion",
    "pyaz": "onion",
    "kanda": "onion",
    "maize": "maize",
    "corn": "maize",
    "makka": "maize",
    "chana": "pulses",
    "gram": "pulses",
    "bengal gram": "pulses",
    "tur": "pulses",
    "toor": "pulses",
    "arhar": "pulses",
    "moong": "pulses",
    "mung": "pulses",
    "urad": "pulses",
    "pulses": "pulses",
    "lentil": "pulses",
    "dal": "pulses",
    "soybean": "oilseeds",
    "soya": "oilseeds",
    "mustard": "oilseeds",
    "sarson": "oilseeds",
    "groundnut": "oilseeds",
    "peanut": "oilseeds",
    "mungfali": "oilseeds",
}


@dataclass
class GradingResult:
    commodity: str
    grade: str
    is_faq: bool
    quality_score: Decimal
    defect_breakdown: list[str] = field(default_factory=list)
    standard_used: str = ""


def resolve_standard(commodity: str) -> CommodityQualityStandard:
    normalized = commodity.strip().casefold()
    key = COMMODITY_ALIASES.get(normalized, "general")
    return COMMODITY_STANDARDS.get(key, COMMODITY_STANDARDS["general"])


def evaluate_crop_quality(
    commodity: str,
    foreign_matter_percent: Decimal | None = None,
    moisture_percent: Decimal | None = None,
    damaged_percent: Decimal | None = None,
    immature_percent: Decimal | None = None,
    weevilled_percent: Decimal | None = None,
) -> GradingResult:
    """Evaluates crop quality and assigns AGMARK / e-NAM certified quality grades."""
    standard = resolve_standard(commodity)

    fm = foreign_matter_percent if foreign_matter_percent is not None else Decimal(0)
    moist = moisture_percent if moisture_percent is not None else standard.optimum_moisture
    dam = damaged_percent if damaged_percent is not None else Decimal(0)
    imm = immature_percent if immature_percent is not None else Decimal(0)
    weev = weevilled_percent if weevilled_percent is not None else Decimal(0)

    breakdown: list[str] = []

    # 1. Parameter checks and breakdown diagnostics
    if moist <= standard.grade_a_moisture_max:
        breakdown.append(
            f"Moisture: {moist}% meets optimum Grade-A tolerance (<= {standard.grade_a_moisture_max}%)."
        )
    elif moist <= standard.grade_b_moisture_max:
        breakdown.append(
            f"Moisture: {moist}% exceeds Grade-A limit but meets FAQ Grade-B tolerance (<= {standard.grade_b_moisture_max}%)."
        )
    elif moist <= standard.grade_c_moisture_max:
        breakdown.append(
            f"Moisture: {moist}% exceeds FAQ limits but meets non-FAQ Grade-II allowance (<= {standard.grade_c_moisture_max}%)."
        )
    else:
        breakdown.append(
            f"Moisture: {moist}% exceeds maximum permissible threshold ({standard.grade_c_moisture_max}%). Spoilage risk."
        )

    if fm <= standard.grade_a_foreign_matter_max:
        breakdown.append(
            f"Foreign Matter: {fm}% meets clean Grade-A tolerance (<= {standard.grade_a_foreign_matter_max}%)."
        )
    elif fm <= standard.grade_b_foreign_matter_max:
        breakdown.append(
            f"Foreign Matter: {fm}% exceeds Grade-A limit but meets FAQ Grade-B tolerance (<= {standard.grade_b_foreign_matter_max}%)."
        )
    elif fm <= standard.grade_c_foreign_matter_max:
        breakdown.append(
            f"Foreign Matter: {fm}% exceeds FAQ limits but meets Grade-II allowance (<= {standard.grade_c_foreign_matter_max}%)."
        )
    else:
        breakdown.append(
            f"Foreign Matter: {fm}% exceeds maximum permissible allowance ({standard.grade_c_foreign_matter_max}%)."
        )

    if dam <= standard.grade_a_damaged_max:
        breakdown.append(
            f"Damaged / Insect kernels: {dam}% meets Grade-A tolerance (<= {standard.grade_a_damaged_max}%)."
        )
    elif dam <= standard.grade_b_damaged_max:
        breakdown.append(
            f"Damaged / Insect kernels: {dam}% exceeds Grade-A limit but meets FAQ Grade-B tolerance (<= {standard.grade_b_damaged_max}%)."
        )
    elif dam <= standard.grade_c_damaged_max:
        breakdown.append(
            f"Damaged / Insect kernels: {dam}% exceeds FAQ limits but meets Grade-II allowance (<= {standard.grade_c_damaged_max}%)."
        )
    else:
        breakdown.append(
            f"Damaged / Insect kernels: {dam}% exceeds acceptable market limit ({standard.grade_c_damaged_max}%)."
        )

    if immature_percent is not None:
        breakdown.append(f"Immature / Shriveled kernels: {imm}%.")
    if weevilled_percent is not None:
        breakdown.append(f"Weevil infested kernels: {weev}%.")

    # 2. Defect Penalty and Quality Score Calculation (0-100)
    penalty = Decimal(0)
    if moist > standard.optimum_moisture:
        penalty += (moist - standard.optimum_moisture) * Decimal("2.0")
    penalty += fm * Decimal("4.0")
    penalty += dam * Decimal("3.0")
    if imm > 0:
        penalty += imm * Decimal("1.5")
    if weev > 0:
        penalty += weev * Decimal("5.0")

    raw_score = max(Decimal("0.00"), min(Decimal("100.00"), Decimal("100.00") - penalty))
    quality_score = raw_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 3. Grade assignment based on AGMARK boundary criteria
    passes_a = (
        moist <= standard.grade_a_moisture_max
        and fm <= standard.grade_a_foreign_matter_max
        and dam <= standard.grade_a_damaged_max
        and imm <= Decimal("3.0")
        and weev <= Decimal("1.0")
    )

    passes_b = (
        moist <= standard.grade_b_moisture_max
        and fm <= standard.grade_b_foreign_matter_max
        and dam <= standard.grade_b_damaged_max
        and imm <= Decimal("6.0")
        and weev <= Decimal("3.0")
    )

    passes_c = (
        moist <= standard.grade_c_moisture_max
        and fm <= standard.grade_c_foreign_matter_max
        and dam <= standard.grade_c_damaged_max
        and imm <= Decimal("10.0")
        and weev <= Decimal("5.0")
    )

    if passes_a and quality_score >= Decimal("80.00"):
        grade = "FAQ-Grade-A"
        is_faq = True
        breakdown.append("Certified Fair Average Quality (FAQ) Grade-A produce under AGMARK/e-NAM standard.")
    elif passes_b and quality_score >= Decimal("65.00"):
        grade = "FAQ-Grade-B"
        is_faq = True
        breakdown.append("Certified Fair Average Quality (FAQ) Grade-B produce under AGMARK/e-NAM standard.")
    elif passes_c and quality_score >= Decimal("35.00"):
        grade = "Grade-II"
        is_faq = False
        breakdown.append("Graded as Grade-II commercial quality (Non-FAQ). Subject to buyer discount.")
    else:
        grade = "Reject"
        is_faq = False
        breakdown.append("Lot rejected: does not satisfy minimum statutory market trading parameters.")

    return GradingResult(
        commodity=commodity,
        grade=grade,
        is_faq=is_faq,
        quality_score=quality_score,
        defect_breakdown=breakdown,
        standard_used=standard.standard_id,
    )
