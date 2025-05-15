# Use a more specific base image
FROM python:3.12-slim-bookworm as builder

# Set working directory
WORKDIR /app

# Install build dependencies and Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create final image
FROM python:3.12-slim-bookworm

# Install Docker CLI and other runtime system dependencies
RUN apt-get update && apt-get install -y \
    net-tools \
    procps \
    iproute2 \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo \
        "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
        "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and non-root user
RUN mkdir -p /app && \
    groupadd -g 999 appgroup && \
    useradd -m -s /bin/bash -g appgroup app && \
    chown -R app:appgroup /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/

# Install gunicorn in the final stage
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    FLASK_DEBUG=False \
    SECRET_KEY="a-very-long-random-string-here-123!@#" \
    ADMIN_SECRET="another-secure-random-string-456!@#" \
    ADMIN_USERNAME="myadmin" \
    ADMIN_PASSWORD="mysecurepassword123!"

# Create volume for SQLite database
VOLUME /app/instance

# Set ownership of all files to app user
RUN chown -R app:appgroup /app

# Switch to non-root user
USER app

# Expose Flask port
EXPOSE 5000

# Run the Flask app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "run:app"]
