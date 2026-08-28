# Weather API

A small Python (FastAPI) service that, given a **location name**, queries an
external weather provider ([Open-Meteo](https://open-meteo.com/) — free, no API
key required) and returns the weather through your own clean, normalized API.

```
client ──► your API (/weather, /forecast) ──► FastAPI app
                                                  │
                                                  ├─ 1. Geocoding API  (name → lat/lon)
                                                  └─ 2. Forecast API   (lat/lon → weather)
                                                                          │
                                              normalized JSON ◄───────────┘
```

> New to REST APIs? Read [`docs/REST_API_GUIDE.md`](docs/REST_API_GUIDE.md) — a
> getting-started guide covering HTTP methods, status codes, data formats, and
> every common authorization scheme, with examples from this project.

## Setup

```bash
cd APITutorial
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The server starts at `http://127.0.0.1:8000`. Interactive Swagger docs are
auto-generated at `http://127.0.0.1:8000/docs`.

## How it works (overview)

Neither of the two upstream Open-Meteo endpoints understands place names — they
only take coordinates. So every request runs in **two steps**:

1. **Geocoding** — the location name (e.g. `"London"`) is sent to the Open-Meteo
   geocoding API, which returns the best-matching place with its latitude and
   longitude. If nothing matches, the API responds `404`.
2. **Forecast** — those coordinates are sent to the Open-Meteo forecast API,
   which returns raw weather data. The app then reshapes that raw response into
   a stable, documented JSON structure (mapping numeric WMO `weather_code`
   values to readable descriptions like `"Overcast"`).

All upstream calls are made asynchronously with `httpx` and share a 10-second
timeout. The two-step logic lives in `app/weather_client.py`; the HTTP routes
live in `app/main.py`.

---

## Endpoints

| Method | Path        | Purpose                                            |
|--------|-------------|----------------------------------------------------|
| GET    | `/weather`  | **Current** weather for a location                 |
| GET    | `/forecast` | **Multi-day** daily forecast for a location        |
| POST   | `/users`    | **Register** a new user                            |
| POST   | `/login`    | **Log in**, receive a Bearer access token          |
| GET    | `/me`       | Current user — **protected** by the Bearer token   |
| POST   | `/logout`   | **Invalidate** the caller's Bearer token           |
| GET    | `/health`   | Liveness check                                     |
| GET    | `/docs`     | Interactive Swagger UI (auto-generated)            |

> The `/users`, `/login`, and `/me` endpoints are a **tutorial demo** of POST
> APIs and Bearer-token auth. Users are stored **in memory** (they vanish on
> restart) and passwords are salted + hashed with the standard library — this is
> for learning, not production.

---

### `GET /weather` — current weather

Returns the current conditions for a single location.

**Query parameters**

| Name       | Type   | Required | Default | Notes                          |
|------------|--------|----------|---------|--------------------------------|
| `location` | string | yes      | —       | City or place name, e.g. `London`. Min length 1. |

**How it works**

1. Geocodes `location` → latitude/longitude.
2. Calls the forecast API requesting the `current` block:
   `temperature_2m`, `relative_humidity_2m`, `apparent_temperature`,
   `wind_speed_10m`, `weather_code` (with `timezone=auto` so the returned time
   is local to the place).
3. Normalizes the response and translates `weather_code` → `description`.

**Example request**

```bash
curl "http://127.0.0.1:8000/weather?location=London"
```

**Example response** (`200 OK`)

```json
{
  "location": {
    "name": "London",
    "country": "United Kingdom",
    "admin1": "England",
    "latitude": 51.50853,
    "longitude": -0.12574,
    "timezone": "Europe/London"
  },
  "current": {
    "time": "2026-08-28T12:00",
    "temperature_c": 18.3,
    "apparent_temperature_c": 17.9,
    "relative_humidity_pct": 64,
    "wind_speed_kmh": 12.4,
    "weather_code": 3,
    "description": "Overcast"
  },
  "units": { "temperature": "°C", "wind_speed": "km/h", "humidity": "%" }
}
```

---

### `GET /forecast` — multi-day forecast

Returns a **daily** forecast covering several days.

**Query parameters**

| Name       | Type   | Required | Default | Notes                                   |
|------------|--------|----------|---------|-----------------------------------------|
| `location` | string | yes      | —       | City or place name. Min length 1.       |
| `days`     | int    | no       | `7`     | Number of forecast days. Must be `1`–`16`. |

**How it works**

1. Geocodes `location` → latitude/longitude.
2. Calls the forecast API requesting the `daily` block for `forecast_days=<days>`:
   `weather_code`, `temperature_2m_max/min`, `apparent_temperature_max/min`,
   `precipitation_sum`, `precipitation_probability_max`, `wind_speed_10m_max`.
3. Open-Meteo returns each variable as a **parallel array** (all the max temps
   in one list, all the dates in another, etc.). The app zips these arrays
   together into one tidy object **per day** and adds a readable `description`.

**Example request**

```bash
curl "http://127.0.0.1:8000/forecast?location=London&days=3"
```

**Example response** (`200 OK`)

```json
{
  "location": {
    "name": "London",
    "country": "United Kingdom",
    "admin1": "England",
    "latitude": 51.50853,
    "longitude": -0.12574,
    "timezone": "Europe/London"
  },
  "forecast_days": 3,
  "daily": [
    {
      "date": "2026-08-28",
      "temperature_max_c": 24.0,
      "temperature_min_c": 15.8,
      "apparent_temperature_max_c": 21.7,
      "apparent_temperature_min_c": 15.5,
      "precipitation_sum_mm": 2.1,
      "precipitation_probability_max_pct": 85,
      "wind_speed_max_kmh": 23.0,
      "weather_code": 55,
      "description": "Dense drizzle"
    }
  ],
  "units": {
    "temperature": "°C",
    "wind_speed": "km/h",
    "precipitation": "mm",
    "precipitation_probability": "%"
  }
}
```

---

### Demo user endpoints (POST + Bearer auth)

A minimal example of write endpoints and token authentication. **In-memory only**
— data resets when the server restarts.

**`POST /users` — register**

```bash
curl -X POST "http://127.0.0.1:8000/users" \
  -H "Content-Type: application/json" \
  -d '{"username":"ana","email":"ana@example.com","password":"s3cret!"}'
```
```json
// 201 Created
{ "username": "ana", "email": "ana@example.com", "created_at": "2026-08-28T19:22:07Z" }
```
Returns `409` if the username is taken, `422` if validation fails
(username < 3 chars, password < 6 chars).

**`POST /login` — get a token**

```bash
curl -X POST "http://127.0.0.1:8000/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"ana","password":"s3cret!"}'
```
```json
// 200 OK
{ "access_token": "XQedaFjNOeTX...", "token_type": "bearer" }
```
Returns `401` on bad credentials.

**`GET /me` — protected endpoint**

Send the token in the `Authorization` header:

```bash
curl "http://127.0.0.1:8000/me" \
  -H "Authorization: Bearer XQedaFjNOeTX..."
```
```json
// 200 OK — or 401 if the token is missing/invalid
{ "username": "ana", "email": "ana@example.com", "created_at": "2026-08-28T19:22:07Z" }
```

**`POST /logout` — invalidate the token**

Revokes the Bearer token so it can no longer be used. Any later request with the
same token returns `401`.

```bash
curl -X POST "http://127.0.0.1:8000/logout" \
  -H "Authorization: Bearer XQedaFjNOeTX..."
```
```json
// 200 OK
{ "detail": "Logged out" }
```
Returns `401` if the token is already missing or invalid.

---

### `GET /health` — liveness check

Returns `{"status": "ok"}`. Makes no upstream calls — useful for uptime probes
and load balancers.

```bash
curl "http://127.0.0.1:8000/health"
```

---

## Errors

All errors return JSON in the form `{ "detail": "..." }`:

| Status | When                                                        |
|--------|-------------------------------------------------------------|
| `401`  | Missing/invalid credentials or Bearer token (`/login`, `/me`). |
| `404`  | The location name could not be geocoded (no match found).   |
| `409`  | Username already exists (`/users`).                         |
| `422`  | Invalid parameters (e.g. missing `location`, `days` out of range, short password). |
| `502`  | The upstream Open-Meteo service was unreachable or errored. |

---

## External APIs used

| Purpose   | Endpoint                                                    |
|-----------|-------------------------------------------------------------|
| Geocoding | `https://geocoding-api.open-meteo.com/v1/search`            |
| Forecast  | `https://api.open-meteo.com/v1/forecast`                    |

Both are free and require no API key. See the
[Open-Meteo docs](https://open-meteo.com/en/docs) for the full list of available
variables. Weather conditions are reported as numeric
[WMO weather codes](https://open-meteo.com/en/docs#weathervariables), which this
service maps to readable descriptions.

## Project layout

```
app/
  __init__.py
  main.py            # FastAPI app + route handlers (/weather, /forecast, /health)
  weather_client.py  # calls the external Open-Meteo APIs and normalizes responses
requirements.txt
README.md
```
