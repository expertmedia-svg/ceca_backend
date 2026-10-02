FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
RUN useradd --create-home --uid 10001 ceca
COPY --chown=ceca:ceca app ./app
COPY --chown=ceca:ceca migrations ./migrations
COPY --chown=ceca:ceca alembic.ini .
USER ceca
EXPOSE 8000
CMD ["sh","-c","python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips 172.30.55.1"]
