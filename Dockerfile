# Stage 1: build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# System deps needed by some Python packages (psycopg2, chromadb)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# uv is used because crewai pins chromadb~=1.1.0 while langchain-chroma needs >=1.3.5.
# The override forces chromadb==1.5.8 (the version proven to work locally).
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend into the location FastAPI serves it from
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Persistent data directories (override with Docker volumes in production)
RUN mkdir -p chroma_db uploads

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
