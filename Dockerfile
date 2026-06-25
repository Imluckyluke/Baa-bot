FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    "aiogram==3.13.1" \
    "sqlalchemy[asyncio]==2.0.36" \
    "asyncpg==0.30.0" \
    "alembic==1.14.0" \
    "redis[hiredis]==5.2.1" \
    "pydantic-settings==2.6.1" \
    "apscheduler==3.10.4"

COPY bot/ bot/
COPY alembic.ini .
COPY migrations/ migrations/
COPY scripts/ scripts/

ENV PYTHONPATH=/app

CMD ["sh", "-c", "alembic upgrade head && python -m bot.main"]
