FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Runs pending migrations before serving - without this, a fresh deploy's
# DB has no tables and every request 500s instead of the fail-closed empty
# response docs/01-ARCHITECTURE.md calls for.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
