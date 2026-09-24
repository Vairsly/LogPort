# syntax=docker/dockerfile:1

# ---- 构建前端 ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- 后端运行时 ----
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /build/dist ./frontend/dist
RUN mkdir -p /data/exports && chown -R app:app /data /app
USER app
WORKDIR /app/backend
ENV FRONTEND_DIST=/app/frontend/dist
EXPOSE 9090
CMD ["gunicorn", "--bind", "0.0.0.0:9090", "--workers", "2", "--access-logfile", "-", "log_server:app"]
