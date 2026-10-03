FROM python:3.12-slim

WORKDIR /app

# System deps: build tools for psycopg/bcrypt wheels, curl for healthchecks,
# libmagic for later document-type validation (document_processing module).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
