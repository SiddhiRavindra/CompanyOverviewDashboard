# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose port
EXPOSE 8000

# Run FastAPI via uvicorn
CMD ["uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]
