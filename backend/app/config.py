"""
Configuration and pilot assumptions for the wind forecast vs. actual comparison.

Everything that is an *assumption* rather than a fact from the assignment or
the Elexon API is isolated here and clearly labeled, so it is easy to find
and change without touching the data-loading or matching logic.
"""
import os
from datetime import date
ELEXON_BASE_URL = os.environ.get("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
ANALYSIS_START_DATE = date(2026, 1, 1)
ANALYSIS_END_DATE = date(2026, 1, 31)
DECISION_CUTOFF_HOUR_UTC = int(os.environ.get("DECISION_CUTOFF_HOUR_UTC", "12"))
FORECAST_PUBLISH_LOOKBACK_DAYS = 3
