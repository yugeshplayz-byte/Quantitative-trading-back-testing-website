# Single-container deployment: the FastAPI backend serves the pre-built website, so ONE URL
# (and one service) gives you the whole app. Used by render.yaml; works on any Docker host.

# ---- 1. build the website as static files ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ENV STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin
RUN npm run build

# ---- 2. the API + the built site ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/out /srv/site
ENV FRONTEND_DIR=/srv/site
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
