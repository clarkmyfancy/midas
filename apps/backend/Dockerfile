FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

ARG OPENAI_API_KEY=""
ARG MIDAS_PRO_TOKEN=""

ENV OPENAI_API_KEY=${OPENAI_API_KEY} \
    MIDAS_PRO_TOKEN=${MIDAS_PRO_TOKEN}

WORKDIR /app

RUN pip install --no-cache-dir "uv>=0.8,<0.9"

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY midas ./midas

RUN uv pip install --system .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
