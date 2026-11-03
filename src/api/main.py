"""FastAPI service exposing the agent: POST /rfi -> CitedResponse | GapReport.

Usage (from the repo root):
    .venv/bin/uvicorn src.api.main:app --reload

Hardening: POST bodies are size-capped, POST /rfi is rate limited per client
IP (in-memory sliding window; single-process deployments only), and CORS is
fail-closed: no cross-origin access unless CORS_ALLOWED_ORIGINS is set.
"""

import hashlib
import logging
import math
import os
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.agent.graph import build_graph
from src.agent.trace import Trace, trace_run
from src.schemas import CitedResponse, GapReport, RFIRequest

ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(ROOT / ".env")

logger = logging.getLogger("aec_rfi_api")

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
            # Guard the empty-deque edge (limit 0 = always blocked).
            oldest = hits[0] if hits else now
            return self.window_seconds - (now - oldest)
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


def persist_trace(
    rfi: RFIRequest, response: CitedResponse | GapReport, rfi_type: str | None, trace: Trace
) -> None:
    """Record one request's telemetry. Best-effort by design: observability
    must never break the answer path, so every failure is logged and swallowed."""
    try:
        summary = response.usage
        question_sha256 = hashlib.sha256(
            re.sub(r"\s+", " ", rfi.question).strip().lower().encode()
        ).hexdigest()
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            conn.execute(
                """
                INSERT INTO rfi_requests
                  (id, question_sha256, rfi_type, verdict, total_latency_ms, total_cost_usd)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    request_id,
                    question_sha256,
                    rfi_type,
                    "gap" if isinstance(response, GapReport) else "answered",
                    summary.total_latency_ms,
                    summary.total_cost_usd,
                ),
            )
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO rfi_request_stages
                      (request_id, stage, latency_ms, input_tokens, output_tokens, cost_usd, model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            request_id,
                            st.stage,
                            st.latency_ms,
                            st.input_tokens,
                            st.output_tokens,
                            st.cost_usd,
                            st.model,
                        )
                        for st in summary.stages
                    ],
                )
    except Exception:  # logged and swallowed: telemetry must never break the answer path
        logger.exception("failed to persist request telemetry")


# Mirror of db/init.sql: the Docker entrypoint only runs init.sql on a fresh
# volume, so deployments initialized before this feature would otherwise never
# get the telemetry tables (and the best-effort writes would fail silently).
TELEMETRY_DDL = """
CREATE TABLE IF NOT EXISTS rfi_requests (
  id               TEXT PRIMARY KEY,
  question_sha256  TEXT NOT NULL,
  rfi_type         TEXT,
  verdict          TEXT NOT NULL CHECK (verdict IN ('answered','gap')),
  total_latency_ms INT NOT NULL,
  total_cost_usd   NUMERIC(10,6) NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rfi_request_stages (
  request_id    TEXT NOT NULL REFERENCES rfi_requests(id) ON DELETE CASCADE,
  stage         TEXT NOT NULL,
  latency_ms    INT NOT NULL,
  input_tokens  INT NOT NULL,
  output_tokens INT NOT NULL,
  cost_usd      NUMERIC(10,6) NOT NULL,
  model         TEXT,
  PRIMARY KEY (request_id, stage)
);
"""


def ensure_telemetry_tables() -> None:
    """Best-effort DDL at startup; an unreachable database must not block boot."""
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            conn.execute(TELEMETRY_DDL)
    except Exception:  # logged and swallowed: the API must boot without the DB
        logger.exception("could not ensure telemetry tables")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_telemetry_tables()
    yield


def create_app() -> FastAPI:
    """App factory so tests can build an app against a modified environment."""
    app = FastAPI(
        title="aec-rfi-agent",
        description="Drafts cited answers to construction RFIs; reports gaps instead of guessing.",
        lifespan=lifespan,
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
        with trace_run() as trace:
            final_state = graph.invoke({"rfi": rfi})
        response = final_state["response"].model_copy(update={"usage": trace.summary()})
        persist_trace(rfi, response, final_state.get("rfi_type"), trace)
        return response

    return app


app = create_app()
