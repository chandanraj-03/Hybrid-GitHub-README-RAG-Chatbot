FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=7860 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Create non-root user for Hugging Face Spaces security standards
RUN useradd -m -u 1000 user
WORKDIR /app

# Install dependencies as user
COPY --chown=user backend/requirements.txt /app/requirements.txt
USER user

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY --chown=user backend/ /app/

# Hugging Face Spaces listens on port 7860 by default
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
