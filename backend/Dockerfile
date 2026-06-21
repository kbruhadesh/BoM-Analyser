FROM python:3.11-slim

# System deps for Playwright + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libxml2-dev libxslt1-dev curl \
    # Playwright Chromium system deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN playwright install chromium --with-deps

COPY . .

# Create __init__.py files so sub-packages import correctly
RUN touch parser/__init__.py scrapers/__init__.py optimizer/__init__.py exporter/__init__.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
