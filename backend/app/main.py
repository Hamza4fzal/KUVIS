"""KUVIS API — FastAPI application.

Run:  .venv/Scripts/python -m uvicorn backend.app.main:app --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .api.v1 import router
from .core.db import CORS_ORIGINS, ROOT, pool

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


# ------------------------------------------------------------------ built frontend (single-port / release mode)
# When frontend/dist exists (after `npm run build`, and always in the portable release), the API also serves the
# web app, so everything runs on one port. Unknown paths fall back to index.html for client-side routing.
STATIC = Path(os.getenv("KUVIS_STATIC_DIR", ROOT / "frontend" / "dist")).resolve()
if (STATIC / "index.html").is_file():
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "unknown API route")
        f = (STATIC / path).resolve()
        if path and f.is_file() and STATIC in f.parents:
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
            return FileResponse(f, headers={"Cache-Control": cache})
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
