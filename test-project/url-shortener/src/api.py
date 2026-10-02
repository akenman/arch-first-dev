from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional

from storage import URLStorage
from encoder import URLEncoder
from analytics import Analytics

app = FastAPI(title="URL Shortener")

storage = URLStorage()
encoder = URLEncoder()
analytics = Analytics()


class ShortenRequest(BaseModel):
    url: HttpUrl
    ttl: Optional[int] = None


class ShortenResponse(BaseModel):
    short_code: str
    short_url: str


@app.post("/shorten", response_model=ShortenResponse)
async def shorten_url(request: ShortenRequest):
    long_url = str(request.url)

    max_retries = 3
    for attempt in range(max_retries):
        short_code = encoder.encode(long_url)
        if storage.save_mapping(short_code, long_url, request.ttl):
            return ShortenResponse(
                short_code=short_code,
                short_url=f"http://localhost:8000/{short_code}"
            )

    raise HTTPException(status_code=409, detail="Failed to generate unique short code")


@app.get("/{short_code}")
async def redirect_url(short_code: str, request: Request):
    if not encoder.is_valid_code(short_code):
        raise HTTPException(status_code=400, detail="Invalid short code format")

    long_url = storage.get_long_url(short_code)
    if not long_url:
        raise HTTPException(status_code=404, detail="Short code not found or expired")

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    analytics.record_click(short_code, client_ip, user_agent)

    return RedirectResponse(url=long_url)


@app.delete("/{short_code}", status_code=204)
async def delete_url(short_code: str):
    if not encoder.is_valid_code(short_code):
        raise HTTPException(status_code=400, detail="Invalid short code format")

    if not storage.delete_mapping(short_code):
        raise HTTPException(status_code=404, detail="Short code not found")

    return None
