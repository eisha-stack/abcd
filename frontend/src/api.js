// API base URL for the Python backend. Override with VITE_API_BASE_URL at
// build/run time (see docker-compose.yml) - defaults to the local dev server.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchComparison(cutoffHour = 12) {
  const query = new URLSearchParams({ cutoff_hour_utc: String(cutoffHour) });
  const response = await fetch(`${API_BASE_URL}/api/comparison?${query}`);
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Backend request failed (${response.status}): ${body || response.statusText}`);
  }
  return response.json();
}
