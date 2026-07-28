import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.compare import router as compare_router

app = FastAPI(
    title="PolicyIQ NZ API",
    version="0.1.0",
    description="Document-grounded insurance comparison. Every AI-derived claim ships with citations.",
)

# "null" is the Origin browsers send for file:// pages (e.g. running site/index.html directly
# in local dev) - listed for local testing convenience only, not a production concern.
_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:8000,https://benjamen.github.io,null"
allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Required for credentials: "include" fetches (docs/11-DATA-CONNECTION.md) once session
    # cookies exist (docs/10-AUTH-AND-ACCOUNTS.md) - the browser blocks a credentialed response
    # unless the server echoes a specific origin (not "*") and sets this explicitly.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(compare_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
