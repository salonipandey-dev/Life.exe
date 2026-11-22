# Two-stage build: compile the frontend, then run the backend serving it.
# NOTE: not built in the verification environment (no registry access); see docs/testing/test-execution-report.md.
FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    LIFEEXE_ENV=production LIFEEXE_HOST=0.0.0.0 LIFEEXE_PORT=8000 \
    LIFEEXE_DB_PATH=/data/lifeexe.db LIFEEXE_FRONTEND_DIST=/app/frontend/dist
RUN useradd --create-home --uid 10001 lifeexe && mkdir /data && chown lifeexe /data
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /app/frontend/dist /app/frontend/dist
USER lifeexe
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["python", "-m", "lifeexe"]
