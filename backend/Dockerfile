FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/tmp/huggingface \
    TRANSFORMERS_CACHE=/tmp/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/tmp/sentence_transformers

WORKDIR /app

# تثبيت متطلبات النظام بأمان
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# تثبيت مكتبات البايثون
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# نسخ كامل محتويات الباك إند (بما فيها dashboard-frontend والـ app)
COPY . .

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]