FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg and other native packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Apply database migrations, then start the API. Using the shell form so
# the two commands chain; the container exits if migrations fail rather
# than serving against an out-of-date schema.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
