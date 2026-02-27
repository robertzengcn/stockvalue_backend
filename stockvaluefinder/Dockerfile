FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv
RUN pip install uv

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY ./stockvaluefinder ./stockvaluefinder

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "python", "-m", "stockvaluefinder.main"]
