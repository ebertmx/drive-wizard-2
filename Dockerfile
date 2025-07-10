# Use the official Python 3.11 slim image as a base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Set environment variables to prevent Python from buffering output
ENV PYTHONUNBUFFERED True

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# The command to run the application using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "main:app"]
