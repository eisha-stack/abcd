"""
Thin client for the two Elexon BMRS dataset endpoints this pilot uses.

Confirmed against the published API spec (https://data.elexon.co.uk/swagger/v1/swagger.json):

- GET /datasets/FUELHH
    Half-hourly outturn generation by fuel type. Query with settlementDateFrom/
    settlementDateTo (yyyy-MM-dd) and fuelType (repeatable). Response field
    `generation` is documented as an average MW value over the half hour.
    Rows: dataset, publishTime, startTime, settlementDate, settlementPeriod,
    fuelType, generation.
    The API rejects a settlementDateFrom/To span of more than 7 days
    (inclusive) with a 400, so a full month is fetched in <=7-day chunks.

- GET /datasets/WINDFOR
    Wind generation forecast. Can only be filtered by publishDateTimeFrom/
    publishDateTimeTo (there is no delivery-time filter), so the caller must
    pass a publish-time window that is wide enough to include the forecast
    versions it needs, and filter by startTime itself afterwards.
    Rows: dataset, publishTime, startTime, generation.
    Same 7-day (inclusive) span limit as FUELHH applies to
    publishDateTimeFrom/To, so a full month is fetched in <=7-day chunks.

Both endpoints wrap their rows in {"data": [...]}. No API key is required.
"""
from datetime import date, datetime, timedelta

import httpx

from .config import ELEXON_BASE_URL

REQUEST_TIMEOUT_SECONDS = 30.0

# Both endpoints reject a date/datetime range of more than this many days
# (inclusive), so wider requests are split into chunks of this size.
MAX_DATE_RANGE_SPAN_DAYS = 7


class ElexonApiError(RuntimeError):
    """Raised when the Elexon API request fails or returns something unusable."""


async def fetch_actual_wind_generation(
    client: httpx.AsyncClient, start_date: date, end_date: date
) -> list[dict]:
    """Fetch half-hourly FUELHH rows for fuelType=WIND, settlement dates in [start_date, end_date]."""
    rows: list[dict] = []
    for chunk_start, chunk_end in _iter_date_chunks(start_date, end_date):
        params = {
            "settlementDateFrom": chunk_start.isoformat(),
            "settlementDateTo": chunk_end.isoformat(),
            "fuelType": "WIND",
            "format": "json",
        }
        rows.extend(await _get_rows(client, f"{ELEXON_BASE_URL}/datasets/FUELHH", params))
    return rows


async def fetch_wind_forecasts(
    client: httpx.AsyncClient, publish_from: datetime, publish_to: datetime
) -> list[dict]:
    """Fetch WINDFOR rows published in [publish_from, publish_to] (UTC, inclusive)."""
    rows: list[dict] = []
    for chunk_start, chunk_end in _iter_date_chunks(publish_from, publish_to):
        params = {
            "publishDateTimeFrom": _to_elexon_timestamp(chunk_start),
            "publishDateTimeTo": _to_elexon_timestamp(chunk_end),
            "format": "json",
        }
        rows.extend(await _get_rows(client, f"{ELEXON_BASE_URL}/datasets/WINDFOR", params))
    return rows


def _iter_date_chunks(start, end):
    """Yield (chunk_start, chunk_end) pairs covering [start, end], each spanning
    at most MAX_DATE_RANGE_SPAN_DAYS. Works for both `date` and `datetime`.

    For `date` inputs, chunks are whole days, so the next chunk starts the day
    after the previous one ends - no gap. For `datetime` inputs, the "to"
    boundary is a single instant (not a whole day), so the next chunk must
    start at exactly that same instant to avoid losing everything published
    between it and the next day boundary; the shared instant is fetched by
    both chunks, which produces a harmless exact-duplicate row rather than a
    gap in forecast coverage.
    """
    is_datetime = isinstance(start, datetime)
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=MAX_DATE_RANGE_SPAN_DAYS - 1), end)
        yield chunk_start, chunk_end
        if chunk_end >= end:
            break
        chunk_start = chunk_end if is_datetime else chunk_end + timedelta(days=1)


async def _get_rows(client: httpx.AsyncClient, url: str, params: dict) -> list[dict]:
    try:
        response = await client.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ElexonApiError(f"Request to {url} failed: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise ElexonApiError(f"Response from {url} was not valid JSON: {exc}") from exc

    rows = body.get("data")
    if rows is None:
        raise ElexonApiError(f"Response from {url} had no 'data' field: {body!r}")
    return rows


def _to_elexon_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
