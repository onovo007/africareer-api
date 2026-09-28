# AfriCareer AI backend API - deploy to Render, Railway, Fly.io, or any container host
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY core.py api.py cv_schema.py guards.py link_safety.py quality.py course_catalog.py evidence.py draft_review.py applications.py feedback_store.py job_verification.py job_discovery.py knowledge_sources.json ./
RUN useradd --create-home appuser
USER appuser

# Hosts inject $PORT; default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
