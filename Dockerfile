FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD gunicorn 'web.app:create_app()' --bind 0.0.0.0:${PORT:-8000} --worker-class gevent --workers 2 --timeout 30 --max-requests 1000 --max-requests-jitter 50 --access-logfile - --error-logfile -
