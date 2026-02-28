FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN python3 -c "import tomllib; \
    deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; \
    print('\n'.join(deps))" > /tmp/reqs.txt && \
    pip install --no-cache-dir -r /tmp/reqs.txt && \
    rm /tmp/reqs.txt

COPY backend/ backend/

RUN mkdir -p workspace

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
