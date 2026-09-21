from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.prices.lgd import state_lgd_code

_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


class FeedError(Exception):
    """The upstream price feed could not be read."""


class QuoteRejected(Exception):
    """One source row cannot be stored."""


class MandiQuote:
    def __init__(
        self,
        *,
        state: str,
        district: str,
        market: str,
        commodity: str,
        variety: str,
        grade: str,
        arrival_date: date,
        min_price: int,
        max_price: int,
        modal_price: int,
        state_lgd_code: str | None,
        commodity_group: str | None,
    ) -> None:
        self.state = state
        self.district = district
        self.market = market
        self.commodity = commodity
        self.variety = variety
        self.grade = grade
        self.arrival_date = arrival_date
        self.min_price = min_price
        self.max_price = max_price
        self.modal_price = modal_price
        self.state_lgd_code = state_lgd_code
        self.commodity_group = commodity_group


def _fields(record: dict) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in record.items():
        if value is None:
            continue
        token = " ".join(str(key).casefold().replace("_", " ").split())
        normalized[token] = str(value).strip()
    return normalized


def _take(fields: dict[str, str], *names: str) -> str:
    for name in names:
        token = " ".join(name.casefold().replace("_", " ").split())
        if fields.get(token):
            return fields[token]
    return ""


def _price(value: str) -> int:
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise QuoteRejected("price is not a number") from exc
    if number < 0 or number != number.to_integral_value():
        raise QuoteRejected("price must be a non-negative whole rupee amount")
    return int(number)


def _arrival_date(value: str) -> date:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise QuoteRejected("arrival date is not recognized")


def parse_quote(record: dict) -> MandiQuote:
    fields = _fields(record)
    state = _take(fields, "state")
    district = _take(fields, "district")
    market = _take(fields, "market")
    commodity = _take(fields, "commodity")
    variety = _take(fields, "variety")
    grade = _take(fields, "grade")
    group = _take(fields, "commodity group", "group") or None
    if not state or not district or not market or not commodity:
        raise QuoteRejected("state, district, market, and commodity are required")
    if max(len(state), len(district), len(market), len(commodity), len(variety)) > 128:
        raise QuoteRejected("a name is longer than 128 characters")
    if len(grade) > 64:
        raise QuoteRejected("grade is longer than 64 characters")
    return MandiQuote(
        state=state,
        district=district,
        market=market,
        commodity=commodity,
        variety=variety,
        grade=grade,
        arrival_date=_arrival_date(_take(fields, "arrival date")),
        min_price=_price(_take(fields, "min price")),
        max_price=_price(_take(fields, "max price")),
        modal_price=_price(_take(fields, "modal price")),
        state_lgd_code=state_lgd_code(state),
        commodity_group=group,
    )


class MandiFeed:
    def __init__(self, api_key: str, resource_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = api_key
        self.resource_url = resource_url
        self._transport = transport

    async def fetch(
        self,
        *,
        state: str | None,
        commodity: str | None,
        max_records: int,
    ) -> list[dict]:
        collected: list[dict] = []
        offset = 0
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            while len(collected) < max_records:
                limit = min(100, max_records - len(collected))
                params: dict[str, str | int] = {
                    "api-key": self.api_key,
                    "format": "json",
                    "offset": offset,
                    "limit": limit,
                }
                if state:
                    params["filters[state.keyword]"] = state
                if commodity:
                    params["filters[commodity]"] = commodity
                try:
                    response = await client.get(self.resource_url, params=params)
                except httpx.HTTPError as exc:
                    raise FeedError("price source request failed") from exc
                if response.status_code >= 400:
                    raise FeedError(f"price source returned {response.status_code}")
                try:
                    body = response.json()
                except ValueError as exc:
                    raise FeedError("price source returned invalid json") from exc
                page = body.get("records") or []
                if not isinstance(page, list):
                    raise FeedError("price source records were not a list")
                collected.extend(item for item in page if isinstance(item, dict))
                offset += len(page)
                if len(page) < limit:
                    break
        return collected[:max_records]
