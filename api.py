#!/usr/bin/env python3
"""FastAPI wrapper around the checker logic from main.py.

Endpoints:
    GET  /            -> service info
    GET  /health      -> health check
    GET  /check/{username}
    GET  /check?username=foo[&username=bar]
    POST /check       {"usernames": ["foo", "bar"]}
"""

import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import main as checker

app = FastAPI(
    title="Telegram Username Checker API",
    description=(
        "Checks Telegram username availability via fragment.com. No rate limits.\n\n"
        "Base URL: `https://tgusernamecheckerapi.xie.su`\n\n"
        "### Quick start\n"
        "```\n"
        "curl https://tgusernamecheckerapi.xie.su/check/durov\n"
        "curl https://tgusernamecheckerapi.xie.su/check?username=telegram\n"
        "curl -X POST https://tgusernamecheckerapi.xie.su/check \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        '  -d \'{"usernames":["durov","some_free_name"]}\'\n'
        "```"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single session shared across requests (fragment cookies are not tied to a client)
_session: requests.Session | None = None
_api_url: str = ""
_api_version: str = ""
_lock = asyncio.Lock()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
MAX_BATCH = 50


class BatchRequest(BaseModel):
    usernames: list[str]


class CheckResult(BaseModel):
    username: str = Field(description="Checked username (without @)")
    status: str = Field(
        description="`taken` if username is registered, `available` if it's free"
    )
    exists: bool = Field(description="Whether the username is registered")
    name: str = Field(description="Account display name (or `-`)")
    dc: str = Field(description="Telegram datacenter id (or `?`)")
    avatar: bool = Field(description="Whether the account has a real avatar photo")
    is_channel: bool = Field(description="Whether the account is a channel")
    is_bot: bool = Field(description="Whether the account is a bot")
    premium: bool = Field(description="Whether the account has Telegram Premium")
    stars_ok: bool = Field(
        description="`True` if gifting Stars is allowed, `False` if blocked for taken"
    )
    premium_ok: bool = Field(
        description="`True` if gifting Premium is allowed, `False` if blocked for taken"
    )
    ads_ok: bool = Field(
        description="`True` if adding funds is allowed, `False` if blocked for taken"
    )
    market: str = Field(description="Market status from fragment.com page (or `-`)")
    market_price: str = Field(description="Market price info (or empty)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "durov",
                    "status": "taken",
                    "exists": True,
                    "name": "Pavel Durov",
                    "dc": "4",
                    "avatar": True,
                    "is_channel": False,
                    "is_bot": False,
                    "premium": False,
                    "stars_ok": False,
                    "premium_ok": False,
                    "ads_ok": False,
                    "market": "-",
                    "market_price": "",
                },
                {
                    "username": "some_free_name",
                    "status": "available",
                    "exists": False,
                    "name": "-",
                    "dc": "?",
                    "avatar": False,
                    "is_channel": False,
                    "is_bot": False,
                    "premium": False,
                    "stars_ok": False,
                    "premium_ok": False,
                    "ads_ok": False,
                    "market": "Unavailable",
                    "market_price": "",
                },
            ]
        }
    }


class BatchResponse(BaseModel):
    results: list[CheckResult]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "username": "durov",
                            "status": "taken",
                            "exists": True,
                            "name": "Pavel Durov",
                            "dc": "4",
                            "avatar": True,
                            "is_channel": False,
                            "is_bot": False,
                            "premium": False,
                            "stars_ok": False,
                            "premium_ok": False,
                            "ads_ok": False,
                            "market": "-",
                            "market_price": "",
                        },
                        {
                            "username": "some_free_name",
                            "status": "available",
                            "exists": False,
                            "name": "-",
                            "dc": "?",
                            "avatar": False,
                            "is_channel": False,
                            "is_bot": False,
                            "premium": False,
                            "stars_ok": False,
                            "premium_ok": False,
                            "ads_ok": False,
                            "market": "Unavailable",
                            "market_price": "",
                        },
                    ]
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    detail: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Invalid username: 'bad!!name'. Only 1-32 chars of a-z, 0-9 and _"
                }
            ]
        }
    }


def _init() -> None:
    global _session, _api_url, _api_version
    _session, _api_version, _api_url = checker.init_session()


from contextlib import asynccontextmanager


async def _noop_lifespan(app: FastAPI):
    yield


@app.on_event("startup")
def startup() -> None:
    _init()


def _ensure_session() -> None:
    global _session, _api_url, _api_version
    if _session is None or not _api_url:
        _init()


def _check_one(username: str) -> dict:
    """Blocking check of a single username (runs in thread pool)."""
    _ensure_session()
    assert _session is not None
    try:
        results = checker.check_username(_session, _api_url, username)
        info = checker.analyze(results)
        info["market"], info["market_price"] = checker.check_fragment_page(
            _session, username
        )
        return {
            "username": username,
            "status": "taken" if info["exists"] else "available",
            **info,
        }
    except requests.RequestException:
        # Session may be broken (connection dropped / fragment blocked it) -> re-init once
        _init()
        assert _session is not None
        results = checker.check_username(_session, _api_url, username)
        info = checker.analyze(results)
        info["market"], info["market_price"] = checker.check_fragment_page(
            _session, username
        )
        return {
            "username": username,
            "status": "taken" if info["exists"] else "available",
            **info,
        }


async def run_checks(usernames: list[str]) -> list[dict]:
    async with _lock:
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(None, _check_one, u) for u in usernames]
        return await asyncio.gather(*tasks)


def validate(usernames: list[str]) -> list[str]:
    cleaned = []
    for u in usernames:
        u = u.strip().lstrip("@")
        if not u:
            continue
        if not USERNAME_RE.match(u):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid username: {u!r}. Only 1-32 chars of a-z, 0-9 and _",
            )
        cleaned.append(u.lower())
    if not cleaned:
        raise HTTPException(status_code=400, detail="No usernames provided")
    if len(cleaned) > MAX_BATCH:
        raise HTTPException(
            status_code=400, detail=f"Too many usernames (max {MAX_BATCH} per request)"
        )
    return cleaned


@app.get("/", response_model=dict, summary="Service info")
def root():
    return {
        "service": "Telegram Username Checker API",
        "base_url": "https://tgusernamecheckerapi.xie.su",
        "docs": "/docs",
        "endpoints": {
            "check_single": "GET /check/{username}",
            "check_query": "GET /check?username=foo&username=bar",
            "check_batch": 'POST /check  {"usernames": ["foo", "bar"]}',
            "health": "GET /health",
        },
        "example": "curl https://tgusernamecheckerapi.xie.su/check/durov",
    }


@app.get("/health", response_model=dict, summary="Health check")
def health():
    return {"ok": True, "api_url": _api_url, "version": _api_version}


@app.get(
    "/check/{username}",
    response_model=CheckResult,
    summary="Check a single username",
    responses={400: {"model": ErrorResponse, "description": "Invalid username"}},
)
async def check_path(username: str):
    usernames = validate([username])
    results = await run_checks(usernames)
    return results[0]


@app.get(
    "/check",
    response_model=CheckResult | BatchResponse,
    summary="Check one or more usernames via query params",
    responses={400: {"model": ErrorResponse, "description": "Invalid username"}},
)
async def check_query(username: list[str] = Query(default=[])):
    usernames = validate(username)
    results = await run_checks(usernames)
    return results[0] if len(results) == 1 else BatchResponse(results=results)


@app.post(
    "/check",
    response_model=CheckResult | BatchResponse,
    summary="Check one or more usernames via JSON body",
    responses={400: {"model": ErrorResponse, "description": "Invalid username"}},
)
async def check_batch(body: BatchRequest):
    usernames = validate(body.usernames)
    results = await run_checks(usernames)
    return results[0] if len(results) == 1 else BatchResponse(results=results)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=6712)
