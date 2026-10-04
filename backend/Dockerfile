FROM python:3.12-slim

WORKDIR /app

# System deps: build tools for psycopg/bcrypt wheels, curl for healthchecks,
# libmagic for document-type validation, tesseract-ocr + poppler-utils for
# the document_processing OCR fallback (Sprint 3) — not installed in every
# dev environment, which is why document_processing/ocr.py raises a clear
# OcrUnavailableError rather than assuming these exist.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libmagic1 \
        tesseract-ocr \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
