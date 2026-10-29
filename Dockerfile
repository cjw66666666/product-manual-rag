FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY migrations ./migrations
COPY src ./src

RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "rag_app.api_main:app", "--host", "0.0.0.0", "--port", "8000"]
