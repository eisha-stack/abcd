# Wind Forecast vs Actual (pilot scaffold)

Compares Elexon's day-ahead UK wind generation forecast (WINDFOR) against
actual wind generation (FUELHH, `fuelType=WIND`) for January 2026.

**Status: pilot implementation, not production-ready.** The backend fetches
real data from Elexon and computes the comparison. The frontend shows accuracy
summary cards, a monthly forecast-versus-actual chart, an hourly detail table,
data-quality status, and a control for changing the forecast cut-off.

## Pilot assumption: decision cut-off

The assignment does not specify the exact decision cut-off, so this scaffold
assumes: **a forecast counts as "available" for a delivery hour only if it
was published by 12:00 UTC on the calendar day before delivery.** When more
than one forecast was published before that cut-off, the latest one is used.

This is one constant, clearly labeled, and easy to change:

- `backend/app/config.py` -> `DECISION_CUTOFF_HOUR_UTC`
- or per-request: `GET /api/comparison?cutoff_hour_utc=6`

The API response also echoes the active rule back in `cutoff_rule` so it's
never ambiguous which assumption produced a given result.

## Data and matching rules

- Actuals: Elexon `FUELHH`, filtered to `fuelType=WIND`, half-hourly.
- Forecasts: Elexon `WINDFOR`, hourly.
- Each hourly forecast is compared with the **average of the two half-hour
  actuals** inside that hour (`HH:00` and `HH:30`).
- `signed_error = forecast - actual`, `abs_error = |signed_error|`.
- `MAE` = mean `abs_error` over matched periods. `bias` = mean `signed_error`
  over matched periods.
- **Missing or conflicting data is never silently treated as zero.** If a
  half-hour actual is missing, or two actual records exist for the same
  half-hour with different values, or no forecast was published by the
  cut-off, or two forecast records share the same (latest) publish time with
  different values, that period is excluded from the metrics and counted
  separately in the summary (`missing_actual_count`, `actual_conflict_count`,
  `missing_forecast_count`, `forecast_conflict_count`).
- Units are reported as `MW`, per Elexon's FUELHH documentation ("average MW
  values over 30 minutes"). WINDFOR's unit is assumed to match; this has not
  been independently re-verified against NGESO source documentation.

No API key is needed - both endpoints are public. Confirmed against the
published spec: https://data.elexon.co.uk/swagger/v1/swagger.json

## Project structure

```
backend/            Python (FastAPI) backend
  app/
    config.py        Pilot assumptions / constants (cut-off, date range)
    elexon_client.py  Elexon HTTP calls (FUELHH, WINDFOR)
    processing.py     Matching, missing/duplicate handling, metrics
    schemas.py        API response models
    main.py           FastAPI app and the /api/comparison endpoint
  requirements.txt
  Dockerfile

frontend/           React (Vite) frontend
  src/
    api.js            Fetch call to the backend
    App.jsx            Loading / error / results-placeholder states
  Dockerfile

docker-compose.yml   Runs both services together
```

## Running it

### Option A: Docker

```
docker compose up --build
```

- Backend: http://localhost:8000/api/comparison
- Frontend: http://localhost:5173

### Option B: manually

Backend:

```
cd backend
python -m venv .venv
.venv\Scripts\activate   # (or `source .venv/bin/activate` on macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (separate terminal):

```
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

## Known limitations / next steps

- No caching: every request to `/api/comparison` re-fetches from Elexon,
  which is slow and unnecessary for a fixed historical month.
- No chart, period table, or cut-off picker in the UI yet - only a summary
  placeholder.
- No automated tests.
- Not deployed anywhere yet (Docker/local only).

## AI tool disclosure

The initial scaffold, folder structure, Elexon integration, and matching logic
were created with the assistance of Claude Code. The dashboard chart, details
table, and cut-off controls were added with the assistance of OpenAI Codex.
