from dataclasses import dataclass
from typing import Protocol

from app.prices.feed import MandiQuote, QuoteRejected, parse_quote


@dataclass(frozen=True)
class IngestCounts:
    fetched: int
    stored: int
    skipped: int


class PriceSink(Protocol):
    async def upsert_market(
        self,
        *,
        state_name: str,
        state_lgd_code: str | None,
        district_name: str,
        market_name: str,
    ) -> int: ...

    async def upsert_commodity(self, *, name: str, group_name: str | None) -> int: ...

    async def upsert_observation(
        self,
        *,
        arrival_date,
        market_id: int,
        commodity_id: int,
        variety: str,
        grade: str,
        min_price: int,
        max_price: int,
        modal_price: int,
    ) -> None: ...


async def store_quotes(records: list[dict], sink: PriceSink) -> IngestCounts:
    stored = 0
    skipped = 0
    for record in records:
        try:
            quote = parse_quote(record)
        except QuoteRejected:
            skipped += 1
            continue
        await _store_quote(sink, quote)
        stored += 1
    return IngestCounts(fetched=len(records), stored=stored, skipped=skipped)


async def _store_quote(sink: PriceSink, quote: MandiQuote) -> None:
    market_id = await sink.upsert_market(
        state_name=quote.state,
        state_lgd_code=quote.state_lgd_code,
        district_name=quote.district,
        market_name=quote.market,
    )
    commodity_id = await sink.upsert_commodity(name=quote.commodity, group_name=quote.commodity_group)
    await sink.upsert_observation(
        arrival_date=quote.arrival_date,
        market_id=market_id,
        commodity_id=commodity_id,
        variety=quote.variety,
        grade=quote.grade,
        min_price=quote.min_price,
        max_price=quote.max_price,
        modal_price=quote.modal_price,
    )
