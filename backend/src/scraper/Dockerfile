FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

ENV PORT=5000

EXPOSE $PORT

CMD gunicorn --worker-class gevent --workers 1 --bind 0.0.0.0:$PORT --timeout 3600 --keep-alive 65 "ScraperTool:app"