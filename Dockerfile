FROM python:3.11-slim

WORKDIR /app

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY cloud_bot.py .
COPY commands/ ./commands/

CMD ["python", "cloud_bot.py"]
