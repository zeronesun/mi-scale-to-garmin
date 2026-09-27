FROM python:3.12.6-slim

WORKDIR /app

# Install dependencies (build context is project root: docker build -f docker/Dockerfile .)
COPY requirements/runtime.txt .
RUN pip install --no-cache-dir -r runtime.txt

# Copy source code
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data

# Default command
CMD ["python", "src/main.py", "--help"]
