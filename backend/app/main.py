"""KUVIS API — FastAPI application.

Run:  .venv/Scripts/python -m uvicorn backend.app.main:app --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import router
from .core.db import CORS_ORIGINS, pool

log = logging.getLogger("kuvis.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open(wait=True, timeout=15)
    yield
    pool.close()


app = FastAPI(title="KUVIS API", version="0.1.0", lifespan=lifespan,
              description="Karachi Urban Vulnerability Intelligence System — geospatial data-mining results. "
                          "All values come from the KUVIS PostGIS database; see /api/v1/data/sources for provenance.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.include_router(router)


@app.middleware("http")
async def timing(request: Request, call_next):
    t = time.perf_counter()
    resp = await call_next(request)
    if not request.url.path.startswith("/api/v1/tiles"):
        log.info("%s %s %d %.0fms", request.method, request.url.path, resp.status_code, (time.perf_counter() - t) * 1000)
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal error", "type": type(exc).__name__})


@app.get("/health")
def health():
    from .core.db import fetch_val
    return {"status": "ok", "postgis": fetch_val("SELECT postgis_full_version()")}
