FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend + classification engine
COPY backend/ ./backend/
COPY src/ ./src/
COPY data/sample_*.csv ./data/

# Copy built frontend
COPY --from=frontend-build /app/frontend/build ./frontend/build

# Default env
ENV LLM_MODEL=google/gemini-3.1-flash-lite-preview
ENV LLM_BASE_URL=https://openrouter.ai/api/v1
ENV ADMIN_USERNAME=admin
ENV ADMIN_PASSWORD=admin123

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
