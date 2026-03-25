FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python - <<'PY' > requirements.txt && \
    pip install --upgrade pip && \
    pip install -r requirements.txt
import tomllib

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)

for dep in data["project"]["dependencies"]:
    print(dep)
PY

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY .env.example ./

RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

RUN mkdir -p /app/backend/data /app/backend/uploads

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
