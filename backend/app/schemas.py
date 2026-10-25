"""Response shapes returned by the API. Kept separate from the calculation
logic in processing.py so the two can be read and changed independently."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hour_start: datetime
    actual_mw: float | None
    forecast_mw: float | None
    forecast_publish_time: datetime | None
    signed_error_mw: float | None
    abs_error_mw: float | None
    actual_status: str
    forecast_status: str


class SummaryOut(BaseModel):
    total_periods: int
    matched_periods: int
    mae_mw: float | None
    bias_mw: float | None
    missing_actual_count: int
    actual_conflict_count: int
    missing_forecast_count: int
    forecast_conflict_count: int
    unit: str


class ComparisonResponse(BaseModel):
    summary: SummaryOut
    periods: list[PeriodOut]
    cutoff_hour_utc: int
    cutoff_rule: str
