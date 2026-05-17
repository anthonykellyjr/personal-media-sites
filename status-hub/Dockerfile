FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask flask-cors requests

COPY api.py .

EXPOSE 5000

CMD ["python", "api.py"]
