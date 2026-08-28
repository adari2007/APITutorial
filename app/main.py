"""FastAPI app exposing a weather endpoint backed by the Open-Meteo service.

Run with:  uvicorn app.main:app --reload
Then try:  http://127.0.0.1:8000/weather?location=London
Docs at:   http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import users
from .weather_client import WeatherServiceError, get_forecast, get_weather

app = FastAPI(
    title="Weather API",
    description="Given a location, queries the Open-Meteo service and returns "
    "the current weather. Also includes demo user signup/login endpoints.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"


# ---- Request/response models for the POST endpoints ----

class UserCreate(BaseModel):
    """Body for registering a new user."""

    username: str = Field(..., min_length=3, max_length=32, examples=["ana"])
    email: str = Field(..., examples=["ana@example.com"])
    password: str = Field(..., min_length=6, examples=["s3cret!"])


class LoginRequest(BaseModel):
    """Body for logging in."""

    username: str = Field(..., examples=["ana"])
    password: str = Field(..., examples=["s3cret!"])


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Dependency: resolve the `Authorization: Bearer <token>` header to a user.

    Demonstrates protecting an endpoint with a Bearer token. Raises 401 if the
    header is missing or the token is invalid.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[len("bearer ") :].strip()
    try:
        return users.user_for_token(token)
    except users.UserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the simple web UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


@app.get("/weather")
async def weather(
    location: str = Query(
        ...,
        min_length=1,
        description="City or place name, e.g. 'London' or 'New York'.",
        examples=["London"],
    )
) -> JSONResponse:
    """Return current weather for the given location."""
    try:
        data = await get_weather(location.strip())
    except WeatherServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return JSONResponse(content=data)


@app.get("/forecast")
async def forecast(
    location: str = Query(
        ...,
        min_length=1,
        description="City or place name, e.g. 'London' or 'New York'.",
        examples=["London"],
    ),
    days: int = Query(
        7,
        ge=1,
        le=16,
        description="Number of forecast days (1-16).",
    ),
) -> JSONResponse:
    """Return a multi-day daily forecast for the given location."""
    try:
        data = await get_forecast(location.strip(), days)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return JSONResponse(content=data)


# ---- Demo user endpoints (POST) ----

@app.post("/users", status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate) -> dict:
    """Create (register) a new user. Returns 201 with the public user record."""
    try:
        return users.create_user(body.username, body.email, body.password)
    except users.UserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@app.post("/login")
async def login(body: LoginRequest) -> dict:
    """Verify credentials and return a Bearer access token."""
    try:
        token = users.authenticate(body.username, body.password)
    except users.UserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me")
async def me(user: dict = Depends(current_user)) -> dict:
    """Return the current user — protected by the Bearer token from /login."""
    return user
