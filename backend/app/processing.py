"""
Matching and error calculation.

Rules implemented here (see README for the full writeup):

1. Actuals (FUELHH, half-hourly) are averaged into hourly values: each hourly
   forecast is compared with the average of the two half-hour actuals that
   fall inside that hour (HH:00 and HH:30).
2. For each hourly delivery period, the forecast used is the latest WINDFOR
   version published at or before a cut-off of 12:00 UTC on the previous
   calendar day (see config.DECISION_CUTOFF_HOUR_UTC - a labeled pilot
   assumption, not a fact from the assignment).
3. Missing or duplicate/conflicting records are never silently treated as
   zero or arbitrarily resolved. They are recorded with an explicit status
   and excluded from the metrics, and the counts are surfaced in the summary.
4. signed_error = forecast - actual; abs_error = |signed_error|; MAE = mean
   abs_error over matched periods; bias = mean signed_error over matched
   periods.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

UTC = timezone.utc


@dataclass
class PeriodResult:
    hour_start: datetime
    actual_mw: float | None
    forecast_mw: float | None
    forecast_publish_time: datetime | None
    signed_error_mw: float | None
    abs_error_mw: float | None
    actual_status: str
    forecast_status: str


@dataclass
class ComparisonResult:
    periods: list[PeriodResult] = field(default_factory=list)

    @property
    def matched(self) -> list[PeriodResult]:
        return [p for p in self.periods if p.signed_error_mw is not None]

    def summary(self) -> dict:
        matched = self.matched
        matched_count = len(matched)
        mae = sum(p.abs_error_mw for p in matched) / matched_count if matched_count else None
        bias = sum(p.signed_error_mw for p in matched) / matched_count if matched_count else None

        def count(status_field: str, status: str) -> int:
            return sum(1 for p in self.periods if getattr(p, status_field) == status)

        return {
            "total_periods": len(self.periods),
            "matched_periods": matched_count,
            "mae_mw": mae,
            "bias_mw": bias,
            "missing_actual_count": count("actual_status", "missing"),
            "actual_conflict_count": count("actual_status", "conflict"),
            "missing_forecast_count": count("forecast_status", "missing"),
            "forecast_conflict_count": count("forecast_status", "conflict"),
            "unit": "MW",
        }


def _parse_timestamp(value: str) -> datetime:
    # Elexon timestamps are ISO-8601 UTC, e.g. "2026-01-01T00:00:00Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _group_actuals_by_half_hour(rows: list[dict]) -> dict[datetime, list[float]]:
    """Group FUELHH rows by their half-hour startTime. Keeps every value seen
    (including duplicates) so callers can detect conflicts explicitly."""
    grouped: dict[datetime, list[float]] = {}
    for row in rows:
        if row.get("startTime") is None or row.get("generation") is None:
            continue
        start = _parse_timestamp(row["startTime"])
        grouped.setdefault(start, []).append(row["generation"])
    return grouped


def _group_forecasts_by_hour(rows: list[dict]) -> dict[datetime, list[tuple[datetime, float]]]:
    """Group WINDFOR rows by their (hourly) startTime, keeping every
    (publishTime, generation) version so callers can apply the cut-off rule."""
    grouped: dict[datetime, list[tuple[datetime, float]]] = {}
    for row in rows:
        if row.get("startTime") is None or row.get("publishTime") is None or row.get("generation") is None:
            continue
        start = _parse_timestamp(row["startTime"])
        publish_time = _parse_timestamp(row["publishTime"])
        grouped.setdefault(start, []).append((publish_time, row["generation"]))
    return grouped


def _resolve_half_hour_value(values: list[float] | None) -> tuple[float | None, str]:
    """Return (value, status) for one half-hour slot of actual generation.

    status is one of: "missing" (no record), "conflict" (more than one
    record with different values - cannot resolve without a documented
    update/versioning rule from the source), or "ok".
    """
    if not values:
        return None, "missing"
    distinct = set(values)
    if len(distinct) > 1:
        return None, "conflict"
    return values[0], "ok"


def _resolve_hourly_actual(
    hour_start: datetime, half_hourly: dict[datetime, list[float]]
) -> tuple[float | None, str]:
    first_value, first_status = _resolve_half_hour_value(half_hourly.get(hour_start))
    second_slot = hour_start + timedelta(minutes=30)
    second_value, second_status = _resolve_half_hour_value(half_hourly.get(second_slot))

    if first_status == "conflict" or second_status == "conflict":
        return None, "conflict"
    if first_status == "missing" or second_status == "missing":
        return None, "missing"
    return (first_value + second_value) / 2, "ok"


def _resolve_forecast(
    hour_start: datetime,
    forecasts_by_hour: dict[datetime, list[tuple[datetime, float]]],
    cutoff: datetime,
) -> tuple[float | None, datetime | None, str]:
    versions = forecasts_by_hour.get(hour_start, [])
    eligible = [(publish_time, value) for publish_time, value in versions if publish_time <= cutoff]
    if not eligible:
        return None, None, "missing"

    latest_publish_time = max(publish_time for publish_time, _ in eligible)
    latest_values = {value for publish_time, value in eligible if publish_time == latest_publish_time}
    if len(latest_values) > 1:
        # Same publishTime, different generation values - an unresolvable duplicate.
        return None, latest_publish_time, "conflict"

    return next(iter(latest_values)), latest_publish_time, "ok"


def build_comparison(
    actual_rows: list[dict],
    forecast_rows: list[dict],
    start_date: date,
    end_date: date,
    cutoff_hour_utc: int,
) -> ComparisonResult:
    half_hourly_actuals = _group_actuals_by_half_hour(actual_rows)
    forecasts_by_hour = _group_forecasts_by_hour(forecast_rows)

    result = ComparisonResult()

    current_hour = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    while current_hour < end_exclusive:
        delivery_day = current_hour.date()
        cutoff = datetime.combine(
            delivery_day - timedelta(days=1), datetime.min.time(), tzinfo=UTC
        ) + timedelta(hours=cutoff_hour_utc)

        actual_value, actual_status = _resolve_hourly_actual(current_hour, half_hourly_actuals)
        forecast_value, publish_time, forecast_status = _resolve_forecast(
            current_hour, forecasts_by_hour, cutoff
        )

        signed_error = abs_error = None
        if actual_status == "ok" and forecast_status == "ok":
            signed_error = forecast_value - actual_value
            abs_error = abs(signed_error)

        result.periods.append(
            PeriodResult(
                hour_start=current_hour,
                actual_mw=actual_value,
                forecast_mw=forecast_value,
                forecast_publish_time=publish_time,
                signed_error_mw=signed_error,
                abs_error_mw=abs_error,
                actual_status=actual_status,
                forecast_status=forecast_status,
            )
        )
        current_hour += timedelta(hours=1)

    return result
