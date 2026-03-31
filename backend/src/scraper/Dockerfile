============================================================================
# Locate918 Scraper Service - Dockerfile
# ============================================================================
# Uses Playwright's base image which includes Chromium + all dependencies

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright chromium is already in the base image, just link it
RUN playwright install chromium

# Copy all scraper source files
COPY . .

# Railway injects PORT automatically
ENV PORT=5000

EXPOSE $PORT

CMD python ScraperTool.py
```

And create `/backend/src/scraper/requirements.txt`:
```
flask>=3.0.0
playwright>=1.44.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
python-dateutil>=2.9.0