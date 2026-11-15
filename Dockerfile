# Hosted demo of Baseline Drift: the real pipeline behind the real page, so it
# can be tried without installing anything. See "Hosted demo" in README.md.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt
COPY pipeline pipeline
COPY web web

ENV BASELINE_DRIFT_HOSTED=1 \
    BASELINE_DRIFT_DATA=/tmp/baseline-drift \
    PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "uvicorn web.server:app --host 0.0.0.0 --port ${PORT:-10000}"]
