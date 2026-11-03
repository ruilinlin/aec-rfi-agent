"""FastAPI service exposing the agent: POST /rfi -> CitedResponse | GapReport.

Usage (from the repo root):
    .venv/bin/uvicorn src.api.main:app --reload

Hardening: POST bodies are size-capped, POST /rfi is rate limited per client
IP (in-memory sliding window; single-process deployments only), and CORS is
fail-closed: no cross-origin access unless CORS_ALLOWED_ORIGINS is set.
"""

import math
import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent.graph import build_graph
from src.schemas import CitedResponse, GapReport, RFIRequest

ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(ROOT / ".env")

# Largest legitimate payload is a long question plus a few references (<10KB);
# 64KB leaves ample headroom while bounding memory per request.
MAX_BODY_BYTES = 64 * 1024

# Per-IP budget for the expensive route: generous for a human clicking around,
# tight enough that one address cannot drain the API credits.
RFI_RATE_LIMIT = 10
RFI_RATE_WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    """In-memory per-key sliding window counter.

    State lives in this process: single-process deployments only. Behind a
    reverse proxy, run uvicorn with --proxy-headers so request.client.host is
    the real client address rather than the proxy's. The clock is injectable
    so tests can advance time without sleeping.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def retry_after(self, key: str) -> float | None:
        """Record a hit and return None, or seconds to wait when over the limit.

        Expired timestamps are pruned on every call, so memory stays bounded
        by the number of keys active within one window.
        """
        now = self.clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return self.window_seconds - (now - hits[0])
        hits.append(now)
        return None


rfi_limiter = SlidingWindowLimiter(RFI_RATE_LIMIT, RFI_RATE_WINDOW_SECONDS)


def cors_origins_from_env() -> list[str]:
    """Parse comma-separated CORS_ALLOWED_ORIGINS; unset means deny cross-origin."""
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_graph():
    """Compile the agent graph once per process; overridable in tests."""
    return build_graph()


def create_app() -> FastAPI:
    """App factory so tests can build an app against a modified environment."""
    app = FastAPI(
        title="aec-rfi-agent",
        description="Drafts cited answers to construction RFIs; reports gaps instead of guessing.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins_from_env(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )

    @app.middleware("http")
    async def reject_oversized_bodies(request: Request, call_next):
        if request.method == "POST":
            declared = request.headers.get("content-length")
            try:
                size = int(declared) if declared is not None else None
            except ValueError:
                size = None
            # Chunked requests carry no Content-Length; reject rather than buffer.
            if size is None or size > MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413, content={"detail": "request body too large"}
                )
        return await call_next(request)

    @app.middleware("http")
    async def rate_limit_rfi(request: Request, call_next):
        if request.method == "POST" and request.url.path == "/rfi":
            key = request.client.host if request.client else "unknown"
            wait = rfi_limiter.retry_after(key)
            if wait is not None:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate limit exceeded"},
                    headers={"Retry-After": str(math.ceil(wait))},
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/rfi", response_model=CitedResponse | GapReport)
    def answer_rfi(
        rfi: RFIRequest, graph: Annotated[object, Depends(get_graph)]
    ) -> CitedResponse | GapReport:
        """Run the full agent on one RFI.

        The response is a CitedResponse when governing evidence supports an
        answer, and a GapReport when it does not. The drafted answer is for a
        licensed professional to review; the agent never issues final answers.
        """
        final_state = graph.invoke({"rfi": rfi})
        return final_state["response"]

    return app


app = create_app()
