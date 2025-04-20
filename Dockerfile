# Use official Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app code
COPY . .

# Set environment variable to avoid warnings
ENV PYTHONUNBUFFERED=1

# Expose Flask port
EXPOSE 5000

# Run the Flask app
CMD ["python", "run.py"]
