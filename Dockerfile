# Dockerfile
# Builds the LC-MS Mass Lookup API container
#
# What's included:  FastAPI app, search engine, requirements
# What's NOT included: PyQt5 GUI, raw data files, database (mounted as volume)
#
# Build:  docker build -t mass-lookup-api .
# Run:    docker-compose up  (preferred — handles volume mounting)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (cached layer — only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/    ./api/
COPY search/ ./search/

# Database is NOT copied — it's mounted as a volume at runtime via docker-compose
# See docker-compose.yml: volumes: ./database:/app/database

# Environment variable for DB path — can be overridden in docker-compose.yml
ENV DB_PATH=database/compounds.db

# Expose API port
EXPOSE 8000

# Start the API server
# --host 0.0.0.0 makes it accessible outside the container
# --workers 2 handles concurrent requests without threading issues on SQLite
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]