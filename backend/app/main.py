from fastapi import FastAPI

from app.api.v1.compare import router as compare_router

app = FastAPI(
    title="PolicyIQ NZ API",
    version="0.1.0",
    description="Document-grounded insurance comparison. Every AI-derived claim ships with citations.",
)

app.include_router(compare_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
