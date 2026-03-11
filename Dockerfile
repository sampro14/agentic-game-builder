FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

# Copy source code
COPY . .

# Create runtime directories
RUN mkdir -p output debug runs .cache frontend

# Non-root user for security
RUN useradd -m -u 1000 gamebuilder && chown -R gamebuilder:gamebuilder /app
USER gamebuilder

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
