import React, { useEffect, useState } from "react";
import { fetchComparison } from "./api.js";

const DEFAULT_CUTOFF_HOUR = 12;
const STATUS = { LOADING: "loading", SUCCESS: "success", ERROR: "error" };

export default function App() {
  const [status, setStatus] = useState(STATUS.LOADING);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [cutoffHour, setCutoffHour] = useState(DEFAULT_CUTOFF_HOUR);
  const [appliedCutoff, setAppliedCutoff] = useState(DEFAULT_CUTOFF_HOUR);

  async function loadComparison(hour = appliedCutoff) {
    setStatus(STATUS.LOADING);
    setError(null);
    try {
      const result = await fetchComparison(hour);
      setData(result);
      setAppliedCutoff(hour);
      setStatus(STATUS.SUCCESS);
    } catch (err) {
      setError(err.message || "The comparison could not be loaded.");
      setStatus(STATUS.ERROR);
    }
  }

  useEffect(() => {
    loadComparison(DEFAULT_CUTOFF_HOUR);
    // Load once when the dashboard opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const periods = data?.periods ?? [];
  const summary = data?.summary;

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Wind Desk home">
          <span className="brand-mark" aria-hidden="true">W</span>
          <span>Wind Desk</span>
        </a>
        <span className="topbar-context">National wind · January 2026</span>
      </header>

      <div className="dashboard" id="top">
        <section className="page-heading">
          <div>
            <p className="eyebrow">DAY-AHEAD FORECAST REVIEW</p>
            <h1>Wind forecast performance</h1>
            <p className="intro">
              Compare the wind forecast available before delivery with the generation that was recorded.
            </p>
          </div>
          <div className="data-source"><span className="live-dot" /> Elexon data</div>
        </section>

        <section className="controls-panel" aria-label="Analysis settings">
          <div className="control-copy">
            <label htmlFor="cutoff-hour">Forecast decision cut-off</label>
            <p>Choose the latest time a forecast could have been published on the day before delivery.</p>
          </div>
          <div className="control-actions">
            <div className="time-input-wrap">
              <input
                id="cutoff-hour"
                type="number"
                min="0"
                max="23"
                step="1"
                value={cutoffHour}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (event.target.value === "") setCutoffHour("");
                  else setCutoffHour(Math.min(23, Math.max(0, Math.trunc(value))));
                }}
                aria-describedby="cutoff-timezone"
              />
              <span id="cutoff-timezone">:00 UTC</span>
            </div>
            <button
              className="button button-primary"
              onClick={() => {
                const hour = cutoffHour === "" ? DEFAULT_CUTOFF_HOUR : cutoffHour;
                setCutoffHour(hour);
                loadComparison(hour);
              }}
              disabled={status === STATUS.LOADING}
            >
              {status === STATUS.LOADING ? "Updating…" : "Update view"}
            </button>
          </div>
          <p className="assumption-note">
            Pilot assumption: this cut-off is not specified in the assignment. Change it to explore other timings.
          </p>
        </section>

        {status === STATUS.LOADING && <LoadingState />}
        {status === STATUS.ERROR && <ErrorState message={error} onRetry={() => loadComparison()} />}
        {status === STATUS.SUCCESS && summary && (
          <>
            <section className="summary-grid" aria-label="Forecast accuracy summary">
              <MetricCard
                label="Mean absolute error"
                value={summary.mae_mw === null ? "—" : `${formatNumber(summary.mae_mw)} MW`}
                detail="Typical difference between forecast and actual"
              />
              <MetricCard
                label="Forecast bias"
                value={summary.bias_mw === null ? "—" : `${summary.bias_mw > 0 ? "+" : ""}${formatNumber(summary.bias_mw)} MW`}
                detail={summary.bias_mw === null ? "Not enough matched periods" : summary.bias_mw > 0 ? "Forecasts were higher on average" : "Forecasts were lower on average"}
              />
              <MetricCard
                label="Periods compared"
                value={`${formatNumber(summary.matched_periods)} / ${formatNumber(summary.total_periods)}`}
                detail="Hourly delivery periods with both values"
              />
              <MetricCard
                label="Data issues"
                value={formatNumber(summary.missing_actual_count + summary.actual_conflict_count + summary.missing_forecast_count + summary.forecast_conflict_count)}
                detail="Missing or conflicting source records"
              />
            </section>

            <section className="panel chart-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">JANUARY OVERVIEW</p>
                  <h2>Forecast and actual generation</h2>
                </div>
                <div className="legend" aria-label="Chart legend">
                  <span><i className="legend-line actual-line" /> Actual</span>
                  <span><i className="legend-line forecast-line" /> Forecast</span>
                </div>
              </div>
              {periods.length > 0 ? <TrendChart periods={periods} /> : <p className="empty-state">No hourly periods were returned.</p>}
              <div className="chart-footnote">
                Each hourly forecast is compared with the average of its two half-hour actual values. Times are UTC.
              </div>
            </section>

            <section className="panel table-panel">
              <div className="panel-heading table-heading">
                <div>
                  <p className="eyebrow">PERIOD DETAILS</p>
                  <h2>Hourly comparison</h2>
                </div>
                <button className="button button-secondary" onClick={() => loadComparison()} disabled={status === STATUS.LOADING}>
                  Refresh data
                </button>
              </div>
              <p className="table-intro">Forecast values use the latest publication available by {formatHour(appliedCutoff)} UTC on the previous day.</p>
              <div className="table-scroll" role="region" aria-label="Hourly forecast and actual data" tabIndex="0">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Delivery hour (UTC)</th>
                      <th scope="col">Forecast (MW)</th>
                      <th scope="col">Forecast published (UTC)</th>
                      <th scope="col">Actual average (MW)</th>
                      <th scope="col">Forecast error (MW)</th>
                      <th scope="col">Data status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {periods.map((period) => (
                      <tr key={period.hour_start}>
                        <td className="delivery-cell">{formatDelivery(period.hour_start)}</td>
                        <td>{formatValue(period.forecast_mw)}</td>
                        <td>{formatTimestamp(period.forecast_publish_time)}</td>
                        <td>{formatValue(period.actual_mw)}</td>
                        <td className={period.signed_error_mw > 0 ? "error-positive" : period.signed_error_mw < 0 ? "error-negative" : ""}>
                          {formatValue(period.signed_error_mw)}
                        </td>
                        <td><StatusBadge period={period} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <footer className="page-footer">
              <span>Source: Elexon FUELHH and WINDFOR</span>
              <span>{data.cutoff_rule}</span>
            </footer>
          </>
        )}
      </div>
    </main>
  );
}

function MetricCard({ label, value, detail }) {
  return (
    <article className="metric-card">
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      <p className="metric-detail">{detail}</p>
    </article>
  );
}

function LoadingState() {
  return <div className="state-card" role="status"><span className="spinner" /> Loading January comparison data…</div>;
}

function ErrorState({ message, onRetry }) {
  return (
    <div role="alert" className="state-card error-state">
      <div><h2>We couldn’t load the comparison</h2><p>{message}</p></div>
      <button className="button button-primary" onClick={onRetry}>Try again</button>
    </div>
  );
}

function StatusBadge({ period }) {
  if (period.actual_status === "conflict" || period.forecast_status === "conflict") {
    return <span className="status-badge status-warning">Conflicting data</span>;
  }
  if (period.actual_status !== "ok" || period.forecast_status !== "ok") {
    return <span className="status-badge status-muted">Incomplete</span>;
  }
  return <span className="status-badge status-good">Matched</span>;
}

function TrendChart({ periods }) {
  const width = 1000;
  const height = 340;
  const margin = { top: 18, right: 18, bottom: 42, left: 64 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const values = periods.flatMap((p) => [p.actual_mw, p.forecast_mw]).filter(Number.isFinite);
  if (!values.length) return <p className="empty-state">No matched generation values are available to chart.</p>;
  const minValue = Math.floor(Math.min(...values) / 5000) * 5000;
  const maxValue = Math.ceil(Math.max(...values) / 5000) * 5000;
  const range = Math.max(maxValue - minValue, 1);
  const x = (index) => margin.left + (index / Math.max(periods.length - 1, 1)) * plotWidth;
  const y = (value) => margin.top + ((maxValue - value) / range) * plotHeight;
  const linePath = (field) => {
    let drawing = false;
    return periods.map((period, index) => {
      const value = period[field];
      if (!Number.isFinite(value)) { drawing = false; return ""; }
      const command = `${drawing ? "L" : "M"}${x(index).toFixed(2)},${y(value).toFixed(2)}`;
      drawing = true;
      return command;
    }).join(" ");
  };
  const yTicks = 4;
  const dateTicks = [0, 96, 216, 336, 456, 576, 720].filter((i) => i < periods.length);

  return (
    <div className="chart-wrap">
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Hourly wind generation forecast and actual values for January 2026">
        <title>Wind forecast and actual generation in megawatts, by delivery hour in January 2026</title>
        {Array.from({ length: yTicks + 1 }, (_, i) => {
          const value = minValue + (range * i) / yTicks;
          const yy = y(value);
          return <g key={i}>
            <line x1={margin.left} x2={width - margin.right} y1={yy} y2={yy} className="grid-line" />
            <text x={margin.left - 10} y={yy + 4} textAnchor="end" className="axis-label">{`${Math.round(value / 1000)}k`}</text>
          </g>;
        })}
        {dateTicks.map((index) => (
          <g key={index}>
            <line x1={x(index)} x2={x(index)} y1={margin.top} y2={height - margin.bottom} className="grid-line grid-vertical" />
            <text x={x(index)} y={height - 14} textAnchor="middle" className="axis-label">{new Date(periods[index].hour_start).toLocaleDateString("en-GB", { timeZone: "UTC", day: "2-digit", month: "short" })}</text>
          </g>
        ))}
        <path d={linePath("actual_mw")} className="chart-path actual-path" />
        <path d={linePath("forecast_mw")} className="chart-path forecast-path" />
      </svg>
    </div>
  );
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(value);
}

function formatValue(value) {
  return Number.isFinite(value) ? formatNumber(value) : "—";
}

function formatHour(hour) {
  return `${String(hour).padStart(2, "0")}:00`;
}

function formatDelivery(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-GB", {
    timeZone: "UTC", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
}

function formatTimestamp(value) {
  return value ? new Date(value).toLocaleString("en-GB", {
    timeZone: "UTC", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }) : "—";
}
