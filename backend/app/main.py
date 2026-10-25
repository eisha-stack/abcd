"""
FastAPI app exposing the forecast-vs-actual comparison for January 2026 UK
wind generation.

This is a pilot/scaffold, not a production service: there is no caching
layer, auth, or persistence yet - every request re-fetches from Elexon.
"""
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .elexon_client import ElexonApiError, fetch_actual_wind_generation, fetch_wind_forecasts
from .processing import build_comparison
from .schemas import ComparisonResponse

app = FastAPI(title="Wind Forecast vs Actual (pilot)")

# Dev-only: the frontend runs on a different origin (Vite dev server).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/comparison", response_model=ComparisonResponse)
async def get_comparison(
    cutoff_hour_utc: int = Query(
        default=config.DECISION_CUTOFF_HOUR_UTC,
        ge=0,
        le=23,
        description=(
            "Pilot assumption: hour (UTC) on the day before delivery by which a "
            "forecast must have been published to count as available. "
            f"Default is {config.DECISION_CUTOFF_HOUR_UTC}:00 UTC."
        ),
    )
) -> ComparisonResponse:
    publish_from = datetime.combine(
        config.ANALYSIS_START_DATE - timedelta(days=config.FORECAST_PUBLISH_LOOKBACK_DAYS),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    publish_to = datetime.combine(config.ANALYSIS_END_DATE, datetime.min.time(), tzinfo=timezone.utc)

    try:
        async with httpx.AsyncClient() as client:
            actual_rows = await fetch_actual_wind_generation(
                client, config.ANALYSIS_START_DATE, config.ANALYSIS_END_DATE
            )
            forecast_rows = await fetch_wind_forecasts(client, publish_from, publish_to)
    except ElexonApiError as exc:
        raise HTTPException(status_code=502, detail=f"Elexon API request failed: {exc}") from exc

    result = build_comparison(
        actual_rows,
        forecast_rows,
        config.ANALYSIS_START_DATE,
        config.ANALYSIS_END_DATE,
        cutoff_hour_utc,
    )

    return ComparisonResponse(
        summary=result.summary(),
        periods=result.periods,
        cutoff_hour_utc=cutoff_hour_utc,
        cutoff_rule=(
            "PILOT ASSUMPTION: latest WINDFOR forecast published at or before "
            f"{cutoff_hour_utc:02d}:00 UTC on the day before delivery. The assignment "
            "does not specify the real decision cut-off."
        ),
    )
