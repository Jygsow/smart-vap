# Utiliser une image Python officielle comme base
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production

# Lancement avec Gunicorn (Railway gère $PORT automatiquement)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT app:app"]
