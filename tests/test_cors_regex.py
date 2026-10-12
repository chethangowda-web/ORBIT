"""Vercel gives every deployment its own address; a pattern lets all of the team's addresses sign in."""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from config import Settings

PATTERN = r"https://orbit-[a-z0-9-]+-chethann1328-7757s-projects\.vercel\.app"


def tiny_app(regex: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://orbit-lyart-tau-78.vercel.app"],
        allow_origin_regex=regex or None,
        allow_credentials=True,
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

    @app.post("/x")
    async def x():
        return {"ok": True}

    return app


async def preflight(app: FastAPI, origin: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        return await c.options("/x", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})


@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("https://orbit-lyart-tau-78.vercel.app", True),  # the fixed main address
        ("https://orbit-jm5hp13n7-chethann1328-7757s-projects.vercel.app", True),  # a one-off deployment address
        ("https://orbit-git-master-chethann1328-7757s-projects.vercel.app", True),
        ("https://orbit-jm5hp13n7-someone-else.vercel.app", False),
        ("https://evil.example.com", False),
        ("https://orbit-x-chethann1328-7757s-projects.vercel.app.evil.com", False),
    ],
)
async def test_the_pattern_allows_only_the_teams_own_addresses(origin, allowed):
    res = await preflight(tiny_app(PATTERN), origin)
    assert (res.headers.get("access-control-allow-origin") == origin) is allowed


async def test_without_a_pattern_a_one_off_address_is_refused():
    res = await preflight(tiny_app(""), "https://orbit-jm5hp13n7-chethann1328-7757s-projects.vercel.app")
    assert "access-control-allow-origin" not in res.headers


@pytest.mark.parametrize("pattern", [".*", "^.*$", ".+", "https?://.*"])
def test_a_pattern_that_allows_every_website_is_refused_in_production(pattern):
    with pytest.raises(Exception, match="too broad"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="x" * 40,
            GOOGLE_CHAT_VERIFY_AUTH=True,
            GOOGLE_CHAT_AUDIENCE="https://example.com/api/chat/webhook",
            CORS_ORIGIN_REGEX=pattern,
            _env_file=None,
        )
