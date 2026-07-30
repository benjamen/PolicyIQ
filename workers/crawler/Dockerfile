FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installs headless Chromium plus every OS-level shared library it needs
# (--with-deps runs apt-get internally). This happens once, inside the
# isolated Docker build, running as root by default - the shared VPS host
# (also running Frappe/bench/n8n) never needs sudo or a single OS package
# installed on it for this. See docs/06-DEPLOYMENT-PLAN.md's isolation
# rationale, which this mirrors.
RUN playwright install --with-deps chromium

COPY . .

# INSURER/OUTFILE are passed as environment variables at `docker run` time
# (see .github/workflows/ingest.yml) - never baked in, so one image serves
# every insurer in the registry. OUTFILE should point under /app/discovered,
# bind-mounted to the host path run_ingest.py reads from.
#
# -O (capital, overwrite), not -o (append): real bug found 2026-07-30 -
# lowercase -o appends to an existing OUTFILE rather than replacing it, so
# every re-run of the same insurer silently doubled up the discovered
# file's content on top of whatever a previous (possibly broken, possibly
# stale) run had already written - confirmed directly, a file that should
# have held one clean crawl's ~58 items held 116 after a second dispatch.
# A fresh crawl should always fully replace what it discovers.
ENTRYPOINT ["sh", "-c", "scrapy crawl policy_documents -a insurer=\"$INSURER\" -O \"$OUTFILE\""]
