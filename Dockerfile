FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY bot/ bot/
COPY alembic.ini .
COPY migrations/ migrations/
COPY scripts/ scripts/

CMD ["sh", "-c", "alembic upgrade head && python -m bot.main"]
