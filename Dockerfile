FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data/exports && chown -R app:app /data
USER app
EXPOSE 9090
CMD ["gunicorn", "--bind", "0.0.0.0:9090", "--workers", "2", "--access-logfile", "-", "log_server:app"]
